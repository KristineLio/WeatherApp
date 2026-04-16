from __future__ import annotations

import logging
import os
import threading

import wx
import wx.lib.scrolledpanel as scrolled

from weather_app.domain.models import WeatherData, CurrentSnapshot, DailyForecast, HourlySeries
from weather_app.domain.modes import HourlyMode, DEFAULT_MODE, get_mode_meta
from weather_app.services.errors import NetworkError, ProviderError, is_retryable_error
from weather_app.services.openmeteo import WeatherService
from weather_app.services.settings_store import SettingsStore
from weather_app.services.storage import StorageRepo
from weather_app.ui.request_state import RequestState
from weather_app.ui.current_weather_panel import CurrentWeatherPanel
from weather_app.ui.current_weather_presenter import build_current_weather_view_data
from weather_app.ui.hour_tile import HourTile
from weather_app.ui.hour_tile_presenter import build_hour_strip_view_data
from weather_app.ui.settings_dialog import SettingsDialog
from weather_app.ui.theme import get_palette, pick_card_bg
from weather_app.ui.weather_card import WeatherCard
from weather_app.ui.weather_card_presenter import build_forecast_card_view_data
from weather_app.utils.formatters import is_night
from weather_app.utils.paths import PNG_DIR

logger = logging.getLogger(__name__)


