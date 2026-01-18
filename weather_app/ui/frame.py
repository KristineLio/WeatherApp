import wx
import os
import wx.adv

import logging
import threading
import datetime as dt
import wx.lib.scrolledpanel as scrolled

from weather_app.services.openmeteo import WeatherService
from weather_app.services.settings_store import SettingsStore

from weather_app.utils.paths import ASSETS_DIR
from weather_app.utils.icons import get_icon_bitmap, code_to_label_icon, get_anim, code_to_gif
from weather_app.utils.formatters import format_full_date, is_night, time_hhmm_from_iso

from weather_app.domain.models import WeatherData, CurrentSnapshot, DailyForecast, HourlySeries
from weather_app.domain.modes import HourlyMode, DEFAULT_MODE, get_mode_meta, format_value

from weather_app.ui.weather_card import WeatherCard 
from weather_app.ui.hour_tile import HourTile
from weather_app.ui.theme import pick_card_bg, get_palette

from weather_app.ui.settings_dialog import SettingsDialog



logger = logging.getLogger(__name__)

class WeatherApp(wx.Frame):
    def __init__(self, parent, title):
        super().__init__(parent, title=title, size=(420, 700))

        self.settings_store = SettingsStore()
        self.settings = self.settings_store.load()

        self._user_started_searching = False

        self.service = WeatherService()  # networking service
        self.forecast_cards = []
        self.hour_tiles = []
        self.data: WeatherData | None = None
        self.selected_date = None   # currently selected forecast date 
        self.hourly_mode: HourlyMode = HourlyMode.TEMPERATURE  # "temperature" | "precip" | "wind" | "humidity"

        self._req_seq = 0
        self._active_req = 0

        self._init_ui()
        self.Centre()
        self.Show()

        # Start a background task to auto-detect location and fetch weather
        threading.Thread(target=self._auto_fetch_on_start, daemon=True).start()
    
    
    def _prompt_use_detected_city(self, detected: str) -> None:
        # Don’t prompt if user already interacted
        if self._user_started_searching:
            return
        
        if not self.settings.ask_detected_on_start:
            return

        msg = (
            f"See results closer to you?\n\n"
            f"Use detected city: {detected}\n"
        )

        # RichMessageDialog supports a checkbox on Windows
        dlg = wx.RichMessageDialog(
            self,
            msg,
            "Use detected location?",
            style=wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION,
        )
        dlg.ShowCheckBox("Don't ask again", checked=True)

        try:
            res = dlg.ShowModal()
            dont_ask_again = dlg.IsCheckBoxChecked()
        finally:
            dlg.Destroy()

        if dont_ask_again:
            self.settings.location_prompted = True

        if res == wx.ID_YES:
            self.settings.use_detected_on_start = True
            self.location.SetValue(detected)
            self.settings.last_city = detected
            self.settings_store.save(self.settings)
            self._on_get_weather(mark_user=False)
            return

        if res == wx.ID_NO:
            self.settings.use_detected_on_start = False
            self.settings_store.save(self.settings)
            return

        # Cancel , still remember "don't ask again" if checked
        self.settings_store.save(self.settings)
    
    def _auto_fetch_on_start(self):
        """
        Startup logic:
        1) Load last_city immediately (fast)
        2) Detect city in background and override ONLY if user hasn't interacted
        """
        # 1) immediate city from settings
        initial_city = (
            self.settings.last_city
            or self.settings.default_city
            or "Sofia"
        ).strip()

        def apply_initial():
            if not self.location.GetValue().strip():
                self.location.SetValue(initial_city)
                self._on_get_weather(mark_user=False)

        wx.CallAfter(apply_initial)

        # 2) background IP detection (optional override)
        detected = self.service.detect_city()
        if not detected:
            return

        detected = detected.strip()

        def apply_detected():
            logger.debug(
                "Location prompt decision: user_started=%s prompted=%s use_detected=%s detected=%s initial=%s",
                self._user_started_searching,
                self.settings.location_prompted,
                self.settings.use_detected_on_start,
                detected,
                initial_city,
            )

            # If user touched anything, never override / prompt
            if self._user_started_searching:
                return
            
            # If same city, nothing to do
            if detected.lower() == initial_city.lower():
                return

            # 1) if user already opted-in, use detected silently
            if self.settings.use_detected_on_start:
                self.location.SetValue(detected)
                self.settings.last_city = detected
                self.settings_store.save(self.settings)
                self._on_get_weather(mark_user=False)
                return
            
            # 2) If user disabled asking entirely, do nothing
            if not self.settings.ask_detected_on_start:
                return

            # 3) Ask (only if not previously "don't ask again")
            if not self.settings.location_prompted:
                self._prompt_use_detected_city(detected)
                return

            # 4) Otherwise do nothing
            return

        wx.CallAfter(apply_detected)   
    
    def _schedule_refetch(self, city: str, *, failed_req_id: int, delay_ms: int = 20000) -> None:
        """Retry once after a delay, but only if still relevant. (UI thread only)"""
        seconds = delay_ms // 1000

        # start countdown immediately
        self._start_reconnect_countdown(
            failed_req_id=failed_req_id,
            seconds=seconds,
        )

        def retry():
            # still the latest request?
            if not self._is_latest(failed_req_id):
                self._hide_reconnect_status()
                return

            # city unchanged?
            current_city = self.location.GetValue().strip()
            if current_city.lower() != city.strip().lower():
                self._hide_reconnect_status()
                return

            # not already loading?
            if not self.search_btn.IsEnabled():
                return
            
            self._hide_reconnect_status()
            logger.info("Auto-refetch retry req_id=%s city=%r", failed_req_id, city)
            self._on_get_weather(mark_user=False)

        wx.CallLater(delay_ms, retry)

        
    def _init_ui(self):
        """Construct and lay out the full UI for the frame."""
        self._apply_theme()

        main_sizer = wx.BoxSizer(wx.VERTICAL)

        top_bar = self._build_top_bar(self)
        current_panel = self._build_current_panel(self)
        self._build_forecast_strip(self)
        tabs_panel = self._build_hourly_tabs(self)
        self.tabs_panel = tabs_panel
        self._build_today_strip(self)

        main_sizer.Add(top_bar,        0, wx.EXPAND)
        main_sizer.Add(current_panel,  0, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(self.forecast_scroll, 0, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(tabs_panel,     0, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)
        main_sizer.Add(self.today_scroll, 0, wx.EXPAND | wx.ALL, 5)

        self.SetSizer(main_sizer)

    def _apply_theme(self):

        dark = (self.settings.theme.value == "dark")
        #dark = "dark"
        self.palette = get_palette(self.settings.theme)

        p = self.palette
        self.COL_BG = p.bg
        self.COL_TOPBAR = p.topbar
        self.COL_TOPBAR_INNER = p.topbar_inner
        self.COL_CURRENT = p.current
        self.COL_TEXT_LIGHT = p.text_light

        self.SetBackgroundColour(self.COL_BG)
       
        # Fonts (centralized)
        self.FONT_LOC = wx.Font(14, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        self.FONT_NOW = wx.Font(13, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        self.FONT_TEMP = wx.Font(42, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        self.FONT_DESC = wx.Font(15, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        self.FONT_META = wx.Font(11, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.FONT_META_BOLD = wx.Font(11, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)

    def _style_light_label(self, lbl: wx.StaticText, font: wx.Font | None = None):
        lbl.SetForegroundColour(self.COL_TEXT_LIGHT)
        if font is not None:
            lbl.SetFont(font)
    
    def _build_metric_label(self, parent: wx.Window, text: str) -> wx.StaticText:
        lbl = wx.StaticText(parent, label=text)
        self._style_light_label(lbl, self.FONT_META)
        return lbl

    

    def _wrap_desc_label(self):
        lbl = getattr(self, "desc_label", None)
        if not lbl:
            return

        # Use the actual allocated width
        w = lbl.GetSize().width
        if w <= 1:
            return  # not laid out yet

        # Wrap a bit before the edge
        lbl.Wrap(max(120, w - 8))
        lbl.GetParent().Layout()
       

    def _on_current_panel_resize(self, event):
        event.Skip()
        wx.CallAfter(self._wrap_desc_label)
        
    def _build_top_bar(self, parent: wx.Window) -> wx.Panel:
        top_bar = wx.Panel(parent, size=(-1, 50))
        self.top_bar = top_bar  # keep reference for theme refresh
        top_bar.SetBackgroundColour(self.COL_TOPBAR)

        s = wx.BoxSizer(wx.HORIZONTAL)

        self.location = wx.TextCtrl(top_bar, style=wx.TE_PROCESS_ENTER)
        self.location.SetForegroundColour(self.COL_TEXT_LIGHT)
        self.location.SetBackgroundColour(self.COL_TOPBAR_INNER)
        self.location.SetFont(self.FONT_LOC)
        self.location.Bind(wx.EVT_TEXT_ENTER, self._on_get_weather)

        # search button
        search_icon_path = os.path.join(ASSETS_DIR, "search_icon30.png")
        self.search_btn = wx.BitmapButton(
            top_bar,
            bitmap=wx.Bitmap(search_icon_path, wx.BITMAP_TYPE_PNG),
            style=wx.NO_BORDER,
        )
        self.search_btn.SetBackgroundColour(self.COL_TOPBAR)
        self.search_btn.Bind(wx.EVT_BUTTON, self._on_get_weather)

        # settings button (uses built-in art, no asset needed)
        gear_bmp = wx.ArtProvider.GetBitmap(wx.ART_HELP_SETTINGS, wx.ART_BUTTON, (24, 24))
        self.settings_btn = wx.BitmapButton(top_bar, bitmap=gear_bmp, style=wx.NO_BORDER)
        self.settings_btn.SetBackgroundColour(self.COL_TOPBAR)
        self.settings_btn.SetToolTip("Settings")
        self.settings_btn.Bind(wx.EVT_BUTTON, self._on_open_settings)

        s.Add(self.location, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 10)
        s.Add(self.search_btn, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 10)
        s.Add(self.settings_btn, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 10)

        top_bar.SetSizer(s)
        return top_bar
    
    def _on_open_settings(self, event: wx.CommandEvent) -> None:
        dlg = SettingsDialog(self, self.settings)
        try:
            res = dlg.ShowModal()
            if res != wx.ID_OK:
                return

            new_settings = dlg.get_settings()

            # capture old values BEFORE overwrite
            old_settings = self.settings
            old_forecast = getattr(old_settings, "forecast_days", 7)

            theme_changed = new_settings.theme != old_settings.theme
            units_changed = new_settings.units != old_settings.units
            forecast_changed = getattr(new_settings, "forecast_days", 7) != old_forecast
            default_changed = new_settings.default_city != old_settings.default_city

            animated_changed = (
                getattr(new_settings, "animated_current_icon", False)
                != getattr(old_settings, "animated_current_icon", False)
            )

            # commit + persist
            self.settings = new_settings
            self.settings_store.save(self.settings)

            if theme_changed:
                self._apply_theme()
                self._apply_theme_to_existing_ui()

            if animated_changed and hasattr(self, "_cur_icon_png"):
                self._set_current_icon(icon_png=self._cur_icon_png, icon_gif=getattr(self, "_cur_icon_gif", None))
                self.icon_host.Layout()
                self.current_panel.Layout()
                self.current_panel.Refresh()

            # If units changed: refetch
            if units_changed and self.location.GetValue().strip():
                self._on_get_weather()  # user initiated is fine here
                return  # optional: avoid double work

            # Forecast days changed:
            if forecast_changed and self.location.GetValue().strip():
                # If increased -> need more data, so refetch
                if self.settings.forecast_days > old_forecast:
                    self._on_get_weather(mark_user=False)  # no need to mark as user typing
                else:
                    # If decreased -> existing data is enough, just rebuild
                    if self.data:
                        self._rebuild_forecast_cards(self.data.daily)
            logger.info("Settings changed: forecast_days %s -> %s", old_forecast, self.settings.forecast_days)

            if default_changed and not self.location.GetValue().strip():
                self.location.SetValue(self.settings.default_city)

        finally:
            dlg.Destroy()
            
    def _apply_theme_to_existing_ui(self) -> None:
        """
        Called after self._apply_theme() to recolor already-created widgets.
        Keeps it minimal and safe.
        """
        p = self.palette

        # frame bg
        self.SetBackgroundColour(self.COL_BG)

        # top bar
        if hasattr(self, "top_bar"):
            self.top_bar.SetBackgroundColour(self.COL_TOPBAR)

        if hasattr(self, "location"):
            self.location.SetForegroundColour(self.COL_TEXT_LIGHT)
            self.location.SetBackgroundColour(self.COL_TOPBAR_INNER)

        if hasattr(self, "search_btn"):
            self.search_btn.SetBackgroundColour(self.COL_TOPBAR)

        if hasattr(self, "settings_btn"):
            self.settings_btn.SetBackgroundColour(self.COL_TOPBAR)
        
        # current panel
        if hasattr(self, "current_panel"):
            self.current_panel.SetBackgroundColour(self.COL_CURRENT)
            self.current_panel.Refresh()

        # strips
        if hasattr(self, "forecast_scroll"):
            self.forecast_scroll.SetBackgroundColour(p.forecast_strip_bg)
        if hasattr(self, "today_scroll"):
            self.today_scroll.SetBackgroundColour(p.hourly_strip_bg)

        # forecast cards: update palette-based bg + selected bg
        if hasattr(self, "forecast_cards"):
            for i, card in enumerate(self.forecast_cards):
                card.base_bg = pick_card_bg(p, i)
                card.selected_bg = p.card_selected_bg
                # keep selection state
                is_sel = (getattr(card, "date_iso", None) == getattr(self, "selected_date", None))
                card.set_selected(bool(is_sel))
                card.refresh_theme()

        # hour tiles: recolor backgrounds + text
        if hasattr(self, "hour_tiles"):
            for t in self.hour_tiles:
                try:
                    t.SetBackgroundColour(p.hour_tile_bg)
                    # HourTile has these labels in your file :contentReference[oaicite:6]{index=6}
                    t.time_lbl.SetForegroundColour(p.hour_tile_text_muted)
                    t.value_lbl.SetForegroundColour(p.hour_tile_text)
                    t.Refresh()
                except Exception:
                    pass

        self.Layout()
        self.Refresh()

    def _build_current_panel(self, parent: wx.Window) -> wx.Panel:
        current_panel = wx.Panel(parent, size=(-1, 220))
        self.current_panel = current_panel
        current_panel.SetBackgroundColour(self.COL_CURRENT)

        cp = wx.BoxSizer(wx.VERTICAL)

        # Now/Date label
        self.now_label = wx.StaticText(current_panel, label="Now")
        self._style_light_label(self.now_label, self.FONT_NOW)

        # Main row
        main_row = wx.BoxSizer(wx.HORIZONTAL)

        left_col = wx.BoxSizer(wx.VERTICAL)
        left_col.SetMinSize((220, -1))

        right_col = wx.BoxSizer(wx.VERTICAL)

        # LEFT
        self.temp_label = wx.StaticText(current_panel, label="--")
        self._style_light_label(self.temp_label, self.FONT_TEMP)

        self.icon_host = wx.Panel(current_panel)
        self.icon_host.SetBackgroundColour(self.COL_CURRENT)

        self.icon_host_sizer = wx.BoxSizer(wx.VERTICAL)
        self.icon_host.SetSizer(self.icon_host_sizer)

        # initial control = static bitmap (current behavior)
        self.current_icon_ctrl = wx.StaticBitmap(
            self.icon_host, bitmap=get_icon_bitmap("unknown.png", size=(60, 60))
        )
        self.icon_host_sizer.Add(self.current_icon_ctrl, 0, wx.ALIGN_LEFT)


        left_col.Add(self.temp_label, 0, wx.BOTTOM, 2)
        left_col.Add(self.icon_host, 0, wx.BOTTOM, 4)

        # RIGHT
        self.desc_label = wx.StaticText(current_panel, label=" ", style=wx.ALIGN_CENTER)
        self._style_light_label(self.desc_label, self.FONT_DESC)

        # reconnect / status (hidden by default)
        self.status_label = wx.StaticText(current_panel, label="")
        self.status_label.SetForegroundColour(wx.Colour(150, 150, 150))

        base_font = self.desc_label.GetFont()
        small_font = wx.Font(
            base_font.GetPointSize() - 1,
            base_font.GetFamily(),
            base_font.GetStyle(),
            base_font.GetWeight(),
        )
        self.status_label.SetFont(small_font)
        self.status_label.Hide()

        self.precip_label   = self._build_metric_label(current_panel, "Precip: —")
        self.humidity_label = self._build_metric_label(current_panel, "Humidity: —")
        self.wind_label     = self._build_metric_label(current_panel, "Wind: —")
        self.feels_label    = self._build_metric_label(current_panel, "Feels like —")
        

        right_col.Add(self.desc_label, 0, wx.EXPAND | wx.BOTTOM, 6)
        right_col.Add(self.status_label, 0, wx.EXPAND | wx.BOTTOM, 6)
        right_col.Add(self.precip_label, 0, wx.EXPAND | wx.BOTTOM, 2)
        right_col.Add(self.humidity_label, 0, wx.EXPAND | wx.BOTTOM, 2)
        right_col.Add(self.wind_label, 0, wx.EXPAND | wx.BOTTOM, 2)
        right_col.Add(self.feels_label, 0, wx.EXPAND)

      
        main_row.Add(left_col, 0, wx.RIGHT, 20)
        main_row.Add(right_col, 1, wx.EXPAND)

        # Bottom row
        bottom_row = wx.BoxSizer(wx.HORIZONTAL)

        self.city_label = wx.StaticText(current_panel, label="")
        self._style_light_label(self.city_label, self.FONT_META)

        bottom_row.Add(self.city_label, 1)

        cp.Add(self.now_label, 0, wx.ALL, 10)
        cp.Add(main_row, 1, wx.LEFT | wx.RIGHT, 10)
        cp.Add(bottom_row, 0, wx.EXPAND | wx.ALL, 10)

        current_panel.SetSizer(cp)

        # Wrap after the control has a real size (critical)
        current_panel.Bind(wx.EVT_SIZE, self._on_current_panel_resize)
        wx.CallAfter(self._wrap_desc_label)

        return current_panel
    
    def _show_reconnect_status(self, seconds: int) -> None:
        self._reconnect_seconds = seconds
        self.status_label.SetLabel(f"Reconnecting… will retry automatically in {seconds}s")
        self.status_label.Show()
        self.Layout()

    def _hide_reconnect_status(self) -> None:
        self.status_label.Hide()
        self.Layout()

    def _start_reconnect_countdown(self, *, failed_req_id: int, seconds: int) -> None:
        """UI-thread only: countdown label update."""

        self._show_reconnect_status(seconds)

        def tick():
            # stop if request is no longer relevant
            if not self._is_latest(failed_req_id):
                self._hide_reconnect_status()
                return

            self._reconnect_seconds -= 1
            if self._reconnect_seconds <= 0:
                return  # retry will happen separately

            self.status_label.SetLabel(
                f"Reconnecting… will retry automatically in {self._reconnect_seconds}s"
            )
            wx.CallLater(1000, tick)

        wx.CallLater(1000, tick)

    def _build_forecast_strip(self, parent: wx.Window) -> None:
        self.forecast_scroll = scrolled.ScrolledPanel(parent, size=(-1, 180), style=wx.SUNKEN_BORDER)
        self.forecast_scroll.SetBackgroundColour(self.palette.forecast_strip_bg)

        self.forecast_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.forecast_scroll.SetSizer(self.forecast_sizer)
        self.forecast_scroll.SetupScrolling(scroll_x=True, scroll_y=False)

    def _build_hourly_tabs(self, parent: wx.Window) -> wx.Panel:
        tabs_panel = wx.Panel(parent)
        tabs_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.mode_buttons: dict[HourlyMode, wx.ToggleButton] = {}

        for mode_key in HourlyMode:
            meta = get_mode_meta(mode_key)
            btn = wx.ToggleButton(tabs_panel, label=meta.tab_label)
            self.mode_buttons[mode_key] = btn
            tabs_sizer.Add(btn, 1, wx.ALL, 4)
            btn.Bind(wx.EVT_TOGGLEBUTTON, self._on_hourly_mode)

        tabs_panel.SetSizer(tabs_sizer)

        # set default
        self.mode_buttons[DEFAULT_MODE].SetValue(True)
        return tabs_panel
    
    def _build_today_strip(self, parent: wx.Window) -> None:
        self.today_scroll = scrolled.ScrolledPanel(parent, size=(-1, 140), style=wx.SUNKEN_BORDER)
        self.today_scroll.SetBackgroundColour(self.palette.hourly_strip_bg)

        self.today_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.today_scroll.SetSizer(self.today_sizer)

        self.today_scroll.SetupScrolling(scroll_x=True, scroll_y=False)
        self.today_scroll.SetScrollRate(10, 0)

    def _set_hourly_mode(self, mode: HourlyMode, *, refresh: bool = True):
        self.hourly_mode = mode
        for k, b in self.mode_buttons.items():
            b.SetValue(k == mode)
        if refresh:
            self._refresh_hourly_strip()

    def _on_hourly_mode(self, event: wx.CommandEvent):
        if not self.data:
            return
        btn = event.GetEventObject()
        for mode, b in self.mode_buttons.items():
            if b is btn:
                self._set_hourly_mode(mode, refresh=True)
                return
 
    def _refresh_hourly_strip(self):
        """Re-render the hourly strip for the selected date and active mode."""
        if not self.data:
            return
        date_iso = self.selected_date or self.data.current.date_iso
        hourly = self._build_hourly_for_date(date_iso, self.hourly_mode)
        self._rebuild_hour_tiles(hourly, date_iso=date_iso)
    
    def _set_current_loading(self, is_loading: bool, *, city: str = "") -> None:
        if is_loading:
            self.search_btn.Disable()

            # Disable hourly mode buttons while loading / before first data arrives
            for b in getattr(self, "mode_buttons", {}).values():
                b.Disable()

            self.temp_label.SetLabel("Loading…")
            self.desc_label.SetLabel("")
            self.city_label.SetLabel(city or "")

            if hasattr(self, "feels_label"):
                self.feels_label.SetLabel("Feels like —")
            if hasattr(self, "precip_label"):
                self.precip_label.SetLabel("Precip: —")
            if hasattr(self, "humidity_label"):
                self.humidity_label.SetLabel("Humidity: —")
            if hasattr(self, "wind_label"):
                self.wind_label.SetLabel("Wind: —")
        else:
            self.search_btn.Enable()

            # Enable when data is ready
            for b in getattr(self, "mode_buttons", {}).values():
                b.Enable()

            # Keep UI consistent: re-assert the active toggle
            if hasattr(self, "hourly_mode"):
                self._set_hourly_mode(self.hourly_mode, refresh=False)

        # Prefer updating the local panel instead of the entire frame
        if hasattr(self, "current_panel"):
            self.current_panel.Layout()
            self.current_panel.Refresh()
        else:
            self.Refresh()
        
        if hasattr(self, "tabs_panel"):
            self.tabs_panel.Disable() if is_loading else self.tabs_panel.Enable()


    def _next_request_id(self) -> int:
        """Monotonic token: latest request wins."""
        self._req_seq += 1
        self._active_req = self._req_seq
        return self._active_req

    def _is_latest(self, req_id: int) -> bool:
        """True if this request is still the most recent one."""
        return req_id == self._active_req

    def _call_after_if_latest(self, req_id: int, fn, *args, **kwargs):
        """Run fn(*args, **kwargs) on UI thread only if req_id is still latest."""
        def runner():
            if self._is_latest(req_id):
                fn(*args, **kwargs)
        try:
            wx.CallAfter(runner)
        except Exception:
            pass


    def _on_get_weather(self, event=None, *, mark_user: bool = True):
        """Fetch weather for the city in the search box.

        Runs the network request in a background thread and applies results back on
        the UI thread. Uses a simple "latest request wins" guard so slower responses
        can't overwrite newer searches.
        """
        self._hide_reconnect_status()

        if mark_user:
            self._user_started_searching = True
        
        if not self.search_btn.IsEnabled():
            return
        
        city = self.location.GetValue().strip()
        if not city:
            return
        
        logger.info(
            "User search city=%r units=%s forecast_days=%s",
            city,
            self.settings.units.value,
            getattr(self.settings, "forecast_days", 7),
        )
                
        self.settings.last_city = city
        self.settings_store.save(self.settings)

        req_id = self._next_request_id()
        
        self._set_current_loading(True, city=city)
        
        def work(local_city: str, local_req_id: int):
            logger.info("Worker start req_id=%s city=%r", local_req_id, local_city)
            try:
                data = self.service.fetch(
                    local_city,
                    units=self.settings.units,
                    forecast_days=self.settings.forecast_days,
                )
                logger.info("Worker success req_id=%s city=%r", local_req_id, local_city)

                # hide "Reconnecting…" on success
                self._call_after_if_latest(local_req_id, self._hide_reconnect_status)

                # update UI with new data
                self._call_after_if_latest(local_req_id, self.update_ui, data)

            except ValueError as e:
                # user input issue (no traceback)
                logger.warning("Worker input error req_id=%s city=%r err=%s", local_req_id, local_city, e)
                self._call_after_if_latest(local_req_id, self.show_error, str(e))

            except RuntimeError as e:
                # network/service issue (retry only on network errors)
                if "Network" in str(e):
                    logger.info("Scheduling auto-refetch due to network error city=%r", local_city)
                    self._call_after_if_latest(
                        local_req_id,
                        self._schedule_refetch,
                        local_city,
                        failed_req_id=local_req_id,
                    )

                logger.error("Worker runtime error req_id=%s city=%r err=%s", local_req_id, local_city, e)
                self._call_after_if_latest(local_req_id, self.show_error, str(e))

            except Exception:
                # unexpected bug (traceback)
                logger.exception("Worker unexpected error req_id=%s city=%r", local_req_id, local_city)
                self._call_after_if_latest(local_req_id, self.show_error, "Unexpected error. Please try again.")

            finally:
                # Only the latest request should end loading
                self._call_after_if_latest(local_req_id, self._set_current_loading, False)

        threading.Thread(target=work, args=(city, req_id), daemon=True).start()

    def show_error(self, msg: str):
        self.temp_label.SetLabel("—°C")
        self.desc_label.SetLabel(msg)
        wx.MessageBox(msg, "Weather App", wx.OK | wx.ICON_ERROR)
    
    def _set_current_metric(self, label: wx.StaticText, mode: HourlyMode, snapshot: CurrentSnapshot) -> None:
        
        meta = get_mode_meta(mode)
        v = meta.current_value(snapshot)
        label.SetLabel(f"{meta.tab_label}: {meta.fmt(v, self.settings.units)}")
    
    def _set_current_icon(self, *, icon_png: str, icon_gif: str | None = None) -> None:
        """
        Current panel only: swap between StaticBitmap and AnimationCtrl
        depending on settings. Keeps hourly + forecast static.
        """
        want_anim = bool(getattr(self.settings, "animated_current_icon", False))

        # figure out current type
        is_anim = isinstance(getattr(self, "current_icon_ctrl", None), wx.adv.AnimationCtrl)

        # if we need to rebuild control
        if want_anim != is_anim:
            if self.current_icon_ctrl:
                self.current_icon_ctrl.Destroy()

            if want_anim:
                gif = icon_gif or "unknown.gif"
                self.current_icon_ctrl = wx.adv.AnimationCtrl(self.icon_host)
                self.current_icon_ctrl.SetAnimation(get_anim(gif))  # from utils/icons.py
                self.current_icon_ctrl.Play()
            else:
                self.current_icon_ctrl = wx.StaticBitmap(
                    self.icon_host, bitmap=get_icon_bitmap(icon_png, size=(60, 60))
                )

            self.icon_host_sizer.Clear(delete_windows=False)
            self.icon_host_sizer.Add(self.current_icon_ctrl, 0, wx.ALIGN_LEFT)
            self.icon_host.Layout()
            return

        # same type: just update content
        if want_anim:
            gif = icon_gif or "unknown.gif"
            self.current_icon_ctrl.SetAnimation(get_anim(gif))
            self.current_icon_ctrl.Play()
        else:
            self.current_icon_ctrl.SetBitmap(get_icon_bitmap(icon_png, size=(60, 60)))


    def _update_current_block(self, data: WeatherData, *, snapshot: CurrentSnapshot | None = None):
        """
        Update the 'current weather' panel.

        Accepts the full WeatherData object and optionally a specific CurrentSnapshot
        (useful when you want to display a selected day's snapshot).
        """
        cur: CurrentSnapshot = snapshot or data.current

        # find the DailyForecast for the same date
        day = next((d for d in data.daily if d.date_iso == cur.date_iso), None)

        night = is_night(
            cur.time_iso,
            day.sunrise_iso if day else None,
            day.sunset_iso if day else None,
        )

        temp = cur.temp
        code = cur.code
        label, icon_file = code_to_label_icon(code or 0, night=night)
        
        # Decide header: "Now" for today, otherwise weekday
        today_iso = data.current.date_iso
        current_date = cur.date_iso

        if current_date and today_iso and current_date == today_iso:
            local_time = dt.datetime.now().strftime("%H:%M")
            self.now_label.SetLabel(f"Now {local_time}")
        elif current_date:
            self.now_label.SetLabel(format_full_date(current_date))
        else:
            self.now_label.SetLabel("")

        self.temp_label.SetLabel(format_value(HourlyMode.TEMPERATURE, temp, self.settings.units))
        self.desc_label.SetLabel(label)
        self.city_label.SetLabel(cur.city)

        # current icon (png + gif for animation)
        self._cur_icon_png = icon_file
        self._cur_icon_gif = code_to_gif(code, night=night)
        self._set_current_icon(icon_png=self._cur_icon_png, icon_gif=self._cur_icon_gif)

        # feels like (keep as-is or also move into MODE_META later)
        self.feels_label.SetLabel("Feels like " + format_value(HourlyMode.TEMPERATURE, cur.feels_like, self.settings.units))
        
        # right side metrics (mode-driven)
        self._set_current_metric(self.precip_label,   HourlyMode.PRECIPITATION, cur)
        self._set_current_metric(self.humidity_label, HourlyMode.HUMIDITY, cur)
        self._set_current_metric(self.wind_label,     HourlyMode.WIND, cur)
      
    def _rebuild_forecast_cards(self, daily_list: list[DailyForecast]):
        """Update (reuse) the 7-day forecast card strip.

        Reuses existing WeatherCard instances when possible, hides any extras,
        and keeps the visual selected state in sync with self.selected_date.
        """
        n = int(getattr(self.settings, "forecast_days", 7))
        days = (daily_list or [])[:n]

        today_iso = self.data.current.date_iso if self.data else None
        active_date = self.selected_date or today_iso # <-- keep user selection if it exists

        # --- ensure we have enough card instances (reuse existing, create missing) ---
        for i in range(len(self.forecast_cards), len(days)):
            card = WeatherCard(
                self.forecast_scroll,
                day="",
                tmax_text="—",
                tmin_text="—",
                icon_file="unknown.png",
                bg_color=pick_card_bg(self.palette, i),
                selected_bg=self.palette.card_selected_bg,
                date_iso="",
                on_click=self._on_forecast_card_click,
                is_selected=False,
            )
            self.forecast_cards.append(card)
            self.forecast_sizer.Add(card, 0, wx.ALL, 5)
        # --- update content + selection on the cards we need ---
        for i, d in enumerate(days):
            card = self.forecast_cards[i]
            _, icon_file_d = code_to_label_icon(d.code or 0)

            card.date_iso = d.date_iso
            card.on_click = self._on_forecast_card_click

            card.base_bg = pick_card_bg(self.palette, i)
            card.selected_bg = self.palette.card_selected_bg
            max_txt = format_value(HourlyMode.TEMPERATURE, d.tmax, self.settings.units)
            min_txt = format_value(HourlyMode.TEMPERATURE, d.tmin, self.settings.units)

            card.update_content(day=d.weekday, tmax_text=max_txt, tmin_text=min_txt, icon_file=icon_file_d)
           
            card.set_selected(d.date_iso == active_date)

            if not card.IsShown():
                card.Show()
        # --- remove extras (only if API returned fewer than before) ---
        for j in range(len(days), len(self.forecast_cards)):
            self.forecast_cards[j].Hide()

         # --- layout/scrolling ---
        self.forecast_scroll.SetupScrolling(scroll_x=True, scroll_y=False)
        self.forecast_scroll.Layout()

    def _build_hourly_for_date(self, date_iso: str, mode: HourlyMode = DEFAULT_MODE) -> dict:
        if not self.data:
            return {"labels": [], "hours_int": [], "values": [], "codes": [], "time_isos": [], "nights": [], "pivot_index": None}

        series = self.data.hourly
        today_iso = self.data.current.date_iso
        current_time_iso = self.data.current.time_iso

        # daily object for this date (for sunrise/sunset)
        day = next((d for d in self.data.daily if d.date_iso == date_iso), None)
        sunrise_iso = day.sunrise_iso if day else None
        sunset_iso  = day.sunset_iso if day else None

        out = series.build_day(
            date_iso,
            mode=mode,
            today_iso=today_iso,
            current_time_iso=current_time_iso,
        )
        # compute night per hour
        time_isos = out.get("time_isos", [])
        out["nights"] = [is_night(t, sunrise_iso, sunset_iso) for t in time_isos]

        def _hour_from_iso(s: str | None) -> int | None:
            if not s:
                return None
            try:
                return int(s.split("T")[1][:2])
            except Exception:
                return None

        out["sunrise_hour"] = _hour_from_iso(sunrise_iso)
        out["sunset_hour"]  = _hour_from_iso(sunset_iso)

        out["sunrise_iso"] = sunrise_iso
        out["sunset_iso"]  = sunset_iso

        return out
    
    def _rebuild_hour_tiles(self, hourly: dict, date_iso: str | None):
        """
        Rebuild the horizontal strip of hourly tiles.

        - Today: rotate so that "now" is first → later → past, and label first tile "NOW".
        - Other days: keep chronological order and scroll to ~10 AM.
        """
        self.today_scroll.Freeze()
        try:
            if not self.data:
                return

            hours = list(hourly.get("labels", []))
            hours_int = list(hourly.get("hours_int", []))
            values = list(hourly.get("values", []))
            codes = list(hourly.get("codes", []))
            nights = list(hourly.get("nights", []))
            sunrise_hour = hourly.get("sunrise_hour")
            sunset_hour  = hourly.get("sunset_hour")
            sunrise_iso  = hourly.get("sunrise_iso")
            sunset_iso   = hourly.get("sunset_iso")
            mode = self.hourly_mode

            if not hours:
                # hide any existing tiles if no data
                for t in self.hour_tiles:
                    t.Hide()
                self.today_scroll.SetupScrolling(scroll_x=True, scroll_y=False)
                self.today_scroll.Layout()
                return

            today_iso = self.data.current.date_iso
            if date_iso is None:
                date_iso = today_iso

            # today: rotate so now first and label it NOW
            if today_iso and date_iso == today_iso:
                pivot = hourly.get("pivot_index")
                if pivot is not None and 0 <= pivot < len(hours):
                    hours = hours[pivot:] + hours[:pivot]
                    hours_int = hours_int[pivot:] + hours_int[:pivot]
                    values = values[pivot:] + values[:pivot]
                    codes = codes[pivot:] + codes[:pivot]
                    nights = nights[pivot:] + nights[:pivot] 
                    hours[0] = "NOW"

            needed = len(hours)

            # 1) ensure enough tile instances exist (create missing once)
            for i in range(len(self.hour_tiles), needed):
                tile = HourTile(
                    self.today_scroll, 
                    time_label="", 
                    mode=DEFAULT_MODE, 
                    value=None, code=None,
                    units=self.settings.units,
                    bg_color=self.palette.hour_tile_bg,
                    text_color=self.palette.hour_tile_text,
                    muted_text_color=self.palette.hour_tile_text_muted,
                )
                self.hour_tiles.append(tile)
                self.today_sizer.Add(tile, 0, wx.ALL, 6)

            # 2) update existing tiles
            for i in range(needed):
                tile = self.hour_tiles[i]

                is_sunrise = sunrise_hour is not None and hours_int[i] == sunrise_hour
                is_sunset  = sunset_hour  is not None and hours_int[i] == sunset_hour

                if is_sunrise:
                    tile.time_lbl.SetLabel("SUNRISE")
                    tile.icon.SetBitmap(get_icon_bitmap("sunrise.png", size=(36, 36)))
                    tile.value_lbl.SetLabel(time_hhmm_from_iso(sunrise_iso))
                    tile.Show()
                    continue

                if is_sunset:
                    tile.time_lbl.SetLabel("SUNSET")
                    tile.icon.SetBitmap(get_icon_bitmap("sunset.png", size=(36, 36)))
                    tile.value_lbl.SetLabel(time_hhmm_from_iso(sunset_iso)) 
                    tile.Show()
                    continue


                tile.update_content(
                    time_label=hours[i],
                    mode=mode,
                    value=values[i],
                    code=codes[i],
                    units=self.settings.units,
                    night=nights[i] if i < len(nights) else False,
                )
                if not tile.IsShown():
                    tile.Show()

            # 3) hide extras
            for j in range(needed, len(self.hour_tiles)):
                self.hour_tiles[j].Hide()

            self.today_scroll.SetupScrolling(scroll_x=True, scroll_y=False)
            self.today_scroll.Layout()

            # scroll behavior
            if today_iso and date_iso == today_iso:
                self.today_scroll.Scroll(0, 0)
            else:
                # find 10 AM
                try:
                    idx10 = hours_int.index(10)
                except ValueError:
                    idx10 = -1

                if 0 <= idx10 < needed:
                    wx.CallAfter(self.today_scroll.ScrollChildIntoView, self.hour_tiles[idx10])
                else:
                    self.today_scroll.Scroll(0, 0)

        finally:
            self.today_scroll.Thaw()

    def _get_hourly_snapshot_for_date(self, date_iso: str):
        if not self.data:
            return None
        series: HourlySeries = self.data.hourly
        return series.snapshot_for_date(date_iso, target_hour=15, strategy="peak_temp")

    def _make_current_for_date(self, date_iso: str) -> CurrentSnapshot | None:
        """Return the dict that should drive the current_panel for the selected date."""
        if not self.data:
            return None

        today_iso = self.data.current.date_iso
        if date_iso == today_iso:
            return self.data.current

        selected_day = next((d for d in self.data.daily if d.date_iso == date_iso), None)
        if not selected_day:
            return None

        snap = self.data.hourly.snapshot_for_date(date_iso, target_hour=15, strategy="peak_temp")

        # fallback based on daily
        base = CurrentSnapshot(
            temp=selected_day.tmax,
            code=selected_day.code,
            feels_like=None,
            humidity=None,
            precip=None,
            wind=None,
            date_iso=date_iso,
            time_iso=None,
            city=self.data.current.city,
        )

        if not snap:
            return base

        return CurrentSnapshot(
            temp=snap.get("temp"),
            code=snap.get("code"),
            feels_like=snap.get("feels_like"),
            humidity=snap.get("humidity"),
            precip=snap.get("precip"),
            wind=snap.get("windspeed"),
            date_iso=date_iso,
            time_iso=snap.get("time"),
            city=self.data.current.city,
        )
        
        
    def _on_forecast_card_click(self, date_iso: str):
        """Handle a forecast card click.

        Updates selected_date, refreshes the current "hero" block for that date,
        rebuilds the hourly strip for the chosen mode, and updates card selection.
        """
        if not self.data:
            return

        self.selected_date = date_iso

        # Build a snapshot for the selected date (today -> current, other day -> derived)
        snap = self._make_current_for_date(date_iso)
        if not snap:
            return

        # Update current panel (render using 'snap', but still use overall dataset for min/max etc.)
        self._update_current_block(self.data, snapshot=snap)

        # Update hourly strip for that date
        hourly_for_day = self._build_hourly_for_date(date_iso, self.hourly_mode)
        self._rebuild_hour_tiles(hourly_for_day, date_iso=date_iso)

        #  Update card selection visuals
        for card in self.forecast_cards:
            card.set_selected(card.date_iso == date_iso)

    def update_ui(self, data: WeatherData):
        """Apply freshly fetched weather data to all UI sections."""
        self.Freeze()
        try:
            # store latest data
            self.data = data

            today_iso = data.current.date_iso
            self.selected_date = today_iso  #default selection to today

            self._update_current_block(data)
            self._rebuild_forecast_cards(data.daily)
            
            self._set_hourly_mode(DEFAULT_MODE, refresh=True)
            self.Layout()
        finally:
            self.Thaw()

