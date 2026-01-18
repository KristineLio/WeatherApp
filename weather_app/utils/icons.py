import wx
import os
import wx.adv
from weather_app.utils.paths import ASSETS_DIR
from typing import Iterable, Tuple, TypeAlias

Value: TypeAlias = float | int | None
IconTable: TypeAlias = Iterable[Tuple[float, str]]

# ============================================================================
# Weather Code Mappings
# ============================================================================

WEATHERCODE_MAP = {
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
HUMIDITY_ICONS = [
    (30, "hum_dry.png"),      # < 30%
    (60, "hum_ok.png"),       # 30–59%
    (80, "hum_humid.png"),    # 60–79%
    (101, "hum_muggy.png"),   # 80–100%
]

PRECIP_ICONS = [
    (20, "precip_low.png"),
    (50, "precip_med.png"),
    (80, "precip_high.png"),
    (101, "precip_storm.png"),
]

WIND_ICONS = [
    (10, "wind_calm.png"),     # <10 km/h
    (25, "wind_breeze.png"),
    (40, "wind_windy.png"),
    (70, "wind_strong.png"),
    (1000, "wind_gale.png"),
]


# ============================================================================
# Icon Cache
# ============================================================================
_ICON_CACHE: dict[tuple[str, tuple[int, int] | None], wx.Bitmap] = {}

def clear_icon_cache() -> None:
    _ICON_CACHE.clear()

def get_icon_bitmap(filename: str, size=None) -> wx.Bitmap:
    """
    Load and cache bitmap icons.
    
    Args:
        filename: Icon filename (e.g. 'clear.png') inside ASSETS_DIR
        size: Optional (width, height) tuple for resizing
    
    Returns:
        wx.Bitmap object (cached for performance)
    """
    full_path = os.path.join(ASSETS_DIR, filename)
    if not os.path.exists(full_path):
        full_path = os.path.join(ASSETS_DIR, "unknown.png") # fallback

    key = (full_path, size)
    if key in _ICON_CACHE:
        return _ICON_CACHE[key]

    if size is None:
        bmp = wx.Bitmap(full_path, wx.BITMAP_TYPE_PNG)
    else:
        img = wx.Image(full_path, wx.BITMAP_TYPE_PNG)
        img = img.Rescale(size[0], size[1], wx.IMAGE_QUALITY_HIGH)
        bmp = wx.Bitmap(img)

    _ICON_CACHE[key] = bmp
    return bmp

def code_to_label_icon(code: int, *, night: bool = False):
    label, icon = WEATHERCODE_MAP.get(int(code), ("Weather", "unknown.png"))

    if night:
        base, ext = icon.rsplit(".", 1)
        night_icon = f"{base}_night.{ext}"
        return label, night_icon

    return label, icon


def pick_icon_by_threshold(
        value: Value,
        table: IconTable,
        fallback: str = "unknown.png",
    ) -> str:
        """Pick icon based on numeric value thresholds."""
        if value is None:
            return fallback

        try:
            v = float(value)
        except (TypeError, ValueError):
            return fallback

        for upper, icon in table:
            if v < upper:
                return icon

        return fallback


# ============================================================================
# Animated Icon Cache
# ============================================================================
_ANIM_CACHE: dict[str, wx.adv.Animation] = {}

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

    if night:
        return base.replace(".gif", "_night.gif")

    return base

def get_anim(filename: str) -> wx.adv.Animation:
    full_path = os.path.join(ASSETS_DIR, filename)
    if not os.path.exists(full_path):
        full_path = os.path.join(ASSETS_DIR, "unknown.gif")  # optional fallback
    if full_path in _ANIM_CACHE:
        return _ANIM_CACHE[full_path]
    anim = wx.adv.Animation(full_path)
    _ANIM_CACHE[full_path] = anim
    return anim

def icon_for_current_static(panel: wx.Window, icon_file: str) -> wx.Control:
    # matches what you already do: StaticBitmap
    return wx.StaticBitmap(panel, bitmap=get_icon_bitmap(icon_file, size=(60, 60)))

def icon_for_current_animated(panel: wx.Window, gif_file: str) -> wx.Control:
    ctrl = wx.adv.AnimationCtrl(panel)
    ctrl.SetAnimation(get_anim(gif_file))
    ctrl.Play()
    return ctrl