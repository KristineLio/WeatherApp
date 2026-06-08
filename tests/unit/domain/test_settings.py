from weather_app.domain.settings import Settings, Theme, Units


def test_settings_to_dict_serializes_enum_values():
    settings = Settings(default_city="Sofia", units=Units.IMPERIAL, theme=Theme.DARK)

    data = settings.to_dict()

    assert data["units"] == "imperial"
    assert data["theme"] == "dark"


def test_settings_from_dict_accepts_valid_values():
    settings = Settings.from_dict(
        {
            "default_city": "Kavala",
            "last_city": "Drama",
            "units": "imperial",
            "theme": "dark",
            "forecast_days": 10,
            "animated_current_icon": True,
            "location_prompted": True,
            "use_detected_on_start": True,
            "ask_detected_on_start": False,
        }
    )

    assert settings.default_city == "Kavala"
    assert settings.last_city == "Drama"
    assert settings.units == Units.IMPERIAL
    assert settings.theme == Theme.DARK
    assert settings.forecast_days == 10
    assert settings.animated_current_icon is True
    assert settings.location_prompted is True
    assert settings.use_detected_on_start is True
    assert settings.ask_detected_on_start is False


def test_settings_from_dict_invalid_values_fall_back_to_defaults():
    settings = Settings.from_dict(
        {
            "default_city": "",
            "last_city": "",
            "units": "bad",
            "theme": "bad",
            "forecast_days": "bad",
        }
    )

    assert settings.default_city == "Sofia"
    assert settings.last_city == "Sofia"
    assert settings.units == Units.METRIC
    assert settings.theme == Theme.LIGHT
    assert settings.forecast_days == 7


def test_settings_from_dict_clamps_forecast_days_to_allowed_range():
    assert Settings.from_dict({"forecast_days": -5}).forecast_days == 1
    assert Settings.from_dict({"forecast_days": 99}).forecast_days == 14


def test_settings_from_non_dict_returns_defaults():
    settings = Settings.from_dict(None)  # type: ignore[arg-type]

    assert settings.default_city == "Sofia"
    assert settings.units == Units.METRIC
    assert settings.theme == Theme.LIGHT
