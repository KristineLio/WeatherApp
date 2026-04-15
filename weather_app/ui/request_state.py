# weather_app/ui/request_state.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RequestState:
    _req_seq: int = 0
    _active_req: int = 0
    reconnect_seconds: int = 0

    def begin_request(self) -> int:
        self._req_seq += 1
        self._active_req = self._req_seq
        return self._active_req

    def is_latest(self, req_id: int) -> bool:
        return req_id == self._active_req

    def start_reconnect(self, seconds: int) -> None:
        self.reconnect_seconds = max(0, int(seconds))

    def clear_reconnect(self) -> None:
        self.reconnect_seconds = 0

    def tick_reconnect(self) -> int:
        """
        Decrease countdown by one second.
        Returns the new value.
        """
        if self.reconnect_seconds > 0:
            self.reconnect_seconds -= 1
        return self.reconnect_seconds

    def should_retry_city(self, *, failed_req_id: int, requested_city: str, current_city: str) -> bool:
        """
        Pure retry policy:
        - only latest failed request may retry
        - only retry if the input city still matches
        """
        return (
            self.is_latest(failed_req_id)
            and (current_city or "").strip().lower() == (requested_city or "").strip().lower()
        )