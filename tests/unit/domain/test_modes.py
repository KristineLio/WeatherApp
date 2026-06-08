from weather_app.domain.modes import (
    DEFAULT_MODE,
    HourlyMode,
    format_value,
    get_mode_meta,
    icon_for,
)
from weather_app.domain.settings import Units


def test_default_mode_is_temperature():
    assert DEFAULT_MODE == HourlyMode.TEMPERATURE


def test_format_temperature_metric_and_imperial():
    assert format_value(HourlyMode.TEMPERATURE, 21.6, Units.METRIC) == "22°C"
    assert format_value(HourlyMode.TEMPERATURE, 70.2, Units.IMPERIAL) == "70°F"


def test_format_wind_metric_and_imperial():
    assert format_value(HourlyMode.WIND, 12.4, Units.METRIC) == "12 km/h"
    assert format_value(HourlyMode.WIND, 12.6, Units.IMPERIAL) == "13 mph"


def test_format_percent_values():
    assert format_value(HourlyMode.HUMIDITY, 58, Units.METRIC) == "58%"
    assert format_value(HourlyMode.PRECIPITATION, None, Units.METRIC) == "—"


def test_get_mode_meta_unknown_falls_back_to_default():
    assert get_mode_meta("bad") == get_mode_meta(DEFAULT_MODE)  # type: ignore[arg-type]


def test_temperature_icon_uses_weather_code():
    assert icon_for(HourlyMode.TEMPERATURE, 20, 0) == "clear.png"
    assert icon_for(HourlyMode.TEMPERATURE, 20, None) == "unknown.png"


def test_threshold_icons_for_metric_modes():
    assert icon_for(HourlyMode.PRECIPITATION, 19, None) == "precip_low.png"
    assert icon_for(HourlyMode.PRECIPITATION, 20, None) == "precip_med.png"
    assert icon_for(HourlyMode.WIND, 9, None) == "wind_calm.png"
    assert icon_for(HourlyMode.HUMIDITY, 80, None) == "hum_muggy.png"

def test_feels_like_mode_formats_like_temperature_and_uses_weather_icon():
    assert format_value(HourlyMode.FEELS_LIKE, 21.6, Units.METRIC) == "22°C"
    assert format_value(HourlyMode.FEELS_LIKE, 70.2, Units.IMPERIAL) == "70°F"
    assert get_mode_meta(HourlyMode.FEELS_LIKE).tab_label == "Feels like"
    assert icon_for(HourlyMode.FEELS_LIKE, 21.6, 1) == "partly.png"
    assert icon_for(HourlyMode.FEELS_LIKE, 21.6, None) == "unknown.png"
