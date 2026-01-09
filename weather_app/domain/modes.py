from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Callable, TYPE_CHECKING
from weather_app.utils.icons import _pick_icon_by_threshold, code_to_label_icon
from weather_app.utils.icons import PRECIP_ICONS, WIND_ICONS, HUMIDITY_ICONS

if TYPE_CHECKING:
    from weather_app.domain.models import HourlySeries, CurrentSnapshot  # only for typing
"""
from enum import Enum
from dataclasses import dataclass
from typing import Callable, TYPE_CHECKING
from weather_app.utils.icons import _pick_icon_by_threshold, code_to_label_icon
from weather_app.domain.models import CurrentSnapshot
from weather_app.utils.icons import PRECIP_ICONS, WIND_ICONS, HUMIDITY_ICONS

if TYPE_CHECKING:
    from weather_app.domain.models import HourlySeries  # only for typing
"""

class HourlyMode(Enum):  #MetricMode
    """Weather metric display modes."""
    TEMPERATURE = "temperature"
    PRECIPITATION = "precip"
    WIND = "wind"
    HUMIDITY = "humidity"


@dataclass(frozen=True)
class ModeMeta:
    """Metadata for a weather metric display mode."""
    key: str
    tab_label: str
    unit: str
    fmt: Callable[[float | None], str]                   # value -> string
    icon: Callable[[float | None, int | None], str]      # (value, code) -> filename
    values: Callable[["HourlySeries"], list[float | None]]  # HourlySeries -> list of values
    current_value: Callable[["CurrentSnapshot"], float | None]  # curSnap-> metric value


def _fmt_temp(v: float | None) -> str:      return f"{round(v)}°C" if v is not None else "—"

def _fmt_percent(v: float | None) -> str:   return f"{int(v)}%" if v is not None else "—"

def _fmt_wind(v: float | None) -> str:      return f"{round(v)} km/h" if v is not None else "—"

def _icon_temp(v: float | None, code: int | None) -> str:   
    return code_to_label_icon(code or 0)[1] if code is not None else "unknown.png"

def _icon_precip(v: float | None, code: int | None) -> str:
    return _pick_icon_by_threshold(v, PRECIP_ICONS, "precip_unknown.png")

def _icon_wind(v: float | None, code: int | None) -> str:
    return _pick_icon_by_threshold(v, WIND_ICONS, "wind_unknown.png")

def _icon_humidity(v: float | None, code: int | None) -> str:
    return _pick_icon_by_threshold(v, HUMIDITY_ICONS, "hum_unknown.png")


MODE_META: dict[HourlyMode, ModeMeta] = {
    HourlyMode.TEMPERATURE: ModeMeta(
        key="temperature",
        tab_label="Temperature",
        unit="°C",
        fmt=_fmt_temp,
        icon=_icon_temp,
        values=lambda s: s.temp,
        current_value=lambda cur: cur.temp,
    ),
    HourlyMode.PRECIPITATION: ModeMeta(
        key="precip",
        tab_label="Precipitation",
        unit="%",
        fmt=_fmt_percent,
        icon=_icon_precip,
        values=lambda s: s.precip,
        current_value=lambda cur: cur.precip,
    ),
    HourlyMode.WIND: ModeMeta(
        key="wind",
        tab_label="Wind",
        unit="km/h",
        fmt=_fmt_wind,
        icon=_icon_wind,
        values=lambda s: s.wind,
        current_value=lambda cur: cur.wind,
    ),
    HourlyMode.HUMIDITY: ModeMeta(
        key="humidity",
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
    """Get metadata for a given metric mode."""
    return MODE_META.get(mode, MODE_META[DEFAULT_MODE])


def format_value(mode: HourlyMode, value: float | None) -> str:
    """Format a value according to its mode."""
    return get_mode_meta(mode).fmt(value)


def icon_for(mode: HourlyMode, value: float | None, code: int | None) -> str:
    """Get icon filename for a value in a given mode."""
    return get_mode_meta(mode).icon(value, code)


