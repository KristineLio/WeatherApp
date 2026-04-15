from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from weather_app.domain.models import CurrentSnapshot, DailyForecast, WeatherData
from weather_app.domain.modes import HourlyMode, format_value, get_mode_meta
from weather_app.domain.settings import Units
from weather_app.utils.formatters import format_full_date, is_night
from weather_app.utils.icon_logic import code_to_gif, code_to_label_icon


@dataclass(frozen=True)
class CurrentWeatherViewData:
    header_text: str
    temp_text: str
    desc_text: str
    city_text: str
    icon_png: str
    icon_gif: str
    feels_text: str
    precip_text: str
    humidity_text: str
    wind_text: str
    is_night: bool


def _build_metric_line(mode: HourlyMode, value, units: Units) -> str:
    meta = get_mode_meta(mode)
    return f"{meta.tab_label}: {meta.fmt(value, units)}"


def build_current_weather_view_data(
    *,
    data: WeatherData,
    units: Units,
    snapshot: CurrentSnapshot | None = None,
    now_dt: dt.datetime | None = None,
) -> CurrentWeatherViewData:
    """
    Convert WeatherData/current snapshot into plain text/icon view data
    for the current hero panel.
    """
    cur: CurrentSnapshot = snapshot or data.current
    now_dt = now_dt or dt.datetime.now()

    day: DailyForecast | None = next(
        (d for d in data.daily if d.date_iso == cur.date_iso),
        None,
    )

    night = is_night(
        cur.time_iso,
        day.sunrise_iso if day else None,
        day.sunset_iso if day else None,
    )

    code = cur.code
    label, icon_png = code_to_label_icon(code or 0, night=night)
    icon_gif = code_to_gif(code, night=night)

    today_iso = data.current.date_iso
    current_date = cur.date_iso

    if current_date and today_iso and current_date == today_iso:
        header_text = f"Now {now_dt.strftime('%H:%M')}"
    elif current_date:
        header_text = format_full_date(current_date)
    else:
        header_text = ""

    return CurrentWeatherViewData(
        header_text=header_text,
        temp_text=format_value(HourlyMode.TEMPERATURE, cur.temp, units),
        desc_text=label,
        city_text=cur.city or "",
        icon_png=icon_png,
        icon_gif=icon_gif,
        feels_text="Feels like " + format_value(HourlyMode.TEMPERATURE, cur.feels_like, units),
        precip_text=_build_metric_line(HourlyMode.PRECIPITATION, cur.precip, units),
        humidity_text=_build_metric_line(HourlyMode.HUMIDITY, cur.humidity, units),
        wind_text=_build_metric_line(HourlyMode.WIND, cur.wind, units),
        is_night=night,
    )