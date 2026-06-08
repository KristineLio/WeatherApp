from pathlib import Path

from weather_app.domain.models import CurrentSnapshot, DailyForecast, HourlySeries, WeatherData
from weather_app.domain.modes import HourlyMode
from weather_app.domain.settings import Settings, Theme, Units
from weather_app.services.settings_store import SettingsStore
from weather_app.services.storage import StorageRepo
from weather_app.ui.weather_controller import WeatherController


def make_weather(city="Sofia, Bulgaria"):
    hourly = HourlySeries.from_api(
        {
            "time": [
                "2026-06-07T04:00",
                "2026-06-07T09:00",
                "2026-06-07T15:00",
                "2026-06-07T21:00",
                "2026-06-08T09:00",
                "2026-06-08T15:00",
            ],
            "temperature_2m": [14, 22, 28, 20, 23, 30],
            "weathercode": [0, 1, 1, 2, 3, 0],
            "apparent_temperature": [13, 22, 29, 20, 24, 31],
            "relativehumidity_2m": [70, 55, 40, 65, 50, 35],
            "precipitation_probability": [0, 10, 20, 0, 5, 0],
            "windspeed": [4, 8, 12, 7, 6, 9],
        }
    )
    return WeatherData(
        current=CurrentSnapshot(
            temp=22,
            code=1,
            feels_like=22,
            humidity=55,
            precip=10,
            wind=8,
            date_iso="2026-06-07",
            time_iso="2026-06-07T09:00",
            city=city,
        ),
        daily=[
            DailyForecast(
                date_iso="2026-06-07",
                weekday="Sun",
                tmin=14,
                tmax=28,
                code=1,
                sunrise_iso="2026-06-07T05:50",
                sunset_iso="2026-06-07T20:55",
            ),
            DailyForecast(
                date_iso="2026-06-08",
                weekday="Mon",
                tmin=16,
                tmax=30,
                code=0,
                sunrise_iso="2026-06-08T05:50",
                sunset_iso="2026-06-08T20:56",
            ),
        ],
        hourly=hourly,
        lat=42.6977,
        lon=23.3219,
        resolved_name="Sofia",
        country="Bulgaria",
    )


def make_controller(tmp_path):
    storage = StorageRepo(tmp_path / "weather.db")
    settings_store = SettingsStore(tmp_path / "settings.json")
    return WeatherController(storage=storage, settings_store=settings_store), storage, settings_store


def test_initial_city_prefers_last_then_default_then_sofia(tmp_path):
    controller, _, _ = make_controller(tmp_path)

    assert controller.initial_city(Settings(last_city="Plovdiv", default_city="Sofia")) == "Plovdiv"
    assert controller.initial_city(Settings(last_city="", default_city="Varna")) == "Varna"
    assert controller.initial_city(Settings(last_city="", default_city="")) == "Sofia"


def test_apply_loaded_city_saves_last_city(tmp_path):
    controller, _, settings_store = make_controller(tmp_path)
    settings = Settings(last_city="Sofia")

    result = controller.apply_loaded_city(settings, "  Kavala  ")

    assert result == "Kavala"
    assert settings.last_city == "Kavala"
    assert settings_store.load().last_city == "Kavala"


def test_apply_loaded_city_ignores_blank_city(tmp_path):
    controller, _, settings_store = make_controller(tmp_path)
    settings = Settings(last_city="Sofia")

    result = controller.apply_loaded_city(settings, "   ")

    assert result is None
    assert settings.last_city == "Sofia"


def test_analyze_settings_change_reports_changed_fields(tmp_path):
    controller, _, _ = make_controller(tmp_path)
    old = Settings(
        default_city="Sofia",
        units=Units.METRIC,
        theme=Theme.LIGHT,
        forecast_days=7,
        animated_current_icon=False,
    )
    new = Settings(
        default_city="Kavala",
        units=Units.IMPERIAL,
        theme=Theme.DARK,
        forecast_days=10,
        animated_current_icon=True,
    )

    plan = controller.analyze_settings_change(old, new)

    assert plan.theme_changed is True
    assert plan.units_changed is True
    assert plan.forecast_changed is True
    assert plan.default_changed is True
    assert plan.animated_changed is True
    assert plan.old_forecast_days == 7


