from weather_app.services.openmeteo import WeatherService


def test_parse_daily_truncates_to_shortest_series():
    svc = WeatherService()

    daily = {
        "time": ["2026-01-01", "2026-01-02", "2026-01-03"],
        "temperature_2m_max": [10.0, 11.0],  # shorter on purpose
        "temperature_2m_min": [1.0, 2.0, 3.0],
        "weathercode": [0, 3, 61],
        "sunrise": ["2026-01-01T08:00", "2026-01-02T08:01", "2026-01-03T08:02"],
        "sunset": ["2026-01-01T17:00", "2026-01-02T17:01", "2026-01-03T17:02"],
    }

    out = svc._parse_daily(daily)

    # n = min(len(time), len(tmax), len(tmin), len(code)) == 2
    assert len(out) == 2
    assert out[0].date_iso == "2026-01-01"
    assert out[0].tmax == 10.0
    assert out[0].tmin == 1.0
    assert out[0].code == 0


def test_parse_daily_includes_sunrise_sunset_fields():
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

#forces mismatch / missing and verifies no crash + None.
def test_parse_daily_sunrise_sunset_shorter_or_missing_is_safe():
    svc = WeatherService()

    daily = {
        "time": ["2026-01-01", "2026-01-02", "2026-01-03"],
        "temperature_2m_max": [10.0, 11.0, 12.0],
        "temperature_2m_min": [1.0, 2.0, 3.0],
        "weathercode": [0, 3, 61],
        # sunrise is shorter (only 1)
        "sunrise": ["2026-01-01T08:00"],
        # sunset missing entirely
        # "sunset": ...
    }

    out = svc._parse_daily(daily)

    assert len(out) == 3

    assert out[0].sunrise_iso == "2026-01-01T08:00"
    assert out[0].sunset_iso is None

    assert out[1].sunrise_iso is None
    assert out[1].sunset_iso is None

    assert out[2].sunrise_iso is None
    assert out[2].sunset_iso is None