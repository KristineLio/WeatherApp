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
    unit: str
    fmt: Callable[[Value], str]                              # value -> string
    icon: Callable[[Value, int | None], str]                 # (value, code) -> filename
    values: Callable[["HourlySeries"], list[Value]]          # HourlySeries -> list of values
    current_value: Callable[["CurrentSnapshot"], Value]      # CurrentSnapshot -> metric value


def _fmt_temp(v: Value) -> str:
    return f"{round(float(v))}°C" if v is not None else "—"


def _fmt_percent(v: Value) -> str:
    return f"{int(v)}%" if v is not None else "—"


def _fmt_wind(v: Value) -> str:
    return f"{round(float(v))} km/h" if v is not None else "—"


def _icon_temp(v: Value, code: int | None) -> str:
    return code_to_label_icon(code or 0)[1] if code is not None else "unknown.png"


def _icon_precip(v: Value, code: int | None) -> str:
    # v may be int|float|None; threshold picker should accept float|None
    vv = float(v) if v is not None else None
    return pick_icon_by_threshold(vv, PRECIP_ICONS, "precip_unknown.png")


def _icon_wind(v: Value, code: int | None) -> str:
    vv = float(v) if v is not None else None
    return pick_icon_by_threshold(vv, WIND_ICONS, "wind_unknown.png")


def _icon_humidity(v: Value, code: int | None) -> str:
    vv = float(v) if v is not None else None
    return pick_icon_by_threshold(vv, HUMIDITY_ICONS, "hum_unknown.png")


MODE_META: dict[HourlyMode, ModeMeta] = {
    HourlyMode.TEMPERATURE: ModeMeta(
        tab_label="Temperature",
        unit="°C",
        fmt=_fmt_temp,
        icon=_icon_temp,
        values=lambda s: s.temp,
        current_value=lambda cur: cur.temp,
    ),
    HourlyMode.PRECIPITATION: ModeMeta(
        tab_label="Precipitation",
        unit="%",
        fmt=_fmt_percent,
        icon=_icon_precip,
        values=lambda s: s.precip,
        current_value=lambda cur: cur.precip,
    ),
    HourlyMode.WIND: ModeMeta(
        tab_label="Wind",
        unit="km/h",
        fmt=_fmt_wind,
        icon=_icon_wind,
        values=lambda s: s.wind,
        current_value=lambda cur: cur.wind,
    ),
    HourlyMode.HUMIDITY: ModeMeta(
        tab_label="Humidity",
        unit="%",
        fmt=_fmt_percent,
        icon=_icon_humidity,
        values=lambda s: s.humidity,
        current_value=lambda cur: cur.humidity,
    ),
}

DEFAULT_MODE = HourlyMode.TEMPERATURE


def get_mode_meta(mode: HourlyMode) -> ModeMeta:
    return MODE_META.get(mode, MODE_META[DEFAULT_MODE])


def format_value(mode: HourlyMode, value: Value) -> str:
    return get_mode_meta(mode).fmt(value)


def icon_for(mode: HourlyMode, value: Value, code: int | None) -> str:
    return get_mode_meta(mode).icon(value, code)
