import json
from pathlib import Path

from weather_app.domain.settings import Settings, Units, Theme
from weather_app.services.settings_store import SettingsStore


def test_settings_store_load_returns_defaults_if_missing(tmp_path: Path):
    path = tmp_path / "nested" / "settings.json"
    store = SettingsStore(path)
    s = store.load()
    assert s == Settings()


def test_settings_store_save_creates_parent_dirs_and_writes_valid_json(tmp_path: Path):
    path = tmp_path / "nested" / "settings.json"
    store = SettingsStore(path)

    settings = Settings(
        default_city="Sofia",
        last_city="Sofia",
        units=Units.IMPERIAL,
        theme=Theme.DARK,
        forecast_days=5,
        animated_current_icon=True,
    )

    store.save(settings)

    assert path.exists()
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)

    assert data["units"] == "imperial"
    assert data["theme"] == "dark"
    assert data["forecast_days"] == 5
    assert data["animated_current_icon"] is True

    # Indirect check for "atomic write": .tmp should be gone after save
    assert not path.with_suffix(".tmp").exists()


def test_settings_store_load_returns_defaults_if_corrupted_json(tmp_path: Path):
    path = tmp_path / "settings.json"
    path.write_text("{ this is not json", encoding="utf-8")

    store = SettingsStore(path)
    s = store.load()
    assert s == Settings()