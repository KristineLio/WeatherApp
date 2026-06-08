import pytest
import requests

from weather_app.domain.models import WeatherData
from weather_app.domain.settings import Units
from weather_app.services.errors import NetworkError, ProviderError
from weather_app.services.openmeteo import FORECAST_URL, WeatherService

from tests.fixtures.weather_payloads import (
    FORECAST_MISSING_CURRENT_TIME,
    FORECAST_MISSING_DAILY_HOURLY_TIME,
    FORECAST_SOFIA,
)


class FakeResponse:
    def __init__(self, *, status_code=200, payload=None, json_error=False):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise ValueError("invalid json")
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

    def get(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": params or {}, "timeout": timeout})
        if not self.responses:
            raise AssertionError("No more fake responses configured")

        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


class FakeLocationService:
    def __init__(
        self,
        *,
        geocode_result=(42.6977, 23.3219, "Sofia", "Bulgaria"),
        detected_city="Sofia",
    ):
        self.geocode_result = geocode_result
        self.detected_city = detected_city
        self.normalize_calls = []
        self.geocode_calls = []
        self.display_calls = []

    def normalize_location_input(self, city):
        self.normalize_calls.append(city)
        text = " ".join((city or "").strip().split())
        return text or "Sofia"

    def geocode_city(self, city):
        self.geocode_calls.append(city)
        return self.geocode_result

    def display_city(self, resolved_name, country):
        self.display_calls.append((resolved_name, country))
        return f"{resolved_name}, {country}" if country else resolved_name

    def detect_city(self):
        return self.detected_city


def make_service(responses, *, location_service=None, cache_ttl_s=120):
    return WeatherService(
        forecast_url=FORECAST_URL,
        session=FakeSession(responses),
        location_service=location_service or FakeLocationService(),
        cache_ttl_s=cache_ttl_s,
    )


def test_fetch_success_builds_weather_data():
    service = make_service([FakeResponse(payload=FORECAST_SOFIA)])

    data = service.fetch("Sofia", units=Units.METRIC, forecast_days=3)

    assert isinstance(data, WeatherData)
    assert data.current.city == "Sofia, Bulgaria"
    assert data.current.temp == 22.4
    assert data.current.code == 1
    assert data.current.date_iso == "2026-06-07"
    assert data.current.time_iso == "2026-06-07T09:30"

    # Current extras are derived from the matching 09:00 hourly row.
    assert data.current.feels_like == 21.0
    assert data.current.humidity == 58
    assert data.current.precip == 10
    assert data.current.wind == 8.0

    assert len(data.daily) == 3
    assert data.daily[0].date_iso == "2026-06-07"
    assert data.daily[0].weekday == "Sun"

    assert data.lat == 42.6977
    assert data.lon == 23.3219
    assert data.resolved_name == "Sofia"
    assert data.country == "Bulgaria"


def test_fetch_uses_location_service_for_normalize_geocode_and_display():
    location = FakeLocationService(
        geocode_result=(40.9376, 24.4129, "Kavala", "Greece"),
    )
    service = make_service([FakeResponse(payload=FORECAST_SOFIA)], location_service=location)

    data = service.fetch("  Kavala   Greece  ")

    assert location.normalize_calls == ["  Kavala   Greece  "]
    assert location.geocode_calls == ["Kavala Greece"]
    assert location.display_calls == [("Kavala", "Greece")]
    assert data.current.city == "Kavala, Greece"
    assert data.lat == 40.9376
    assert data.lon == 24.4129


def test_detect_city_delegates_to_location_service():
    location = FakeLocationService(detected_city="Drama")
    service = make_service([], location_service=location)

    assert service.detect_city() == "Drama"


def test_fetch_imperial_adds_unit_params_to_forecast_request():
    service = make_service([FakeResponse(payload=FORECAST_SOFIA)])

    service.fetch("Sofia", units=Units.IMPERIAL, forecast_days=5)

    forecast_call = service._session.calls[-1]
    params = forecast_call["params"]

    assert params["forecast_days"] == 5
    assert params["temperature_unit"] == "fahrenheit"
    assert params["wind_speed_unit"] == "mph"
    assert params["precipitation_unit"] == "inch"


def test_fetch_missing_current_time_raises_provider_error():
    service = make_service([FakeResponse(payload=FORECAST_MISSING_CURRENT_TIME)])

    with pytest.raises(ProviderError, match="missing current time"):
        service.fetch("Sofia")


def test_fetch_missing_daily_time_raises_provider_error():
    service = make_service([FakeResponse(payload=FORECAST_MISSING_DAILY_HOURLY_TIME)])

    with pytest.raises(ProviderError, match="missing daily/hourly time arrays"):
        service.fetch("Sofia")


def test_fetch_value_error_from_location_service_is_preserved():
    class NotFoundLocation(FakeLocationService):
        def geocode_city(self, city):
            raise ValueError("City not found. Please try another name.")

    service = make_service([], location_service=NotFoundLocation())

    with pytest.raises(ValueError, match="City not found"):
        service.fetch("Unknown City")


def test_fetch_uses_weather_cache_on_second_call():
    session = FakeSession([FakeResponse(payload=FORECAST_SOFIA)])
    service = WeatherService(
        forecast_url=FORECAST_URL,
        session=session,
        location_service=FakeLocationService(),
        cache_ttl_s=120,
    )

    first = service.fetch("Sofia", units=Units.METRIC, forecast_days=7)
    second = service.fetch("Sofia", units=Units.METRIC, forecast_days=7)

    assert second is first
    assert len(session.calls) == 1


def test_fetch_cache_key_separates_units():
    service = make_service(
        [
            FakeResponse(payload=FORECAST_SOFIA),
            FakeResponse(payload=FORECAST_SOFIA),
        ]
    )

    metric = service.fetch("Sofia", units=Units.METRIC, forecast_days=7)
    imperial = service.fetch("Sofia", units=Units.IMPERIAL, forecast_days=7)

    assert imperial is not metric
    assert len(service._session.calls) == 2


def test_fetch_cache_key_normalizes_city_spacing_and_case():
    service = make_service([FakeResponse(payload=FORECAST_SOFIA)])

    first = service.fetch("Sofia", units=Units.METRIC, forecast_days=7)
    second = service.fetch("  SOFIA  ", units=Units.METRIC, forecast_days=7)

    assert second is first
    assert len(service._session.calls) == 1


def test_get_json_retries_429_then_succeeds(monkeypatch):
    monkeypatch.setattr("weather_app.services.openmeteo.time.sleep", lambda _seconds: None)

    service = make_service(
        [
            FakeResponse(status_code=429, payload={"error": "rate limited"}),
            FakeResponse(payload={"ok": True}),
        ],
        cache_ttl_s=0,
    )

    result = service._get_json(
        "https://example.test/forecast",
        attempts=2,
        backoff_s=0,
    )

    assert result == {"ok": True}
    assert len(service._session.calls) == 2


def test_get_json_retries_500_then_raises_network_error(monkeypatch):
    monkeypatch.setattr("weather_app.services.openmeteo.time.sleep", lambda _seconds: None)

    service = make_service(
        [
            FakeResponse(status_code=500, payload={"error": "server"}),
            FakeResponse(status_code=500, payload={"error": "server"}),
        ],
        cache_ttl_s=0,
    )

    with pytest.raises(NetworkError, match="HTTP 500"):
        service._get_json(
            "https://example.test/forecast",
            attempts=2,
            backoff_s=0,
        )


def test_get_json_404_raises_provider_error_without_retry():
    service = make_service([FakeResponse(status_code=404, payload={"error": "not found"})])

    with pytest.raises(ProviderError, match="HTTP 404"):
        service._get_json("https://example.test/forecast", attempts=3)

    assert len(service._session.calls) == 1


def test_get_json_invalid_json_raises_provider_error():
    service = make_service([FakeResponse(payload=None, json_error=True)])

    with pytest.raises(ProviderError, match="invalid JSON"):
        service._get_json("https://example.test/forecast")


def test_get_json_timeout_retries_then_raises_network_error(monkeypatch):
    monkeypatch.setattr("weather_app.services.openmeteo.time.sleep", lambda _seconds: None)

    service = make_service(
        [
            requests.exceptions.Timeout("first timeout"),
            requests.exceptions.Timeout("second timeout"),
        ]
    )

    with pytest.raises(NetworkError, match="Network timeout"):
        service._get_json("https://example.test/forecast", attempts=2, backoff_s=0)

    assert len(service._session.calls) == 2


def test_get_json_request_exception_retries_then_raises_network_error(monkeypatch):
    monkeypatch.setattr("weather_app.services.openmeteo.time.sleep", lambda _seconds: None)

    service = make_service(
        [
            requests.RequestException("connection failed"),
            requests.RequestException("connection failed again"),
        ]
    )

    with pytest.raises(NetworkError, match="Network error"):
        service._get_json("https://example.test/forecast", attempts=2, backoff_s=0)

    assert len(service._session.calls) == 2


def test_parse_daily_truncates_to_shortest_required_array():
    service = make_service([])

    days = service._parse_daily(
        {
            "time": ["2026-06-07", "2026-06-08", "2026-06-09"],
            "temperature_2m_max": [25.0, 26.0],
            "temperature_2m_min": [15.0, 16.0],
            "weathercode": [1, 2],
            "sunrise": ["2026-06-07T05:50"],
            "sunset": ["2026-06-07T20:55"],
        }
    )

    assert len(days) == 2
    assert days[0].date_iso == "2026-06-07"
    assert days[0].sunrise_iso == "2026-06-07T05:50"
    assert days[0].sunset_iso == "2026-06-07T20:55"
    assert days[1].date_iso == "2026-06-08"
    assert days[1].sunrise_iso is None
    assert days[1].sunset_iso is None
