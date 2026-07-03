"""Deribit DVOL volatility-index adapter."""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Optional

import httpx


class DeribitDVOLClient:
    """Fetch Deribit volatility index OHLC rows."""

    endpoint = "https://www.deribit.com/api/v2/public/get_volatility_index_data"

    def __init__(self, timeout: float = 20.0) -> None:
        self.timeout = timeout

    def _get(self, params: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(self.endpoint, params=params)
            response.raise_for_status()
            return response.json()

    def fetch(
        self,
        *,
        currency: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        resolution: str = "1D",
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "currency": str(currency).upper(),
            "resolution": str(resolution),
        }
        if start:
            params["start_timestamp"] = _to_ms(start)
        if end:
            params["end_timestamp"] = _to_ms(end)

        result = (self._get(params).get("result") or {})
        rows: list[dict[str, Any]] = []
        for item in result.get("data", []) or []:
            parsed = _parse_item(item)
            if not parsed:
                continue
            observed_at, open_, high, low, close = parsed
            if start and observed_at < _as_utc(start):
                continue
            if end and observed_at >= _as_utc(end):
                continue
            if close is None:
                continue
            rows.append({
                "observed_at": observed_at,
                "published_at": observed_at,
                "value_num": close,
                "value_text": None,
                "fields": {
                    "currency": str(currency).upper(),
                    "resolution": str(resolution),
                    "unit": "dvol_index_points",
                    "value_unit": "dvol_index_points",
                    "source_value_field": "close",
                    "open": open_,
                    "high": high,
                    "low": low,
                    "close": close,
                },
                "quality_status": "raw",
                "raw_payload": item,
            })
        return sorted(rows, key=lambda row: row["observed_at"])


def _parse_item(item: Any) -> Optional[tuple[datetime, Optional[float], Optional[float], Optional[float], Optional[float]]]:
    if isinstance(item, dict):
        ts = item.get("timestamp") or item.get("time")
        values = [item.get("open"), item.get("high"), item.get("low"), item.get("close")]
    elif isinstance(item, (list, tuple)) and len(item) >= 5:
        ts = item[0]
        values = list(item[1:5])
    else:
        return None
    try:
        observed_at = datetime.fromtimestamp(int(ts) / 1000, tz=timezone.utc)
    except (TypeError, ValueError):
        return None
    return (
        observed_at,
        _to_float(values[0]),
        _to_float(values[1]),
        _to_float(values[2]),
        _to_float(values[3]),
    )


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
