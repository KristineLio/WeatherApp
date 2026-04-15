from weather_app.domain.modes import HourlyMode
from weather_app.domain.settings import Units
from weather_app.ui.hour_tile_presenter import build_hour_strip_view_data


def test_today_rotates_and_marks_now():
    hourly = {
        "labels": ["9 AM", "10 AM", "11 AM", "12 PM"],
        "hours_int": [9, 10, 11, 12],
        "values": [1, 2, 3, 4],
        "codes": [0, 0, 0, 0],
        "nights": [False, False, False, False],
        "pivot_index": 2,
        "sunrise_hour": None,
        "sunset_hour": None,
        "sunrise_iso": None,
        "sunset_iso": None,
    }

    out = build_hour_strip_view_data(
        hourly=hourly,
        mode=HourlyMode.TEMPERATURE,
        units=Units.METRIC,
        date_iso="2026-03-15",
        today_iso="2026-03-15",
    )

    assert [x.hour_int for x in out.items] == [11, 12, 9, 10]
    assert out.items[0].time_label == "NOW"
    assert out.scroll_to_index is None


def test_non_today_keeps_order():
    hourly = {
        "labels": ["9 AM", "10 AM", "11 AM"],
        "hours_int": [9, 10, 11],
        "values": [1, 2, 3],
        "codes": [0, 0, 0],
        "nights": [False, False, False],
        "pivot_index": 1,
        "sunrise_hour": None,
        "sunset_hour": None,
        "sunrise_iso": None,
        "sunset_iso": None,
    }

    out = build_hour_strip_view_data(
        hourly=hourly,
        mode=HourlyMode.TEMPERATURE,
        units=Units.METRIC,
        date_iso="2026-03-16",
        today_iso="2026-03-15",
    )

    assert [x.hour_int for x in out.items] == [9, 10, 11]
    assert out.items[0].time_label == "9 AM"


def test_sunrise_and_sunset_replace_matching_hours():
    hourly = {
        "labels": ["6 AM", "7 AM", "6 PM"],
        "hours_int": [6, 7, 18],
        "values": [1, 2, 3],
        "codes": [0, 0, 0],
        "nights": [True, False, True],
        "pivot_index": None,
        "sunrise_hour": 6,
        "sunset_hour": 18,
        "sunrise_iso": "2026-03-16T06:24",
        "sunset_iso": "2026-03-16T18:41",
    }

    out = build_hour_strip_view_data(
        hourly=hourly,
        mode=HourlyMode.TEMPERATURE,
        units=Units.METRIC,
        date_iso="2026-03-16",
        today_iso="2026-03-15",
    )

    assert out.items[0].time_label == "SUNRISE"
    assert out.items[0].icon_file == "sunrise.png"
    assert out.items[0].value_label == "06:24"

    assert out.items[2].time_label == "SUNSET"
    assert out.items[2].icon_file == "sunset.png"
    assert out.items[2].value_label == "18:41"


def test_non_today_scrolls_to_10am_when_present():
    hourly = {
        "labels": ["8 AM", "9 AM", "10 AM", "11 AM"],
        "hours_int": [8, 9, 10, 11],
        "values": [1, 2, 3, 4],
        "codes": [0, 0, 0, 0],
        "nights": [False, False, False, False],
        "pivot_index": None,
        "sunrise_hour": None,
        "sunset_hour": None,
        "sunrise_iso": None,
        "sunset_iso": None,
    }

    out = build_hour_strip_view_data(
        hourly=hourly,
        mode=HourlyMode.TEMPERATURE,
        units=Units.METRIC,
        date_iso="2026-03-16",
        today_iso="2026-03-15",
    )

    assert out.scroll_to_index == 2


def test_empty_hourly_returns_empty_strip():
    out = build_hour_strip_view_data(
        hourly={},
        mode=HourlyMode.TEMPERATURE,
        units=Units.METRIC,
        date_iso="2026-03-16",
        today_iso="2026-03-15",
    )

    assert out.items == []
    assert out.scroll_to_index is None