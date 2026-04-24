# tests/test_openmeteo_error_mapping.py
from __future__ import annotations

import pytest
import requests

from weather_app.services.openmeteo import WeatherService
from weather_app.services.errors import NetworkError, ProviderError
from weather_app.domain.settings import Units


class FakeResponse:
    def __init__(self, json_data=None, status_code=200):
        self._json = json_data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError("HTTP error")

    def json(self):
        return self._json


class FakeSession:
    def __init__(self, *, should_timeout=False, json_data=None):
        self.should_timeout = should_timeout
        self.json_data = json_data

    def get(self, *args, **kwargs):
        if self.should_timeout:
            raise requests.Timeout("timeout")
        return FakeResponse(self.json_data)

def _make_svc() -> WeatherService:
    # Inject a dummy session so nothing real is used.
    session = requests.Session()
    return WeatherService(session=session)

def test_fetch_city_not_found_keeps_valueerror(monkeypatch):
    svc = _make_svc()

    def fake_geocode(_city: str):
        raise ValueError("City not found")

    monkeypatch.setattr(svc, "_geocode_city", fake_geocode)

    with pytest.raises(ValueError, match="City not found"):
        svc.fetch("NoSuchCity", units=Units.METRIC, forecast_days=3)

def test_timeout_becomes_network_error():
    svc = WeatherService(session=FakeSession(should_timeout=True))

    with pytest.raises(NetworkError):
        svc.fetch("Sofia", units=Units.METRIC, forecast_days=3)

def test_fetch_network_runtimeerror_becomes_networkerror(monkeypatch):
    svc = _make_svc()

    monkeypatch.setattr(svc, "_geocode_city", lambda city: (42.0, 23.0, "Sofia", "BG"))

    def fake_get_json(_url: str, *, params=None, timeout=10):
        raise RuntimeError("Network error: timeout")

    monkeypatch.setattr(svc, "_get_json", fake_get_json)

    with pytest.raises(NetworkError, match=r"^Network error: timeout$"):
        svc.fetch("Sofia", units=Units.METRIC, forecast_days=3)


def test_fetch_provider_runtimeerror_becomes_providererror(monkeypatch):
    svc = _make_svc()

    monkeypatch.setattr(svc, "_geocode_city", lambda city: (42.0, 23.0, "Sofia", "BG"))

    def fake_get_json(_url: str, *, params=None, timeout=10):
        raise RuntimeError("Weather service error: upstream returned 500")

    monkeypatch.setattr(svc, "_get_json", fake_get_json)

    with pytest.raises(ProviderError, match=r"^Weather service error: upstream returned 500$"):
        svc.fetch("Sofia", units=Units.METRIC, forecast_days=3)


def test_fetch_missing_current_time_becomes_providererror(monkeypatch):
    svc = _make_svc()

    monkeypatch.setattr(svc, "_geocode_city", lambda city: (42.0, 23.0, "Sofia", "BG"))

    # Minimal payload shape but missing current_weather.time
    def fake_get_json(_url: str, *, params=None, timeout=10):
        return {
            "current_weather": {"temperature": 10.0, "weathercode": 2},
            "daily": {"time": ["2026-01-01"], "temperature_2m_max": [12.0], "temperature_2m_min": [5.0],
                      "weathercode": [2], "sunrise": ["2026-01-01T07:30"], "sunset": ["2026-01-01T17:10"]},
            "hourly": {"time": ["2026-01-01T12:00"], "temperature_2m": [10.0], "weathercode": [2]},
        }

    monkeypatch.setattr(svc, "_get_json", fake_get_json)

    with pytest.raises(ProviderError, match="unexpected response"):
        svc.fetch("Sofia", units=Units.METRIC, forecast_days=1)


def test_fetch_unexpected_exception_becomes_providererror(monkeypatch):
    svc = _make_svc()

    monkeypatch.setattr(svc, "_geocode_city", lambda city: (42.0, 23.0, "Sofia", "BG"))

    def fake_get_json(_url: str, *, params=None, timeout=10):
        return {
            # trigger a random bug downstream (e.g. None or wrong type)
            "current_weather": None,
            "daily": None,
            "hourly": None,
        }

    monkeypatch.setattr(svc, "_get_json", fake_get_json)

    with pytest.raises(ProviderError, match="failed while processing data"):
        svc.fetch("Sofia", units=Units.METRIC, forecast_days=1)