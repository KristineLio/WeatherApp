import wx
import os

import logging
import threading
import datetime as dt
import wx.lib.scrolledpanel as scrolled

from weather_app.domain.settings import Settings, Units, Theme
from weather_app.services.settings_store import SettingsStore

from weather_app.utils.paths import ASSETS_DIR
from weather_app.utils.icons import get_icon_bitmap, code_to_label_icon
from weather_app.utils.formatters import format_full_date
from weather_app.domain.models import WeatherData, CurrentSnapshot, DailyForecast, HourlySeries
from weather_app.domain.modes import HourlyMode, DEFAULT_MODE, get_mode_meta, format_value
from weather_app.services.openmeteo import WeatherService
from weather_app.ui.weather_card import WeatherCard 
from weather_app.ui.hour_tile import HourTile
from weather_app.ui.theme import pick_bg


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
                self._on_get_weather()

        wx.CallAfter(apply_initial)

        # 2) background IP detection (optional override)
        detected = self.service.detect_city()
        if not detected:
            return

        detected = detected.strip()

        def apply_detected():
            if self._user_started_searching:
                return
            if detected.lower() == initial_city.lower():
                return

            self.location.SetValue(detected)
            self.settings.last_city = detected
            self.settings_store.save(self.settings)
            self._on_get_weather()

        wx.CallAfter(apply_detected)   
        
    def _init_ui(self):
        """Construct and lay out the full UI for the frame."""
        self._apply_theme()

        main_sizer = wx.BoxSizer(wx.VERTICAL)

        top_bar = self._build_top_bar(self)
        current_panel = self._build_current_panel(self)
        self._build_forecast_strip(self)
        tabs_panel = self._build_hourly_tabs(self)
        self._build_today_strip(self)

        main_sizer.Add(top_bar,        0, wx.EXPAND)
        main_sizer.Add(current_panel,  0, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(self.forecast_scroll, 0, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(tabs_panel,     0, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)
        main_sizer.Add(self.today_scroll, 0, wx.EXPAND | wx.ALL, 5)

        self.SetSizer(main_sizer)

    def _apply_theme(self):

        dark = (self.settings.theme.value == "dark")

        if not dark:
            self.COL_BG = wx.Colour(183, 210, 230)
            self.COL_TOPBAR = wx.Colour(50, 50, 100)
            self.COL_TOPBAR_INNER = wx.Colour(70, 70, 120)
            self.COL_CURRENT = wx.Colour(90, 120, 255)
            self.COL_TEXT_LIGHT = wx.WHITE
        else:
            self.COL_BG = wx.Colour(20, 22, 28)
            self.COL_TOPBAR = wx.Colour(30, 32, 40)
            self.COL_TOPBAR_INNER = wx.Colour(45, 48, 60)
            self.COL_CURRENT = wx.Colour(55, 70, 110)
            self.COL_TEXT_LIGHT = wx.Colour(240, 240, 240)

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

        s.Add(self.location, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 10)
        s.Add(self.search_btn, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 10)

        top_bar.SetSizer(s)
        return top_bar

    def _build_current_panel(self, parent: wx.Window) -> wx.Panel:
        current_panel = wx.Panel(parent, size=(-1, 220))

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

        self.current_icon = wx.StaticBitmap(
            current_panel, bitmap=get_icon_bitmap("unknown.png", size=(60, 60))
        )

        left_col.Add(self.temp_label, 0, wx.BOTTOM, 2)
        left_col.Add(self.current_icon, 0, wx.BOTTOM, 4)

        # RIGHT
        self.desc_label = wx.StaticText(current_panel, label=" ", style=wx.ALIGN_CENTER)
        self._style_light_label(self.desc_label, self.FONT_DESC)

        self.precip_label   = self._build_metric_label(current_panel, "Precip: —")
        self.humidity_label = self._build_metric_label(current_panel, "Humidity: —")
        self.wind_label     = self._build_metric_label(current_panel, "Wind: —")
        self.feels_label    = self._build_metric_label(current_panel, "Feels like —")
        

        right_col.Add(self.desc_label, 0, wx.EXPAND | wx.BOTTOM, 6)
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
    
    def _build_forecast_strip(self, parent: wx.Window) -> None:
        self.forecast_scroll = scrolled.ScrolledPanel(parent, size=(-1, 180), style=wx.SUNKEN_BORDER)
        self.forecast_scroll.SetBackgroundColour(wx.Colour(240, 240, 240))

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
        self.today_scroll.SetBackgroundColour(wx.Colour(245, 245, 245))

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

            # Keep UI consistent: re-assert the active toggle (optional but nice)
            if hasattr(self, "hourly_mode"):
                self._set_hourly_mode(self.hourly_mode, refresh=False)

        # Prefer updating the local panel instead of the entire frame
        if hasattr(self, "current_panel"):
            self.current_panel.Layout()
            self.current_panel.Refresh()
        else:
            self.Refresh()


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


    def _on_get_weather(self, event=None):
        """Fetch weather for the city in the search box.

        Runs the network request in a background thread and applies results back on
        the UI thread. Uses a simple "latest request wins" guard so slower responses
        can't overwrite newer searches.
        """
        self._user_started_searching = True
        if not self.search_btn.IsEnabled():
            return
        
        city = self.location.GetValue().strip()
        if not city:
            return
        
        self.settings.last_city = city
        self.settings_store.save(self.settings)

        req_id = self._next_request_id()
        
        self._set_current_loading(True, city=city)
        
        def work(local_city: str, local_req_id: int):
            logger.info("Worker start req_id=%s city=%r", local_req_id, local_city)
            try:
                data = self.service.fetch(local_city, units=self.settings.units)
                logger.info("Worker success req_id=%s city=%r", local_req_id, local_city)
                self._call_after_if_latest(local_req_id, self.update_ui, data)
            except Exception as e:
                # Only show error if this is still the latest request
                logger.exception("Worker error req_id=%s city=%r", local_req_id, local_city)
                self._call_after_if_latest(local_req_id, self.show_error, str(e))
            finally:
                # Only the latest request should end loading
                self._call_after_if_latest(local_req_id, self._set_current_loading, False)

        threading.Thread(target=work, args=(city, req_id), daemon=True).start()

    def show_error(self, msg: str):
        self.temp_label.SetLabel("—°C")
        self.desc_label.SetLabel(msg)
        wx.MessageBox(msg, "Weather App", wx.OK | wx.ICON_ERROR)
    """
    def show_error(self, msg: str):
        self.temp_label.SetLabel("—°C")
        self.desc_label.SetLabel(msg)
    """
    def _set_current_metric(self, label: wx.StaticText, mode: HourlyMode, snapshot: CurrentSnapshot) -> None:
        
        meta = get_mode_meta(mode)
        v = meta.current_value(snapshot)
        label.SetLabel(f"{meta.tab_label}: {meta.fmt(v, self.settings.units)}")

    def _update_current_block(self, data: WeatherData, *, snapshot: CurrentSnapshot | None = None):
        """
        Update the 'current weather' panel.

        Accepts the full WeatherData object and optionally a specific CurrentSnapshot
        (useful when you want to display a selected day's snapshot).
        """
        cur: CurrentSnapshot = snapshot or data.current

        temp = cur.temp
        code = cur.code
        label, icon_file = code_to_label_icon(code or 0)

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

        self.current_icon.SetBitmap(get_icon_bitmap(icon_file, size=(60, 60)))

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
        days = (daily_list or [])[:7]

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
                bg_color=pick_bg(i),
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

            card.base_bg = pick_bg(i)
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
            return {"labels": [], "hours_int": [], "values": [], "codes": [], "pivot_index": None}
        
        series = self.data.hourly
        today_iso = self.data.current.date_iso
        current_time_iso = self.data.current.time_iso

        return series.build_day(
            date_iso,
            mode=mode,
            today_iso=today_iso,
            current_time_iso=current_time_iso,
        )

    
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
                )
                self.hour_tiles.append(tile)
                self.today_sizer.Add(tile, 0, wx.ALL, 6)

            # 2) update existing tiles
            for i in range(needed):
                tile = self.hour_tiles[i]
                tile.update_content(
                    time_label=hours[i],
                    mode=mode,
                    value=values[i],
                    code=codes[i],
                    units=self.settings.units,
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

