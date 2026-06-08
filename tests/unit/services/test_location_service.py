from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
import requests

from weather_app.services.errors import NetworkError, ProviderError
from weather_app.services.location import LocationService


@dataclass
class FakeResponse:
    payload: dict | None = None
    status_code: int = 200
    json_error: Exception | None = None

    def json(self) -> dict:
        if self.json_error is not None:
            raise self.json_error
        return self.payload or {}

    def raise_for_status(self) -> None:
        if 400 <= self.status_code:
            err = requests.exceptions.HTTPError(f"HTTP {self.status_code}")
            err.response = self
            raise err


class FakeSession:
    def __init__(self, responses: list[Any]):
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, *, params: dict | None = None, timeout: int | None = None):
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        if not self.responses:
            raise AssertionError("FakeSession has no more responses")

        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


# ---------------------------------------------------------------------------
# Normalization / display helpers
# ---------------------------------------------------------------------------


def test_normalize_empty_city_defaults_to_sofia():
    service = LocationService(json_getter=lambda *args, **kwargs: {})

    assert service.normalize_location_input("") == "Sofia"
    assert service.normalize_location_input("   ") == "Sofia"


def test_normalize_collapses_extra_whitespace():
    service = LocationService(json_getter=lambda *args, **kwargs: {})

    assert service.normalize_location_input("  Sofia   Bulgaria  ") == "Sofia, Bulgaria"


def test_normalize_two_words_without_comma_treats_last_word_as_country_hint():
    service = LocationService(json_getter=lambda *args, **kwargs: {})

    assert service.normalize_location_input("Kavala Greece") == "Kavala, Greece"


def test_normalize_keeps_existing_comma():
    service = LocationService(json_getter=lambda *args, **kwargs: {})

    assert service.normalize_location_input("Kavala, Greece") == "Kavala, Greece"


def test_display_city_with_and_without_country():
    service = LocationService(json_getter=lambda *args, **kwargs: {})

    assert service.display_city("Sofia", "Bulgaria") == "Sofia, Bulgaria"
    assert service.display_city("Sofia", None) == "Sofia"
    assert service.display_city("", "") == "Unknown"


def test_normalize_city_key_lowercases_and_collapses_spaces():
    service = LocationService(json_getter=lambda *args, **kwargs: {})

    assert service._normalize_city_key("  New   York  ") == "new york"


# ---------------------------------------------------------------------------
# detect_city
# ---------------------------------------------------------------------------


def test_detect_city_success_trims_city_name():
    session = FakeSession([FakeResponse({"city": " Sofia "})])
    service = LocationService(session=session)

    assert service.detect_city() == "Sofia"
    assert session.calls[0]["timeout"] == 5


def test_detect_city_returns_none_when_city_missing():
    session = FakeSession([FakeResponse({"city": ""})])
    service = LocationService(session=session)

    assert service.detect_city() is None


def test_detect_city_returns_none_on_network_or_http_failure():
    session = FakeSession([requests.exceptions.Timeout("slow")])
    service = LocationService(session=session)

    assert service.detect_city() is None

    session = FakeSession([FakeResponse({}, status_code=500)])
    service = LocationService(session=session)

    assert service.detect_city() is None


# ---------------------------------------------------------------------------
# geocode_city with injected json_getter
# ---------------------------------------------------------------------------


def test_geocode_city_success_returns_lat_lon_name_country():
    calls: list[dict[str, Any]] = []

    def fake_json_getter(url: str, **kwargs):
        calls.append({"url": url, **kwargs})
        return {
            "results": [
                {
                    "latitude": 42.6977,
                    "longitude": 23.3219,
                    "name": "Sofia",
                    "country": "Bulgaria",
                }
            ]
        }

    service = LocationService(json_getter=fake_json_getter)

    assert service.geocode_city("Sofia") == (42.6977, 23.3219, "Sofia", "Bulgaria")
    assert calls[0]["params"] == {
        "name": "Sofia",
        "count": 1,
        "language": "en",
        "format": "json",
    }


def test_geocode_city_uses_cache_on_second_call():
    call_count = 0

    def fake_json_getter(url: str, **kwargs):
        nonlocal call_count
        call_count += 1
        return {
            "results": [
                {
                    "latitude": 42.6977,
                    "longitude": 23.3219,
                    "name": "Sofia",
                    "country": "Bulgaria",
                }
            ]
        }

    service = LocationService(json_getter=fake_json_getter)

    first = service.geocode_city("Sofia")
    second = service.geocode_city("  sofia  ")

    assert first == second
    assert call_count == 1


def test_geocode_city_cache_disabled_when_ttl_is_zero():
    call_count = 0

    def fake_json_getter(url: str, **kwargs):
        nonlocal call_count
        call_count += 1
        return {
            "results": [
                {
                    "latitude": 42.6977,
                    "longitude": 23.3219,
                    "name": "Sofia",
                    "country": "Bulgaria",
                }
            ]
        }

    service = LocationService(json_getter=fake_json_getter, geo_cache_ttl_s=0)

    service.geocode_city("Sofia")
    service.geocode_city("Sofia")

    assert call_count == 2


