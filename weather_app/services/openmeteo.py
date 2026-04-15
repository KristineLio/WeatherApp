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
        Raises RuntimeError / ValueError with user-friendly messages.
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
            #logger.info("Geocoded city=%r -> lat=%s lon=%s resolved=%r country=%r", city, lat, lon, resolved_name, country)

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

            forecast = self._get_json(self._forecast_url, params=params, timeout=self._forecast_timeout)

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

            logger.info(
                "Fetch weather success city=%r resolved=%r lat=%s lon=%s",
                city, wd.current.city, lat, lon
            )

            logger.debug(
                "Cache STORE city=%r units=%s days=%s ttl=%ss",
                city, units, forecast_days, self._cache_ttl_s
            )
            self._cache_set(key, wd)
            logger.info("Fetch weather success city=%r resolved=%r lat=%s lon=%s", city, wd.current.city, lat, lon)
            return wd
        
        except ValueError:
            # user input / city not found
            raise

        except RuntimeError as e:
            # _get_json already raises RuntimeError for network/provider errors.
            # Re-map them into typed exceptions for UI logic.
            msg = str(e)
            if msg.startswith("Network"):
                raise NetworkError(msg) from e
            raise ProviderError(msg) from e

        except Exception as e:
            # Any bug / parsing surprise -> ProviderError (consistent for UI)
            logger.exception("Unexpected service error city=%r", city)
            raise ProviderError("Weather service failed while processing data.") from e


    # ---------- internal helpers ----------

    def _get_json(self, url: str, *, params: dict | None = None, timeout: int = 10) -> dict:
        """HTTP GET → JSON with consistent errors."""
        endpoint = url.rstrip("/").split("/")[-1]

        try:
            safe_params = {k: v for k, v in params.items() if k not in {"hourly", "daily"}}
            logger.debug("HTTP GET endpoint=%s url=%s params=%s timeout=%s", endpoint, url, safe_params, timeout)
            r = self._session.get(url, params=params, timeout=timeout)
            r.raise_for_status()
            return r.json()

        except requests.exceptions.Timeout as e:
            logger.warning("Timeout calling %s params=%s timeout=%s", url, params, timeout)
            raise RuntimeError("Network timeout while contacting weather service.") from e

        except requests.exceptions.HTTPError as e:
            status = getattr(e.response, "status_code", "unknown")
            logger.warning("HTTP error calling %s (HTTP %s) params=%s", url, status, params)
            raise RuntimeError(f"Weather service error (HTTP {status}).") from e

        except ValueError as e:
            logger.warning("Invalid JSON from %s params=%s err=%s", url, params, e)
            raise RuntimeError("Weather service returned invalid JSON.") from e

        except requests.RequestException as e:
            # includes DNS failures like getaddrinfo and connection resets
            logger.warning("Request error calling %s params=%s err=%s", url, params, e)
            raise RuntimeError("Network error while contacting weather service.") from e

    def _geocode_city(self, city: str) -> tuple[float, float, str, str]:
        """Return (lat, lon, resolved_name, country). Raise ValueError if not found."""
        geo = self._get_json(
            self._geo_url,
            params={"name": city, "count": 1, "language": "en", "format": "json"},
            timeout=self._geo_timeout,
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
   