from weather_app.utils.formatters import (
    format_d_m_hhmm,
    format_full_date,
    format_hour_label,
    is_night,
    time_hhmm_from_iso,
    weekday_from_iso,
)


def test_weekday_from_iso():
    assert weekday_from_iso("2026-06-07") == "Sun"


def test_format_full_date():
    assert format_full_date("2026-06-07") == "Sunday, 07 Jun"


def test_format_hour_label_removes_leading_zero():
    assert format_hour_label(9) == "9 AM"
    assert format_hour_label(15) == "3 PM"


def test_is_night_before_sunrise_and_after_sunset():
    sunrise = "2026-06-07T05:50"
    sunset = "2026-06-07T20:55"

    assert is_night("2026-06-07T04:00", sunrise, sunset) is True
    assert is_night("2026-06-07T12:00", sunrise, sunset) is False
    assert is_night("2026-06-07T21:00", sunrise, sunset) is True


def test_is_night_missing_data_returns_false():
    assert is_night(None, "2026-06-07T05:50", "2026-06-07T20:55") is False
    assert is_night("2026-06-07T21:00", None, "2026-06-07T20:55") is False


def test_time_hhmm_from_iso():
    assert time_hhmm_from_iso("2026-06-07T05:50") == "05:50"
    assert time_hhmm_from_iso(None) == ""
    assert time_hhmm_from_iso("bad") == ""


def test_format_d_m_hhmm():
    assert format_d_m_hhmm("2026-06-07T09:30") == "07 Jun 09:30"
    assert format_d_m_hhmm("bad") == "bad"
    assert format_d_m_hhmm("") == "—"