def test_geocode_city_raises_value_error_when_not_found():
    service = LocationService(json_getter=lambda *args, **kwargs: {"results": []})

    with pytest.raises(ValueError, match="City not found"):
        service.geocode_city("Nowhere")


def test_geocode_city_falls_back_to_input_name_when_api_name_missing():
    service = LocationService(
        json_getter=lambda *args, **kwargs: {
            "results": [
                {
                    "latitude": 40.0,
                    "longitude": 20.0,
                    "name": "",
                    "country": "Greece",
                }
            ]
        }
    )

    assert service.geocode_city("Kavala") == (40.0, 20.0, "Kavala", "Greece")


def test_geocode_city_converts_blank_country_to_none():
    service = LocationService(
        json_getter=lambda *args, **kwargs: {
            "results": [
                {
                    "latitude": 40.0,
                    "longitude": 20.0,
                    "name": "Kavala",
                    "country": "",
                }
            ]
        }
    )

    assert service.geocode_city("Kavala") == (40.0, 20.0, "Kavala", None)


# ---------------------------------------------------------------------------
# _get_json direct HTTP behavior when no json_getter is injected
# ---------------------------------------------------------------------------


def test_get_json_success_uses_session_get():
    session = FakeSession([FakeResponse({"ok": True})])
    service = LocationService(session=session)

    data = service._get_json("https://example.test/search", params={"name": "Sofia"}, timeout=3)

    assert data == {"ok": True}
    assert session.calls[0]["url"] == "https://example.test/search"
    assert session.calls[0]["params"] == {"name": "Sofia"}
    assert session.calls[0]["timeout"] == 3


def test_get_json_invalid_json_raises_provider_error():
    session = FakeSession([FakeResponse(json_error=ValueError("bad json"))])
    service = LocationService(session=session)

    with pytest.raises(ProviderError, match="invalid JSON"):
        service._get_json("https://example.test/search")


def test_get_json_http_404_raises_provider_error():
    session = FakeSession([FakeResponse({}, status_code=404)])
    service = LocationService(session=session)

    with pytest.raises(ProviderError, match="HTTP 404"):
        service._get_json("https://example.test/search")


def test_get_json_retries_429_then_succeeds(monkeypatch):
    monkeypatch.setattr("weather_app.services.location.time.sleep", lambda seconds: None)

    session = FakeSession(
        [
            FakeResponse({}, status_code=429),
            FakeResponse({"ok": True}, status_code=200),
        ]
    )
    service = LocationService(session=session)

    assert service._get_json("https://example.test/search", attempts=3) == {"ok": True}
    assert len(session.calls) == 2


def test_get_json_retries_5xx_then_raises_network_error(monkeypatch):
    monkeypatch.setattr("weather_app.services.location.time.sleep", lambda seconds: None)

    session = FakeSession(
        [
            FakeResponse({}, status_code=500),
            FakeResponse({}, status_code=502),
            FakeResponse({}, status_code=503),
        ]
    )
    service = LocationService(session=session)

    with pytest.raises(NetworkError, match="temporarily unavailable"):
        service._get_json("https://example.test/search", attempts=3)

    assert len(session.calls) == 3


def test_get_json_timeout_raises_network_error_after_retries(monkeypatch):
    monkeypatch.setattr("weather_app.services.location.time.sleep", lambda seconds: None)

    session = FakeSession(
        [
            requests.exceptions.Timeout("slow"),
            requests.exceptions.Timeout("slow"),
            requests.exceptions.Timeout("slow"),
        ]
    )
    service = LocationService(session=session)

    with pytest.raises(NetworkError, match="timeout"):
        service._get_json("https://example.test/search", attempts=3)

    assert len(session.calls) == 3


def test_get_json_request_exception_raises_network_error_after_retries(monkeypatch):
    monkeypatch.setattr("weather_app.services.location.time.sleep", lambda seconds: None)

    session = FakeSession(
        [
            requests.exceptions.ConnectionError("down"),
            requests.exceptions.ConnectionError("down"),
            requests.exceptions.ConnectionError("down"),
        ]
    )
    service = LocationService(session=session)

    with pytest.raises(NetworkError, match="Network error"):
        service._get_json("https://example.test/search", attempts=3)

    assert len(session.calls) == 3


def test_get_json_caps_attempts_to_three(monkeypatch):
    monkeypatch.setattr("weather_app.services.location.time.sleep", lambda seconds: None)

    session = FakeSession(
        [
            FakeResponse({}, status_code=500),
            FakeResponse({}, status_code=500),
            FakeResponse({}, status_code=500),
            FakeResponse({"should_not": "be_used"}, status_code=200),
        ]
    )
    service = LocationService(session=session)

    with pytest.raises(NetworkError):
        service._get_json("https://example.test/search", attempts=10)

    assert len(session.calls) == 3
