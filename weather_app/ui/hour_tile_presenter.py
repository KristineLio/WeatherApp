from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from weather_app.domain.modes import HourlyMode, icon_for, format_value
from weather_app.domain.settings import Units
from weather_app.utils.formatters import time_hhmm_from_iso

Value: TypeAlias = float | int | None


@dataclass(frozen=True)
class HourTileViewData:
    time_label: str
    icon_file: str
    value_label: str
    hour_int: int | None = None
    is_sunrise: bool = False
    is_sunset: bool = False


@dataclass(frozen=True)
class HourStripViewData:
    items: list[HourTileViewData]
    scroll_to_index: int | None


def build_hour_tile_view_data(
    *,
    time_label: str,
    mode: HourlyMode,
    value: Value,
    code: int | None,
    units: Units,
    night: bool = False,
    hour_int: int | None = None,
) -> HourTileViewData:
    return HourTileViewData(
        time_label=time_label,
        icon_file=icon_for(mode, value, code, night=night),
        value_label=format_value(mode, value, units),
        hour_int=hour_int,
    )


def build_hour_strip_view_data(
    *,
    hourly: dict,
    mode: HourlyMode,
    units: Units,
    date_iso: str | None,
    today_iso: str | None,
) -> HourStripViewData:
    """
    Convert raw hourly/day data into display-ready tile view models.

    Rules:
    - Today: rotate so current hour comes first and rename first tile to NOW
    - Other days: keep chronological order
    - Replace matching sunrise/sunset hours with dedicated tiles
    - Default scroll target:
        * today -> no specific child target (scroll to start)
        * other day -> 10 AM tile if present
    """
    hours = list(hourly.get("labels", []))
    hours_int = list(hourly.get("hours_int", []))
    values = list(hourly.get("values", []))
    codes = list(hourly.get("codes", []))
    nights = list(hourly.get("nights", []))

    sunrise_hour = hourly.get("sunrise_hour")
    sunset_hour = hourly.get("sunset_hour")
    sunrise_iso = hourly.get("sunrise_iso")
    sunset_iso = hourly.get("sunset_iso")

    if not hours:
        return HourStripViewData(items=[], scroll_to_index=None)

    is_today = bool(today_iso and date_iso == today_iso)

    if is_today:
        pivot = hourly.get("pivot_index")
        if pivot is not None and 0 <= pivot < len(hours):
            hours = hours[pivot:] + hours[:pivot]
            hours_int = hours_int[pivot:] + hours_int[:pivot]
            values = values[pivot:] + values[:pivot]
            codes = codes[pivot:] + codes[:pivot]
            nights = nights[pivot:] + nights[:pivot]
            hours[0] = "NOW"

    items: list[HourTileViewData] = []

    for i in range(len(hours)):
        hour_int = hours_int[i] if i < len(hours_int) else None
        night = nights[i] if i < len(nights) else False

        is_sunrise = sunrise_hour is not None and hour_int == sunrise_hour
        if is_sunrise:
            items.append(
                HourTileViewData(
                    time_label="SUNRISE",
                    icon_file="sunrise.png",
                    value_label=time_hhmm_from_iso(sunrise_iso),
                    hour_int=hour_int,
                    is_sunrise=True,
                )
            )
            continue

        is_sunset = sunset_hour is not None and hour_int == sunset_hour
        if is_sunset:
            items.append(
                HourTileViewData(
                    time_label="SUNSET",
                    icon_file="sunset.png",
                    value_label=time_hhmm_from_iso(sunset_iso),
                    hour_int=hour_int,
                    is_sunset=True,
                )
            )
            continue

        items.append(
            build_hour_tile_view_data(
                time_label=hours[i],
                mode=mode,
                value=values[i] if i < len(values) else None,
                code=codes[i] if i < len(codes) else None,
                units=units,
                night=night,
                hour_int=hour_int,
            )
        )

    if is_today:
        scroll_to_index = None
    else:
        try:
            scroll_to_index = next(i for i, item in enumerate(items) if item.hour_int == 10)
        except StopIteration:
            scroll_to_index = None

    return HourStripViewData(items=items, scroll_to_index=scroll_to_index)