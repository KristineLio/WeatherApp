from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, TYPE_CHECKING, TypeAlias

from weather_app.utils.icons import (
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
    PRECIPITATION = "precip"
    WIND = "wind"
    HUMIDITY = "humidity"


@dataclass(frozen=True)
class ModeMeta:
    """Metadata for a weather metric display mode."""
    tab_label: str
    fmt: Callable[[Value, Units], str]                     # (value, units) -> string (incl. unit)
    icon: Callable[[Value, int | None], str]               # (value, code) -> filename
    values: Callable[["HourlySeries"], list[Value]]        # HourlySeries -> list of values
    current_value: Callable[["CurrentSnapshot"], Value]    # CurrentSnapshot -> metric value


# ----------------------------
# Formatters (return FULL string)
# ----------------------------
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


# ----------------------------
# Icons (unchanged behavior)
# ----------------------------
def _icon_temp(v: Value, code: int | None) -> str:
    return code_to_label_icon(code or 0)[1] if code is not None else "unknown.png"


def _icon_precip(v: Value, code: int | None) -> str:
    vv = float(v) if v is not None else None
    return pick_icon_by_threshold(vv, PRECIP_ICONS, "precip_unknown.png")


def _icon_wind(v: Value, code: int | None) -> str:
    vv = float(v) if v is not None else None
    return pick_icon_by_threshold(vv, WIND_ICONS, "wind_unknown.png")


def _icon_humidity(v: Value, code: int | None) -> str:
    vv = float(v) if v is not None else None
    return pick_icon_by_threshold(vv, HUMIDITY_ICONS, "hum_unknown.png")


# ----------------------------
# MODE_META table
# ----------------------------
MODE_META: dict[HourlyMode, ModeMeta] = {
    HourlyMode.TEMPERATURE: ModeMeta(
        tab_label="Temperature",
        fmt=_fmt_temp,
        icon=_icon_temp,
        values=lambda s: s.temp,
        current_value=lambda cur: cur.temp,
    ),
    HourlyMode.PRECIPITATION: ModeMeta(
        tab_label="Precipitation",
        fmt=_fmt_percent,  # returns "34%"
        icon=_icon_precip,
        values=lambda s: s.precip,
        current_value=lambda cur: cur.precip,
    ),
    HourlyMode.WIND: ModeMeta(
        tab_label="Wind",
        fmt=_fmt_wind,     # returns "12 km/h" or "8 mph"
        icon=_icon_wind,
        values=lambda s: s.wind,
        current_value=lambda cur: cur.wind,
    ),
    HourlyMode.HUMIDITY: ModeMeta(
        tab_label="Humidity",
        fmt=_fmt_percent,  # returns "51%"
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


def icon_for(mode: HourlyMode, value: Value, code: int | None) -> str:
    return get_mode_meta(mode).icon(value, code)





