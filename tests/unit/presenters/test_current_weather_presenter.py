import datetime as dt

from weather_app.domain.models import CurrentSnapshot
from weather_app.domain.settings import Units
from weather_app.ui.current_weather_presenter import build_current_weather_view_data


def test_current_weather_view_data_for_today(sample_weather_data):
    view = build_current_weather_view_data(
        data=sample_weather_data,
        units=Units.METRIC,
        now_dt=dt.datetime(2026, 6, 7, 12, 34),
    )

    assert view.header_text == "Now 12:34"
    assert view.temp_text == "22°C"
    assert view.desc_text == "Mainly clear"
    assert view.city_text == "Sofia, Bulgaria"
    assert view.icon_png == "partly.png"
    assert view.icon_gif == "partly.gif"
    assert view.feels_text == "Feels like: 21°C"
    assert view.precip_text == "Precipitation: 10%"
    assert view.humidity_text == "Humidity: 58%"
    assert view.wind_text == "Wind: 8 km/h"


def test_current_weather_view_data_for_selected_future_date(sample_weather_data):
    snapshot = CurrentSnapshot(
        temp=28.0,
        code=61,
        feels_like=27.0,
        humidity=65,
        precip=30,
        wind=12.0,
        date_iso="2026-06-08",
        time_iso="2026-06-08T15:00",
        city="Sofia, Bulgaria",
    )

    view = build_current_weather_view_data(
        data=sample_weather_data,
        snapshot=snapshot,
        units=Units.METRIC,
        now_dt=dt.datetime(2026, 6, 7, 12, 34),
    )

    assert view.header_text == "Monday, 08 Jun"
    assert view.temp_text == "28°C"
    assert view.desc_text == "Light rain"
    assert view.icon_png == "rain.png"


def test_current_weather_view_data_detects_night(sample_weather_data):
    snapshot = CurrentSnapshot(
        temp=18.0,
        code=0,
        feels_like=18.0,
        humidity=70,
        precip=0,
        wind=4.0,
        date_iso="2026-06-07",
        time_iso="2026-06-07T22:00",
        city="Sofia, Bulgaria",
    )

    view = build_current_weather_view_data(
        data=sample_weather_data,
        snapshot=snapshot,
        units=Units.METRIC,
        now_dt=dt.datetime(2026, 6, 7, 22, 0),
    )

    assert view.is_night is True

def test_current_weather_view_data_formats_imperial_units(sample_weather_data):
    view = build_current_weather_view_data(
        data=sample_weather_data,
        units=Units.IMPERIAL,
        now_dt=dt.datetime(2026, 6, 7, 12, 34),
    )

    assert view.temp_text == "22°F"
    assert view.feels_text == "Feels like: 21°F"
    assert view.wind_text == "Wind: 8 mph"
