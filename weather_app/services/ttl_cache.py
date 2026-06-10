from __future__ import annotations

import threading
import time
from typing import Generic, TypeVar


K = TypeVar("K")
V = TypeVar("V")


class TTLCache(Generic[K, V]):
    """
    Tiny thread-safe in-memory TTL cache.

    Stores:
        key -> (timestamp, value)

    Notes:
    - ttl_s <= 0 means get() treats items as expired immediately.
    - Expired entries are removed lazily on read.
    """

    def __init__(self, ttl_s: int):
        self._ttl_s = max(0, int(ttl_s))
        self._data: dict[K, tuple[float, V]] = {}
        self._lock = threading.Lock()

    @property
    def ttl_s(self) -> int:
        return self._ttl_s

    def get(self, key: K) -> V | None:
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None

            ts, value = item
            if self._ttl_s <= 0 or (time.time() - ts > self._ttl_s):
                self._data.pop(key, None)
                return None

            return value

    def set(self, key: K, value: V) -> None:
        with self._lock:
            self._data[key] = (time.time(), value)

    def delete(self, key: K) -> None:
        with self._lock:
            self._data.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()