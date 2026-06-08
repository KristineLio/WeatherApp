import json

from weather_app.domain.settings import Settings, Theme, Units
from weather_app.services.settings_store import SettingsStore


def test_load_returns_defaults_when_file_missing(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")

    settings = store.load()

    assert settings.default_city == "Sofia"
    assert settings.last_city == "Sofia"
    assert settings.units == Units.METRIC
    assert settings.theme == Theme.LIGHT


def test_save_creates_parent_directory_and_writes_json(tmp_path):
    path = tmp_path / "nested" / "settings.json"
    store = SettingsStore(path)

    store.save(
        Settings(
            default_city="Kavala",
            last_city="Sofia",
            units=Units.IMPERIAL,
            theme=Theme.DARK,
            forecast_days=10,
            animated_current_icon=True,
            location_prompted=True,
            use_detected_on_start=True,
            ask_detected_on_start=False,
        )
    )

    assert path.exists()

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["default_city"] == "Kavala"
    assert raw["last_city"] == "Sofia"
    assert raw["units"] == "imperial"
    assert raw["theme"] == "dark"
    assert raw["forecast_days"] == 10
    assert raw["animated_current_icon"] is True
    assert raw["location_prompted"] is True
    assert raw["use_detected_on_start"] is True
    assert raw["ask_detected_on_start"] is False


def test_load_reads_saved_settings(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "default_city": "Drama",
                "last_city": "Kavala",
                "units": "imperial",
                "theme": "dark",
                "forecast_days": 12,
                "animated_current_icon": True,
                "location_prompted": True,
                "use_detected_on_start": False,
                "ask_detected_on_start": True,
            }
        ),
        encoding="utf-8",
    )

    settings = SettingsStore(path).load()

    assert settings.default_city == "Drama"
    assert settings.last_city == "Kavala"
    assert settings.units == Units.IMPERIAL
    assert settings.theme == Theme.DARK
    assert settings.forecast_days == 12
    assert settings.animated_current_icon is True
    assert settings.location_prompted is True
    assert settings.use_detected_on_start is False
    assert settings.ask_detected_on_start is True


def test_load_returns_defaults_when_json_is_invalid(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{ invalid json", encoding="utf-8")

    settings = SettingsStore(path).load()

    assert settings == Settings()


def test_load_uses_settings_resilience_for_invalid_values(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "default_city": "",
                "last_city": "",
                "units": "bad-units",
                "theme": "bad-theme",
                "forecast_days": 999,
            }
        ),
        encoding="utf-8",
    )

    settings = SettingsStore(path).load()

    assert settings.default_city == "Sofia"
    assert settings.last_city == "Sofia"
    assert settings.units == Units.METRIC
    assert settings.theme == Theme.LIGHT
    assert settings.forecast_days == 14
