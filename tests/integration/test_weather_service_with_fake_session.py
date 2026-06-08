import pytest
import requests

from weather_app.domain.settings import Units
from weather_app.services.errors import NetworkError, ProviderError
from weather_app.services.openmeteo import WeatherService


GEOCODE_SOFIA = {
    "results": [
        {
            "name": "Sofia",
            "latitude": 42.6977,
            "longitude": 23.3219,
            "country": "Bulgaria",
        }
    ]
}

FORECAST_SOFIA = {
    "current_weather": {
        "time": "2026-06-07T09:30",
        "temperature": 22,
        "weathercode": 1,
        "windspeed": 8,
    },
    "daily": {
        "time": ["2026-06-07", "2026-06-08"],
        "temperature_2m_max": [25, 27],
        "temperature_2m_min": [16, 17],
        "weathercode": [1, 0],
        "sunrise": ["2026-06-07T05:50", "2026-06-08T05:50"],
        "sunset": ["2026-06-07T20:55", "2026-06-08T20:56"],
    },
    "hourly": {
        "time": ["2026-06-07T09:00", "2026-06-07T10:00"],
        "temperature_2m": [22, 24],
        "weathercode": [1, 1],
        "apparent_temperature": [21, 23],
        "relativehumidity_2m": [55, 56],
        "precipitation_probability": [10, 20],
        "windspeed": [8, 10],
    },
}


class FakeResponse:
    def __init__(self, status_code=200, payload=None, json_error=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise self._json_error
        return self._payload

    def raise_for_status(self):
        if 400 <= self.status_code:
            err = requests.exceptions.HTTPError(f"HTTP {self.status_code}")
            err.response = self
            raise err


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, *, params=None, timeout=None):
        self.calls.append((url, params or {}, timeout))
        if not self.responses:
            raise AssertionError("No fake responses left")
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


def test_fetch_success_builds_weather_data_without_real_http():
    session = FakeSession([
        FakeResponse(payload=GEOCODE_SOFIA),
        FakeResponse(payload=FORECAST_SOFIA),
    ])
    service = WeatherService(session=session, cache_ttl_s=120)

    data = service.fetch("Sofia", units=Units.METRIC, forecast_days=2)

    assert data.current.city == "Sofia, Bulgaria"
    assert data.current.temp == 22
    assert data.current.feels_like == 21
    assert data.current.humidity == 55
    assert len(data.daily) == 2
    assert len(session.calls) == 2


def test_fetch_imperial_adds_unit_params_to_forecast_request():
    session = FakeSession([
        FakeResponse(payload=GEOCODE_SOFIA),
        FakeResponse(payload=FORECAST_SOFIA),
    ])
    service = WeatherService(session=session, cache_ttl_s=120)

    service.fetch("Sofia", units=Units.IMPERIAL, forecast_days=3)

    forecast_params = session.calls[1][1]
    assert forecast_params["temperature_unit"] == "fahrenheit"
    assert forecast_params["wind_speed_unit"] == "mph"
    assert forecast_params["precipitation_unit"] == "inch"
    assert forecast_params["forecast_days"] == 3


def test_fetch_uses_weather_cache_on_second_identical_call():
    session = FakeSession([
        FakeResponse(payload=GEOCODE_SOFIA),
        FakeResponse(payload=FORECAST_SOFIA),
    ])
    service = WeatherService(session=session, cache_ttl_s=120)

    first = service.fetch("Sofia", units=Units.METRIC, forecast_days=2)
    second = service.fetch("Sofia", units=Units.METRIC, forecast_days=2)

    assert second is first
    assert len(session.calls) == 2


def test_fetch_city_not_found_raises_value_error():
    session = FakeSession([FakeResponse(payload={"results": []})])
    service = WeatherService(session=session)

    with pytest.raises(ValueError, match="City not found"):
        service.fetch("NoSuchCity")


def test_fetch_missing_current_time_raises_provider_error():
    bad_forecast = dict(FORECAST_SOFIA)
    bad_forecast["current_weather"] = {"temperature": 22, "weathercode": 1}
    session = FakeSession([
        FakeResponse(payload=GEOCODE_SOFIA),
        FakeResponse(payload=bad_forecast),
    ])
    service = WeatherService(session=session)

    with pytest.raises(ProviderError, match="missing current time"):
        service.fetch("Sofia")


def test_get_json_retries_429_then_succeeds(monkeypatch):
    session = FakeSession([
        FakeResponse(status_code=429, payload={}),
        FakeResponse(payload={"ok": True}),
    ])
    service = WeatherService(session=session)
    monkeypatch.setattr("weather_app.services.openmeteo.time.sleep", lambda _: None)

    result = service._get_json("https://example.test/forecast", attempts=2)

    assert result == {"ok": True}
    assert len(session.calls) == 2


def test_get_json_timeout_after_retries_raises_network_error(monkeypatch):
    session = FakeSession([
        requests.exceptions.Timeout("slow"),
        requests.exceptions.Timeout("slow"),
    ])
    service = WeatherService(session=session)
    monkeypatch.setattr("weather_app.services.openmeteo.time.sleep", lambda _: None)

    with pytest.raises(NetworkError):
        service._get_json("https://example.test/forecast", attempts=2)


def test_get_json_404_raises_provider_error():
    session = FakeSession([FakeResponse(status_code=404, payload={})])
    service = WeatherService(session=session)

    with pytest.raises(ProviderError, match="HTTP 404"):
        service._get_json("https://example.test/forecast")


def test_get_json_invalid_json_raises_provider_error():
    session = FakeSession([FakeResponse(json_error=ValueError("bad json"))])
    service = WeatherService(session=session)

    with pytest.raises(ProviderError, match="invalid JSON"):
        service._get_json("https://example.test/forecast")
