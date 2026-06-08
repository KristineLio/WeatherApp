from weather_app.domain.models import CurrentSnapshot, DailyForecast, HourlySeries, WeatherData
from weather_app.domain.settings import Settings
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
            "time": ["2026-06-07T09:00"],
            "temperature_2m": [temp],
            "weathercode": [1],
            "apparent_temperature": [temp],
            "relativehumidity_2m": [55],
            "precipitation_probability": [0],
            "windspeed": [8],
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
                tmax=temp + 3,
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


def test_cache_then_refresh_flow_shows_cached_then_stores_fresh_data():
    settings = Settings(forecast_days=7)
    cached = make_weather(temp=20)
    fresh = make_weather(temp=25)
    refresh_service = FakeRefreshService(fresh)
    manager = CacheRefreshManager(refresh_service=refresh_service)

    manager.store_cached_weather("Sofia", cached, settings)

    lookup = manager.lookup_for_search(city="Sofia", settings=settings)
    assert lookup.hit is True
    assert lookup.cached.current.temp == 20

    fresh_result = manager.fetch_fresh("Sofia", settings)
    manager.store_cached_weather("Sofia", fresh_result, settings)

    lookup_after_refresh = manager.lookup_for_search(city="Sofia", settings=settings)
    assert lookup_after_refresh.hit is True
    assert lookup_after_refresh.cached.current.temp == 25
    assert refresh_service.calls == [("Sofia", settings.units, settings.forecast_days)]


def test_force_refresh_skips_cached_lookup_but_can_still_fetch_fresh():
    settings = Settings()
    cached = make_weather(temp=20)
    fresh = make_weather(temp=27)
    refresh_service = FakeRefreshService(fresh)
    manager = CacheRefreshManager(refresh_service=refresh_service)
    manager.store_cached_weather("Sofia", cached, settings)

    lookup = manager.lookup_for_search(city="Sofia", settings=settings, force=True)
    fresh_result = manager.fetch_fresh("Sofia", settings)

    assert lookup.hit is False
    assert fresh_result.current.temp == 27
