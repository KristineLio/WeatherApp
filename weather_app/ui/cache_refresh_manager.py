from __future__ import annotations

from dataclasses import dataclass

from weather_app.domain.models import WeatherData
from weather_app.domain.settings import Settings
from weather_app.services.openmeteo import WeatherService


@dataclass(frozen=True)
class CacheLookup:
    """Result of checking the UI cache before starting a refresh."""

    cached: WeatherData | None

    @property
    def hit(self) -> bool:
        return self.cached is not None


class CacheRefreshManager:
    """
    Coordinates UI-level cache-then-refresh state.

    This class intentionally has no wx imports and no widget code. The frame is
    still responsible for rendering cached/fresh data and scheduling callbacks.
    """

    def __init__(
        self,
        *,
        service: WeatherService | None = None,
        refresh_service: WeatherService | None = None,
        max_auto_retries: int = 1,
    ) -> None:
        # Normal service keeps WeatherService's own TTL cache.
        self.service = service or WeatherService()

        # Refresh service disables WeatherService's internal weather cache so a
        # background refresh really contacts the provider.
        self.refresh_service = refresh_service or WeatherService(cache_ttl_s=0)

        self._ui_weather_cache: dict[tuple[str, str, int], WeatherData] = {}
        self._max_auto_retries = max(0, int(max_auto_retries))
        self._auto_retry_city: str | None = None
        self._auto_retry_count: int = 0

    # ---------- cache helpers ----------

    def weather_cache_key(self, city: str, settings: Settings) -> tuple[str, str, int]:
        normalized_city = " ".join((city or "").strip().lower().split())
        return (
            normalized_city,
            settings.units.value,
            int(getattr(settings, "forecast_days", 7)),
        )

    def get_cached_weather(self, city: str, settings: Settings) -> WeatherData | None:
        return self._ui_weather_cache.get(self.weather_cache_key(city, settings))

    def store_cached_weather(self, city: str, data: WeatherData, settings: Settings) -> None:
        # Store under the typed city and the resolved display city. This helps
        # future searches hit the cache after update_ui changes the text box to
        # "City, Country".
        self._ui_weather_cache[self.weather_cache_key(city, settings)] = data

        display_city = (getattr(data.current, "city", "") or "").strip()
        if display_city:
            self._ui_weather_cache[self.weather_cache_key(display_city, settings)] = data

    def lookup_for_search(self, *, city: str, settings: Settings, force: bool = False) -> CacheLookup:
        cached = None if force else self.get_cached_weather(city, settings)
        return CacheLookup(cached=cached)

    def fetch_fresh(self, city: str, settings: Settings) -> WeatherData:
        return self.refresh_service.fetch(
            city,
            units=settings.units,
            forecast_days=settings.forecast_days,
        )

    # ---------- auto retry helpers ----------

    def reset_auto_retry(self) -> None:
        self._auto_retry_city = None
        self._auto_retry_count = 0

    def start_auto_retry_cycle(self, city: str) -> None:
        self._auto_retry_city = (city or "").strip().lower()
        self._auto_retry_count = 0

    def can_auto_retry(self, city: str) -> bool:
        norm_city = (city or "").strip().lower()
        if not norm_city:
            return False

        if self._auto_retry_city != norm_city:
            self._auto_retry_city = norm_city
            self._auto_retry_count = 0

        return self._auto_retry_count < self._max_auto_retries

    def mark_auto_retry_scheduled(self, city: str) -> None:
        norm_city = (city or "").strip().lower()
        if self._auto_retry_city != norm_city:
            self._auto_retry_city = norm_city
            self._auto_retry_count = 0
        self._auto_retry_count += 1

    @property
    def auto_retry_count(self) -> int:
        return self._auto_retry_count

    @property
    def max_auto_retries(self) -> int:
        return self._max_auto_retries
