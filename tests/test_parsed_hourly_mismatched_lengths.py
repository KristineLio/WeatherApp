
from weather_app.services.openmeteo import WeatherService
from weather_app.domain.settings import Units
from weather_app.domain.modes import HourlyMode


class StubWeatherService(WeatherService):
    def __init__(self):
        super().__init__(session=None)

    def _geocode_city(self, city: str):
        return (42.0, 23.0, city.strip() or "Sofia", "BG")


def test_fake_openmeteo_payload_with_mismatched_hourly_lengths_is_safe(monkeypatch):
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
    # Expect service/parsing to clamp to a safe min length across available arrays.
    n = len(hs.time)
    assert n > 0

    assert n == len(hs.temp)
    assert n == len(hs.code)

    # Optional arrays may be None-filled or clamped depending on implementation,
    # but they should be list-shaped and not crash consumers.
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

    # snapshot_for_date should still work (either returns a valid dict or None, but never crashes)
    snap = hs.snapshot_for_date("2026-01-18", strategy="peak_temp")
    assert snap is None or set(snap.keys()) >= {"time", "temp", "code"}