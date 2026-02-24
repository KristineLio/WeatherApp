from dataclasses import dataclass
from typing import  Any
from weather_app.domain.modes import HourlyMode, get_mode_meta
from weather_app.utils.formatters import format_hour_label


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
        time_isos: list[str] = []
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

            time_isos.append(tstr)
            hour_int = int(time_part[:2])
            label = format_hour_label(hour_int)

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
            "time_isos": time_isos,
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
    sunrise_iso: str | None
    sunset_iso: str | None
    # optional later: precip_sum, wind_max, etc.

@dataclass(frozen=True)
class WeatherData:
    """Complete weather data for a location."""
    current: CurrentSnapshot
    daily: list[DailyForecast]
    hourly: HourlySeries
    lat: float
    lon: float
