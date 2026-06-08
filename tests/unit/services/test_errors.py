import pytest

from weather_app.services.errors import (
    NetworkError,
    ProviderError,
    WeatherServiceError,
    is_retryable_error,
)


def test_network_error_is_weather_service_error():
    assert issubclass(NetworkError, WeatherServiceError)


def test_provider_error_is_weather_service_error():
    assert issubclass(ProviderError, WeatherServiceError)


def test_only_network_errors_are_retryable():
    assert is_retryable_error(NetworkError("timeout")) is True
    assert is_retryable_error(ProviderError("bad provider response")) is False
    assert is_retryable_error(ValueError("bad user input")) is False
    assert is_retryable_error(RuntimeError("other")) is False
