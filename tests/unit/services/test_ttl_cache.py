import time

from weather_app.services.ttl_cache import TTLCache


def test_set_and_get_value():
    cache = TTLCache[str, int](ttl_s=60)

    cache.set("a", 1)

    assert cache.get("a") == 1


def test_missing_key_returns_none():
    cache = TTLCache[str, int](ttl_s=60)

    assert cache.get("missing") is None


def test_expired_key_returns_none():
    cache = TTLCache[str, int](ttl_s=0)

    cache.set("a", 1)

    assert cache.get("a") is None


def test_delete_removes_key():
    cache = TTLCache[str, int](ttl_s=60)
    cache.set("a", 1)

    cache.delete("a")

    assert cache.get("a") is None


def test_clear_removes_all_keys():
    cache = TTLCache[str, int](ttl_s=60)
    cache.set("a", 1)
    cache.set("b", 2)

    cache.clear()

    assert cache.get("a") is None
    assert cache.get("b") is None


def test_value_expires_after_ttl():
    cache = TTLCache[str, int](ttl_s=1)
    cache.set("a", 1)

    time.sleep(1.05)

    assert cache.get("a") is None
