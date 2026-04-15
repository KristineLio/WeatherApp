import datetime as dt

from weather_app.domain.models import CurrentSnapshot, DailyForecast, HourlySeries, WeatherData
from weather_app.domain.settings import Units
from weather_app.ui.current_weather_presenter import build_current_weather_view_data


def make_weather_data(
    *,
    current: CurrentSnapshot,
    daily: list[DailyForecast],
) -> WeatherData:
    return WeatherData(
        current=current,
        daily=daily,
        hourly=HourlySeries(
            time=[],
            temp=[],
            code=[],
            feels_like=[],
            humidity=[],
            precip=[],
            wind=[],
        ),
        lat=0.0,
        lon=0.0,
    )


def test_today_header_uses_now_time():
    current = CurrentSnapshot(
        temp=12.0,
        code=1,
        feels_like=10.0,
        humidity=50,
        precip=20,
        wind=8.0,
        date_iso="2026-03-15",
        time_iso="2026-03-15T12:30",
        city="Sofia, BG",
    )

    daily = [
        DailyForecast(
            date_iso="2026-03-15",
            weekday="Sun",
            tmin=5.0,
            tmax=13.0,
            code=1,
            sunrise_iso="2026-03-15T06:30",
            sunset_iso="2026-03-15T18:30",
        )
    ]

    data = make_weather_data(current=current, daily=daily)

    out = build_current_weather_view_data(
        data=data,
        units=Units.METRIC,
        now_dt=dt.datetime(2026, 3, 15, 14, 5),
    )

    assert out.header_text == "Now 14:05"


def test_non_today_header_uses_formatted_date():
    current = CurrentSnapshot(
        temp=12.0,
        code=1,
        feels_like=10.0,
        humidity=50,
        precip=20,
        wind=8.0,
        date_iso="2026-03-15",
        time_iso="2026-03-15T12:30",
        city="Sofia, BG",
    )

    selected = CurrentSnapshot(
        temp=18.0,
        code=3,
        feels_like=17.0,
        humidity=55,
        precip=10,
        wind=12.0,
        date_iso="2026-03-16",
        time_iso="2026-03-16T15:00",
        city="Sofia, BG",
    )

    daily = [
        DailyForecast(
            date_iso="2026-03-15",
            weekday="Sun",
            tmin=5.0,
            tmax=13.0,
            code=1,
            sunrise_iso="2026-03-15T06:30",
            sunset_iso="2026-03-15T18:30",
        ),
        DailyForecast(
            date_iso="2026-03-16",
            weekday="Mon",
            tmin=7.0,
            tmax=18.0,
            code=3,
            sunrise_iso="2026-03-16T06:28",
            sunset_iso="2026-03-16T18:31",
        ),
    ]

    data = make_weather_data(current=current, daily=daily)

    out = build_current_weather_view_data(
        data=data,
        snapshot=selected,
        units=Units.METRIC,
        now_dt=dt.datetime(2026, 3, 15, 14, 5),
    )

    assert out.header_text == "Monday, 16 Mar"


def test_metric_lines_are_formatted():
    current = CurrentSnapshot(
        temp=12.4,
        code=1,
        feels_like=10.2,
        humidity=51,
        precip=34,
        wind=12.4,
        date_iso="2026-03-15",
        time_iso="2026-03-15T12:30",
        city="Sofia, BG",
    )

    daily = [
        DailyForecast(
            date_iso="2026-03-15",
            weekday="Sun",
            tmin=5.0,
            tmax=13.0,
            code=1,
            sunrise_iso="2026-03-15T06:30",
            sunset_iso="2026-03-15T18:30",
        )
    ]

    data = make_weather_data(current=current, daily=daily)

    out = build_current_weather_view_data(
        data=data,
        units=Units.METRIC,
    )

    assert out.temp_text == "12°C"
    assert out.feels_text == "Feels like 10°C"
    assert out.precip_text == "Precipitation: 34%"
    assert out.humidity_text == "Humidity: 51%"
    assert out.wind_text == "Wind: 12 km/h"


def test_imperial_lines_are_formatted():
    current = CurrentSnapshot(
        temp=54.0,
        code=1,
        feels_like=50.0,
        humidity=40,
        precip=15,
        wind=9.0,
        date_iso="2026-03-15",
        time_iso="2026-03-15T12:30",
        city="Sofia, BG",
    )

    daily = [
        DailyForecast(
            date_iso="2026-03-15",
            weekday="Sun",
            tmin=40.0,
            tmax=60.0,
            code=1,
            sunrise_iso="2026-03-15T06:30",
            sunset_iso="2026-03-15T18:30",
        )
    ]

    data = make_weather_data(current=current, daily=daily)

    out = build_current_weather_view_data(
        data=data,
        units=Units.IMPERIAL,
    )

    assert out.temp_text.endswith("°F")
    assert out.feels_text.endswith("°F")
    assert out.wind_text.endswith("mph")


def test_night_icon_variant_is_used_when_after_sunset():
    current = CurrentSnapshot(
        temp=8.0,
        code=1,
        feels_like=6.0,
        humidity=70,
        precip=10,
        wind=5.0,
        date_iso="2026-03-15",
        time_iso="2026-03-15T22:00",
        city="Sofia, BG",
    )

    daily = [
        DailyForecast(
            date_iso="2026-03-15",
            weekday="Sun",
            tmin=5.0,
            tmax=13.0,
            code=1,
            sunrise_iso="2026-03-15T06:30",
            sunset_iso="2026-03-15T18:30",
        )
    ]

    data = make_weather_data(current=current, daily=daily)

    out = build_current_weather_view_data(
        data=data,
        units=Units.METRIC,
    )

    assert out.is_night is True
    assert out.icon_png.endswith("_night.png")
    assert out.icon_gif.endswith("_night.gif")


def test_missing_matching_day_falls_back_to_non_night_logic():
    current = CurrentSnapshot(
        temp=8.0,
        code=3,
        feels_like=None,
        humidity=None,
        precip=None,
        wind=None,
        date_iso="2026-03-20",
        time_iso="2026-03-20T22:00",
        city="Sofia, BG",
    )

    data = make_weather_data(current=current, daily=[])

    out = build_current_weather_view_data(
        data=data,
        units=Units.METRIC,
    )

    assert out.is_night is False
    assert out.desc_text == "Overcast"
    assert out.feels_text == "Feels like —"
    assert out.precip_text == "Precipitation: —"
    assert out.humidity_text == "Humidity: —"
    assert out.wind_text == "Wind: —"