from weather_app.domain.settings import Settings, Units, Theme


def test_settings_to_dict_converts_enums_to_strings():
    s = Settings(units=Units.IMPERIAL, theme=Theme.DARK)
    d = s.to_dict()

    assert isinstance(d["units"], str)
    assert isinstance(d["theme"], str)
    assert d["units"] == "imperial"
    assert d["theme"] == "dark"


def test_settings_from_dict_non_dict_returns_defaults():
    s = Settings.from_dict(None)  # type: ignore[arg-type]
    assert isinstance(s, Settings)
    assert s == Settings()


def test_settings_from_dict_missing_keys_uses_defaults():
    s = Settings.from_dict({})
    assert s.default_city == "Sofia"
    assert s.last_city == "Sofia"
    assert s.units == Units.METRIC
    assert s.theme == Theme.LIGHT
    assert s.forecast_days == 7
    assert s.animated_current_icon is False
    assert s.location_prompted is False
    assert s.use_detected_on_start is False
    assert s.ask_detected_on_start is True


def test_settings_roundtrip_preserves_values():
    original = Settings(
        default_city="Varna",
        last_city="Plovdiv",
        units=Units.IMPERIAL,
        theme=Theme.DARK,
        forecast_days=10,
        animated_current_icon=True,
        location_prompted=True,
        use_detected_on_start=True,
        ask_detected_on_start=False,
    )

    restored = Settings.from_dict(original.to_dict())
    assert restored == original


def test_settings_from_dict_last_city_fallbacks_to_default_city():
    s = Settings.from_dict({"default_city": "Burgas"})
    assert s.default_city == "Burgas"
    assert s.last_city == "Burgas"