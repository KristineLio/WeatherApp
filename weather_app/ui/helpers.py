import wx

def set_label_for_value(
    label: wx.StaticText,
    prefix: str,
    value,
    *,
    fmt=str,
    suffix: str = ""
) -> None:
    if value is None:
        label.SetLabel(f"{prefix}—")
    else:
        label.SetLabel(f"{prefix}{fmt(value)}{suffix}")

