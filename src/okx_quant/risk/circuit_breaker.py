"""
Infrastructure circuit breakers — independent of market/strategy conditions.
Trips on excessive WS reconnects or high REST error rate.
"""
from __future__ import annotations

import time
from collections import deque
from typing import Optional

from loguru import logger


class CircuitBreaker:
    def __init__(
        self,
        ws_reconnect_threshold: int = 3,
        ws_window_secs: float = 60.0,
        rest_error_threshold: float = 0.05,
        rest_window: int = 100,
        on_trip_callback=None,
    ) -> None:
        self._ws_threshold = ws_reconnect_threshold
        self._ws_window = ws_window_secs
        self._rest_threshold = rest_error_threshold
        self._rest_window = rest_window
        self._on_trip = on_trip_callback

        self._ws_reconnect_times: list[float] = []
        self._rest_results: deque = deque(maxlen=rest_window)  # True=success, False=error

        self.tripped: bool = False
        self.trip_reason: Optional[str] = None
        self.trip_time: Optional[float] = None

    def record_ws_reconnect(self) -> None:
        """Call each time the WebSocket reconnects."""
        now = time.time()
        self._ws_reconnect_times.append(now)
        self._ws_reconnect_times = [
            t for t in self._ws_reconnect_times if now - t <= self._ws_window
        ]
        count = len(self._ws_reconnect_times)
        if count > self._ws_threshold:
            self._trip(f"WS reconnect: {count} times in {self._ws_window}s")

    def record_rest_call(self, success: bool) -> None:
        """Call after every REST API call. success=False for HTTP errors."""
        self._rest_results.append(success)
        if len(self._rest_results) >= self._rest_window:
            error_rate = 1 - (sum(self._rest_results) / len(self._rest_results))
            if error_rate > self._rest_threshold:
                self._trip(
                    f"REST error rate: {error_rate:.1%} over last {len(self._rest_results)} calls"
                )

    def _trip(self, reason: str) -> None:
        if self.tripped:
            return
        self.tripped = True
        self.trip_reason = reason
        self.trip_time = time.time()
        logger.error("Circuit breaker TRIPPED", reason=reason)
        if self._on_trip:
            self._on_trip(reason)

    def reset(self) -> None:
        """Manual reset only — called via Telegram /reset command."""
        if not self.tripped:
            return
        self.tripped = False
        self.trip_reason = None
        self.trip_time = None
        self._ws_reconnect_times.clear()
        self._rest_results.clear()
        logger.warning("Circuit breaker RESET by operator")
