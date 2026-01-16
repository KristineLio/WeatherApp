# weather_app/ui/settings_dialog.py
from __future__ import annotations

import wx

from weather_app.domain.settings import Settings, Units, Theme
from weather_app.ui.theme import get_palette


class SettingsDialog(wx.Dialog):
    """
    Modal settings dialog.
    The dialog is themed using the same palette system as the main frame.
    """

    def __init__(self, parent: wx.Window, settings: Settings,):
        super().__init__(
            parent,
            title="Settings",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self._original = settings
        self.palette = get_palette(settings.theme)

        root = wx.BoxSizer(wx.VERTICAL)

        # -------------------------
        # Form
        # -------------------------
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

        self.chk_use_detected = wx.CheckBox(self, label="Use detected city on startup")
        self.chk_use_detected.SetValue(bool(settings.use_detected_on_start))

        self.chk_ask_detected = wx.CheckBox(self, label="Ask about location on startup")
        self.chk_ask_detected.SetValue(bool(getattr(settings, "ask_detected_on_start", True)))

        # If auto-use is ON, asking is irrelevant (disable it)
        if self.chk_use_detected.GetValue():
            self.chk_ask_detected.SetValue(False)
            self.chk_ask_detected.Disable()

        self.chk_use_detected.Bind(wx.EVT_CHECKBOX, self._on_toggle_use_detected)


        form.Add(self.lbl_default, 0, wx.ALIGN_CENTER_VERTICAL)
        form.Add(self.default_city, 1, wx.EXPAND)

        form.Add(self.lbl_units, 0, wx.ALIGN_CENTER_VERTICAL)
        form.Add(self.units, 1, wx.EXPAND)

        form.Add(self.lbl_theme, 0, wx.ALIGN_CENTER_VERTICAL)
        form.Add(self.theme, 1, wx.EXPAND)

        root.Add(form, 1, wx.EXPAND | wx.ALL, 14)
        root.Add(self.chk_use_detected, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 14)
        root.Add(self.chk_ask_detected, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 14)

        # -------------------------
        # Buttons (Reset | OK Cancel)
        # -------------------------
        btn_row = wx.BoxSizer(wx.HORIZONTAL)

        self.reset_btn = wx.Button(self, label="Reset")
        self.reset_btn.show_focus = False
        self.reset_btn.Bind(wx.EVT_BUTTON, self._on_reset)

        btn_row.Add(self.reset_btn, 0, wx.RIGHT, 8)
        btn_row.AddStretchSpacer(1)

        ok_btn = wx.Button(self, wx.ID_OK)
        cancel_btn = wx.Button(self, wx.ID_CANCEL)

        btn_sizer = wx.StdDialogButtonSizer()
        btn_sizer.AddButton(ok_btn)
        btn_sizer.AddButton(cancel_btn)
        btn_sizer.Realize()

        btn_row.Add(btn_sizer, 0)

        root.Add(btn_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        self.SetSizer(root)
        self.SetMinSize((360, 220))
        self.Fit()

        self._apply_theme()

        self.default_city.SetFocus()
        self.default_city.SetInsertionPointEnd()
    
    def _on_reset(self, event: wx.CommandEvent) -> None:
        # Defaults based on Settings defaults 
        self.default_city.SetValue(Settings().default_city)
        self.units.SetSelection(0)  # Metric
        self.theme.SetSelection(0)  # Light

        # Update dialog theme immediately to match selection
        self.palette = get_palette(Theme.LIGHT)
        self._apply_theme()
    
    def _on_toggle_use_detected(self, event: wx.CommandEvent) -> None:
        if self.chk_use_detected.GetValue():
            # If auto-use is on, don't ask
            self.chk_ask_detected.SetValue(False)
            self.chk_ask_detected.Disable()
        else:
            self.chk_ask_detected.Enable()

    # -------------------------------------------------
    # Theme
    # -------------------------------------------------
    def _apply_theme(self) -> None:
        p = self.palette

        self.SetBackgroundColour(p.dialog_bg)

        for lbl in (self.lbl_default, self.lbl_units, self.lbl_theme):
            lbl.SetForegroundColour(p.text_primary)

        for ctrl in (self.default_city, self.units, self.theme):
            ctrl.SetBackgroundColour(p.input_bg)
            ctrl.SetForegroundColour(p.input_text)
        
        for cb in (self.chk_use_detected, self.chk_ask_detected):
            cb.SetForegroundColour(p.text_primary)

        self.Refresh()

    # -------------------------------------------------
    # Result
    # -------------------------------------------------
    def get_settings(self) -> Settings:
        default_city = (self.default_city.GetValue() or "").strip() or "Sofia"

        units = Units.METRIC if self.units.GetSelection() == 0 else Units.IMPERIAL
        theme = Theme.LIGHT if self.theme.GetSelection() == 0 else Theme.DARK

        use_detected = bool(self.chk_use_detected.GetValue())
        ask_detected = bool(self.chk_ask_detected.GetValue()) and (not use_detected)

        # initialize from old value (UnboundLocalError)
        location_prompted = self._original.location_prompted

        # If user turns asking ON, allow the prompt again.(undo "don't ask again")
        if ask_detected:
            location_prompted = False

        return Settings(
            default_city=default_city,
            last_city=self._original.last_city,
            units=units,
            theme=theme,
            location_prompted=location_prompted,
            use_detected_on_start=use_detected,
            ask_detected_on_start=ask_detected,
        )