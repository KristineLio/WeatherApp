from weather_app.services.openmeteo import WeatherService


def test_parse_daily_min_length_truncation():
    svc = WeatherService()

    daily = {
        "time": ["2026-01-01", "2026-01-02", "2026-01-03"],
        "temperature_2m_max": [10.0, 11.0],          # shorter on purpose
        "temperature_2m_min": [1.0, 2.0, 3.0],
        "weathercode": [0, 3, 61],
        "sunrise": ["2026-01-01T08:00", "2026-01-02T08:01", "2026-01-03T08:02"],
        "sunset": ["2026-01-01T17:00", "2026-01-02T17:01", "2026-01-03T17:02"],
    }

    out = svc._parse_daily(daily)

    # n = min(len(times), len(tmax), len(tmin), len(codes)) -> 2
    assert len(out) == 2
    assert out[0].date_iso == "2026-01-01"
    assert out[0].tmax == 10.0
    assert out[0].tmin == 1.0
    assert out[0].code == 0


def test_parse_daily_preserves_sunrise_sunset_lists():
    svc = WeatherService()

    daily = {
        "time": ["2026-01-01"],
        "temperature_2m_max": [10.0],
        "temperature_2m_min": [1.0],
        "weathercode": [0],
        "sunrise": ["2026-01-01T08:00"],
        "sunset": ["2026-01-01T17:00"],
    }

    out = svc._parse_daily(daily)
    assert out[0].sunrise_iso == "2026-01-01T08:00"
    assert out[0].sunset_iso == "2026-01-01T17:00"