import requests
import logging
import time
import threading
from weather_app.domain.models import WeatherData, CurrentSnapshot, DailyForecast, HourlySeries
from weather_app.utils.formatters import weekday_from_iso
from weather_app.domain.settings import Units
from weather_app.services.errors import NetworkError, ProviderError

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
_GEO_TIMEOUT = 7
_FORECAST_TIMEOUT = 10

_MAX_HTTP_ATTEMPTS = 3
_RETRY_BACKOFF_S = 0.6

logger = logging.getLogger(__name__)

# ============================================================================
# Weather Service
# ============================================================================

class WeatherService:
    """
    Pure networking + parsing service.

    - No wx usage
    - No threading
    - Deterministic inputs/outputs (easy to unit test)
    """

    def __init__(
        self,
        *,
        geo_url: str = GEO_URL,
        forecast_url: str = FORECAST_URL,
        geo_timeout: int = _GEO_TIMEOUT,
        forecast_timeout: int = _FORECAST_TIMEOUT,
        session: requests.Session | None = None,
    ):
        self._cache: dict[tuple, tuple[float, WeatherData]] = {}
        self._cache_ttl_s = 120  # 2 minutes
        self._cache_lock = threading.Lock()

        self._geo_url = geo_url
        self._forecast_url = forecast_url
        self._geo_timeout = geo_timeout
        self._forecast_timeout = forecast_timeout
        self._session = session or requests.Session()

    # ---------- caching helpers ----------
    """ Simple in-memory cache with TTL. """
    """
        “Cache-then-refresh”
        If cached data exists and is recent → show it immediately
        In background → still fetch fresh data and update UI when done
    """
    def _cache_key(self, city: str, units, forecast_days: int) -> tuple:
        return (city.strip().lower(), str(units), int(forecast_days))

    def _cache_get(self, key):
        with self._cache_lock:
            item = self._cache.get(key)
            if not item:
                return None
            ts, data = item
            if time.time() - ts > self._cache_ttl_s:
                self._cache.pop(key, None)
                return None
            return data
    
    def _cache_set(self, key, data):
        with self._cache_lock:
            self._cache[key] = (time.time(), data)

    # ---------- public API ----------

    def detect_city(self) -> str | None:
        """
        Try to detect user city from public IP.
        Returns city string or None on failure.
        """
        try:
            r = self._session.get("https://ipapi.co/json/", timeout=5)
            r.raise_for_status()
            data = r.json()
            return data.get("city")
        except Exception:
            return None

    def fetch(self, city: str, *, units: Units = Units.METRIC, forecast_days: int = 7,) -> WeatherData:
        """
        Fetch weather for a city and return a fully built WeatherData domain object.
        Raises typed service exceptions for network/provider failures.
        """
        key = self._cache_key(city, units, forecast_days)
        t0 = time.perf_counter()
        cached = self._cache_get(key)
        if cached is not None:
            logger.info(
                "Cache HIT city=%r (%.2f ms)",
                city,
                (time.perf_counter() - t0) * 1000,
            )
            return cached
        logger.debug("Cache MISS city=%r units=%s days=%s", city, units, forecast_days)

        city = (city or "").strip() or "Sofia"
        logger.info("Fetch weather start city=%r", city)

        try:
            lat, lon, resolved_name, country = self._geocode_city(city)

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
                params.update({
                    "temperature_unit": "fahrenheit",
                    "wind_speed_unit": "mph",
                    "precipitation_unit": "inch",
                })

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

            display_city = f"{resolved_name}, {country}" if country else resolved_name

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
            )

            logger.debug(
                "Cache STORE city=%r units=%s days=%s ttl=%ss",
                city, units, forecast_days, self._cache_ttl_s
            )
            self._cache_set(key, wd)

            logger.info(
                "Fetch weather success city=%r resolved=%r lat=%s lon=%s",
                city, wd.current.city, lat, lon
            )
            return wd

        except ValueError:
            # user input / city not found
            raise

        except (NetworkError, ProviderError):
            raise

        except Exception as e:
            # Any bug / parsing surprise -> ProviderError (consistent for UI)
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

        raise ProviderError("Weather service failed unexpectedly.")

    def _geocode_city(self, city: str) -> tuple[float, float, str, str]:
        """Return (lat, lon, resolved_name, country). Raise ValueError if not found."""
        geo = self._get_json(
            self._geo_url,
            params={"name": city, "count": 1, "language": "en", "format": "json"},
            timeout=self._geo_timeout,
            attempts=_MAX_HTTP_ATTEMPTS,
            backoff_s=_RETRY_BACKOFF_S,
        )
        results = geo.get("results") or []
        if not results:
            raise ValueError("City not found. Please try another name.")
        r0 = results[0]
        return (
            float(r0["latitude"]),
            float(r0["longitude"]),
            r0.get("name", city),
            r0.get("country", ""),
        )

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
            sunrise_iso = sunrises[i] if i < len(sunrises) else None
            sunset_iso = sunsets[i] if i < len(sunsets) else None

            out.append(
                DailyForecast(
                    date_iso=date_iso,
                    weekday=weekday_from_iso(date_iso),
                    tmax=tmaxs[i],
                    tmin=tmins[i],
                    code=codes[i],
                    sunrise_iso=sunrise_iso,
                    sunset_iso=sunset_iso,
                )
            )
        return out