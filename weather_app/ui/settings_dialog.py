from __future__ import annotations

import wx

from weather_app.domain.settings import Settings, Units, Theme
from weather_app.services.storage import StorageRepo
from weather_app.ui.saved_places_panels import ExpandRow, FavoritesPanel, HistoryPanel
from weather_app.ui.theme import get_palette


class SettingsDialog(wx.Dialog):
    def __init__(
        self,
        parent: wx.Window,
        settings: Settings,
        *,
        repo: StorageRepo | None = None,
        on_load_city=None,
        on_favorites_changed=None,
        on_apply_settings=None,
        on_close_dialog=None,
    ):
        super().__init__(
            parent,
            title="Settings",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self._original = settings
        self.repo = repo
        self.on_load_city = on_load_city
        self.on_favorites_changed = on_favorites_changed
        self.on_apply_settings = on_apply_settings
        self.on_close_dialog = on_close_dialog
        self.palette = get_palette(settings.theme)

        self.favorites_panel: FavoritesPanel | None = None
        self.history_panel: HistoryPanel | None = None
        self._closing = False

        root = wx.BoxSizer(wx.VERTICAL)

        
        self.general_box = wx.StaticBox(self, label="General")
        general_box = wx.StaticBoxSizer(self.general_box, wx.VERTICAL)

        form = wx.FlexGridSizer(rows=0, cols=2, vgap=10, hgap=12)
        form.AddGrowableCol(1, 1)

        self.lbl_default = wx.StaticText(self, label="Default city:")
        self.default_city = wx.TextCtrl(self, value=settings.default_city)

        self.lbl_units = wx.StaticText(self, label="Units:")
        self.units = wx.Choice(self, choices=["Metric (°C, km/h)", "Imperial (°F, mph)"])
        self.units.SetSelection(0 if settings.units == Units.METRIC else 1)

        self.lbl_theme = wx.StaticText(self, label="Theme:")
        self.theme = wx.Choice(self, choices=["Light", "Dark"])
        self.theme.SetSelection(0 if settings.theme == Theme.LIGHT else 1)

        self.lbl_forecast_days = wx.StaticText(self, label="Forecast days:")
        self.forecast_days = wx.SpinCtrl(
            self,
            min=3,
            max=14,
            initial=getattr(settings, "forecast_days", 7),
        )

        self.chk_animated_current = wx.CheckBox(self, label="Animate current weather icon (GIF)")
        self.chk_animated_current.SetValue(bool(getattr(settings, "animated_current_icon", False)))

        self.chk_use_detected = wx.CheckBox(self, label="Use detected city on startup")
        self.chk_use_detected.SetValue(bool(settings.use_detected_on_start))

        self.chk_ask_detected = wx.CheckBox(self, label="Ask about location on startup")
        self.chk_ask_detected.SetValue(bool(getattr(settings, "ask_detected_on_start", True)))

        if self.chk_use_detected.GetValue():
            self.chk_ask_detected.SetValue(False)
            self.chk_ask_detected.Disable()

        self.chk_use_detected.Bind(wx.EVT_CHECKBOX, self._on_toggle_use_detected)
        self.theme.Bind(wx.EVT_CHOICE, self._on_theme_changed)

        form.Add(self.lbl_default, 0, wx.ALIGN_CENTER_VERTICAL)
        form.Add(self.default_city, 1, wx.EXPAND)

        form.Add(self.lbl_units, 0, wx.ALIGN_CENTER_VERTICAL)
        form.Add(self.units, 1, wx.EXPAND)

        form.Add(self.lbl_theme, 0, wx.ALIGN_CENTER_VERTICAL)
        form.Add(self.theme, 1, wx.EXPAND)

        form.Add(self.lbl_forecast_days, 0, wx.ALIGN_CENTER_VERTICAL)
        form.Add(self.forecast_days, 1, wx.EXPAND)

        general_box.Add(form, 0, wx.EXPAND | wx.ALL, 12)
        general_box.Add(self.chk_animated_current, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        general_box.Add(self.chk_use_detected, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        general_box.Add(self.chk_ask_detected, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        root.Add(general_box, 0, wx.EXPAND | wx.ALL, 12)

        #saved places  
        if self.repo is not None:
            self.saved_box = wx.StaticBox(self, label="Saved places")
            saved_box = wx.StaticBoxSizer(self.saved_box, wx.VERTICAL)

            self.row_favorites = ExpandRow(
                self,
                title="Favorites",
                subtitle="Saved cities you starred",
                theme=settings.theme,
                on_toggle=self._toggle_favorites_panel,
            )
            saved_box.Add(self.row_favorites, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 8)

            self.favorites_panel = FavoritesPanel(
                self,
                repo=self.repo,
                theme=settings.theme,
                on_load_city=self._on_saved_place_load,
                on_changed=self.on_favorites_changed,
            )
            self.favorites_panel.Hide()
            saved_box.Add(self.favorites_panel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

            saved_box.Add(wx.StaticLine(self), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

            self.row_history = ExpandRow(
                self,
                title="Search history (last 20)",
                subtitle="Recently searched places",
                theme=settings.theme,
                on_toggle=self._toggle_history_panel,
            )
            saved_box.Add(self.row_history, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 8)

            self.history_panel = HistoryPanel(
                self,
                repo=self.repo,
                theme=settings.theme,
                on_load_city=self._on_saved_place_load,
                on_changed=None,
            )
            self.history_panel.Hide()
            saved_box.Add(self.history_panel, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

            root.Add(saved_box, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        
        btn_row = wx.BoxSizer(wx.HORIZONTAL)

        self.reset_btn = wx.Button(self, label="Reset")
        self.reset_btn.Bind(wx.EVT_BUTTON, self._on_reset)

        btn_row.Add(self.reset_btn, 0, wx.RIGHT, 8)
        btn_row.AddStretchSpacer(1)

        self.ok_btn = wx.Button(self, wx.ID_OK, label="Save")
        self.cancel_btn = wx.Button(self, wx.ID_CANCEL, label="Close")

        self.ok_btn.Bind(wx.EVT_BUTTON, self._on_save)
        self.cancel_btn.Bind(wx.EVT_BUTTON, self._on_close)

        btn_sizer = wx.StdDialogButtonSizer()
        btn_sizer.AddButton(self.ok_btn)
        btn_sizer.AddButton(self.cancel_btn)
        btn_sizer.Realize()

        btn_row.Add(btn_sizer, 0)
        root.Add(btn_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        self.SetSizer(root)

        self.SetMinSize((760, 700))
        self.SetInitialSize((460, 650))

        self._apply_theme()

        self.Bind(wx.EVT_CLOSE, self._on_close)

        self.default_city.SetFocus()
        self.default_city.SetInsertionPointEnd()

   
    def _relayout(self) -> None:
        self.Layout()
        self.Refresh()
        self.Update()

   
    def _on_saved_place_load(self, city: str) -> None:
        city = (city or "").strip()
        if not city:
            return

        if callable(self.on_load_city):
            self.on_load_city(city)

        self.Close()

    # Toggle panels (favorites/history) - ensure only one is open at a time
    def _toggle_favorites_panel(self, expanded: bool) -> None:
        if not self.favorites_panel:
            return

        if expanded:
            self.favorites_panel.refresh_data()
            self.favorites_panel.Show()

            if hasattr(self, "row_history") and self.row_history.expanded:
                self.row_history.set_expanded(False)
            if self.history_panel and self.history_panel.IsShown():
                self.history_panel.Hide()
        else:
            self.favorites_panel.Hide()

        self._relayout()

    def _toggle_history_panel(self, expanded: bool) -> None:
        if not self.history_panel:
            return

        if expanded:
            self.history_panel.refresh_data()
            self.history_panel.Show()

            if hasattr(self, "row_favorites") and self.row_favorites.expanded:
                self.row_favorites.set_expanded(False)
            if self.favorites_panel and self.favorites_panel.IsShown():
                self.favorites_panel.Hide()
        else:
            self.history_panel.Hide()

        self._relayout()
    
    def _on_reset(self, event: wx.CommandEvent) -> None:
        defaults = Settings()

        self.default_city.SetValue(defaults.default_city)
        self.units.SetSelection(0)
        self.theme.SetSelection(0)
        self.forecast_days.SetValue(defaults.forecast_days)
        self.chk_animated_current.SetValue(defaults.animated_current_icon)
        self.chk_use_detected.SetValue(defaults.use_detected_on_start)
        self.chk_ask_detected.SetValue(defaults.ask_detected_on_start)

        if hasattr(self, "row_favorites"):
            self.row_favorites.set_expanded(False)
        if hasattr(self, "row_history"):
            self.row_history.set_expanded(False)

        if self.favorites_panel:
            self.favorites_panel.Hide()
        if self.history_panel:
            self.history_panel.Hide()

        self.palette = get_palette(Theme.LIGHT)
        self._apply_theme()

        if self.favorites_panel:
            self.favorites_panel.apply_theme(Theme.LIGHT)
        if self.history_panel:
            self.history_panel.apply_theme(Theme.LIGHT)
        if hasattr(self, "row_favorites"):
            self.row_favorites.apply_theme(Theme.LIGHT)
        if hasattr(self, "row_history"):
            self.row_history.apply_theme(Theme.LIGHT)

        self._relayout()

    
    def _on_toggle_use_detected(self, event: wx.CommandEvent) -> None:
        if self.chk_use_detected.GetValue():
            self.chk_ask_detected.SetValue(False)
            self.chk_ask_detected.Disable()
        else:
            self.chk_ask_detected.Enable()

    def _on_theme_changed(self, event: wx.CommandEvent) -> None:
        theme = Theme.LIGHT if self.theme.GetSelection() == 0 else Theme.DARK
        self.palette = get_palette(theme)
        self._apply_theme()

        if self.favorites_panel:
            self.favorites_panel.apply_theme(theme)
        if self.history_panel:
            self.history_panel.apply_theme(theme)
        if hasattr(self, "row_favorites"):
            self.row_favorites.apply_theme(theme)
        if hasattr(self, "row_history"):
            self.row_history.apply_theme(theme)

    def _on_save(self, event: wx.CommandEvent | None = None) -> None:
        new_settings = self.get_settings()

        if callable(self.on_apply_settings):
            self.on_apply_settings(new_settings)

        self.Close()

    def _on_close(self, event: wx.Event | None = None) -> None:
        if self._closing:
            return

        self._closing = True
        try:
            if callable(self.on_close_dialog):
                self.on_close_dialog()
            self.Destroy()
        finally:
            self._closing = False

    def _apply_theme(self) -> None:
        p = self.palette
        self.SetBackgroundColour(p.dialog_bg)

        if hasattr(self, "general_box"):
            self.general_box.SetForegroundColour(p.text_primary)

        if hasattr(self, "saved_box"):
            self.saved_box.SetForegroundColour(p.text_primary)

        for lbl in (self.lbl_default, self.lbl_units, self.lbl_theme, self.lbl_forecast_days):
            lbl.SetForegroundColour(p.text_primary)

        for ctrl in (self.default_city, self.units, self.theme, self.forecast_days):
            ctrl.SetBackgroundColour(p.input_bg)
            ctrl.SetForegroundColour(p.input_text)

        for cb in (self.chk_use_detected, self.chk_ask_detected, self.chk_animated_current):
            cb.SetForegroundColour(p.text_primary)

        self.Refresh()

    # Extract current settings from the dialog controls into a Settings object/ Result
    def get_settings(self) -> Settings:
        default_city = (self.default_city.GetValue() or "").strip() or "Sofia"

        units = Units.METRIC if self.units.GetSelection() == 0 else Units.IMPERIAL
        theme = Theme.LIGHT if self.theme.GetSelection() == 0 else Theme.DARK
        forecast_days = int(self.forecast_days.GetValue())
        animated_current_icon = bool(self.chk_animated_current.GetValue())

        use_detected = bool(self.chk_use_detected.GetValue())
        ask_detected = bool(self.chk_ask_detected.GetValue()) and (not use_detected)

        location_prompted = self._original.location_prompted
        if ask_detected:
            location_prompted = False

        return Settings(
            default_city=default_city,
            last_city=self._original.last_city,
            units=units,
            theme=theme,
            forecast_days=forecast_days,
            animated_current_icon=animated_current_icon,
            location_prompted=location_prompted,
            use_detected_on_start=use_detected,
            ask_detected_on_start=ask_detected,
        )