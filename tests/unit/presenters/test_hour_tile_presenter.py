from weather_app.domain.modes import HourlyMode
from weather_app.domain.settings import Units
from weather_app.ui.hour_tile_presenter import (
    build_hour_strip_view_data,
    build_hour_tile_view_data,
)


def test_build_hour_tile_view_data_formats_value_and_icon():
    view = build_hour_tile_view_data(
        time_label="9 AM",
        mode=HourlyMode.TEMPERATURE,
        value=22.4,
        code=1,
        units=Units.METRIC,
        night=False,
        hour_int=9,
    )

    assert view.time_label == "9 AM"
    assert view.value_label == "22°C"
    assert view.icon_file == "partly.png"
    assert view.hour_int == 9


def test_hour_strip_today_rotates_from_pivot_and_labels_now():
    hourly = {
        "labels": ["8 AM", "9 AM", "10 AM"],
        "hours_int": [8, 9, 10],
        "values": [20, 22, 24],
        "codes": [0, 1, 2],
        "nights": [False, False, False],
        "pivot_index": 1,
    }

    strip = build_hour_strip_view_data(
        hourly=hourly,
        mode=HourlyMode.TEMPERATURE,
        units=Units.METRIC,
        date_iso="2026-06-07",
        today_iso="2026-06-07",
    )

    assert [item.time_label for item in strip.items] == ["NOW", "10 AM", "8 AM"]
    assert [item.hour_int for item in strip.items] == [9, 10, 8]
    assert strip.scroll_to_index is None


def test_hour_strip_other_day_scrolls_to_10am():
    hourly = {
        "labels": ["8 AM", "9 AM", "10 AM"],
        "hours_int": [8, 9, 10],
        "values": [20, 22, 24],
        "codes": [0, 1, 2],
        "nights": [False, False, False],
        "pivot_index": None,
    }

    strip = build_hour_strip_view_data(
        hourly=hourly,
        mode=HourlyMode.TEMPERATURE,
        units=Units.METRIC,
        date_iso="2026-06-08",
        today_iso="2026-06-07",
    )

    assert [item.time_label for item in strip.items] == ["8 AM", "9 AM", "10 AM"]
    assert strip.scroll_to_index == 2


def test_hour_strip_replaces_sunrise_and_sunset_tiles():
    hourly = {
        "labels": ["5 AM", "6 AM", "8 PM", "9 PM"],
        "hours_int": [5, 6, 20, 21],
        "values": [15, 16, 20, 19],
        "codes": [0, 0, 1, 1],
        "nights": [True, False, False, True],
        "sunrise_hour": 6,
        "sunset_hour": 20,
        "sunrise_iso": "2026-06-07T06:12",
        "sunset_iso": "2026-06-07T20:44",
    }

    strip = build_hour_strip_view_data(
        hourly=hourly,
        mode=HourlyMode.TEMPERATURE,
        units=Units.METRIC,
        date_iso="2026-06-08",
        today_iso="2026-06-07",
    )

    assert strip.items[1].time_label == "SUNRISE"
    assert strip.items[1].icon_file == "sunrise.png"
    assert strip.items[1].value_label == "06:12"
    assert strip.items[1].is_sunrise is True

    assert strip.items[2].time_label == "SUNSET"
    assert strip.items[2].icon_file == "sunset.png"
    assert strip.items[2].value_label == "20:44"
    assert strip.items[2].is_sunset is True


def test_hour_strip_empty_input_returns_no_items():
    strip = build_hour_strip_view_data(
        hourly={"labels": []},
        mode=HourlyMode.TEMPERATURE,
        units=Units.METRIC,
        date_iso="2026-06-07",
        today_iso="2026-06-07",
    )

    assert strip.items == []
    assert strip.scroll_to_index is None
