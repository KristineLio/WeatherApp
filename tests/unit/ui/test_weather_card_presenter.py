from weather_app.domain.models import DailyForecast
from weather_app.domain.settings import Units
from weather_app.ui.weather_card_presenter import build_forecast_card_view_data


def make_day(
    *,
    date_iso: str,
    weekday: str,
    tmin: float | None,
    tmax: float | None,
    code: int | None = 1,
) -> DailyForecast:
    return DailyForecast(
        date_iso=date_iso,
        weekday=weekday,
        tmin=tmin,
        tmax=tmax,
        code=code,
        sunrise_iso=None,
        sunset_iso=None,
    )


def test_build_forecast_card_view_data_limits_to_forecast_days():
    days = [
        make_day(date_iso="2026-03-15", weekday="Sun", tmin=5, tmax=12),
        make_day(date_iso="2026-03-16", weekday="Mon", tmin=6, tmax=13),
        make_day(date_iso="2026-03-17", weekday="Tue", tmin=7, tmax=14),
    ]

    out = build_forecast_card_view_data(
        daily_list=days,
        units=Units.METRIC,
        forecast_days=2,
        selected_date=None,
        today_iso="2026-03-15",
    )

    assert len(out) == 2
    assert out[0].date_iso == "2026-03-15"
    assert out[1].date_iso == "2026-03-16"


def test_selected_date_wins_over_today():
    days = [
        make_day(date_iso="2026-03-15", weekday="Sun", tmin=5, tmax=12),
        make_day(date_iso="2026-03-16", weekday="Mon", tmin=6, tmax=13),
    ]

    out = build_forecast_card_view_data(
        daily_list=days,
        units=Units.METRIC,
        forecast_days=7,
        selected_date="2026-03-16",
        today_iso="2026-03-15",
    )

    assert out[0].selected is False
    assert out[1].selected is True


def test_today_is_selected_when_selected_date_missing():
    days = [
        make_day(date_iso="2026-03-15", weekday="Sun", tmin=5, tmax=12),
        make_day(date_iso="2026-03-16", weekday="Mon", tmin=6, tmax=13),
    ]

    out = build_forecast_card_view_data(
        daily_list=days,
        units=Units.METRIC,
        forecast_days=7,
        selected_date=None,
        today_iso="2026-03-15",
    )

    assert out[0].selected is True
    assert out[1].selected is False


def test_metric_temperature_text_is_formatted():
    days = [
        make_day(date_iso="2026-03-15", weekday="Sun", tmin=5, tmax=12),
    ]

    out = build_forecast_card_view_data(
        daily_list=days,
        units=Units.METRIC,
        forecast_days=7,
        selected_date=None,
        today_iso="2026-03-15",
    )

    assert out[0].tmax_text == "12°C"
    assert out[0].tmin_text == "5°C"


def test_imperial_temperature_text_is_formatted():
    days = [
        make_day(date_iso="2026-03-15", weekday="Sun", tmin=0, tmax=10),
    ]

    out = build_forecast_card_view_data(
        daily_list=days,
        units=Units.IMPERIAL,
        forecast_days=7,
        selected_date=None,
        today_iso="2026-03-15",
    )

    assert out[0].tmax_text.endswith("°F")
    assert out[0].tmin_text.endswith("°F")


def test_empty_input_returns_empty_list():
    out = build_forecast_card_view_data(
        daily_list=[],
        units=Units.METRIC,
        forecast_days=7,
        selected_date=None,
        today_iso="2026-03-15",
    )

    assert out == []