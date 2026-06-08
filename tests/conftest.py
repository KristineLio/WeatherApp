from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from weather_app.domain.models import (
    CurrentSnapshot,
    DailyForecast,
    HourlySeries,
    WeatherData,
)
from weather_app.services.settings_store import SettingsStore
from weather_app.services.storage import StorageRepo


@pytest.fixture
def sample_hourly_series() -> HourlySeries:
    return HourlySeries.from_api(
        {
            "time": [
                "2026-06-07T08:00",
                "2026-06-07T09:00",
                "2026-06-07T10:00",
                "2026-06-07T15:00",
                "2026-06-08T10:00",
                "2026-06-08T15:00",
            ],
            "temperature_2m": [20.0, 22.0, 24.0, 25.0, 23.0, 28.0],
            "weathercode": [0, 1, 2, 3, 61, 0],
            "apparent_temperature": [19.0, 21.0, 23.0, 24.0, 22.0, 27.0],
            "relativehumidity_2m": [55, 58, 60, 62, 70, 65],
            "precipitation_probability": [0, 10, 20, 30, 55, 10],
            "windspeed": [5.0, 8.0, 10.0, 12.0, 15.0, 7.0],
        }
    )


@pytest.fixture
def sample_weather_data(sample_hourly_series: HourlySeries) -> WeatherData:
    return WeatherData(
        current=CurrentSnapshot(
            temp=22.0,
            code=1,
            feels_like=21.0,
            humidity=58,
            precip=10,
            wind=8.0,
            date_iso="2026-06-07",
            time_iso="2026-06-07T09:30",
            city="Sofia, Bulgaria",
        ),
        daily=[
            DailyForecast(
                date_iso="2026-06-07",
                weekday="Sun",
                tmin=16.0,
                tmax=25.0,
                code=1,
                sunrise_iso="2026-06-07T05:50",
                sunset_iso="2026-06-07T20:55",
            ),
            DailyForecast(
                date_iso="2026-06-08",
                weekday="Mon",
                tmin=17.0,
                tmax=28.0,
                code=61,
                sunrise_iso="2026-06-08T05:50",
                sunset_iso="2026-06-08T20:56",
            ),
        ],
        hourly=sample_hourly_series,
        lat=42.6977,
        lon=23.3219,
        resolved_name="Sofia",
        country="Bulgaria",
    )


@pytest.fixture
def tmp_settings_store(tmp_path) -> SettingsStore:
    return SettingsStore(tmp_path / "settings.json")


@pytest.fixture
def tmp_storage_repo(tmp_path) -> StorageRepo:
    return StorageRepo(tmp_path / "weather.db")


class FakeResponse:
    def __init__(self, payload: dict[str, Any] | None = None, *, status_code: int = 200):
        self._payload = payload or {}
        self.status_code = status_code
        self.response = self

    def json(self) -> dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:
        import requests

        if 400 <= self.status_code:
            raise requests.exceptions.HTTPError(response=self)


@dataclass
class FakeSession:
    responses: list[FakeResponse]

    def __post_init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, *, params=None, timeout=None):
        self.calls.append({"url": url, "params": params or {}, "timeout": timeout})
        if not self.responses:
            raise AssertionError("FakeSession has no more responses")
        return self.responses.pop(0)


@pytest.fixture
def fake_session_factory():
    def factory(*responses: FakeResponse) -> FakeSession:
        return FakeSession(list(responses))

    return factory
