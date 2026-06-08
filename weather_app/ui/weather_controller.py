from __future__ import annotations

from dataclasses import dataclass

from weather_app.domain.models import CurrentSnapshot, WeatherData
from weather_app.domain.modes import DEFAULT_MODE, HourlyMode
from weather_app.domain.settings import Settings
from weather_app.services.settings_store import SettingsStore
from weather_app.services.storage import StorageRepo
from weather_app.utils.formatters import is_night


@dataclass(frozen=True)
class SettingsChangePlan:
    theme_changed: bool
    units_changed: bool
    forecast_changed: bool
    default_changed: bool
    animated_changed: bool
    old_forecast_days: int


class WeatherController:
    """
    Non-wx app coordination logic used by WeatherApp.

    The frame still owns widgets and rendering. This class handles small pieces
    of state/business logic that are easy to unit test.
    """

    def __init__(self, *, storage: StorageRepo, settings_store: SettingsStore) -> None:
        self.storage = storage
        self.settings_store = settings_store

    # ---------- startup / settings ----------

    def initial_city(self, settings: Settings) -> str:
        return (settings.last_city or settings.default_city or "Sofia").strip()

    def apply_loaded_city(self, settings: Settings, city: str) -> str | None:
        city = (city or "").strip()
        if not city:
            return None
        settings.last_city = city
        self.settings_store.save(settings)
        return city

    def analyze_settings_change(self, old_settings: Settings, new_settings: Settings) -> SettingsChangePlan:
        old_forecast = int(getattr(old_settings, "forecast_days", 7))
        return SettingsChangePlan(
            theme_changed=new_settings.theme != old_settings.theme,
            units_changed=new_settings.units != old_settings.units,
            forecast_changed=int(getattr(new_settings, "forecast_days", 7)) != old_forecast,
            default_changed=new_settings.default_city != old_settings.default_city,
            animated_changed=(
                bool(getattr(new_settings, "animated_current_icon", False))
                != bool(getattr(old_settings, "animated_current_icon", False))
            ),
            old_forecast_days=old_forecast,
        )

    def selected_date_after_forecast_change(
        self,
        *,
        data: WeatherData,
        selected_date: str | None,
        forecast_days: int,
    ) -> str | None:
        visible_dates = {d.date_iso for d in data.daily[: int(forecast_days)]}
        if selected_date not in visible_dates:
            return data.current.date_iso
        return selected_date

    # ---------- favorites/search history ----------

    def current_city_for_star(self, data: WeatherData | None, typed_city: str) -> str:
        if data and getattr(data, "current", None) and getattr(data.current, "city", ""):
            return (data.current.city or "").strip()
        return (typed_city or "").strip()

    def current_display_city(self, data: WeatherData | None, typed_city: str) -> str:
        if data and data.current and data.current.city:
            return data.current.city
        return (typed_city or "").strip()

    def is_favorite(self, city: str) -> bool:
        city = (city or "").strip()
        return bool(city and self.storage.is_favorite(city))

    def toggle_favorite(self, *, data: WeatherData | None, typed_city: str) -> None:
        city = self.current_city_for_star(data, typed_city)
        if not city:
            return

        if self.storage.is_favorite(city):
            self.storage.remove_favorite(city)
            return

        self.storage.add_favorite(
            city=city,
            lat=getattr(data, "lat", None) if data else None,
            lon=getattr(data, "lon", None) if data else None,
            country=getattr(data, "country", None) if data else None,
        )

    def write_history(self, data: WeatherData) -> None:
        city = (data.current.city or "").strip()
        if city:
            self.storage.add_history(city=city, lat=data.lat, lon=data.lon)

    # ---------- weather data selection helpers ----------

    def build_hourly_for_date(
        self,
        *,
        data: WeatherData | None,
        date_iso: str,
        mode: HourlyMode = DEFAULT_MODE,
    ) -> dict:
        if not data:
            return {
                "labels": [],
                "hours_int": [],
                "values": [],
                "codes": [],
                "time_isos": [],
                "nights": [],
                "pivot_index": None,
            }

        series = data.hourly
        today_iso = data.current.date_iso
        current_time_iso = data.current.time_iso

        day = next((d for d in data.daily if d.date_iso == date_iso), None)
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

    def make_current_for_date(self, *, data: WeatherData | None, date_iso: str) -> CurrentSnapshot | None:
        if not data:
            return None

        today_iso = data.current.date_iso
        if date_iso == today_iso:
            return data.current

        selected_day = next((d for d in data.daily if d.date_iso == date_iso), None)
        if not selected_day:
            return None

        snap = data.hourly.snapshot_for_date(date_iso, target_hour=15, strategy="peak_temp")

        base = CurrentSnapshot(
            temp=selected_day.tmax,
            code=selected_day.code,
            feels_like=None,
            humidity=None,
            precip=None,
            wind=None,
            date_iso=date_iso,
            time_iso=None,
            city=data.current.city,
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
            city=data.current.city,
        )
