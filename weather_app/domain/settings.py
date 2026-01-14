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
        )
