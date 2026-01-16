# weather_app/ui/theme.py
from __future__ import annotations

from dataclasses import dataclass
import wx

from weather_app.domain.settings import Theme


@dataclass(frozen=True)
class ThemePalette:
    # frame-level
    bg: wx.Colour
    topbar: wx.Colour
    topbar_inner: wx.Colour
    current: wx.Colour

    # text
    text_light: wx.Colour      # text ON DARK (topbar, current panel)
    text_primary: wx.Colour    # text on LIGHT surfaces (dialogs, panels)

    # strips
    forecast_strip_bg: wx.Colour
    hourly_strip_bg: wx.Colour

    # cards
    card_selected_bg: wx.Colour
    card_palette: tuple[wx.Colour, ...]

    # hour tiles
    hour_tile_bg: wx.Colour
    hour_tile_text: wx.Colour
    hour_tile_text_muted: wx.Colour

    # dialog + inputs
    dialog_bg: wx.Colour
    input_bg: wx.Colour
    input_text: wx.Colour           # used for TextCtrl / Choice text

LIGHT = ThemePalette(
    bg=wx.Colour(183, 210, 230),
    topbar=wx.Colour(50, 50, 100),
    topbar_inner=wx.Colour(70, 70, 120),
    current=wx.Colour(90, 120, 255),

    text_light=wx.WHITE,                 # on dark blue panels
    text_primary=wx.Colour(25, 25, 25),  # <-- (black-ish)

    forecast_strip_bg=wx.Colour(240, 240, 240),
    hourly_strip_bg=wx.Colour(245, 245, 245),

    card_selected_bg=wx.Colour(80, 110, 180),
    card_palette=(
        wx.Colour(0, 200, 200), wx.Colour(255, 100, 150),
        wx.Colour(255, 180, 50), wx.Colour(100, 200, 255),
        wx.Colour(120, 160, 255), wx.Colour(200, 120, 255),
        wx.Colour(80, 180, 120),
    ),

    hour_tile_bg=wx.Colour(250, 250, 250),
    hour_tile_text=wx.Colour(45, 45, 45),
    hour_tile_text_muted=wx.Colour(70, 70, 70),

    dialog_bg=wx.Colour(250, 250, 250),
    input_bg=wx.WHITE,
    input_text=wx.Colour(25, 25, 25),
)

DARK = ThemePalette(
    bg=wx.Colour(20, 22, 28),
    topbar=wx.Colour(30, 32, 40),
    topbar_inner=wx.Colour(45, 48, 60),
    current=wx.Colour(55, 70, 110),

    text_light=wx.Colour(240, 240, 240),
    text_primary=wx.Colour(240, 240, 240),  # light text on dark dialog

    forecast_strip_bg=wx.Colour(28, 30, 36),
    hourly_strip_bg=wx.Colour(28, 30, 36),

    card_selected_bg=wx.Colour(70, 110, 190),
    card_palette=(
        wx.Colour(40, 140, 140), wx.Colour(160, 80, 110),
        wx.Colour(160, 120, 60), wx.Colour(70, 120, 160),
        wx.Colour(90, 110, 170), wx.Colour(120, 90, 160),
        wx.Colour(60, 120, 90),
    ),

    hour_tile_bg=wx.Colour(34, 36, 44),
    hour_tile_text=wx.Colour(230, 230, 235),
    hour_tile_text_muted=wx.Colour(180, 180, 190),

    dialog_bg=wx.Colour(28, 30, 36),
    input_bg=wx.Colour(45, 48, 60),
    input_text=wx.Colour(240, 240, 240),
)

_PALETTES: dict[Theme, ThemePalette] = {
    Theme.LIGHT: LIGHT,
    Theme.DARK: DARK,
}


def get_palette(theme: Theme) -> ThemePalette:
    """Single source of truth: Theme -> ThemePalette."""
    return _PALETTES.get(theme, LIGHT)


def pick_card_bg(p: ThemePalette, i: int) -> wx.Colour:
    return p.card_palette[i % len(p.card_palette)]
