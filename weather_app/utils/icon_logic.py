# weather_app/utils/icon_logic.py
from __future__ import annotations

from typing import Iterable, Tuple, TypeAlias

Value: TypeAlias = float | int | None
IconTable: TypeAlias = Iterable[Tuple[float, str]]

# ============================================================================
# Weather Code Mappings
# ============================================================================

WEATHERCODE_MAP: dict[int, tuple[str, str]] = {
    # open-meteo weather codes → (label, suggested icon filename in assets folder)
    0: ("Clear sky", "clear.png"),
    1: ("Mainly clear", "partly.png"),
    2: ("Partly cloudy", "partly.png"),
    3: ("Overcast", "cloudy.png"),
    45: ("Fog", "fog.png"),
    48: ("Depositing rime fog", "fog.png"),
    51: ("Light drizzle", "drizzle.png"),
    53: ("Drizzle", "drizzle.png"),
    55: ("Heavy drizzle", "drizzle.png"),
    61: ("Light rain", "rain.png"),
    63: ("Rain", "rain.png"),
    65: ("Heavy rain", "rain.png"),
    71: ("Light snow", "snow.png"),
    73: ("Snow", "snow.png"),
    75: ("Heavy snow", "snow.png"),
    80: ("Rain showers", "showers.png"),
    81: ("Heavy showers", "showers.png"),
    82: ("Violent showers", "showers.png"),
    95: ("Thunderstorm", "storm.png"),
    96: ("Thunders. w/ hail", "storm.png"),
    99: ("Thunders. w/ hail", "storm.png"),
}

HUMIDITY_ICONS: list[tuple[float, str]] = [
    (30, "hum_dry.png"),    # < 30%
    (60, "hum_ok.png"),     # 30–59%
    (80, "hum_humid.png"),  # 60–79%
    (101, "hum_muggy.png"), # 80–100%
]

PRECIP_ICONS: list[tuple[float, str]] = [
    (20, "precip_low.png"),
    (50, "precip_med.png"),
    (80, "precip_high.png"),
    (101, "precip_storm.png"),
]

WIND_ICONS: list[tuple[float, str]] = [
    (10, "wind_calm.png"),      # <10 km/h
    (25, "wind_breeze.png"),
    (40, "wind_windy.png"),
    (70, "wind_strong.png"),
    (1000, "wind_gale.png"),
]


def code_to_label_icon(code: int, *, night: bool = False) -> tuple[str, str]:
    label, icon = WEATHERCODE_MAP.get(int(code), ("Weather", "unknown.png"))
    if night:
        base, ext = icon.rsplit(".", 1)
        return label, f"{base}_night.{ext}"
    return label, icon


def pick_icon_by_threshold(value: Value, table: IconTable, fallback: str = "unknown.png") -> str:
    if value is None:
        return fallback
    try:
        v = float(value)
    except (TypeError, ValueError):
        return fallback

    for upper, icon in table:
        if v < float(upper):
            return icon
    return fallback


def code_to_gif(code: int | None, *, night: bool = False) -> str:
    """
    Map Open-Meteo weather code -> animated GIF filename.

    Used ONLY for the current panel (optional animation).
    Hourly + forecast icons remain static PNGs.
    """
    if code is None:
        return "unknown.gif"

    base = {
        0: "clear.gif",
        1: "partly.gif",
        2: "partly.gif",
        3: "cloudy.gif",
        45: "fog.gif",
        48: "fog.gif",
        51: "drizzle.gif",
        53: "drizzle.gif",
        55: "drizzle.gif",
        61: "rain.gif",
        63: "rain.gif",
        65: "rain.gif",
        71: "snow.gif",
        73: "snow.gif",
        75: "snow.gif",
        95: "storm.gif",
        96: "storm.gif",
        99: "storm.gif",
    }.get(int(code), "unknown.gif")


    return base.replace(".gif", "_night.gif") if night else base