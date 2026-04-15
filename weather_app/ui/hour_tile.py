from __future__ import annotations

import wx

from weather_app.utils.icons import get_icon_bitmap
from weather_app.ui.hour_tile_presenter import HourTileViewData


class HourTile(wx.Panel):
    SIZE = (72, 120)

    def __init__(
        self,
        parent: wx.Window,
        *,
        bg_color: wx.Colour | None = None,
        text_color: wx.Colour = wx.Colour(255, 255, 255),
        muted_text_color: wx.Colour = wx.Colour(180, 180, 180),
    ):
        super().__init__(parent, size=self.SIZE)

        if bg_color is not None:
            self.SetBackgroundColour(bg_color)

        self._text_color = text_color
        self._muted_text_color = muted_text_color

        self._build_ui()

    def _build_ui(self) -> None:
        v = wx.BoxSizer(wx.VERTICAL)

        self.time_lbl = wx.StaticText(self, label="", style=wx.ALIGN_CENTER)
        self.time_lbl.SetFont(
            wx.Font(10, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        )
        self.time_lbl.SetForegroundColour(self._muted_text_color)

        self.icon = wx.StaticBitmap(
            self,
            bitmap=get_icon_bitmap("unknown.png", size=(36, 36)),
        )

        self.value_lbl = wx.StaticText(self, label="", style=wx.ALIGN_CENTER)
        self.value_lbl.SetFont(
            wx.Font(10, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        )
        self.value_lbl.SetForegroundColour(self._text_color)

        v.Add(self.time_lbl, 0, wx.ALIGN_CENTER | wx.TOP, 6)
        v.Add(self.icon, 0, wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM, 4)
        v.Add(self.value_lbl, 0, wx.ALIGN_CENTER)

        self.SetSizer(v)

    def apply_view(self, view: HourTileViewData) -> None:
        self.time_lbl.SetLabel(view.time_label)
        self.icon.SetBitmap(get_icon_bitmap(view.icon_file, size=(36, 36)))
        self.value_lbl.SetLabel(view.value_label)

        self.Layout()
        self.Refresh()