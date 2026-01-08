import wx
import os
import requests
import logging
import threading
import datetime as dt
import wx.lib.scrolledpanel as scrolled
from dataclasses import dataclass
from typing import Callable, Any, Literal
from enum import Enum

from weather_app.utils.paths import ASSETS_DIR
from weather_app.utils.icons import get_icon_bitmap, code_to_label_icon
from weather_app.utils.icons import WEATHERCODE_MAP, PRECIP_ICONS, WIND_ICONS, HUMIDITY_ICONS
from weather_app.utils.icons import _pick_icon_by_threshold


logger = logging.getLogger(__name__)

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
_GEO_TIMEOUT = 7
_FORECAST_TIMEOUT = 10


class HourlyMode(Enum):  #MetricMode
    """Weather metric display modes."""
    TEMPERATURE = "temperature"
    PRECIPITATION = "precip"
    WIND = "wind"
    HUMIDITY = "humidity"


@dataclass(frozen=True)
class ModeMeta:
    """Metadata for a weather metric display mode."""
    key: str
    tab_label: str
    unit: str
    fmt: Callable[[float | None], str]                   # value -> string
    icon: Callable[[float | None, int | None], str]      # (value, code) -> filename
    values: Callable[["HourlySeries"], list[float | None]]  # HourlySeries -> list of values
    current_value: Callable[["CurrentSnapshot"], float | None]  # curSnap-> metric value


def _fmt_temp(v: float | None) -> str:      return f"{round(v)}°C" if v is not None else "—"

def _fmt_percent(v: float | None) -> str:   return f"{int(v)}%" if v is not None else "—"

def _fmt_wind(v: float | None) -> str:      return f"{round(v)} km/h" if v is not None else "—"

def _icon_temp(v: float | None, code: int | None) -> str:   
    return code_to_label_icon(code or 0)[1] if code is not None else "unknown.png"

def _icon_precip(v: float | None, code: int | None) -> str:
    return _pick_icon_by_threshold(v, PRECIP_ICONS, "precip_unknown.png")

def _icon_wind(v: float | None, code: int | None) -> str:
    return _pick_icon_by_threshold(v, WIND_ICONS, "wind_unknown.png")

def _icon_humidity(v: float | None, code: int | None) -> str:
    return _pick_icon_by_threshold(v, HUMIDITY_ICONS, "hum_unknown.png")


MODE_META: dict[HourlyMode, ModeMeta] = {
    HourlyMode.TEMPERATURE: ModeMeta(
        key="temperature",
        tab_label="Temperature",
        unit="°C",
        fmt=_fmt_temp,
        icon=_icon_temp,
        values=lambda s: s.temp,
        current_value=lambda cur: cur.temp,
    ),
    HourlyMode.PRECIPITATION: ModeMeta(
        key="precip",
        tab_label="Precipitation",
        unit="%",
        fmt=_fmt_percent,
        icon=_icon_precip,
        values=lambda s: s.precip,
        current_value=lambda cur: cur.precip,
    ),
    HourlyMode.WIND: ModeMeta(
        key="wind",
        tab_label="Wind",
        unit="km/h",
        fmt=_fmt_wind,
        icon=_icon_wind,
        values=lambda s: s.wind,
        current_value=lambda cur: cur.wind,
    ),
    HourlyMode.HUMIDITY: ModeMeta(
        key="humidity",
        tab_label="Humidity",
        unit="%",
        fmt=_fmt_percent,
        icon=_icon_humidity,
        values=lambda s: s.humidity,
        current_value=lambda cur: cur.humidity,
    ),
}

DEFAULT_MODE = HourlyMode.TEMPERATURE

def get_mode_meta(mode: HourlyMode) -> ModeMeta:
    """Get metadata for a given metric mode."""
    return MODE_META.get(mode, MODE_META[DEFAULT_MODE])


def format_value(mode: HourlyMode, value: float | None) -> str:
    """Format a value according to its mode."""
    return get_mode_meta(mode).fmt(value)


def icon_for(mode: HourlyMode, value: float | None, code: int | None) -> str:
    """Get icon filename for a value in a given mode."""
    return get_mode_meta(mode).icon(value, code)


def set_current_metric(label: wx.StaticText, mode: HourlyMode, snapshot: "CurrentSnapshot") -> None:
    """Set label text for a current metric."""
    meta = get_mode_meta(mode)
    v = meta.current_value(snapshot)
    label.SetLabel(f"{meta.tab_label}: {meta.fmt(v)}")

