from weather_app.domain.modes import (
    HourlyMode,
    get_mode_meta,
    format_value,
    icon_for,
)
from weather_app.domain.settings import Units


def test_get_mode_meta_returns_meta_for_each_mode():
    for m in HourlyMode:
        meta = get_mode_meta(m)
        assert meta.tab_label
        assert callable(meta.fmt)
        assert callable(meta.icon)


def test_format_value_temperature_metric_imperial():
    assert format_value(HourlyMode.TEMPERATURE, 10.4, Units.METRIC).endswith("°C")
    assert format_value(HourlyMode.TEMPERATURE, 10.4, Units.IMPERIAL).endswith("°F")


def test_format_value_wind_metric_imperial():
    assert "km/h" in format_value(HourlyMode.WIND, 12.2, Units.METRIC)
    assert "mph" in format_value(HourlyMode.WIND, 12.2, Units.IMPERIAL)


def test_format_value_percent():
    assert format_value(HourlyMode.HUMIDITY, 51, Units.METRIC) == "51%"
    assert format_value(HourlyMode.PRECIPITATION, None, Units.METRIC) == "—"


def test_icon_for_temperature_uses_weather_code_icon():
    # code 0 -> clear.png (day)
    assert icon_for(HourlyMode.TEMPERATURE, 10, 0, night=False) == "clear.png"
    # night variant appends _night
    assert icon_for(HourlyMode.TEMPERATURE, 10, 0, night=True) == "clear_night.png"