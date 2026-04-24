# tests/test_retry_policy.py
from __future__ import annotations

from weather_app.services.errors import NetworkError, ProviderError, is_retryable_error


def test_retry_policy_retries_only_on_network_error():
    assert is_retryable_error(NetworkError("Network error: timeout")) is True
    assert is_retryable_error(ProviderError("Weather service error: bad payload")) is False
    assert is_retryable_error(RuntimeError("some other runtime")) is False
    assert is_retryable_error(ValueError("city not found")) is False