import pytest
import requests

from weather_app.domain.settings import Units
from weather_app.services.errors import NetworkError, ProviderError
from weather_app.services.openmeteo import WeatherService
from tests.fixtures.weather_payloads import (
    FORECAST_MISSING_CURRENT_TIME,
    FORECAST_SOFIA,
    GEOCODE_EMPTY,
    GEOCODE_SOFIA,
)

pytestmark = pytest.mark.integration


def make_service(fake_session_factory, *responses, cache_ttl_s=120):
    return WeatherService(
        session=fake_session_factory(*responses),
        cache_ttl_s=cache_ttl_s,
    )


def test_fetch_success_builds_weather_data_without_real_http(
    fake_session_factory,
    fake_response,
):
    service = make_service(
        fake_session_factory,
        fake_response(payload=GEOCODE_SOFIA),
        fake_response(payload=FORECAST_SOFIA),
        cache_ttl_s=120,
    )

    data = service.fetch("Sofia", units=Units.METRIC, forecast_days=2)

    assert data.current.city == "Sofia, Bulgaria"
    assert data.current.temp == 22.4
    assert data.current.feels_like == 21.0
    assert data.current.humidity == 58
    assert len(data.daily) == 3
    assert len(service._session.calls) == 2


def test_fetch_imperial_adds_unit_params_to_forecast_request(
    fake_session_factory,
    fake_response,
):
    service = make_service(
        fake_session_factory,
        fake_response(payload=GEOCODE_SOFIA),
        fake_response(payload=FORECAST_SOFIA),
        cache_ttl_s=120,
    )

    service.fetch("Sofia", units=Units.IMPERIAL, forecast_days=3)

    forecast_params = service._session.calls[1]["params"]
    assert forecast_params["temperature_unit"] == "fahrenheit"
    assert forecast_params["wind_speed_unit"] == "mph"
    assert forecast_params["precipitation_unit"] == "inch"
    assert forecast_params["forecast_days"] == 3


def test_fetch_uses_weather_cache_on_second_identical_call(
    fake_session_factory,
    fake_response,
):
    service = make_service(
        fake_session_factory,
        fake_response(payload=GEOCODE_SOFIA),
        fake_response(payload=FORECAST_SOFIA),
        cache_ttl_s=120,
    )

    first = service.fetch("Sofia", units=Units.METRIC, forecast_days=2)
    second = service.fetch("Sofia", units=Units.METRIC, forecast_days=2)

    assert second is first
    assert len(service._session.calls) == 2


def test_fetch_city_not_found_raises_value_error(fake_session_factory, fake_response):
    service = make_service(
        fake_session_factory,
        fake_response(payload=GEOCODE_EMPTY),
    )

    with pytest.raises(ValueError, match="City not found"):
        service.fetch("NoSuchCity")


def test_fetch_missing_current_time_raises_provider_error(
    fake_session_factory,
    fake_response,
):
    service = make_service(
        fake_session_factory,
        fake_response(payload=GEOCODE_SOFIA),
        fake_response(payload=FORECAST_MISSING_CURRENT_TIME),
    )

    with pytest.raises(ProviderError, match="missing current time"):
        service.fetch("Sofia")


def test_get_json_retries_429_then_succeeds(
    monkeypatch,
    fake_session_factory,
    fake_response,
):
    service = make_service(
        fake_session_factory,
        fake_response(status_code=429, payload={}),
        fake_response(payload={"ok": True}),
    )
    monkeypatch.setattr("weather_app.services.openmeteo.time.sleep", lambda _: None)

    result = service._get_json("https://example.test/forecast", attempts=2)

    assert result == {"ok": True}
    assert len(service._session.calls) == 2


def test_get_json_timeout_after_retries_raises_network_error(
    monkeypatch,
    fake_session_factory,
):
    service = make_service(
        fake_session_factory,
        requests.exceptions.Timeout("slow"),
        requests.exceptions.Timeout("slow"),
    )
    monkeypatch.setattr("weather_app.services.openmeteo.time.sleep", lambda _: None)

    with pytest.raises(NetworkError):
        service._get_json("https://example.test/forecast", attempts=2)


def test_get_json_404_raises_provider_error(fake_session_factory, fake_response):
    service = make_service(
        fake_session_factory,
        fake_response(status_code=404, payload={}),
    )

    with pytest.raises(ProviderError, match="HTTP 404"):
        service._get_json("https://example.test/forecast")


def test_get_json_invalid_json_raises_provider_error(fake_session_factory, fake_response):
    service = make_service(
        fake_session_factory,
        fake_response(json_error=ValueError("bad json")),
    )

    with pytest.raises(ProviderError, match="invalid JSON"):
        service._get_json("https://example.test/forecast")
