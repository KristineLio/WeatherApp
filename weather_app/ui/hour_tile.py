import wx
from weather_app.utils.icons import get_icon_bitmap
from weather_app.domain.modes import HourlyMode, icon_for, format_value

# ============================================================================
# UI Component
# ============================================================================

class HourTile(wx.Panel):
    SIZE = (72, 120)

    def __init__(self, parent, time_label: str, mode: HourlyMode, value, code: int | None):
        super().__init__(parent, size=self.SIZE)
        self.SetBackgroundColour(wx.Colour(250, 250, 250))
        self._build_ui()
        self.update_content(time_label=time_label, mode=mode, value=value, code=code)

    def _build_ui(self):
        v = wx.BoxSizer(wx.VERTICAL)

        self.time_lbl = wx.StaticText(self, label="", style=wx.ALIGN_CENTER)
        self.time_lbl.SetFont(wx.Font(10, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        self.time_lbl.SetForegroundColour(wx.Colour(60, 60, 60))

        self.icon = wx.StaticBitmap(self, bitmap=get_icon_bitmap("unknown.png", size=(36, 36)))

        self.value_lbl = wx.StaticText(self, label="", style=wx.ALIGN_CENTER)
        self.value_lbl.SetFont(wx.Font(10, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        self.value_lbl.SetForegroundColour(wx.Colour(60, 60, 60))

        v.Add(self.time_lbl, 0, wx.ALIGN_CENTER | wx.TOP, 6)
        v.Add(self.icon, 0, wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM, 4)
        v.Add(self.value_lbl, 0, wx.ALIGN_CENTER)

        self.SetSizer(v)

    def update_content(self, *, time_label: str, mode: HourlyMode, value, code: int | None):
        self.time_lbl.SetLabel(time_label)

        icon_file = icon_for(mode, value, code)
        self.icon.SetBitmap(get_icon_bitmap(icon_file, size=(36, 36)))

        self.value_lbl.SetLabel(format_value(mode, value))

        # lightweight refresh (no heavy rebuild)
        self.Layout()
        self.Refresh()