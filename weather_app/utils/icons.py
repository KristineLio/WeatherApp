import wx
import os
from weather_app.utils.paths import ASSETS_DIR

# ============================================================================
# Weather Code Mappings
# ============================================================================

WEATHERCODE_MAP = {
    # open-meteo weather codes → (label, suggested icon filename in your assets folder)
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


def code_to_label_icon(code: int):
    """Map weather code to (label, icon_filename)."""
    return WEATHERCODE_MAP.get(int(code), ("Weather", "unknown.png"))


def _pick_icon_by_threshold(value, table, fallback="unknown.png"):
    """Pick icon based on value thresholds."""
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

