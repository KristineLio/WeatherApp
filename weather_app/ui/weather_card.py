import wx
from weather_app.utils.icons import get_icon_bitmap

# ============================================================================
# UI Component
# ============================================================================

class WeatherCard(wx.Panel):
    """Forecast card for daily weather summary."""
    SIZE = (120, 160)

    def __init__(
        self,
        parent,
        day: str,
        tmax_text: str,
        tmin_text: str,
        icon_file: str,
        bg_color: wx.Colour,
        date_iso: str,
        on_click,
        is_selected: bool = False,
        selected_bg: wx.Colour | None = None
    ):
        super().__init__(parent, size=self.SIZE)

        self.date_iso = date_iso
        self.on_click = on_click

        self.base_bg = bg_color
        self.selected_bg = selected_bg or wx.Colour(80, 110, 180) 
        self.is_selected = None  # will be set by set_selected()

        # --- build UI ---
        self._build_ui(day, tmax_text, tmin_text, icon_file)

        # --- interactions ---
        self._bind_click_recursive(self)

        # --- initial visual state ---
        self.set_selected(is_selected)

    def _build_ui(self, day: str, tmax_text: str, tmin_text: str, icon_file: str):
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Title (weekday)
        self.day_text = wx.StaticText(self, label=day, style=wx.ALIGN_CENTER)
        self.day_text.SetForegroundColour(wx.WHITE)
        self.day_text.SetFont(wx.Font(12, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))

        # Icon
        self.icon = wx.StaticBitmap(self, bitmap=get_icon_bitmap(icon_file, size=(48, 48)))

        # Temps line (you don't actually need an inner Panel, but keep it so bg is guaranteed)
        self.temps_panel = wx.Panel(self)
        temps_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.max_text = wx.StaticText(self.temps_panel, label=tmax_text)
        self.max_text.SetFont(wx.Font(12, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        self.max_text.SetForegroundColour(wx.WHITE)

        self.min_text = wx.StaticText(self.temps_panel, label=f"/{tmin_text}")
        self.min_text.SetFont(wx.Font(12, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        self.min_text.SetForegroundColour(wx.Colour(220, 230, 255))

        temps_sizer.Add(self.max_text, 0, wx.RIGHT, 1)
        temps_sizer.Add(self.min_text, 0,)

        self.temps_panel.SetSizer(temps_sizer)

        vbox.AddStretchSpacer()
        vbox.Add(self.day_text, 0, wx.ALIGN_CENTER)
        vbox.Add(self.icon, 0, wx.ALIGN_CENTER | wx.TOP, 5)
        vbox.Add(self.temps_panel, 0, wx.ALIGN_CENTER | wx.TOP, 5)
        vbox.AddStretchSpacer()

        self.SetSizer(vbox)

    def update_content(self, *, day=None, tmax_text=None, tmin_text=None, icon_file=None):
        """Optional helper to reuse cards instead of destroying them."""
        if day is not None:
            self.day_text.SetLabel(day)
        if tmax_text is not None:
            self.max_text.SetLabel(tmax_text)
        if tmin_text is not None:
            self.min_text.SetLabel(f"/{tmin_text}")
        if icon_file is not None:
            self.icon.SetBitmap(get_icon_bitmap(icon_file, size=(48, 48)))
        self.Layout()
        self.Refresh()
    
    def _bind_click_recursive(self, window: wx.Window):
        window.Bind(wx.EVT_LEFT_UP, self._handle_click)
        for child in window.GetChildren():
            self._bind_click_recursive(child)

    def _handle_click(self, event):
        if callable(self.on_click):
            self.on_click(self.date_iso)
        event.Skip()
    
    def set_selected(self, selected: bool):
        if self.is_selected == selected:
            return  # avoids extra Refresh noise

        self.is_selected = selected
        bg = self.selected_bg if selected else self.base_bg

        self.SetBackgroundColour(bg)
        self.temps_panel.SetBackgroundColour(bg)

        # if you later add more inner panels, this keeps them consistent
        for child in self.GetChildren():
            if isinstance(child, wx.Panel):
                child.SetBackgroundColour(bg)

        self.Refresh()

