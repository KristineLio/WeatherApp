from __future__ import annotations

from weather_app.services.openmeteo import WeatherService
from weather_app.domain.settings import Units


class CountingWeatherService(WeatherService):
    """
    Subclass that avoids real network calls and counts "forecast" fetches.
    """

    def __init__(self):
        super().__init__(session=None)
        self.forecast_calls = 0
        self.geo_calls = 0

    def _geocode_city(self, city: str):
        self.geo_calls += 1
        return (42.0, 23.0, city.strip() or "Sofia", "BG")

    def _get_json(self, url: str, *, params: dict | None = None, timeout: int = 10) -> dict:
        # Count only forecast calls (geocode uses _get_json in base, but we override _geocode_city anyway)
        if "forecast" in url:
            self.forecast_calls += 1

        # Minimal valid Open-Meteo shaped payload for WeatherService.fetch()
        return {
            "current_weather": {
                "temperature": 10.0,
                "weathercode": 1,
                "time": "2026-01-18T12:50",
            },
            "daily": {
                "time": ["2026-01-18"],
                "temperature_2m_max": [12.0],
                "temperature_2m_min": [5.0],
                "weathercode": [1],
                "sunrise": ["2026-01-18T07:30"],
                "sunset": ["2026-01-18T17:10"],
            },
            "hourly": {
                "time": ["2026-01-18T12:00", "2026-01-18T13:00"],
                "temperature_2m": [10.0, 11.0],
                "weathercode": [1, 2],
                "apparent_temperature": [9.0, 10.0],
                "windspeed": [5.0, 6.0],
                "relativehumidity_2m": [50, 48],
                "precipitation_probability": [10, 15],
            },
        }


def test_fetch_cache_hit_skips_second_network_call():
    svc = CountingWeatherService()

    _ = svc.fetch("Sofia", units=Units.METRIC, forecast_days=7)
    _ = svc.fetch("Sofia", units=Units.METRIC, forecast_days=7)

    assert svc.forecast_calls == 1
    assert svc.geo_calls == 1


def test_cache_key_normalizes_city_strip_lower_and_forecast_days_int():
    svc = CountingWeatherService()

    _ = svc.fetch("  SOFIA  ", units=Units.METRIC, forecast_days=7)
    _ = svc.fetch("sofia", units=Units.METRIC, forecast_days="7")  # type: ignore[arg-type]

    assert svc.forecast_calls == 1
    assert svc.geo_calls == 1