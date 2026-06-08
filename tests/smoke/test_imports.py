import importlib

import pytest

pytestmark = pytest.mark.smoke


def test_import_domain_modules():
    import weather_app.domain.models
    import weather_app.domain.modes
    import weather_app.domain.settings


def test_import_service_modules():
    import weather_app.services.errors
    import weather_app.services.location
    import weather_app.services.openmeteo
    import weather_app.services.settings_store
    import weather_app.services.storage
    import weather_app.services.ttl_cache


def test_import_pure_ui_logic_modules():
    import weather_app.ui.cache_refresh_manager
    import weather_app.ui.current_weather_presenter
    import weather_app.ui.hour_tile_presenter
    import weather_app.ui.request_state
    import weather_app.ui.weather_card_presenter
    import weather_app.ui.weather_controller


def test_import_utils_that_do_not_require_wx():
    import weather_app.utils.formatters
    import weather_app.utils.icon_logic
    import weather_app.utils.logging_config
    import weather_app.utils.paths


def test_import_wx_ui_modules_when_wx_is_available():
    pytest.importorskip("wx")

    modules = [
        "weather_app.ui.current_weather_panel",
        "weather_app.ui.frame",
        "weather_app.ui.hour_tile",
        "weather_app.ui.saved_places_panels",
        "weather_app.ui.settings_dialog",
        "weather_app.ui.theme",
        "weather_app.ui.weather_card",
    ]

    for module_name in modules:
        importlib.import_module(module_name)
