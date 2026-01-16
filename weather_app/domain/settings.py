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

        return cls(
            default_city=str(data.get("default_city") or "Sofia"),
            last_city=str(data.get("last_city") or data.get("default_city") or "Sofia"),
            units=Units(str(data.get("units") or Units.METRIC.value)),
            theme=Theme(str(data.get("theme") or Theme.LIGHT.value)),
            location_prompted=bool(data.get("location_prompted", False)),
            use_detected_on_start=bool(data.get("use_detected_on_start", False)),
            ask_detected_on_start=bool(data.get("ask_detected_on_start", True)),
        )
