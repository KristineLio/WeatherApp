"""
Hourly pipeline contracts for Open-Meteo -> WeatherService.fetch() -> HourlySeries consumers.

This file intentionally keeps two tests:
1) "Happy path" payload: correctness + expected behaviors 
        -snapshot_for_date/build_day regressions after refactors
        -“current extras” hour-bucketing logic
2) "Mismatched arrays" payload: resilience + internal consistency
        -intentionally gives hourly arrays with different lengths and 
        -checks that: fetch() does not crash
        -the resulting HourlySeries is internally consistent 
         (all lists same length), build_day() still works
"""
import pytest

from weather_app.services.openmeteo import WeatherService
from weather_app.domain.settings import Units
from weather_app.domain.modes import HourlyMode

pytestmark = pytest.mark.contract


class StubWeatherService(WeatherService):
    """No-network service. We monkeypatch _get_json per test."""

    def __init__(self):
        super().__init__(session=None)

    def _geocode_city(self, city: str):
        return (42.0, 23.0, city.strip() or "Sofia", "BG")


def test_hourly_contract_happy_path(monkeypatch):
    svc = StubWeatherService()

    def fake_get_json(url: str, *, params=None, timeout=10):
        if "forecast" in url:
            return {
                "current_weather": {
                    "temperature": 10.0,
                    "weathercode": 2,
                    "time": "2026-01-18T12:50",
                },
                "daily": {
                    "time": ["2026-01-18", "2026-01-19"],
                    "temperature_2m_max": [12.0, 9.0],
                    "temperature_2m_min": [5.0, 3.0],
                    "weathercode": [2, 45],
                    "sunrise": ["2026-01-18T07:30", "2026-01-19T07:29"],
                    "sunset": ["2026-01-18T17:10", "2026-01-19T17:11"],
                },
                "hourly": {
                    "time": [
                        "2026-01-18T11:00",
                        "2026-01-18T12:00",
                        "2026-01-18T13:00",
                        "2026-01-19T12:00",
                    ],
                    "temperature_2m": [8.0, 10.0, 11.0, 6.0],
                    "weathercode": [1, 2, 3, 45],
                    "apparent_temperature": [7.0, 9.0, 10.0, 5.0],
                    "windspeed": [3.0, 5.0, 6.0, 2.0],
                    "relativehumidity_2m": [60, 55, 50, 80],
                    "precipitation_probability": [10, 20, 30, 40],
                },
            }
        raise AssertionError("Unexpected URL in test")

    monkeypatch.setattr(svc, "_get_json", fake_get_json)

    wd = svc.fetch("Sofia", units=Units.METRIC, forecast_days=7)

    # Parsed hourly series exists and has expected shape
    hs = wd.hourly
    assert hs.time[:3] == ["2026-01-18T11:00", "2026-01-18T12:00", "2026-01-18T13:00"]
    assert len(hs.time) == len(hs.temp) == len(hs.code)

    # snapshot_for_date: peak temp on 2026-01-18 should select 13:00 (11.0)
    snap = hs.snapshot_for_date("2026-01-18", strategy="peak_temp")
    assert snap is not None
    assert snap["time"] == "2026-01-18T13:00"
    assert snap["temp"] == 11.0

    # build_day contract across all modes (no crash, consistent lengths)
    for mode in HourlyMode:
        day = hs.build_day(
            "2026-01-18",
            mode=mode,
            today_iso="2026-01-18",
            current_time_iso="2026-01-18T12:50",
        )
        n = len(day["time_isos"])
        assert n > 0
        assert n == len(day["labels"]) == len(day["hours_int"]) == len(day["values"]) == len(day["codes"])

        pivot = day["pivot_index"]
        assert pivot is None or (0 <= pivot < n)

    # Extra: current extras should align with 12:00 bucket (matches 12:50)
    assert wd.current.time_iso == "2026-01-18T12:50"
    assert wd.current.feels_like == 9.0
    assert wd.current.humidity == 55
    assert wd.current.precip == 20
    assert wd.current.wind == 5.0


def test_hourly_contract_mismatched_lengths_is_safe(monkeypatch):
    svc = StubWeatherService()

    def fake_get_json(url: str, *, params=None, timeout=10):
        if "forecast" in url:
            return {
                "current_weather": {
                    "temperature": 10.0,
                    "weathercode": 2,
                    "time": "2026-01-18T12:50",
                },
                "daily": {
                    "time": ["2026-01-18"],
                    "temperature_2m_max": [12.0],
                    "temperature_2m_min": [5.0],
                    "weathercode": [2],
                    "sunrise": ["2026-01-18T07:30"],
                    "sunset": ["2026-01-18T17:10"],
                },
                "hourly": {
                    # time has 4 points
                    "time": [
                        "2026-01-18T11:00",
                        "2026-01-18T12:00",
                        "2026-01-18T13:00",
                        "2026-01-18T14:00",
                    ],
                    # temperature has only 3 points (short)
                    "temperature_2m": [8.0, 10.0, 11.0],
                    # code has 5 points (long)
                    "weathercode": [1, 2, 3, 45, 51],
                    # feels_like missing last entry (short)
                    "apparent_temperature": [7.0, 9.0, 10.0],
                    # wind has exact 4 points (matches time)
                    "windspeed": [3.0, 5.0, 6.0, 2.0],
                    # humidity has 2 points (very short)
                    "relativehumidity_2m": [60, 55],
                    # precip has 4 points (matches time)
                    "precipitation_probability": [10, 20, 30, 40],
                },
            }
        raise AssertionError("Unexpected URL in test")

    monkeypatch.setattr(svc, "_get_json", fake_get_json)

    wd = svc.fetch("Sofia", units=Units.METRIC, forecast_days=7)
    hs = wd.hourly

    # Contract: HourlySeries should have consistent internal lengths.
    n = len(hs.time)
    assert n > 0
    assert n == len(hs.temp) == len(hs.code)
    assert len(hs.feels_like) == n
    assert len(hs.humidity) == n
    assert len(hs.precip) == n
    assert len(hs.wind) == n

    # build_day must not crash for any mode, and must keep list lengths aligned
    for mode in HourlyMode:
        day = hs.build_day(
            "2026-01-18",
            mode=mode,
            today_iso="2026-01-18",
            current_time_iso="2026-01-18T12:50",
        )
        m = len(day["time_isos"])
        assert m == len(day["labels"]) == len(day["hours_int"]) == len(day["values"]) == len(day["codes"])

    # snapshot_for_date should still work (valid dict or None, but never crashes)
    snap = hs.snapshot_for_date("2026-01-18", strategy="peak_temp")
    assert snap is None or set(snap.keys()) >= {"time", "temp", "code"}