import wx

from weather_app.utils.icons import get_icon_bitmap
from weather_app.ui.weather_card_presenter import ForecastCardViewData


class WeatherCard(wx.Panel):
    """Forecast card for daily weather summary."""
    SIZE = (120, 160)

    def __init__(
        self,
        parent,
        *,
        bg_color: wx.Colour,
        date_iso: str,
        on_click,
        is_selected: bool = False,
        selected_bg: wx.Colour | None = None,
    ):
        super().__init__(parent, size=self.SIZE)

        self.date_iso = date_iso
        self.on_click = on_click

        self.base_bg = bg_color
        self.selected_bg = selected_bg or wx.Colour(80, 110, 180)
        self.is_selected = None

        self._build_ui()
        self._bind_click_recursive(self)
        self.set_selected(is_selected)

    def _build_ui(self) -> None:
        vbox = wx.BoxSizer(wx.VERTICAL)

        self.day_text = wx.StaticText(self, label="", style=wx.ALIGN_CENTER)
        self.day_text.SetForegroundColour(wx.WHITE)
        self.day_text.SetFont(
            wx.Font(12, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        )

        self.icon = wx.StaticBitmap(
            self,
            bitmap=get_icon_bitmap("unknown.png", size=(48, 48)),
        )

        self.temps_panel = wx.Panel(self)
        temps_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.max_text = wx.StaticText(self.temps_panel, label="—")
        self.max_text.SetFont(
            wx.Font(12, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        )
        self.max_text.SetForegroundColour(wx.WHITE)

        self.min_text = wx.StaticText(self.temps_panel, label="/—")
        self.min_text.SetFont(
            wx.Font(12, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        )
        self.min_text.SetForegroundColour(wx.Colour(220, 230, 255))

        temps_sizer.Add(self.max_text, 0, wx.RIGHT, 1)
        temps_sizer.Add(self.min_text, 0)

        self.temps_panel.SetSizer(temps_sizer)

        vbox.AddStretchSpacer()
        vbox.Add(self.day_text, 0, wx.ALIGN_CENTER)
        vbox.Add(self.icon, 0, wx.ALIGN_CENTER | wx.TOP, 5)
        vbox.Add(self.temps_panel, 0, wx.ALIGN_CENTER | wx.TOP, 5)
        vbox.AddStretchSpacer()

        self.SetSizer(vbox)

    def apply_view(self, view: ForecastCardViewData) -> None:
        self.date_iso = view.date_iso
        self.day_text.SetLabel(view.day_label)
        self.max_text.SetLabel(view.tmax_text)
        self.min_text.SetLabel(f"/{view.tmin_text}")
        self.icon.SetBitmap(get_icon_bitmap(view.icon_file, size=(48, 48)))
        self.set_selected(view.selected)

        self.Layout()
        self.Refresh()

    def _bind_click_recursive(self, window: wx.Window) -> None:
        window.Bind(wx.EVT_LEFT_UP, self._handle_click)
        for child in window.GetChildren():
            self._bind_click_recursive(child)

    def _handle_click(self, event) -> None:
        if callable(self.on_click):
            self.on_click(self.date_iso)
        event.Skip()

    def set_selected(self, selected: bool) -> None:
        if self.is_selected == selected:
            return

        self.is_selected = selected
        bg = self.selected_bg if selected else self.base_bg

        self.SetBackgroundColour(bg)
        self.temps_panel.SetBackgroundColour(bg)

        for child in self.GetChildren():
            if isinstance(child, wx.Panel):
                child.SetBackgroundColour(bg)

        self.Refresh()

    def refresh_theme(self) -> None:
        bg = self.selected_bg if self.is_selected else self.base_bg
        self.SetBackgroundColour(bg)
        self.temps_panel.SetBackgroundColour(bg)

        for child in self.GetChildren():
            if isinstance(child, wx.Panel):
                child.SetBackgroundColour(bg)

        self.Refresh()