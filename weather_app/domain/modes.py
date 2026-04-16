from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, TYPE_CHECKING, TypeAlias

from weather_app.utils.icon_logic import (
    pick_icon_by_threshold,
    code_to_label_icon,
    PRECIP_ICONS,
    WIND_ICONS,
    HUMIDITY_ICONS,
)
from weather_app.domain.settings import Units

if TYPE_CHECKING:
    from weather_app.domain.models import HourlySeries, CurrentSnapshot


Value: TypeAlias = float | int | None


class HourlyMode(Enum):
    """Weather metric display modes."""
    TEMPERATURE = "temperature"
    FEELS_LIKE = "feels_like"
    PRECIPITATION = "precip"
    WIND = "wind"
    HUMIDITY = "humidity"


@dataclass(frozen=True)
class ModeMeta:
    """Metadata for a weather metric display mode."""
    tab_label: str
    fmt: Callable[[Value, Units], str]
    icon: Callable[[Value, int | None, bool], str]
    values: Callable[["HourlySeries"], list[Value]]
    current_value: Callable[["CurrentSnapshot"], Value]


def _fmt_temp(v: Value, units: Units) -> str:
    if v is None:
        return "—"
    return f"{round(v)}°C" if units == Units.METRIC else f"{round(v)}°F"


def _fmt_wind(v: Value, units: Units) -> str:
    if v is None:
        return "—"
    return f"{round(v)} km/h" if units == Units.METRIC else f"{round(v)} mph"


def _fmt_percent(v: Value, units: Units) -> str:
    return f"{int(v)}%" if v is not None else "—"


def _icon_temp(v: Value, code: int | None, night: bool) -> str:
    return code_to_label_icon(code or 0, night=night)[1] if code is not None else "unknown.png"


def _icon_precip(v: Value, code: int | None, night: bool) -> str:
    vv = float(v) if v is not None else None
    return pick_icon_by_threshold(vv, PRECIP_ICONS, "precip_unknown.png")


def _icon_wind(v: Value, code: int | None, night: bool) -> str:
    vv = float(v) if v is not None else None
    return pick_icon_by_threshold(vv, WIND_ICONS, "wind_unknown.png")


def _icon_humidity(v: Value, code: int | None, night: bool) -> str:
    vv = float(v) if v is not None else None
    return pick_icon_by_threshold(vv, HUMIDITY_ICONS, "hum_unknown.png")


MODE_META: dict[HourlyMode, ModeMeta] = {
    HourlyMode.TEMPERATURE: ModeMeta(
        tab_label="Temperature",
        fmt=_fmt_temp,
        icon=_icon_temp,
        values=lambda s: s.temp,
        current_value=lambda cur: cur.temp,
    ),
    HourlyMode.FEELS_LIKE: ModeMeta(
        tab_label="Feels like",
        fmt=_fmt_temp,
        icon=_icon_temp,
        values=lambda s: s.feels_like,
        current_value=lambda cur: cur.feels_like,
    ),
    HourlyMode.PRECIPITATION: ModeMeta(
        tab_label="Precipitation",
        fmt=_fmt_percent,
        icon=_icon_precip,
        values=lambda s: s.precip,
        current_value=lambda cur: cur.precip,
    ),
    HourlyMode.WIND: ModeMeta(
        tab_label="Wind",
        fmt=_fmt_wind,
        icon=_icon_wind,
        values=lambda s: s.wind,
        current_value=lambda cur: cur.wind,
    ),
    HourlyMode.HUMIDITY: ModeMeta(
        tab_label="Humidity",
        fmt=_fmt_percent,
        icon=_icon_humidity,
        values=lambda s: s.humidity,
        current_value=lambda cur: cur.humidity,
    ),
}

DEFAULT_MODE = HourlyMode.TEMPERATURE


def get_mode_meta(mode: HourlyMode) -> ModeMeta:
    return MODE_META.get(mode, MODE_META[DEFAULT_MODE])


def format_value(mode: HourlyMode, value: Value, units: Units) -> str:
    return get_mode_meta(mode).fmt(value, units)


def icon_for(mode: HourlyMode, value: Value, code: int | None, *, night: bool = False) -> str:
    return get_mode_meta(mode).icon(value, code, night)