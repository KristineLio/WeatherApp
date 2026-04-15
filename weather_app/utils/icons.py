# weather_app/utils/icons.py
from __future__ import annotations

import os

import wx
import wx.adv

from weather_app.utils.paths import PNG_DIR, GIF_DIR  

_ICON_CACHE: dict[tuple[str, tuple[int, int] | None], wx.Bitmap] = {}
_ANIM_CACHE: dict[str, wx.adv.Animation] = {}


def clear_icon_cache() -> None:
    _ICON_CACHE.clear()
    _ANIM_CACHE.clear()


def _png_path(filename: str) -> str:
    return os.fspath(PNG_DIR / filename)


def _gif_path(filename: str) -> str:
    return os.fspath(GIF_DIR / filename)

# ============================================================================
# Icon Cache
# ============================================================================

def get_icon_bitmap(filename: str, size: tuple[int, int] | None = None) -> wx.Bitmap:
    """
    Load and cache bitmap icons.
    
    Args:
        filename: Icon filename (e.g. 'clear.png') inside ASSETS_DIR
        size: Optional (width, height) tuple for resizing
    
    Returns:
        wx.Bitmap object (cached for performance)
    """
    full_path = _png_path(filename)
    if not os.path.exists(full_path):
        full_path = _png_path("unknown.png")

    key = (full_path, size)
    bmp = _ICON_CACHE.get(key)
    if bmp is not None:
        return bmp

    if size is None:
        bmp = wx.Bitmap(full_path, wx.BITMAP_TYPE_PNG)
    else:
        img = wx.Image(full_path, wx.BITMAP_TYPE_PNG)
        img = img.Rescale(size[0], size[1], wx.IMAGE_QUALITY_HIGH)
        bmp = wx.Bitmap(img)

    _ICON_CACHE[key] = bmp
    return bmp


# ============================================================================
# Animated Icon Cache
# ============================================================================

def get_anim(filename: str) -> wx.adv.Animation:
    full_path = _gif_path(filename)
    if not os.path.exists(full_path):
        full_path = _gif_path("unknown.gif")

    anim = _ANIM_CACHE.get(full_path)
    if anim is not None:
        return anim

    anim = wx.adv.Animation(full_path)
    _ANIM_CACHE[full_path] = anim
    return anim


def icon_for_current_static(panel: wx.Window, icon_file: str) -> wx.Control:
    return wx.StaticBitmap(panel, bitmap=get_icon_bitmap(icon_file, size=(60, 60)))

def icon_for_current_animated(panel: wx.Window, gif_file: str) -> wx.Control:
    ctrl = wx.adv.AnimationCtrl(panel)
    ctrl.SetAnimation(get_anim(gif_file))
    ctrl.Play()
    return ctrl