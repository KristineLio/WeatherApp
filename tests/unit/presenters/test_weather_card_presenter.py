from weather_app.domain.models import DailyForecast
from weather_app.domain.settings import Units
from weather_app.ui.weather_card_presenter import build_forecast_card_view_data


def _days():
    return [
        DailyForecast("2026-06-07", "Sun", 16.1, 25.2, 1, None, None),
        DailyForecast("2026-06-08", "Mon", 17.0, 28.0, 61, None, None),
        DailyForecast("2026-06-09", "Tue", 18.0, 27.0, 0, None, None),
    ]


def test_forecast_cards_limit_to_forecast_days():
    view = build_forecast_card_view_data(
        daily_list=_days(),
        units=Units.METRIC,
        forecast_days=2,
        selected_date=None,
        today_iso="2026-06-07",
    )

    assert len(view) == 2
    assert [item.date_iso for item in view] == ["2026-06-07", "2026-06-08"]


def test_forecast_cards_selected_date_wins_over_today():
    view = build_forecast_card_view_data(
        daily_list=_days(),
        units=Units.METRIC,
        forecast_days=3,
        selected_date="2026-06-08",
        today_iso="2026-06-07",
    )

    assert [item.selected for item in view] == [False, True, False]


def test_forecast_cards_today_selected_when_no_selected_date():
    view = build_forecast_card_view_data(
        daily_list=_days(),
        units=Units.METRIC,
        forecast_days=3,
        selected_date=None,
        today_iso="2026-06-07",
    )

    assert [item.selected for item in view] == [True, False, False]


def test_forecast_cards_format_temperatures_and_icons():
    view = build_forecast_card_view_data(
        daily_list=_days(),
        units=Units.METRIC,
        forecast_days=1,
        selected_date=None,
        today_iso="2026-06-07",
    )

    assert view[0].day_label == "Sun"
    assert view[0].icon_file == "partly.png"
    assert view[0].tmax_text == "25°C"
    assert view[0].tmin_text == "16°C"


def test_forecast_cards_none_list_returns_empty_list():
    view = build_forecast_card_view_data(
        daily_list=None,
        units=Units.METRIC,
        forecast_days=7,
        selected_date=None,
        today_iso=None,
    )

    assert view == []
