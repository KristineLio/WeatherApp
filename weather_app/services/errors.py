# weather_app/services/errors.py
from __future__ import annotations


class WeatherServiceError(RuntimeError):
    """Base class for service/runtime failures (not user input)."""


class NetworkError(WeatherServiceError):
    """Connectivity / timeout / DNS / request-layer problems."""


class ProviderError(WeatherServiceError):
    """Upstream API returned bad data / unexpected response / parsing failure."""


def is_retryable_error(err: BaseException) -> bool:
    """UI/network retry policy: only retry on network failures."""
    return isinstance(err, NetworkError)