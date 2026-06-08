from dataclasses import dataclass

from weather_app.domain.models import CurrentSnapshot, DailyForecast, HourlySeries, WeatherData
from weather_app.domain.settings import Settings, Units
from weather_app.ui.cache_refresh_manager import CacheRefreshManager


class FakeRefreshService:
    def __init__(self, data):
        self.data = data
        self.calls = []

    def fetch(self, city, *, units, forecast_days):
        self.calls.append((city, units, forecast_days))
        return self.data


def make_weather(city="Sofia, Bulgaria", temp=22):
    hourly = HourlySeries.from_api(
        {
            "time": ["2026-06-07T09:00", "2026-06-07T10:00"],
            "temperature_2m": [temp, temp + 1],
            "weathercode": [1, 1],
            "apparent_temperature": [temp, temp + 1],
            "relativehumidity_2m": [55, 56],
            "precipitation_probability": [0, 10],
            "windspeed": [8, 9],
        }
    )
    return WeatherData(
        current=CurrentSnapshot(
            temp=temp,
            code=1,
            feels_like=temp,
            humidity=55,
            precip=0,
            wind=8,
            date_iso="2026-06-07",
            time_iso="2026-06-07T09:00",
            city=city,
        ),
        daily=[
            DailyForecast(
                date_iso="2026-06-07",
                weekday="Sun",
                tmin=16,
                tmax=25,
                code=1,
                sunrise_iso="2026-06-07T05:50",
                sunset_iso="2026-06-07T20:55",
            )
        ],
        hourly=hourly,
        lat=42.6977,
        lon=23.3219,
        resolved_name="Sofia",
        country="Bulgaria",
    )


def test_weather_cache_key_normalizes_city_and_uses_units_and_days():
    manager = CacheRefreshManager(refresh_service=FakeRefreshService(make_weather()))
    settings = Settings(units=Units.IMPERIAL, forecast_days=5)

    key = manager.weather_cache_key("  Sofia   Bulgaria  ", settings)

    assert key == ("sofia bulgaria", "imperial", 5)


def test_store_cached_weather_saves_typed_and_display_city_keys():
    manager = CacheRefreshManager(refresh_service=FakeRefreshService(make_weather()))
    settings = Settings(units=Units.METRIC, forecast_days=7)
    data = make_weather(city="Sofia, Bulgaria")

    manager.store_cached_weather("sofia", data, settings)

    assert manager.get_cached_weather("sofia", settings) is data
    assert manager.get_cached_weather("Sofia, Bulgaria", settings) is data


def test_lookup_for_search_returns_hit_unless_force_true():
    manager = CacheRefreshManager(refresh_service=FakeRefreshService(make_weather()))
    settings = Settings()
    data = make_weather()
    manager.store_cached_weather("Sofia", data, settings)

    normal_lookup = manager.lookup_for_search(city="Sofia", settings=settings)
    forced_lookup = manager.lookup_for_search(city="Sofia", settings=settings, force=True)

    assert normal_lookup.hit is True
    assert normal_lookup.cached is data
    assert forced_lookup.hit is False
    assert forced_lookup.cached is None


def test_fetch_fresh_uses_refresh_service_with_current_settings():
    fresh = make_weather(temp=30)
    refresh_service = FakeRefreshService(fresh)
    manager = CacheRefreshManager(refresh_service=refresh_service)
    settings = Settings(units=Units.IMPERIAL, forecast_days=3)

    result = manager.fetch_fresh("Sofia", settings)

    assert result is fresh
    assert refresh_service.calls == [("Sofia", Units.IMPERIAL, 3)]


def test_auto_retry_allows_only_configured_number_per_city():
    manager = CacheRefreshManager(
        refresh_service=FakeRefreshService(make_weather()),
        max_auto_retries=1,
    )

    manager.start_auto_retry_cycle("Sofia")

    assert manager.can_auto_retry("sofia") is True
    manager.mark_auto_retry_scheduled("sofia")
    assert manager.auto_retry_count == 1
    assert manager.can_auto_retry("sofia") is False

    # A different city starts a new retry cycle.
    assert manager.can_auto_retry("Plovdiv") is True
    assert manager.auto_retry_count == 0


def test_reset_auto_retry_clears_state():
    manager = CacheRefreshManager(refresh_service=FakeRefreshService(make_weather()))
    manager.start_auto_retry_cycle("Sofia")
    manager.mark_auto_retry_scheduled("Sofia")

    manager.reset_auto_retry()

    assert manager.auto_retry_count == 0
    assert manager.can_auto_retry("Sofia") is True