# ============================================================================
# Date/Time Formatting
# ============================================================================

def _format_date(date_iso: str, pattern: str) -> str:
    d = dt.date.fromisoformat(date_iso)
    return d.strftime(pattern)

def weekday_from_iso(date_str: str) -> str:
    # "2025-09-23" -> "Tue"
    return _format_date(date_str, "%a")

def format_full_date(date_iso: str) -> str:
    # "2025-12-30" -> "Tuesday 30 Dec"
    return _format_date(date_iso, "%A, %d %b")  #b Dec, B December

def pick_bg(i: int):
    # Simple rotating palette for cards
    colors = [
        wx.Colour(0, 200, 200), wx.Colour(255, 100, 150),
        wx.Colour(255, 180, 50), wx.Colour(100, 200, 255),
        wx.Colour(120, 160, 255), wx.Colour(200, 120, 255),
        wx.Colour(80, 180, 120),
    ]
    return colors[i % len(colors)]

def _format_hour_label(hour_int: int) -> str:
    t = dt.time(hour=hour_int)
    try:
        return t.strftime("%-I %p")   # Unix
    except ValueError:
        return t.strftime("%I %p").lstrip("0")  # Windows

def _set_label_for_value(
    label: wx.StaticText,
    prefix: str,
    value,
    *,
    fmt=str,
    suffix: str = ""
) -> None:
    if value is None:
        label.SetLabel(f"{prefix}—")
    else:
        label.SetLabel(f"{prefix}{fmt(value)}{suffix}")

@dataclass(frozen=True)    
class HourlySeries:
    """Immutable container for hourly forecast data."""
    time: list[str]
    temp: list[float | None]
    code: list[int | None]
    feels_like: list[float | None]
    humidity: list[int | None]
    precip: list[int | None]
    wind: list[float | None]

    @classmethod
    def from_api(cls, hourly: dict) -> "HourlySeries":
        """Build HourlySeries from Open-Meteo API hourly block."""
        return cls(
            time=hourly.get("time") or [],
            temp=hourly.get("temperature_2m") or [],
            code=hourly.get("weathercode") or [],
            feels_like=hourly.get("apparent_temperature") or [],
            humidity=hourly.get("relativehumidity_2m") or [],
            precip=hourly.get("precipitation_probability") or [],
            wind=hourly.get("windspeed") or [],
        )

    # helper to safely get value at index or None, Guard lengths (API weirdness)
    def _at(self, arr: list, i: int):
        return arr[i] if 0 <= i < len(arr) else None

    def _index_for_iso_hour(self, iso_hour: str) -> int | None:
        try:
            return self.time.index(iso_hour)
        except ValueError:
            return None
    
    def derive_current_extras(self, current_time_iso: str | None):
        """
        Extract (feels_like, humidity, precip, wind) for current time.
        
        Given current_time_iso like '2025-12-23T12:50', finds '2025-12-23T12:00'.
        """
        if not current_time_iso:
            return None, None, None, None

        # "2025-12-23T12:50" -> want "2025-12-23T12:00"
        date, tm = current_time_iso.split("T")
        hour = tm[:2]
        target = f"{date}T{hour}:00"

        idx = self._index_for_iso_hour(target)
        if idx is None:
            return None, None, None, None

        return (
            self._at(self.feels_like, idx),
            self._at(self.humidity, idx),
            self._at(self.precip, idx),
            self._at(self.wind, idx),
        )

    def snapshot_for_date(
        self,
        date_iso: str,
        *,
        target_hour: int = 15,
        strategy: str = "peak_temp",  # "peak_temp" | "target_hour"
    ) -> dict | None:
        """
        Get representative hourly snapshot for a date.
        
        Returns dict with: time, temp, code, feels_like, humidity, precip, windspeed
        """
        # collect indices for this date
        day_idxs: list[int] = []
        for i, tstr in enumerate(self.time):
            if tstr.startswith(date_iso):
                day_idxs.append(i)

        if not day_idxs:
            return None

        target_idx = None

        if strategy == "peak_temp":
            # pick index with max temp (ignore None)
            best_i = None
            best_temp = None
            for i in day_idxs:
                t = self._at(self.temp, i)
                if t is None:
                    continue
                if best_temp is None or t > best_temp:
                    best_temp = t
                    best_i = i
            target_idx = best_i  # may remain None if all temps missing

        if target_idx is None:
            # try target_hour (e.g. 15:00)
            for i in day_idxs:
                _, time_part = self.time[i].split("T")
                if int(time_part[:2]) == target_hour:
                    target_idx = i
                    break

        if target_idx is None:
            target_idx = day_idxs[0]  # fallback: first available hour

        return {
            "time": self._at(self.time, target_idx),
            "temp": self._at(self.temp, target_idx),
            "code": self._at(self.code, target_idx),
            "feels_like": self._at(self.feels_like, target_idx),
            "humidity": self._at(self.humidity, target_idx),
            "precip": self._at(self.precip, target_idx),
            "windspeed": self._at(self.wind, target_idx),
        }
        
    def build_day(self, date_iso: str, *, mode: HourlyMode, today_iso: str | None, current_time_iso: str | None) -> dict:
        """
        Build hourly data for a specific date.
        
        Returns: {"labels", "hours_int", "values", "codes", "pivot_index"}
        """
        meta = get_mode_meta(mode)
        values_src = meta.values(self)

        labels: list[str] = []
        hours_ints: list[int] = []
        values: list[Any] = []
        clist: list[Any] = []
        pivot_index = None

        current_hour_int = None
        if today_iso and current_time_iso:
            try:
                current_hour_int = int(current_time_iso.split("T")[1][:2])
            except Exception:
                current_hour_int = None

        for tstr, val, code in zip(self.time, values_src, self.code):
            day_part, time_part = tstr.split("T")
            if day_part != date_iso:
                continue

            hour_int = int(time_part[:2])
            label = _format_hour_label(hour_int)

            if (
                date_iso == today_iso
                and current_hour_int is not None
                and pivot_index is None
                and hour_int == current_hour_int
            ):
                pivot_index = len(labels)

            labels.append(label)
            hours_ints.append(hour_int)
            values.append(val)
            clist.append(code)

        return {
            "labels": labels,
            "hours_int": hours_ints,
            "values": values,
            "codes": clist,
            "pivot_index": pivot_index,
        }

