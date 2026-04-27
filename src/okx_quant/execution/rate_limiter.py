"""
Token-bucket rate limiter for OKX API rate limits.
OKX limits: 60 orders/2s per instrument (REST + WS shared bucket).
Public market data: 40 req/2s per endpoint.
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict


class RateLimiter:
    def __init__(
        self,
        # Trading: 60 req per 2s per instrument
        trade_rate: int = 60,
        trade_window_secs: float = 2.0,
        # Market data: 40 req per 2s
        market_rate: int = 40,
        market_window_secs: float = 2.0,
    ) -> None:
        self._trade_rate = trade_rate
        self._trade_window = trade_window_secs
        self._market_rate = market_rate
        self._market_window = market_window_secs

        # Timestamps of recent requests per (bucket_type, key)
        self._timestamps: dict[tuple, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def acquire_trade(self, inst_id: str) -> None:
        """Wait until a trade request slot is available for this instrument."""
        await self._acquire("trade", inst_id, self._trade_rate, self._trade_window)

    async def acquire_market(self, endpoint: str) -> None:
        """Wait until a market data slot is available for this endpoint."""
        await self._acquire("market", endpoint, self._market_rate, self._market_window)

    async def _acquire(self, bucket: str, key: str, rate: int, window: float) -> None:
        async with self._lock:
            bkey = (bucket, key)
            now = time.monotonic()
            # Remove expired timestamps
            self._timestamps[bkey] = [
                t for t in self._timestamps[bkey] if now - t < window
            ]
            if len(self._timestamps[bkey]) >= rate:
                # Wait until oldest slot expires
                oldest = self._timestamps[bkey][0]
                wait = window - (now - oldest)
                if wait > 0:
                    await asyncio.sleep(wait)
                # Clean up again after waiting
                now = time.monotonic()
                self._timestamps[bkey] = [
                    t for t in self._timestamps[bkey] if now - t < window
                ]
            self._timestamps[bkey].append(time.monotonic())