def test_selected_date_after_forecast_change_resets_when_hidden(tmp_path):
    controller, _, _ = make_controller(tmp_path)
    data = make_weather()

    assert controller.selected_date_after_forecast_change(
        data=data,
        selected_date="2026-06-08",
        forecast_days=1,
    ) == "2026-06-07"

    assert controller.selected_date_after_forecast_change(
        data=data,
        selected_date="2026-06-08",
        forecast_days=2,
    ) == "2026-06-08"


def test_current_city_and_display_city_prefer_weather_data(tmp_path):
    controller, _, _ = make_controller(tmp_path)
    data = make_weather(city="Sofia, Bulgaria")

    assert controller.current_city_for_star(data, "typed") == "Sofia, Bulgaria"
    assert controller.current_display_city(data, "typed") == "Sofia, Bulgaria"
    assert controller.current_city_for_star(None, " typed ") == "typed"


def test_toggle_favorite_adds_then_removes_current_city(tmp_path):
    controller, storage, _ = make_controller(tmp_path)
    data = make_weather(city="Sofia, Bulgaria")

    controller.toggle_favorite(data=data, typed_city="ignored")
    assert storage.is_favorite("Sofia, Bulgaria") is True

    controller.toggle_favorite(data=data, typed_city="ignored")
    assert storage.is_favorite("Sofia, Bulgaria") is False


def test_write_history_adds_search_history_row(tmp_path):
    controller, storage, _ = make_controller(tmp_path)
    data = make_weather(city="Sofia, Bulgaria")

    controller.write_history(data)

    rows = storage.list_history()
    assert len(rows) == 1
    assert rows[0].city == "Sofia, Bulgaria"


def test_build_hourly_for_date_adds_night_and_sunrise_sunset_metadata(tmp_path):
    controller, _, _ = make_controller(tmp_path)
    data = make_weather()

    hourly = controller.build_hourly_for_date(
        data=data,
        date_iso="2026-06-07",
        mode=HourlyMode.TEMPERATURE,
    )

    assert hourly["pivot_index"] == 1
    assert hourly["sunrise_hour"] == 5
    assert hourly["sunset_hour"] == 20
    assert hourly["nights"] == [True, False, False, True]


def test_make_current_for_today_returns_current_snapshot(tmp_path):
    controller, _, _ = make_controller(tmp_path)
    data = make_weather()

    snap = controller.make_current_for_date(data=data, date_iso="2026-06-07")

    assert snap is data.current


def test_make_current_for_future_day_uses_hourly_peak_snapshot(tmp_path):
    controller, _, _ = make_controller(tmp_path)
    data = make_weather()

    snap = controller.make_current_for_date(data=data, date_iso="2026-06-08")

    assert snap is not None
    assert snap.temp == 30
    assert snap.time_iso == "2026-06-08T15:00"
    assert snap.city == "Sofia, Bulgaria"


def test_make_current_for_missing_day_returns_none(tmp_path):
    controller, _, _ = make_controller(tmp_path)
    data = make_weather()

    assert controller.make_current_for_date(data=data, date_iso="2026-06-20") is None

def test_build_hourly_for_date_without_data_returns_empty_payload(tmp_path):
    controller, _, _ = make_controller(tmp_path)

    hourly = controller.build_hourly_for_date(
        data=None,
        date_iso="2026-06-07",
        mode=HourlyMode.TEMPERATURE,
    )

    assert hourly == {
        "labels": [],
        "hours_int": [],
        "values": [],
        "codes": [],
        "time_isos": [],
        "nights": [],
        "pivot_index": None,
    }


def test_make_current_for_date_without_data_returns_none(tmp_path):
    controller, _, _ = make_controller(tmp_path)

    assert controller.make_current_for_date(data=None, date_iso="2026-06-07") is None