@dataclass(frozen=True)
class CurrentSnapshot:
    """Current weather conditions snapshot."""
    temp: float | None
    code: int | None
    feels_like: float | None
    humidity: float | None
    precip: float | None
    wind: float | None
    date_iso: str | None          # "YYYY-MM-DD"
    time_iso: str | None          # "YYYY-MM-DDTHH:MM"
    city: str                     # display city string (e.g. "Sofia, BG")

@dataclass(frozen=True)
class DailyForecast:
    """Daily forecast summary."""
    date_iso: str
    weekday: str
    tmin: float | None
    tmax: float | None
    code: int | None
    # optional later: precip_sum, wind_max, etc.

@dataclass(frozen=True)
class WeatherData:
    """Complete weather data for a location."""
    current: CurrentSnapshot
    daily: list[DailyForecast]
    hourly: HourlySeries
    lat: float
    lon: float

# ============================================================================
# Weather Service
# ============================================================================

class WeatherService:
    """
    Pure networking + parsing service.

    - No wx usage
    - No threading
    - Deterministic inputs/outputs (easy to unit test)
    """

    def __init__(
        self,
        *,
        geo_url: str = GEO_URL,
        forecast_url: str = FORECAST_URL,
        geo_timeout: int = _GEO_TIMEOUT,
        forecast_timeout: int = _FORECAST_TIMEOUT,
        session: requests.Session | None = None,
    ):
        self._geo_url = geo_url
        self._forecast_url = forecast_url
        self._geo_timeout = geo_timeout
        self._forecast_timeout = forecast_timeout
        self._session = session or requests.Session()

    # ---------- public API ----------

    def detect_city(self) -> str | None:
        """
        Try to detect user city from public IP.
        Returns city string or None on failure.
        """
        try:
            r = self._session.get("https://ipapi.co/json/", timeout=5)
            r.raise_for_status()
            data = r.json()
            return data.get("city")
        except Exception:
            return None

    def fetch(self, city: str) -> WeatherData:
        """
        Fetch weather for a city and return a fully built WeatherData domain object.
        Raises RuntimeError / ValueError with user-friendly messages.
        """
        city = (city or "").strip() or "Sofia"
        logger.info("Fetch weather start city=%r", city)
        try:
            lat, lon, resolved_name, country = self._geocode_city(city)
            logger.debug("Geocoded city=%r -> lat=%s lon=%s resolved=%r country=%r", city, lat, lon, resolved_name, country)

            forecast = self._get_json(
                self._forecast_url,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current_weather": True,
                    "daily": "temperature_2m_max,temperature_2m_min,weathercode",
                    "hourly": (
                        "temperature_2m,weathercode,apparent_temperature,windspeed,"
                        "relativehumidity_2m,precipitation_probability"
                    ),
                    "timezone": "auto",
                },
                timeout=self._forecast_timeout,
            )

            current = forecast.get("current_weather") or {}
            daily = forecast.get("daily") or {}
            hourly = forecast.get("hourly") or {}

            if "time" not in current:
                raise RuntimeError("Unexpected API response: missing current time.")
            if "time" not in daily or "time" not in hourly:
                raise RuntimeError("Unexpected API response: missing daily/hourly time arrays.")

            days = self._parse_daily(daily)

            current_time_iso = current.get("time")
            current_date_iso = current_time_iso.split("T")[0] if current_time_iso else None

            hourly_series = HourlySeries.from_api(hourly)
            current_feels, current_hum, current_precip, current_wind = (
                hourly_series.derive_current_extras(current_time_iso)
            )

            display_city = f"{resolved_name}, {country}" if country else resolved_name

            cur = CurrentSnapshot(
                temp=current.get("temperature"),
                code=current.get("weathercode"),
                feels_like=current_feels,
                humidity=current_hum,
                precip=current_precip,
                wind=current_wind,
                date_iso=current_date_iso,
                time_iso=current_time_iso,
                city=display_city,
            )

            wd = WeatherData(
                current=cur,
                daily=days,
                hourly=hourly_series,
                lat=lat,
                lon=lon,
            )

            logger.info(
                "Fetch weather success city=%r resolved=%r lat=%s lon=%s",
                city, wd.current.city, lat, lon
            )

            return wd
        except Exception:
            logger.exception("Fetch weather failed city=%r", city)
            raise    
    # ---------- internal helpers ----------

    def _get_json(self, url: str, *, params: dict | None = None, timeout: int = 10) -> dict:
        """HTTP GET → JSON with consistent errors."""
        try:
            logger.debug("HTTP GET %s params=%s timeout=%s", url, params, timeout)
            r = self._session.get(url, params=params, timeout=timeout)
            r.raise_for_status()
            return r.json()

        except requests.exceptions.Timeout:
            logger.exception("Timeout calling %s params=%s timeout=%s", url, params, timeout)
            raise RuntimeError("Network timeout while contacting weather service.")

        except requests.exceptions.HTTPError as e:
            status = getattr(e.response, "status_code", "unknown")
            logger.exception("HTTP error calling %s (HTTP %s) params=%s", url, status, params)
            raise RuntimeError(f"Weather service error (HTTP {status}).")

        except ValueError:
            logger.exception("Invalid JSON from %s params=%s", url, params)
            raise RuntimeError("Weather service returned invalid JSON.")

        except requests.RequestException:
            logger.exception("Request error calling %s params=%s", url, params)
            raise RuntimeError("Network error while contacting weather service.")

    def _geocode_city(self, city: str) -> tuple[float, float, str, str]:
        """Return (lat, lon, resolved_name, country). Raise ValueError if not found."""
        geo = self._get_json(
            self._geo_url,
            params={"name": city, "count": 1, "language": "en", "format": "json"},
            timeout=self._geo_timeout,
        )
        results = geo.get("results") or []
        if not results:
            raise ValueError("City not found. Please try another name.")
        r0 = results[0]
        return (
            r0["latitude"],
            r0["longitude"],
            r0.get("name", city),
            r0.get("country", ""),
        )

    def _parse_daily(self, daily: dict) -> list[DailyForecast]:
        times = daily.get("time") or []
        tmaxs = daily.get("temperature_2m_max") or []
        tmins = daily.get("temperature_2m_min") or []
        codes = daily.get("weathercode") or []

        n = min(len(times), len(tmaxs), len(tmins), len(codes))
        out: list[DailyForecast] = []
        for i in range(n):
            date_iso = times[i]
            out.append(
                DailyForecast(
                    date_iso=date_iso,
                    weekday=weekday_from_iso(date_iso),
                    tmax=tmaxs[i],
                    tmin=tmins[i],
                    code=codes[i],
                )
            )
        return out
    
