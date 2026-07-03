"""Binance futures open-interest history adapter."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx


class BinanceOIClient:
    """Fetch Binance USDT-M futures open-interest history."""

    endpoint = "https://fapi.binance.com/futures/data/openInterestHist"

    def __init__(self, timeout: float = 20.0) -> None:
        self.timeout = timeout

    def _get(self, params: dict[str, Any]) -> Any:
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(self.endpoint, params=params)
            response.raise_for_status()
            return response.json()

    def fetch(
        self,
        *,
        symbol: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        interval: str = "1h",
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        start_ms = _to_ms(start) if start else None
        end_ms = _to_ms(end) if end else None
        if start_ms is None and end_ms is None:
            start_ms = _to_ms(now - timedelta(days=30))
            end_ms = _to_ms(now)

        payload: list[Any] = []
        cursor_ms = start_ms
        while True:
            params: dict[str, Any] = {
                "symbol": str(symbol).upper(),
                "period": str(interval),
                "limit": int(limit),
            }
            if cursor_ms is not None:
                params["startTime"] = cursor_ms
            if end_ms is not None:
                params["endTime"] = end_ms
            batch = self._get(params)
            if not isinstance(batch, list) or not batch:
                break
            payload.extend(batch)
            timestamps = [int(item["timestamp"]) for item in batch if "timestamp" in item]
            if cursor_ms is None or len(batch) < int(limit) or not timestamps:
                break
            next_cursor = max(timestamps) + 1
            if next_cursor <= cursor_ms or (end_ms is not None and next_cursor >= end_ms):
                break
            cursor_ms = next_cursor

        rows: list[dict[str, Any]] = []
        for item in payload:
            try:
                observed_at = datetime.fromtimestamp(int(item["timestamp"]) / 1000, tz=timezone.utc)
            except (KeyError, TypeError, ValueError):
                continue
            if start and observed_at < _as_utc(start):
                continue
            if end and observed_at >= _as_utc(end):
                continue
            notional = _to_float(item.get("sumOpenInterestValue"))
            contracts = _to_float(item.get("sumOpenInterest"))
            if notional is None:
                continue
            rows.append({
                "observed_at": observed_at,
                "published_at": observed_at,
                "value_num": notional,
                "value_text": None,
                "fields": {
                    "symbol": str(symbol).upper(),
                    "interval": str(interval),
                    "unit": "USDT_notional",
                    "value_unit": "USDT_notional",
                    "source_value_field": "sumOpenInterestValue",
                    "open_interest_contracts": contracts,
                },
                "quality_status": "raw",
                "raw_payload": item,
            })
        return sorted(rows, key=lambda row: row["observed_at"])


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _to_ms(value: datetime) -> int:
    return int(_as_utc(value).timestamp() * 1000)


def _to_float(value: Any) -> Optional[float]:
    if value in (None, "", "."):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
