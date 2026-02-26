import json
from pathlib import Path

from weather_app.domain.settings import Settings, Units, Theme
from weather_app.services.settings_store import SettingsStore


def test_settings_store_load_returns_defaults_if_missing(tmp_path: Path):
    path = tmp_path / "nested" / "settings.json"
    store = SettingsStore(path)
    s = store.load()
    assert s == Settings()


#test corrupted JSON: load() should return defaults, not crash.
def test_settings_store_load_returns_defaults_if_corrupted_json(tmp_path: Path):
    path = tmp_path / "settings.json"
    path.write_text("{ this is not json", encoding="utf-8")

    store = SettingsStore(path)
    s = store.load()
    assert s == Settings()


def test_settings_store_load_sanitizes_bad_json_values(tmp_path: Path):
    bad_data = {
        "default_city": "   ",          # invalid -> Sofia
        "last_city": "",                # invalid -> Sofia
        "units": "banana",              # invalid enum
        "theme": "ultra_dark",          # invalid enum
        "forecast_days": "abc",         # invalid int
    }

    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps(bad_data), encoding="utf-8")

    store = SettingsStore(path=settings_file)
    s = store.load()

    assert isinstance(s, Settings)

    assert s.default_city == "Sofia"
    assert s.last_city == "Sofia"
    assert s.units == Units.METRIC
    assert s.theme == Theme.LIGHT
    assert s.forecast_days == 7

             
def test_settings_store_save_creates_parent_dir_and_writes_json(tmp_path: Path):
    """Save should create parent dirs and write valid JSON."""
    # Put file in a nested directory that doesn't exist yet
    settings_file = tmp_path / "nested" / "dir" / "settings.json"
    store = SettingsStore(path=settings_file)

    s = Settings(default_city="Varna", last_city="Sofia", units=Units.METRIC, theme=Theme.LIGHT, forecast_days=7)
    store.save(s)

    assert settings_file.exists()

    data = json.loads(settings_file.read_text(encoding="utf-8"))
    assert data["default_city"] == "Varna"
    assert data["last_city"] == "Sofia"
    assert data["units"] == Units.METRIC.value
    assert data["theme"] == Theme.LIGHT.value
    assert data["forecast_days"] == 7


def test_settings_store_save_is_atomic_no_tmp_leftover(tmp_path: Path):
    settings_file = tmp_path / "settings.json"
    store = SettingsStore(path=settings_file)

    store.save(Settings(default_city="Sofia"))

    # Your implementation uses .with_suffix(".tmp")
    tmp_file = settings_file.with_suffix(".tmp")
    assert not tmp_file.exists()


def test_settings_store_round_trip_save_then_load(tmp_path: Path):
    settings_file = tmp_path / "settings.json"
    store = SettingsStore(path=settings_file)

    original = Settings(
        default_city="Plovdiv",
        last_city="Varna",
        units=Units.IMPERIAL,
        theme=Theme.DARK,
        forecast_days=14,
        animated_current_icon=True,
        location_prompted=True,
        use_detected_on_start=True,
        ask_detected_on_start=False,
    )

    store.save(original)
    loaded = store.load()

    assert loaded.to_dict() == original.to_dict()