# ============================================================================
# UI Components
# ============================================================================

class WeatherCard(wx.Panel):
    """Forecast card for daily weather summary."""
    SIZE = (120, 160)

    def __init__(
        self,
        parent,
        day: str,
        tmax: float,
        tmin: float,
        icon_file: str,
        bg_color: wx.Colour,
        date_iso: str,
        on_click,
        is_selected: bool = False,
    ):
        super().__init__(parent, size=self.SIZE)

        self.date_iso = date_iso
        self.on_click = on_click

        self.base_bg = bg_color
        self.selected_bg = wx.Colour(80, 110, 180)
        self.is_selected = None  # will be set by set_selected()

        # --- build UI ---
        self._build_ui(day, tmax, tmin, icon_file)

        # --- interactions ---
        self._bind_click_recursive(self)

        # --- initial visual state ---
        self.set_selected(is_selected)

    def _build_ui(self, day: str, tmax: float, tmin: float, icon_file: str):
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

        self.max_text = wx.StaticText(self.temps_panel, label=f"{round(tmax)}°")
        self.max_text.SetFont(wx.Font(12, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        self.max_text.SetForegroundColour(wx.WHITE)

        self.min_text = wx.StaticText(self.temps_panel, label=f"/{round(tmin)}°")
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

    def update_content(self, *, day=None, tmax=None, tmin=None, icon_file=None):
        """Optional helper to reuse cards instead of destroying them."""
        if day is not None:
            self.day_text.SetLabel(day)
        if tmax is not None:
            self.max_text.SetLabel(f"{round(tmax)}°")
        if tmin is not None:
            self.min_text.SetLabel(f"/{round(tmin)}°")
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

class WeatherApp(wx.Frame):
    def __init__(self, parent, title):
        super().__init__(parent, title=title, size=(420, 700))

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
        Runs once on app start: detect city from IP and trigger initial fetch.
        Runs in a background thread so the UI doesn't freeze.
        """

        city = self.service.detect_city() or "Sofia"

        # Update UI + trigger fetch on the main thread
        wx.CallAfter(lambda: (self.location.SetValue(city), self._on_get_weather()))
        
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
        # Centralize colors so you can tweak the whole app quickly
        self.COL_BG = wx.Colour(183, 210, 230)
        self.COL_TOPBAR = wx.Colour(50, 50, 100)
        self.COL_TOPBAR_INNER = wx.Colour(70, 70, 120)
        self.COL_CURRENT = wx.Colour(90, 120, 255)
        self.COL_TEXT_LIGHT = wx.WHITE

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
        self.temp_label = wx.StaticText(current_panel, label="-°C")
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
        if not self.search_btn.IsEnabled():
            return
        
        city = self.location.GetValue().strip()
        if not city:
            return

        req_id = self._next_request_id()
        
        self._set_current_loading(True, city=city)
        
        def work(local_city: str, local_req_id: int):
            logger.info("Worker start req_id=%s city=%r", local_req_id, local_city)
            try:
                data = self.service.fetch(local_city)
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

        self.temp_label.SetLabel(f"{round(temp)}°C" if temp is not None else "—°C")
        self.desc_label.SetLabel(label)
        self.city_label.SetLabel(cur.city)

        self.current_icon.SetBitmap(get_icon_bitmap(icon_file, size=(60, 60)))

        # feels like (keep as-is or also move into MODE_META later)
        _set_label_for_value(self.feels_label, "Feels like : ", cur.feels_like, fmt=lambda v: round(v), suffix="°",)
        
        # right side metrics (mode-driven)
        set_current_metric(self.precip_label,   HourlyMode.PRECIPITATION, cur)
        set_current_metric(self.humidity_label, HourlyMode.HUMIDITY, cur)
        set_current_metric(self.wind_label,     HourlyMode.WIND, cur)
  
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
                tmax=0,
                tmin=0,
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
            card.update_content(
                day=d.weekday,
                tmax=d.tmax,
                tmin=d.tmin,
                icon_file=icon_file_d,
            )
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
                tile = HourTile(self.today_scroll, time_label="", mode=DEFAULT_MODE, value=None, code=None)
                self.hour_tiles.append(tile)
                self.today_sizer.Add(tile, 0, wx.ALL, 6)

            # 2) update existing tiles
            for i in range(needed):
                tile = self.hour_tiles[i]
                tile.update_content(time_label=hours[i], mode=mode, value=values[i], code=codes[i])
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


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,  # change to DEBUG when you want more details
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    app = wx.App()
    WeatherApp(None, title="Weather App")
    app.MainLoop()
