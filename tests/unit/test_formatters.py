from weather_app.utils.formatters import (
    weekday_from_iso,
    format_full_date,
    format_hour_label,
    is_night,
    time_hhmm_from_iso,
)


def test_weekday_from_iso_returns_three_letters():
    s = weekday_from_iso("2026-01-18")
    assert isinstance(s, str)
    assert len(s) == 3


def test_format_full_date_contains_comma_and_day_number():
    s = format_full_date("2026-01-18")
    assert "," in s
    assert "18" in s


def test_format_hour_label_am_pm():
    s = format_hour_label(7).upper()
    assert ("AM" in s) or ("PM" in s)


def test_is_night_before_sunrise_true():
    assert is_night("2026-01-18T06:00", "2026-01-18T07:30", "2026-01-18T17:00") is True


def test_is_night_midday_false():
    assert is_night("2026-01-18T12:00", "2026-01-18T07:30", "2026-01-18T17:00") is False


def test_is_night_after_sunset_true():
    assert is_night("2026-01-18T18:00", "2026-01-18T07:30", "2026-01-18T17:00") is True


def test_time_hhmm_from_iso_and_none():
    assert time_hhmm_from_iso("2026-01-18T07:52") == "07:52"
    assert time_hhmm_from_iso(None) == ""

                  

def test_format_hour_label_midnight_and_noon_are_reasonable():
    """Guard: platform-specific strftime should produce a non-empty AM/PM label for 0 and 12."""
    s0 = format_hour_label(0).strip()
    s12 = format_hour_label(12).strip()

    # not empty / not whitespace
    assert s0
    assert s12

    # should still be a "time-like" label: contains at least one digit
    assert any(ch.isdigit() for ch in s0)
    assert any(ch.isdigit() for ch in s12)

    # keep your existing contract: should indicate AM/PM
    assert ("AM" in s0.upper()) or ("PM" in s0.upper())
    assert ("AM" in s12.upper()) or ("PM" in s12.upper())