from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum


class Units(str, Enum):
    METRIC = "metric"       # °C, km/h
    IMPERIAL = "imperial"   # °F, mph


class Theme(str, Enum):
    LIGHT = "light"
    DARK = "dark"


@dataclass
class Settings:
    default_city: str = "Sofia"
    last_city: str = "Sofia"
    units: Units = Units.METRIC
    theme: Theme = Theme.LIGHT

    forecast_days: int = 7
    animated_current_icon: bool = False

    location_prompted: bool = False
    use_detected_on_start: bool = False
    ask_detected_on_start: bool = True

    def to_dict(self) -> dict:
        d = asdict(self)
        d["units"] = self.units.value
        d["theme"] = self.theme.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Settings":
        if not isinstance(data, dict):
            return cls()
        
        # --- resilient city parsing ---
        raw_default_city = str(data.get("default_city") or "").strip()
        default_city = raw_default_city or "Sofia"

        raw_last_city = str(data.get("last_city") or "").strip()
        last_city = raw_last_city or default_city

        # --- resilient enum parsing ---
        raw_units = str(data.get("units") or Units.METRIC.value)
        try:
            units = Units(raw_units)
        except ValueError:
            units = Units.METRIC

        raw_theme = str(data.get("theme") or Theme.LIGHT.value)
        try:
            theme = Theme(raw_theme)
        except ValueError:
            theme = Theme.LIGHT
        
        # --- resilient forecast_days parsing ---
        raw_days = data.get("forecast_days", 7)

        try:
            forecast_days = int(raw_days)
        except (TypeError, ValueError):
            forecast_days = 7

        # clamp to allowed range 3–14
        forecast_days = max(3, min(14, forecast_days))

        return cls(
            default_city=default_city,
            last_city=last_city,
            units=units,
            theme=theme,
            forecast_days=forecast_days,
            animated_current_icon=bool(data.get("animated_current_icon", False)),
            location_prompted=bool(data.get("location_prompted", False)),
            use_detected_on_start=bool(data.get("use_detected_on_start", False)),
            ask_detected_on_start=bool(data.get("ask_detected_on_start", True)),
        )
   