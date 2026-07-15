"""Deribit public REST client for perpetual 1m candles."""
from __future__ import annotations

import math
import time
from typing import Any

import httpx


_BASE_URL = "https://www.deribit.com"
_CHART_PATH = "/api/v2/public/get_tradingview_chart_data"
_RATE_SLEEP = 0.2  # Project Deribit limit: no more than five requests/second.


class DeribitPublicClient:
    """Credential-free Deribit TradingView candle client."""

    def __init__(
        self,
        timeout: float = 20.0,
        rate_sleep: float = _RATE_SLEEP,
        base_url: str = _BASE_URL,
    ) -> None:
        self._client = httpx.Client(base_url=base_url, timeout=timeout)
        self._rate_sleep = rate_sleep

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "DeribitPublicClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _get(self, params: dict[str, Any]) -> dict[str, Any]:
        response = self._client.get(_CHART_PATH, params=params)
        response.raise_for_status()
        payload = response.json()
        if payload.get("error"):
            raise RuntimeError(f"Deribit public API error: {payload['error']}")
        result = payload.get("result")
        if not isinstance(result, dict):
            raise RuntimeError("Deribit chart response missing result")
        return result

    def get_tradingview_chart_data(
        self,
        instrument_name: str,
        *,
        start_ms: int,
        end_ms: int,
        resolution: int = 1,
    ) -> list[dict[str, Any]]:
        """Fetch one bounded page of normalized 1m trade candles."""
        if resolution != 1:
            raise ValueError("Deribit ingestion supports resolution=1 only")
        time.sleep(self._rate_sleep)
        result = self._get(
            {
                "instrument_name": instrument_name,
                "start_timestamp": start_ms,
                "end_timestamp": end_ms,
                "resolution": str(resolution),
            }
        )
        if result.get("status") == "no_data":
            return []
        if result.get("status") != "ok":
            raise RuntimeError(f"Deribit chart status: {result.get('status')!r}")

        names = ("ticks", "open", "high", "low", "close", "volume", "cost")
        columns = [result.get(name) for name in names]
        if any(not isinstance(column, list) for column in columns):
            raise RuntimeError("Deribit chart response has invalid columns")
        if len({len(column) for column in columns}) != 1:
            raise RuntimeError("Deribit chart response has mismatched column lengths")

        now_ms = int(time.time() * 1000)
        rows: list[dict[str, Any]] = []
        for tick, open_, high, low, close, volume, cost in zip(*columns):
            values = [float(open_), float(high), float(low), float(close)]
            if not all(math.isfinite(value) and value > 0 for value in values):
                raise RuntimeError("Deribit chart response has invalid OHLC values")
            ts_ms = int(tick)
            rows.append(
                {
                    "ts_ms": ts_ms,
                    "open": values[0],
                    "high": values[1],
                    "low": values[2],
                    "close": values[3],
                    "vol_contract": None,
                    "vol_base": float(volume) if volume is not None else None,
                    "vol_quote": float(cost) if cost is not None else None,
                    "is_closed": ts_ms + 60_000 <= now_ms,
                    "raw_payload": {
                        "exchange": "deribit",
                        "instrument_name": instrument_name,
                        "resolution": "1",
                    },
                }
            )
        rows.sort(key=lambda row: row["ts_ms"])
        return rows
