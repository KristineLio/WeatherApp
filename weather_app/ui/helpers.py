from __future__ import annotations

import wx
from typing import Callable, TypeAlias

# Metric values used across the UI
Value: TypeAlias = float | int | None
Formatter: TypeAlias = Callable[[Value], str]


def set_label_for_value(
    label: wx.StaticText,
    prefix: str,
    value: Value,
    *,
    fmt: Formatter = str,
    suffix: str = "",
    none_text: str = "—",
) -> None:
    """
    Safely set a wx.StaticText label for an optional metric value.

    - value=None → shows prefix + none_text
    - value!=None → shows prefix + fmt(value) + suffix
    """
    if value is None:
        label.SetLabel(f"{prefix}{none_text}")
    else:
        label.SetLabel(f"{prefix}{fmt(value)}{suffix}")