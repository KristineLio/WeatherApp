"""These are “parsing resilience” tests that:

avoid real network

ensure fetch works if hourly optional arrays are missing

ensure daily mismatched lengths are safely clamped

ensure missing required time fields still raise """

from __future__ import annotations

import pytest

from weather_app.services.openmeteo import WeatherService
from weather_app.domain.settings import Units


class StubWeatherService(WeatherService):
    def __init__(self):
        super().__init__(session=None)

    def _geocode_city(self, city: str):
        return (42.0, 23.0, city.strip() or "Sofia", "BG")


def test_fetch_succeeds_if_hourly_optional_arrays_missing(monkeypatch):
    svc = StubWeatherService()

    def fake_get_json(url: str, *, params=None, timeout=10):
        # Forecast URL call
        if "forecast" in url:
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
                    # Missing these on purpose (should not crash):
                    # "apparent_temperature": ...
                    # "windspeed": ...
                    # "relativehumidity_2m": ...
                    # "precipitation_probability": ...
                },
            }
        raise AssertionError("Unexpected URL in test")

    monkeypatch.setattr(svc, "_get_json", fake_get_json)

    wd = svc.fetch("Sofia", units=Units.METRIC, forecast_days=7)
    assert wd.current.city.startswith("Sofia")
    assert wd.current.time_iso == "2026-01-18T12:50"
    assert wd.hourly.time == ["2026-01-18T12:00", "2026-01-18T13:00"]

    # derive_current_extras will try to find 12:00; optional arrays are missing => extras should be None
    assert wd.current.feels_like is None
    assert wd.current.humidity is None
    assert wd.current.precip is None
    assert wd.current.wind is None


def test_parse_daily_clamps_to_min_length(monkeypatch):
    svc = StubWeatherService()

    def fake_get_json(url: str, *, params=None, timeout=10):
        if "forecast" in url:
            return {
                "current_weather": {
                    "temperature": 10.0,
                    "weathercode": 1,
                    "time": "2026-01-18T12:50",
                },
                "daily": {
                    "time": ["2026-01-18", "2026-01-19", "2026-01-20"],
                    "temperature_2m_max": [12.0],  # shorter on purpose
                    "temperature_2m_min": [5.0, 6.0],  # longer than max, shorter than time
                    "weathercode": [1, 2, 3, 4],  # longer on purpose
                    "sunrise": ["2026-01-18T07:30"],
                    "sunset": ["2026-01-18T17:10"],
                },
                "hourly": {
                    "time": ["2026-01-18T12:00"],
                    "temperature_2m": [10.0],
                    "weathercode": [1],
                    "apparent_temperature": [9.0],
                    "windspeed": [5.0],
                    "relativehumidity_2m": [50],
                    "precipitation_probability": [10],
                },
            }
        raise AssertionError("Unexpected URL in test")

    monkeypatch.setattr(svc, "_get_json", fake_get_json)

    wd = svc.fetch("Sofia", units=Units.METRIC, forecast_days=7)

    # _parse_daily uses min(len(time), len(tmax), len(tmin), len(code)) => min is 1 here
    assert len(wd.daily) == 1
    assert wd.daily[0].date_iso == "2026-01-18"


def test_fetch_raises_if_missing_required_time_fields(monkeypatch):
    svc = StubWeatherService()

    def fake_get_json(url: str, *, params=None, timeout=10):
        if "forecast" in url:
            return {
                "current_weather": {
                    "temperature": 10.0,
                    "weathercode": 1,
                    # missing "time" -> should raise RuntimeError
                },
                "daily": {"time": ["2026-01-18"], "temperature_2m_max": [12.0], "temperature_2m_min": [5.0], "weathercode": [1]},
                "hourly": {"time": ["2026-01-18T12:00"], "temperature_2m": [10.0], "weathercode": [1]},
            }
        raise AssertionError("Unexpected URL in test")

    monkeypatch.setattr(svc, "_get_json", fake_get_json)

    with pytest.raises(RuntimeError, match="missing current time"):
        svc.fetch("Sofia", units=Units.METRIC, forecast_days=7)