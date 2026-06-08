from __future__ import annotations

import logging
import time
from collections.abc import Callable

import requests

from weather_app.services.errors import NetworkError, ProviderError
from weather_app.services.ttl_cache import TTLCache


GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
_GEO_TIMEOUT = 7
_IP_DETECT_URL = "https://ipapi.co/json/"
_IP_DETECT_TIMEOUT = 5
_MAX_HTTP_ATTEMPTS = 3
_RETRY_BACKOFF_S = 0.6
_DEFAULT_GEO_CACHE_TTL_S = 7 * 24 * 60 * 60  # 7 days

logger = logging.getLogger(__name__)


class LocationService:
    """
    Location/geocoding service.

    Responsibilities:
    - normalize user city input
    - detect city from public IP
    - geocode city -> lat/lon/resolved name/country
    - cache geocode results

    It intentionally has no wx usage and no UI responsibilities.
    """

    def __init__(
        self,
        *,
        geo_url: str = GEO_URL,
        geo_timeout: int = _GEO_TIMEOUT,
        session: requests.Session | None = None,
        geo_cache_ttl_s: int = _DEFAULT_GEO_CACHE_TTL_S,
        json_getter: Callable[..., dict] | None = None,
    ) -> None:
        self._geo_url = geo_url
        self._geo_timeout = geo_timeout
        self._session = session or requests.Session()
        self._geo_cache = TTLCache[str, tuple[float, float, str, str | None]](geo_cache_ttl_s)
        self._json_getter = json_getter

    # ---------- normalization/display helpers ----------

    def normalize_location_input(self, city: str) -> str:
        text = " ".join((city or "").strip().split())
        if not text:
            return "Sofia"

        # Accept "Kavala Greece" by turning last word into country hint
        # only when user did not already type a comma.
        if "," not in text:
            parts = text.split()
            if len(parts) >= 2:
                return f"{' '.join(parts[:-1])}, {parts[-1]}"

        return text

    def display_city(self, resolved_name: str, country: str | None) -> str:
        name = (resolved_name or "").strip() or "Unknown"
        country = (country or "").strip()

        if not country:
            return name

        return f"{name}, {country}"

    def _normalize_city_key(self, city: str) -> str:
        return " ".join((city or "").strip().lower().split())

    # ---------- geocode cache helpers ----------

    def _geo_cache_get(self, city: str) -> tuple[float, float, str, str | None] | None:
        key = self._normalize_city_key(city)
        if not key:
            return None
        return self._geo_cache.get(key)

    def _geo_cache_set(
        self,
        city: str,
        value: tuple[float, float, str, str | None],
    ) -> None:
        key = self._normalize_city_key(city)
        if not key:
            return
        self._geo_cache.set(key, value)

    # ---------- public API ----------

    def detect_city(self) -> str | None:
        """
        Try to detect user city from public IP.
        Returns city string or None on failure.
        """
        try:
            r = self._session.get(_IP_DETECT_URL, timeout=_IP_DETECT_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            city = data.get("city")
            return str(city).strip() if city else None
        except Exception:
            return None

    def geocode_city(self, city: str) -> tuple[float, float, str, str | None]:
        """
        Return (lat, lon, resolved_name, country).
        Raise ValueError if city is not found.
        """
        cached = self._geo_cache_get(city)
        if cached is not None:
            logger.info("Geocode cache HIT city=%r", city)
            return cached

        logger.debug("Geocode cache MISS city=%r", city)

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

        resolved_name = (
            str(r0.get("name") or "").strip()
            or str(city or "").strip()
            or "Unknown"
        )
        country = str(r0.get("country") or "").strip() or None

        out = (
            float(r0["latitude"]),
            float(r0["longitude"]),
            resolved_name,
            country,
        )

        self._geo_cache_set(city, out)
        logger.info(
            "Geocode resolved city=%r -> lat=%s lon=%s resolved=%r country=%r",
            city,
            out[0],
            out[1],
            out[2],
            out[3],
        )
        return out

    # ---------- internal HTTP helper ----------

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
        HTTP GET -> JSON.

        If json_getter was injected, delegate to it. This allows WeatherService
        and LocationService to share one HTTP retry implementation if desired.
        """
        if self._json_getter is not None:
            return self._json_getter(
                url,
                params=params,
                timeout=timeout,
                attempts=attempts,
                backoff_s=backoff_s,
            )

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

                    raise NetworkError(f"Weather service temporarily unavailable (HTTP {r.status_code}).")

                r.raise_for_status()

                try:
                    return r.json()
                except ValueError as e:
                    raise ProviderError("Weather service returned invalid JSON.") from e

            except requests.exceptions.Timeout as e:
                if attempt < max_attempts:
                    time.sleep(backoff_s * (2 ** (attempt - 1)))
                    continue
                raise NetworkError("Network timeout while contacting weather service.") from e

            except requests.exceptions.HTTPError as e:
                status = getattr(e.response, "status_code", "unknown")
                raise ProviderError(f"Weather service error (HTTP {status}).") from e

            except requests.RequestException as e:
                if attempt < max_attempts:
                    time.sleep(backoff_s * (2 ** (attempt - 1)))
                    continue
                raise NetworkError("Network error while contacting weather service.") from e

        raise NetworkError("Network error while contacting weather service.")
