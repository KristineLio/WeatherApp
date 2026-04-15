from __future__ import annotations

from dataclasses import dataclass

from weather_app.domain.models import DailyForecast
from weather_app.domain.modes import HourlyMode, format_value
from weather_app.domain.settings import Units
from weather_app.utils.icon_logic import code_to_label_icon


@dataclass(frozen=True)
class ForecastCardViewData:
    date_iso: str
    day_label: str
    icon_file: str
    tmax_text: str
    tmin_text: str
    selected: bool


def build_forecast_card_view_data(
    *,
    daily_list: list[DailyForecast] | None,
    units: Units,
    forecast_days: int,
    selected_date: str | None,
    today_iso: str | None,
) -> list[ForecastCardViewData]:
    """
    Convert DailyForecast models into simple view data for WeatherCard widgets.

    Rules:
    - limit output to forecast_days
    - selected_date wins if present
    - otherwise today_iso is selected
    """
    days = (daily_list or [])[: max(0, int(forecast_days))]
    active_date = selected_date or today_iso

    out: list[ForecastCardViewData] = []

    for d in days:
        _, icon_file = code_to_label_icon(d.code or 0, night=False)

        out.append(
            ForecastCardViewData(
                date_iso=d.date_iso,
                day_label=d.weekday,
                icon_file=icon_file,
                tmax_text=format_value(HourlyMode.TEMPERATURE, d.tmax, units),
                tmin_text=format_value(HourlyMode.TEMPERATURE, d.tmin, units),
                selected=(d.date_iso == active_date),
            )
        )

    return out