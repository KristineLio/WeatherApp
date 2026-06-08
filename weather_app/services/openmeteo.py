import requests
import logging
import time

from weather_app.domain.models import WeatherData, CurrentSnapshot, DailyForecast, HourlySeries
from weather_app.utils.formatters import weekday_from_iso
from weather_app.domain.settings import Units
from weather_app.services.errors import NetworkError, ProviderError
from weather_app.services.ttl_cache import TTLCache
from weather_app.services.location import (
    GEO_URL,
    LocationService,
    _DEFAULT_GEO_CACHE_TTL_S,
    _GEO_TIMEOUT,
)


FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
_FORECAST_TIMEOUT = 10

_MAX_HTTP_ATTEMPTS = 3
_RETRY_BACKOFF_S = 0.6
_DEFAULT_WEATHER_CACHE_TTL_S = 120

logger = logging.getLogger(__name__)


class WeatherService:
    """
    Pure weather networking + forecast parsing service.

    Location/geocoding behavior is delegated to LocationService.

    - No wx usage
    - No threading
    - Deterministic inputs/outputs when a fake session/location service is injected
    """

    def __init__(
        self,
        *,
        geo_url: str = GEO_URL,
        forecast_url: str = FORECAST_URL,
        geo_timeout: int = _GEO_TIMEOUT,
        forecast_timeout: int = _FORECAST_TIMEOUT,
        session: requests.Session | None = None,
        cache_ttl_s: int = _DEFAULT_WEATHER_CACHE_TTL_S,
        geo_cache_ttl_s: int = _DEFAULT_GEO_CACHE_TTL_S,
        location_service: LocationService | None = None,
    ):
        self._cache = TTLCache[tuple[str, str, int], WeatherData](cache_ttl_s)

        self._forecast_url = forecast_url
        self._forecast_timeout = forecast_timeout
        self._session = session or requests.Session()

        self.location_service = location_service or LocationService(
            geo_url=geo_url,
            geo_timeout=geo_timeout,
            session=self._session,
            geo_cache_ttl_s=geo_cache_ttl_s,
            json_getter=self._get_json,
        )

    # ---------- weather cache helpers ----------
    def _cache_key(self, city: str, units: Units, forecast_days: int) -> tuple[str, str, int]:
        return (" ".join((city or "").strip().lower().split()), units.value, int(forecast_days))

    def _cache_get(self, key: tuple[str, str, int]) -> WeatherData | None:
        return self._cache.get(key)

    def _cache_set(self, key: tuple[str, str, int], data: WeatherData) -> None:
        self._cache.set(key, data)

    # ---------- compatibility wrappers ----------
    # These wrappers let existing code/tests keep working while the real logic
    # lives in services/location.py.

    def _normalize_location_input(self, city: str) -> str:
        return self.location_service.normalize_location_input(city)

    def _display_city(self, resolved_name: str, country: str | None) -> str:
        return self.location_service.display_city(resolved_name, country)

    def _geocode_city(self, city: str) -> tuple[float, float, str, str | None]:
        return self.location_service.geocode_city(city)

    def detect_city(self) -> str | None:
        return self.location_service.detect_city()

    # ---------- public API ----------

    def fetch(
        self,
        city: str,
        *,
        units: Units = Units.METRIC,
        forecast_days: int = 7,
    ) -> WeatherData:
        """
        Fetch weather for a city and return a fully built WeatherData domain object.
        Raises typed service exceptions for network/provider failures.
        """
        city = self.location_service.normalize_location_input(city)
        key = self._cache_key(city, units, forecast_days)

        t0 = time.perf_counter()
        cached = self._cache_get(key)
        if cached is not None:
            logger.info(
                "Cache HIT city=%r units=%s days=%s (%.2f ms)",
                city,
                units.value,
                forecast_days,
                (time.perf_counter() - t0) * 1000,
            )
            return cached

        logger.debug(
            "Cache MISS city=%r units=%s days=%s",
            city,
            units.value,
            forecast_days,
        )
        logger.info("Fetch weather start city=%r", city)

        try:
            lat, lon, resolved_name, country = self.location_service.geocode_city(city)

            params = {
                "latitude": lat,
                "longitude": lon,
                "current_weather": True,
                "daily": "temperature_2m_max,temperature_2m_min,weathercode,sunrise,sunset",
                "hourly": (
                    "temperature_2m,weathercode,apparent_temperature,windspeed,"
                    "relativehumidity_2m,precipitation_probability"
                ),
                "timezone": "auto",
                "forecast_days": int(forecast_days),
            }

            if units == Units.IMPERIAL:
                params.update(
                    {
                        "temperature_unit": "fahrenheit",
                        "wind_speed_unit": "mph",
                        "precipitation_unit": "inch",
                    }
                )

            forecast = self._get_json(
                self._forecast_url,
                params=params,
                timeout=self._forecast_timeout,
                attempts=_MAX_HTTP_ATTEMPTS,
                backoff_s=_RETRY_BACKOFF_S,
            )

            current = forecast.get("current_weather") or {}
            daily = forecast.get("daily") or {}
            hourly = forecast.get("hourly") or {}

            if "time" not in current:
                raise ProviderError("Weather service returned an unexpected response (missing current time).")
            if "time" not in daily or "time" not in hourly:
                raise ProviderError("Weather service returned an unexpected response (missing daily/hourly time arrays).")

            days = self._parse_daily(daily)

            current_time_iso = current.get("time")
            current_date_iso = current_time_iso.split("T")[0] if current_time_iso else None

            hourly_series = HourlySeries.from_api(hourly)
            current_feels, current_hum, current_precip, current_wind = (
                hourly_series.derive_current_extras(current_time_iso)
            )

            display_city = self.location_service.display_city(resolved_name, country)

            cur = CurrentSnapshot(
                temp=current.get("temperature"),
                code=current.get("weathercode"),
                feels_like=current_feels,
                humidity=current_hum,
                precip=current_precip,
                wind=current_wind,
                date_iso=current_date_iso,
                time_iso=current_time_iso,
                city=display_city,
            )

            wd = WeatherData(
                current=cur,
                daily=days,
                hourly=hourly_series,
                lat=lat,
                lon=lon,
                resolved_name=resolved_name,
                country=country,
            )

            logger.debug(
                "Cache STORE city=%r units=%s days=%s ttl=%ss",
                city,
                units.value,
                forecast_days,
                self._cache.ttl_s,
            )
            self._cache_set(key, wd)

            logger.info(
                "Fetch weather success city=%r resolved=%r lat=%s lon=%s",
                city,
                wd.current.city,
                lat,
                lon,
            )
            return wd

        except ValueError:
            # user input / city not found
            raise

        except (NetworkError, ProviderError):
            raise

        except Exception as e:
            # Any bug / parsing surprise -> ProviderError
            logger.exception("Unexpected service error city=%r", city)
            raise ProviderError("Weather service failed while processing data.") from e

    # ---------- internal helpers ----------

    def _get_json(
        self,
        url: str,
        *,
        params: dict | None = None,
        timeout: int = 10,
        attempts: int = 3,
        backoff_s: float = 0.6,
    ) -> dict:
        """
        HTTP GET -> JSON with typed exceptions and limited retry/backoff.

        Retries only for transient failures:
        - Timeout
        - RequestException (DNS / connection reset / etc.)
        - HTTP 429
        - HTTP 5xx

        Does NOT retry:
        - HTTP 4xx other than 429
        - invalid JSON
        """
        endpoint = url.rstrip("/").split("/")[-1]
        params = params or {}
        safe_params = {k: v for k, v in params.items() if k not in {"hourly", "daily"}}
        max_attempts = max(1, min(int(attempts), 3))

        for attempt in range(1, max_attempts + 1):
            try:
                logger.debug(
                    "HTTP GET attempt=%s/%s endpoint=%s url=%s params=%s timeout=%s",
                    attempt,
                    max_attempts,
                    endpoint,
                    url,
                    safe_params,
                    timeout,
                )

                r = self._session.get(url, params=params, timeout=timeout)

                # Retry only 429 + 5xx
                if r.status_code == 429 or 500 <= r.status_code <= 599:
                    if attempt < max_attempts:
                        delay = backoff_s * (2 ** (attempt - 1))
                        logger.warning(
                            "Retryable HTTP status endpoint=%s status=%s attempt=%s/%s sleeping=%.2fs",
                            endpoint,
                            r.status_code,
                            attempt,
                            max_attempts,
                            delay,
                        )
                        time.sleep(delay)
                        continue

                    logger.warning(
                        "Retryable HTTP error endpoint=%s status=%s params=%s",
                        endpoint,
                        r.status_code,
                        safe_params,
                    )
                    raise NetworkError(f"Weather service temporarily unavailable (HTTP {r.status_code}).")

                # Non-retryable HTTP errors (400/404/etc.)
                r.raise_for_status()

                try:
                    return r.json()
                except ValueError as e:
                    logger.warning(
                        "Invalid JSON endpoint=%s params=%s err=%s",
                        endpoint,
                        safe_params,
                        e,
                    )
                    raise ProviderError("Weather service returned invalid JSON.") from e

            except requests.exceptions.Timeout as e:
                if attempt < max_attempts:
                    delay = backoff_s * (2 ** (attempt - 1))
                    logger.warning(
                        "Timeout endpoint=%s attempt=%s/%s sleeping=%.2fs",
                        endpoint,
                        attempt,
                        max_attempts,
                        delay,
                    )
                    time.sleep(delay)
                    continue

                logger.warning(
                    "Timeout endpoint=%s params=%s timeout=%s",
                    endpoint,
                    safe_params,
                    timeout,
                )
                raise NetworkError("Network timeout while contacting weather service.") from e

            except requests.exceptions.HTTPError as e:
                status = getattr(e.response, "status_code", "unknown")
                logger.warning(
                    "HTTP error endpoint=%s status=%s params=%s",
                    endpoint,
                    status,
                    safe_params,
                )
                raise ProviderError(f"Weather service error (HTTP {status}).") from e

            except requests.RequestException as e:
                if attempt < max_attempts:
                    delay = backoff_s * (2 ** (attempt - 1))
                    logger.warning(
                        "Request error endpoint=%s attempt=%s/%s err=%s sleeping=%.2fs",
                        endpoint,
                        attempt,
                        max_attempts,
                        e,
                        delay,
                    )
                    time.sleep(delay)
                    continue

                logger.warning(
                    "Request error endpoint=%s params=%s err=%s",
                    endpoint,
                    safe_params,
                    e,
                )
                raise NetworkError("Network error while contacting weather service.") from e

        raise NetworkError("Network error while contacting weather service.")

    def _parse_daily(self, daily: dict) -> list[DailyForecast]:
        times = daily.get("time") or []
        tmaxs = daily.get("temperature_2m_max") or []
        tmins = daily.get("temperature_2m_min") or []
        codes = daily.get("weathercode") or []
        sunrises = daily.get("sunrise") or []
        sunsets = daily.get("sunset") or []

        n = min(len(times), len(tmaxs), len(tmins), len(codes))

        out: list[DailyForecast] = []
        for i in range(n):
            date_iso = times[i]
            out.append(
                DailyForecast(
                    date_iso=date_iso,
                    weekday=weekday_from_iso(date_iso),
                    tmin=tmins[i],
                    tmax=tmaxs[i],
                    code=codes[i],
                    sunrise_iso=sunrises[i] if i < len(sunrises) else None,
                    sunset_iso=sunsets[i] if i < len(sunsets) else None,
                )
            )
        return out
