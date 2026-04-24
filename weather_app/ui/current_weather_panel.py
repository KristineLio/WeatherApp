from __future__ import annotations

import wx
import wx.adv

from weather_app.utils.icons import get_icon_bitmap, get_anim
from weather_app.ui.current_weather_presenter import CurrentWeatherViewData


class CurrentWeatherPanel(wx.Panel):
    def __init__(
        self,
        parent: wx.Window,
        *,
        bg_color: wx.Colour,
        text_color: wx.Colour,
        muted_text_color: wx.Colour,
        font_now: wx.Font,
        font_temp: wx.Font,
        font_desc: wx.Font,
        font_meta: wx.Font,
        animated_current_icon: bool = False,
    ):
        super().__init__(parent, size=(-1, 220))

        self._bg_color = bg_color
        self._text_color = text_color
        self._muted_text_color = muted_text_color
        self._font_now = font_now
        self._font_temp = font_temp
        self._font_desc = font_desc
        self._font_meta = font_meta
        self._animated_current_icon = animated_current_icon

        self._cur_icon_png: str | None = None
        self._cur_icon_gif: str | None = None
        self.current_icon_ctrl: wx.Window | None = None

        self._build_ui()
        self.apply_theme(
            bg_color=bg_color,
            text_color=text_color,
            muted_text_color=muted_text_color,
        )

    def _style_label(self, lbl: wx.StaticText, font: wx.Font, colour: wx.Colour) -> None:
        lbl.SetFont(font)
        lbl.SetForegroundColour(colour)

    def _build_metric_label(self, text: str) -> wx.StaticText:
        lbl = wx.StaticText(self, label=text)
        self._style_label(lbl, self._font_meta, self._text_color)
        return lbl

    def _build_ui(self) -> None:
        self.SetBackgroundColour(self._bg_color)

        root = wx.BoxSizer(wx.VERTICAL)

        self.now_label = wx.StaticText(self, label="Now")
        self._style_label(self.now_label, self._font_now, self._muted_text_color)

        main_row = wx.BoxSizer(wx.HORIZONTAL)
        left_col = wx.BoxSizer(wx.VERTICAL)
        right_col = wx.BoxSizer(wx.VERTICAL)

        left_col.SetMinSize((220, -1))

        self.temp_label = wx.StaticText(self, label="--")
        self._style_label(self.temp_label, self._font_temp, self._text_color)

        self.icon_host = wx.Panel(self)
        self.icon_host.SetBackgroundColour(self._bg_color)
        self.icon_host_sizer = wx.BoxSizer(wx.VERTICAL)
        self.icon_host.SetSizer(self.icon_host_sizer)

        self.current_icon_ctrl = wx.StaticBitmap(
            self.icon_host,
            bitmap=get_icon_bitmap("unknown.png", size=(60, 60)),
        )
        self.icon_host_sizer.Add(self.current_icon_ctrl, 0, wx.ALIGN_LEFT)

        self.desc_label = wx.StaticText(self, label=" ", style=wx.ALIGN_CENTER)
        self._style_label(self.desc_label, self._font_desc, self._text_color)

        self.status_label = wx.StaticText(self, label="")
        self.status_label.SetForegroundColour(self._muted_text_color)
        base_font = self.desc_label.GetFont()
        self.status_label.SetFont(
            wx.Font(
                max(8, base_font.GetPointSize() - 1),
                base_font.GetFamily(),
                base_font.GetStyle(),
                base_font.GetWeight(),
            )
        )
        self.status_label.Hide()

        self.retry_btn = wx.Button(self, label="Retry")
        self.retry_btn.Hide()

        self.precip_label = self._build_metric_label("Precipitation: —")
        self.humidity_label = self._build_metric_label("Humidity: —")
        self.wind_label = self._build_metric_label("Wind: —")
        self.feels_label = self._build_metric_label("Feels like —")

        self.city_label = wx.StaticText(self, label="")
        self._style_label(self.city_label, self._font_meta, self._muted_text_color)

        left_col.Add(self.temp_label, 0, wx.BOTTOM, 2)
        left_col.Add(self.icon_host, 0, wx.BOTTOM, 4)

        right_col.Add(self.desc_label, 0, wx.EXPAND | wx.BOTTOM, 6)
        right_col.Add(self.status_label, 0, wx.EXPAND | wx.BOTTOM, 6)
        right_col.Add(self.retry_btn, 0, wx.TOP | wx.BOTTOM, 4)
        right_col.Add(self.precip_label, 0, wx.EXPAND | wx.BOTTOM, 2)
        right_col.Add(self.humidity_label, 0, wx.EXPAND | wx.BOTTOM, 2)
        right_col.Add(self.wind_label, 0, wx.EXPAND | wx.BOTTOM, 2)
        right_col.Add(self.feels_label, 0, wx.EXPAND)

        main_row.Add(left_col, 0, wx.RIGHT, 20)
        main_row.Add(right_col, 1, wx.EXPAND)

        bottom_row = wx.BoxSizer(wx.HORIZONTAL)
        bottom_row.Add(self.city_label, 1)

        root.Add(self.now_label, 0, wx.ALL, 10)
        root.Add(main_row, 1, wx.LEFT | wx.RIGHT, 10)
        root.Add(bottom_row, 0, wx.EXPAND | wx.ALL, 10)

        self.SetSizer(root)

    def set_retry_callback(self, callback) -> None:
        self.retry_btn.Bind(wx.EVT_BUTTON, lambda event: callback())

    def _replace_icon_ctrl(self, ctrl: wx.Window) -> None:
        if self.current_icon_ctrl is not None:
            self.current_icon_ctrl.Destroy()

        self.icon_host_sizer.Clear(delete_windows=False)
        self.current_icon_ctrl = ctrl
        self.icon_host_sizer.Add(ctrl, 0, wx.ALIGN_LEFT)
        self.icon_host.Layout()

    def _show_loading_animation(self) -> None:
        ctrl = wx.adv.AnimationCtrl(self.icon_host)
        ctrl.SetAnimation(get_anim("loading.gif"))
        ctrl.Play()
        self._replace_icon_ctrl(ctrl)

    def _set_current_icon(self, *, icon_png: str, icon_gif: str | None = None) -> None:
        want_anim = bool(self._animated_current_icon)
        is_anim = isinstance(self.current_icon_ctrl, wx.adv.AnimationCtrl)

        if want_anim != is_anim:
            if want_anim:
                ctrl = wx.adv.AnimationCtrl(self.icon_host)
                ctrl.SetAnimation(get_anim(icon_gif or "unknown.gif"))
                ctrl.Play()
                self._replace_icon_ctrl(ctrl)
            else:
                ctrl = wx.StaticBitmap(
                    self.icon_host,
                    bitmap=get_icon_bitmap(icon_png, size=(60, 60)),
                )
                self._replace_icon_ctrl(ctrl)
            return

        if want_anim and isinstance(self.current_icon_ctrl, wx.adv.AnimationCtrl):
            self.current_icon_ctrl.SetAnimation(get_anim(icon_gif or "unknown.gif"))
            self.current_icon_ctrl.Play()
        elif isinstance(self.current_icon_ctrl, wx.StaticBitmap):
            self.current_icon_ctrl.SetBitmap(get_icon_bitmap(icon_png, size=(60, 60)))

    def apply_view(self, view: CurrentWeatherViewData) -> None:
        self._cur_icon_png = view.icon_png
        self._cur_icon_gif = view.icon_gif

        self.now_label.SetLabel(view.header_text)
        self.temp_label.SetLabel(view.temp_text)
        self.desc_label.SetLabel(view.desc_text)
        self.city_label.SetLabel(view.city_text)
        self.feels_label.SetLabel(view.feels_text)
        self.precip_label.SetLabel(view.precip_text)
        self.humidity_label.SetLabel(view.humidity_text)
        self.wind_label.SetLabel(view.wind_text)

        self.desc_label.SetForegroundColour(self._text_color)
        self.status_label.Hide()
        self.retry_btn.Hide()
        self._set_current_icon(icon_png=view.icon_png, icon_gif=view.icon_gif)

        self.Layout()
        self.Refresh()

    def _set_metric_placeholders(self) -> None:
        self.feels_label.SetLabel("Feels like —")
        self.precip_label.SetLabel("Precipitation: —")
        self.humidity_label.SetLabel("Humidity: —")
        self.wind_label.SetLabel("Wind: —")

    def set_loading(self, is_loading: bool, *, city: str = "") -> None:
        if is_loading:
            self.status_label.Hide()
            self.retry_btn.Hide()
            self.now_label.SetLabel("Now")
            self.temp_label.SetLabel("")
            self.desc_label.SetForegroundColour(self._text_color)
            self.desc_label.SetLabel("Fetching weather data…")
            self.city_label.SetLabel(city or "")

            self._set_metric_placeholders()
            self._show_loading_animation()

        self.Layout()
        self.Refresh()

    def set_error(self, msg: str, *, city: str = "", show_retry: bool = False) -> None:
        self.status_label.Hide()
        self.retry_btn.Show(show_retry)

        self.temp_label.SetLabel("—")
        self.desc_label.SetForegroundColour(self._text_color)
        self.desc_label.SetLabel(msg)
        self.city_label.SetLabel(city or "")

        self._set_metric_placeholders()
        self._set_current_icon(icon_png="unknown.png", icon_gif="unknown.gif")

        self.Layout()
        self.Refresh()
    
    def show_reconnect_status(self, seconds: int) -> None:
        self._show_loading_animation()
        self.temp_label.SetLabel("")
        self.desc_label.SetForegroundColour(self._muted_text_color)
        self.desc_label.SetLabel("Reconnecting…")
        self.status_label.Show()
        self.status_label.SetLabel(f"Retrying automatically in {seconds}s")
        self.retry_btn.Hide()
        self.Layout()
        self.Refresh()
        self.Update()

    def update_reconnect_status(self, seconds: int) -> None:
        self.status_label.SetLabel(f"Retrying automatically in {seconds}s")
        self.Layout()
        self.Refresh()

    def hide_reconnect_status(self) -> None:
        self.status_label.Hide()
        self.Layout()
        self.Refresh()

    def set_animated_enabled(self, enabled: bool) -> None:
        self._animated_current_icon = enabled
        if self._cur_icon_png:
            self._set_current_icon(
                icon_png=self._cur_icon_png,
                icon_gif=self._cur_icon_gif,
            )

    def apply_theme(
        self,
        *,
        bg_color: wx.Colour,
        text_color: wx.Colour,
        muted_text_color: wx.Colour,
    ) -> None:
        self._bg_color = bg_color
        self._text_color = text_color
        self._muted_text_color = muted_text_color

        self.SetBackgroundColour(bg_color)
        self.icon_host.SetBackgroundColour(bg_color)

        self.now_label.SetForegroundColour(muted_text_color)
        self.temp_label.SetForegroundColour(text_color)
        self.desc_label.SetForegroundColour(text_color)
        self.city_label.SetForegroundColour(muted_text_color)
        self.status_label.SetForegroundColour(muted_text_color)
        self.precip_label.SetForegroundColour(text_color)
        self.humidity_label.SetForegroundColour(text_color)
        self.wind_label.SetForegroundColour(text_color)
        self.feels_label.SetForegroundColour(text_color)

        self.Refresh()