class WeatherApp(wx.Frame):
    def __init__(self, parent, title):
        super().__init__(parent, title=title, size=(420, 700))

        self.settings_store = SettingsStore()
        self.settings = self.settings_store.load()

        self.settings_dialog: SettingsDialog | None = None

        self.storage = StorageRepo()
        logger.info("DB path: %s", self.storage.db_path)

        self._user_started_searching = False

        self.service = WeatherService()
        self.forecast_cards: list[WeatherCard] = []
        self.hour_tiles: list[HourTile] = []
        self.data: WeatherData | None = None
        self.selected_date: str | None = None
        self.hourly_mode: HourlyMode = HourlyMode.TEMPERATURE

        self.request_state = RequestState()

        self._init_ui()
        self.Centre()
        self.Show()

        threading.Thread(target=self._auto_fetch_on_start, daemon=True).start()

    def _prompt_use_detected_city(self, detected: str) -> None:
        if self._user_started_searching:
            return
        if not self.settings.ask_detected_on_start:
            return

        msg = (
            "See results closer to you?\n\n"
            f"Use detected city: {detected}\n"
        )

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

        self.settings_store.save(self.settings)

    def _auto_fetch_on_start(self):
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

            if self._user_started_searching:
                return
            if detected.lower() == initial_city.lower():
                return

            if self.settings.use_detected_on_start:
                self.location.SetValue(detected)
                self.settings.last_city = detected
                self.settings_store.save(self.settings)
                self._on_get_weather(mark_user=False)
                return

            if not self.settings.ask_detected_on_start:
                return

            if not self.settings.location_prompted:
                self._prompt_use_detected_city(detected)

        wx.CallAfter(apply_detected)

    def _schedule_refetch(self, city: str, *, failed_req_id: int, delay_ms: int = 20000) -> None:
        seconds = delay_ms // 1000
        self._start_reconnect_countdown(failed_req_id=failed_req_id, seconds=seconds)

        def retry():
            current_city = self.location.GetValue().strip()

            if not self.request_state.should_retry_city(
                failed_req_id=failed_req_id,
                requested_city=city,
                current_city=current_city,
            ):
                self._hide_reconnect_status()
                return

            if not self.search_btn.IsEnabled():
                return

            self._hide_reconnect_status()
            logger.info("Auto-refetch retry req_id=%s city=%r", failed_req_id, city)
            self._on_get_weather(mark_user=False)

        wx.CallLater(delay_ms, retry)

    def _init_ui(self):
        self._apply_theme()

        main_sizer = wx.BoxSizer(wx.VERTICAL)

        top_bar = self._build_top_bar(self)
        current_panel = self._build_current_panel(self)
        self._build_forecast_strip(self)
        tabs_panel = self._build_hourly_tabs(self)
        self.tabs_panel = tabs_panel
        self._build_today_strip(self)

        main_sizer.Add(top_bar, 0, wx.EXPAND)
        main_sizer.Add(current_panel, 0, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(self.forecast_scroll, 0, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(tabs_panel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)
        main_sizer.Add(self.today_scroll, 0, wx.EXPAND | wx.ALL, 5)

        self.SetSizer(main_sizer)

    def _apply_theme(self):
        self.palette = get_palette(self.settings.theme)

        p = self.palette
        self.COL_BG = p.bg
        self.COL_TOPBAR = p.topbar
        self.COL_TOPBAR_INNER = p.topbar_inner
        self.COL_CURRENT = p.current
        self.COL_TEXT_LIGHT = p.text_light

        self.SetBackgroundColour(self.COL_BG)

        self.FONT_LOC = wx.Font(14, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        self.FONT_NOW = wx.Font(13, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        self.FONT_TEMP = wx.Font(42, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        self.FONT_DESC = wx.Font(15, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        self.FONT_META = wx.Font(11, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
    
    def _toolbar_bitmap(self, filename: str, size: tuple[int, int] = (24, 24)) -> wx.Bitmap:
        img = wx.Image(os.fspath(PNG_DIR / filename), wx.BITMAP_TYPE_PNG)
        img = img.Rescale(size[0], size[1], wx.IMAGE_QUALITY_HIGH)
        return wx.Bitmap(img)

    def _build_top_bar(self, parent: wx.Window) -> wx.Panel:
        top_bar = wx.Panel(parent, size=(-1, 50))
        self.top_bar = top_bar
        top_bar.SetBackgroundColour(self.COL_TOPBAR)

        s = wx.BoxSizer(wx.HORIZONTAL)

        self.location = wx.TextCtrl(top_bar, style=wx.TE_PROCESS_ENTER)
        self.location.SetForegroundColour(self.COL_TEXT_LIGHT)
        self.location.SetBackgroundColour(self.COL_TOPBAR_INNER)
        self.location.SetFont(self.FONT_LOC)
        self.location.Bind(wx.EVT_TEXT_ENTER, self._on_get_weather)

        search_icon_path = os.fspath(PNG_DIR / "search_icon30.png")
        self.search_btn = wx.BitmapButton(
            top_bar,
            bitmap=wx.Bitmap(search_icon_path, wx.BITMAP_TYPE_PNG),
            style=wx.NO_BORDER,
        )
        self.search_btn.SetBackgroundColour(self.COL_TOPBAR)
        self.search_btn.Bind(wx.EVT_BUTTON, self._on_get_weather)
        
        self._fav_empty_bmp = self._toolbar_bitmap("star_outline.png", size=(24, 24))
        self._fav_filled_bmp = self._toolbar_bitmap("star_filled.png", size=(24, 24))
        self.fav_btn = wx.BitmapButton(
            top_bar,
            bitmap=self._fav_empty_bmp,
            style=wx.NO_BORDER,
        )
        self.fav_btn.SetBackgroundColour(self.COL_TOPBAR)
        self.fav_btn.SetToolTip("Add / remove favorite")
        self.fav_btn.Bind(wx.EVT_BUTTON, self._on_star_click)

        settings_bmp = self._toolbar_bitmap("settings.png", size=(24, 24))
        self.settings_btn = wx.BitmapButton(
            top_bar,
            bitmap=settings_bmp,
            style=wx.NO_BORDER,
        )
        self.settings_btn.SetBackgroundColour(self.COL_TOPBAR)
        self.settings_btn.SetToolTip("Settings")
        self.settings_btn.Bind(wx.EVT_BUTTON, self._on_open_settings)

        s.Add(self.location, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 10)
        s.Add(self.search_btn, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 10)
        s.Add(self.fav_btn, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 10)
        s.Add(self.settings_btn, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 10)

        top_bar.SetSizer(s)
        return top_bar
    

    def _on_star_click(self, event: wx.CommandEvent) -> None:
        self._toggle_favorite_for_current()

    def _current_city_for_star(self) -> str:
        if self.data and getattr(self.data, "current", None) and getattr(self.data.current, "city", ""):
            return (self.data.current.city or "").strip()
        return (self.location.GetValue() or "").strip()

    def _current_display_city(self) -> str:
        if self.data and self.data.current and self.data.current.city:
            return self.data.current.city
        return (self.location.GetValue() or "").strip()

    def _set_star_state(self, filled: bool) -> None:
        if not hasattr(self, "fav_btn"):
            return
        self.fav_btn.SetBitmap(self._fav_filled_bmp if filled else self._fav_empty_bmp)
        self.fav_btn.Refresh()

    def _refresh_star_state(self) -> None:
        city = self._current_city_for_star()
        if not city:
            self._set_star_state(False)
            return
        try:
            self._set_star_state(self.storage.is_favorite(city))
        except Exception:
            self._set_star_state(False)

    def _toggle_favorite_for_current(self) -> None:
        city = self._current_city_for_star()
        if not city:
            return

        try:
            if self.storage.is_favorite(city):
                self.storage.remove_favorite(city)
            else:
                lat = getattr(self.data, "lat", None) if self.data else None
                lon = getattr(self.data, "lon", None) if self.data else None
                country = city.split(",")[-1].strip() if "," in city else None
                self.storage.add_favorite(city=city, lat=lat, lon=lon, country=country)
        finally:
            self._refresh_star_state()

    def _load_city_from_settings(self, city: str) -> None:
        city = (city or "").strip()
        if not city:
            return

        self.location.SetValue(city)
        self.settings.last_city = city
        self.settings_store.save(self.settings)
        self._on_get_weather(mark_user=False)
    
    def _apply_settings_from_dialog(self, new_settings) -> None:
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

        self.settings = new_settings
        self.settings_store.save(self.settings)

        if theme_changed:
            self._apply_theme()
            self._apply_theme_to_existing_ui()

        if animated_changed and hasattr(self, "current_panel"):
            self.current_panel.set_animated_enabled(
                getattr(self.settings, "animated_current_icon", False)
            )
            self.current_panel.Layout()
            self.current_panel.Refresh()

        if units_changed and self.location.GetValue().strip():
            self._on_get_weather(mark_user=False)
            return

        if forecast_changed and self.data:
            visible_dates = {d.date_iso for d in self.data.daily[: self.settings.forecast_days]}
            if self.selected_date not in visible_dates:
                self.selected_date = self.data.current.date_iso
                self._update_current_block(self.data)

            self._rebuild_forecast_cards(self.data.daily)
            self._refresh_hourly_strip()

            if self.settings.forecast_days > old_forecast and self.location.GetValue().strip():
                self._on_get_weather(mark_user=False)
                return

        logger.info(
            "Settings changed: forecast_days %s -> %s",
            old_forecast,
            self.settings.forecast_days,
        )

        if default_changed and not self.location.GetValue().strip():
            self.location.SetValue(self.settings.default_city)

    def _on_open_settings(self, event: wx.CommandEvent) -> None:
        if self.settings_dialog and self.settings_dialog.IsShown():
            self.settings_dialog.Close()
            return

        dlg = SettingsDialog(
            self,
            self.settings,
            repo=self.storage,
            on_load_city=self._load_city_from_settings,
            on_favorites_changed=self._refresh_star_state,
            on_apply_settings=self._apply_settings_from_dialog,
            on_close_dialog=self._on_settings_dialog_closed,
        )

        self.settings_dialog = dlg
        dlg.Show()

    def _on_settings_dialog_closed(self) -> None:
        self.settings_dialog = None
    
    def _apply_theme_to_existing_ui(self) -> None:
        p = self.palette

        self.SetBackgroundColour(self.COL_BG)

        if hasattr(self, "top_bar"):
            self.top_bar.SetBackgroundColour(self.COL_TOPBAR)

        if hasattr(self, "location"):
            self.location.SetForegroundColour(self.COL_TEXT_LIGHT)
            self.location.SetBackgroundColour(self.COL_TOPBAR_INNER)

        if hasattr(self, "search_btn"):
            self.search_btn.SetBackgroundColour(self.COL_TOPBAR)

        if hasattr(self, "fav_btn"):
            self.fav_btn.SetBackgroundColour(self.COL_TOPBAR)

        if hasattr(self, "settings_btn"):
            self.settings_btn.SetBackgroundColour(self.COL_TOPBAR)

        if hasattr(self, "current_panel"):
            self.current_panel.apply_theme(
                bg_color=self.COL_CURRENT,
                text_color=self.COL_TEXT_LIGHT,
                muted_text_color=self.COL_TEXT_LIGHT,
            )

        if hasattr(self, "forecast_scroll"):
            self.forecast_scroll.SetBackgroundColour(p.forecast_strip_bg)

        if hasattr(self, "today_scroll"):
            self.today_scroll.SetBackgroundColour(p.hourly_strip_bg)

        if hasattr(self, "forecast_cards"):
            for i, card in enumerate(self.forecast_cards):
                card.base_bg = pick_card_bg(p, i)
                card.selected_bg = p.card_selected_bg
                is_sel = getattr(card, "date_iso", None) == getattr(self, "selected_date", None)
                card.set_selected(bool(is_sel))
                card.refresh_theme()

        if hasattr(self, "hour_tiles"):
            for t in self.hour_tiles:
                t.SetBackgroundColour(p.hour_tile_bg)
                t.time_lbl.SetForegroundColour(p.hour_tile_text_muted)
                t.value_lbl.SetForegroundColour(p.hour_tile_text)
                t.Refresh()

        self.Layout()
        self.Refresh()

    def _build_current_panel(self, parent: wx.Window) -> wx.Panel:
        self.current_panel = CurrentWeatherPanel(
            parent,
            bg_color=self.COL_CURRENT,
            text_color=self.COL_TEXT_LIGHT,
            muted_text_color=self.COL_TEXT_LIGHT,
            font_now=self.FONT_NOW,
            font_temp=self.FONT_TEMP,
            font_desc=self.FONT_DESC,
            font_meta=self.FONT_META,
            animated_current_icon=getattr(self.settings, "animated_current_icon", False),
        )
        return self.current_panel

    def _show_reconnect_status(self, seconds: int) -> None:
        self.request_state.start_reconnect(seconds)
        self.current_panel.show_reconnect_status(self.request_state.reconnect_seconds)

    def _hide_reconnect_status(self) -> None:
        self.request_state.clear_reconnect()
        self.current_panel.hide_reconnect_status()

    def _start_reconnect_countdown(self, *, failed_req_id: int, seconds: int) -> None:
        self._show_reconnect_status(seconds)

        def tick():
            if not self._is_latest(failed_req_id):
                self._hide_reconnect_status()
                return

            remaining = self.request_state.tick_reconnect()
            if remaining <= 0:
                return

            self.current_panel.update_reconnect_status(remaining)
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
        if not self.data:
            return
        date_iso = self.selected_date or self.data.current.date_iso
        hourly = self._build_hourly_for_date(date_iso, self.hourly_mode)
        self._rebuild_hour_tiles(hourly, date_iso=date_iso)

    def _set_current_loading(self, is_loading: bool, *, city: str = "") -> None:
        if is_loading:
            self.search_btn.Disable()
            for b in getattr(self, "mode_buttons", {}).values():
                b.Disable()
            self.current_panel.set_loading(True, city=city)
        else:
            self.search_btn.Enable()
            for b in getattr(self, "mode_buttons", {}).values():
                b.Enable()
            if hasattr(self, "hourly_mode"):
                self._set_hourly_mode(self.hourly_mode, refresh=False)

        if hasattr(self, "tabs_panel"):
            self.tabs_panel.Disable() if is_loading else self.tabs_panel.Enable()

    def _next_request_id(self) -> int:
        return self.request_state.begin_request()

    def _is_latest(self, req_id: int) -> bool:
        return self.request_state.is_latest(req_id)

    def _call_after_if_latest(self, req_id: int, fn, *args, **kwargs):
        def runner():
            if self._is_latest(req_id):
                fn(*args, **kwargs)

        try:
            wx.CallAfter(runner)
        except Exception:
            pass

    def _on_get_weather(self, event=None, *, mark_user: bool = True):
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

                self._call_after_if_latest(local_req_id, self._hide_reconnect_status)
                self._call_after_if_latest(local_req_id, self.update_ui, data)

            except ValueError as e:
                logger.warning("Worker input error req_id=%s city=%r err=%s", local_req_id, local_city, e)
                self._call_after_if_latest(local_req_id, self.show_error, str(e))

            except (NetworkError, ProviderError) as e:
                if is_retryable_error(e):
                    logger.info("Scheduling auto-refetch due to retryable error city=%r", local_city)
                    self._call_after_if_latest(
                        local_req_id,
                        self._schedule_refetch,
                        local_city,
                        failed_req_id=local_req_id,
                    )
                else:
                    logger.error(
                        "Worker provider error req_id=%s city=%r err=%s",
                        local_req_id, local_city, e
                    )

                self._call_after_if_latest(local_req_id, self.show_error, str(e))

            finally:
                self._call_after_if_latest(local_req_id, self._set_current_loading, False)

        threading.Thread(target=work, args=(city, req_id), daemon=True).start()

    def show_error(self, msg: str):
        self.current_panel.set_error(msg, city=self._current_display_city())
        wx.MessageBox(msg, "Weather App", wx.OK | wx.ICON_ERROR)

    def _update_current_block(self, data: WeatherData, *, snapshot: CurrentSnapshot | None = None):
        view = build_current_weather_view_data(
            data=data,
            snapshot=snapshot,
            units=self.settings.units,
        )
        self.current_panel.apply_view(view)

    def _rebuild_forecast_cards(self, daily_list: list[DailyForecast]):
        view_items = build_forecast_card_view_data(
            daily_list=daily_list,
            units=self.settings.units,
            forecast_days=int(getattr(self.settings, "forecast_days", 7)),
            selected_date=self.selected_date,
            today_iso=self.data.current.date_iso if self.data else None,
        )

        for i in range(len(self.forecast_cards), len(view_items)):
            card = WeatherCard(
                self.forecast_scroll,
                bg_color=pick_card_bg(self.palette, i),
                selected_bg=self.palette.card_selected_bg,
                date_iso="",
                on_click=self._on_forecast_card_click,
                is_selected=False,
            )
            self.forecast_cards.append(card)
            self.forecast_sizer.Add(card, 0, wx.ALL, 5)

        for i, item in enumerate(view_items):
            card = self.forecast_cards[i]
            card.on_click = self._on_forecast_card_click
            card.base_bg = pick_card_bg(self.palette, i)
            card.selected_bg = self.palette.card_selected_bg
            card.apply_view(item)

            if not card.IsShown():
                card.Show()

        for j in range(len(view_items), len(self.forecast_cards)):
            self.forecast_cards[j].Hide()

        self.forecast_scroll.SetupScrolling(scroll_x=True, scroll_y=False)
        self.forecast_scroll.Layout()

    def _build_hourly_for_date(self, date_iso: str, mode: HourlyMode = DEFAULT_MODE) -> dict:
        if not self.data:
            return {
                "labels": [],
                "hours_int": [],
                "values": [],
                "codes": [],
                "time_isos": [],
                "nights": [],
                "pivot_index": None,
            }

        series = self.data.hourly
        today_iso = self.data.current.date_iso
        current_time_iso = self.data.current.time_iso

        day = next((d for d in self.data.daily if d.date_iso == date_iso), None)
        sunrise_iso = day.sunrise_iso if day else None
        sunset_iso = day.sunset_iso if day else None

        out = series.build_day(
            date_iso,
            mode=mode,
            today_iso=today_iso,
            current_time_iso=current_time_iso,
        )

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
        out["sunset_hour"] = _hour_from_iso(sunset_iso)
        out["sunrise_iso"] = sunrise_iso
        out["sunset_iso"] = sunset_iso

        return out

    def _rebuild_hour_tiles(self, hourly: dict, date_iso: str | None):
        self.today_scroll.Freeze()
        try:
            if not self.data:
                return

            today_iso = self.data.current.date_iso
            if date_iso is None:
                date_iso = today_iso

            strip = build_hour_strip_view_data(
                hourly=hourly,
                mode=self.hourly_mode,
                units=self.settings.units,
                date_iso=date_iso,
                today_iso=today_iso,
            )

            if not strip.items:
                for t in self.hour_tiles:
                    t.Hide()
                self.today_scroll.SetupScrolling(scroll_x=True, scroll_y=False)
                self.today_scroll.Layout()
                return

            needed = len(strip.items)

            for i in range(len(self.hour_tiles), needed):
                tile = HourTile(
                    self.today_scroll,
                    bg_color=self.palette.hour_tile_bg,
                    text_color=self.palette.hour_tile_text,
                    muted_text_color=self.palette.hour_tile_text_muted,
                )
                self.hour_tiles.append(tile)
                self.today_sizer.Add(tile, 0, wx.ALL, 6)

            for i, item in enumerate(strip.items):
                tile = self.hour_tiles[i]
                tile.apply_view(item)

                if not tile.IsShown():
                    tile.Show()

            for j in range(needed, len(self.hour_tiles)):
                self.hour_tiles[j].Hide()

            self.today_scroll.SetupScrolling(scroll_x=True, scroll_y=False)
            self.today_scroll.Layout()

            if today_iso and date_iso == today_iso:
                self.today_scroll.Scroll(0, 0)
            elif strip.scroll_to_index is not None and 0 <= strip.scroll_to_index < needed:
                wx.CallAfter(self.today_scroll.ScrollChildIntoView, self.hour_tiles[strip.scroll_to_index])
            else:
                self.today_scroll.Scroll(0, 0)

        finally:
            self.today_scroll.Thaw()

    def _make_current_for_date(self, date_iso: str) -> CurrentSnapshot | None:
        if not self.data:
            return None

        today_iso = self.data.current.date_iso
        if date_iso == today_iso:
            return self.data.current

        selected_day = next((d for d in self.data.daily if d.date_iso == date_iso), None)
        if not selected_day:
            return None

        snap = self.data.hourly.snapshot_for_date(date_iso, target_hour=15, strategy="peak_temp")

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
        if not self.data:
            return

        self.selected_date = date_iso

        snap = self._make_current_for_date(date_iso)
        if not snap:
            return

        self._update_current_block(self.data, snapshot=snap)

        hourly_for_day = self._build_hourly_for_date(date_iso, self.hourly_mode)
        self._rebuild_hour_tiles(hourly_for_day, date_iso=date_iso)

        for card in self.forecast_cards:
            card.set_selected(card.date_iso == date_iso)

    def update_ui(self, data: WeatherData):
        self.Freeze()
        try:
            self.data = data

            try:
                city = (data.current.city or "").strip()
                if city:
                    self.storage.add_history(city=city, lat=data.lat, lon=data.lon)
            except Exception:
                logger.exception("Failed to write search history")

            today_iso = data.current.date_iso
            self.selected_date = today_iso

            self._refresh_star_state()
            self._update_current_block(data)
            self._rebuild_forecast_cards(data.daily)
            self._set_hourly_mode(DEFAULT_MODE, refresh=True)
            self.Layout()
        finally:
            self.Thaw()