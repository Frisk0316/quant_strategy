"""Deribit perpetual funding-history adapter."""
from __future__ import annotations

import math
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

import httpx


class DeribitFundingClient:
    """Fetch Deribit hourly perpetual funding rows."""

    endpoint = "https://www.deribit.com/api/v2/public/get_funding_rate_history"

    def __init__(
        self,
        timeout: float = 20.0,
        *,
        sleep: Callable[[float], None] = time.sleep,
        page_delay: float = 0.2,
        retries: int = 2,
    ) -> None:
        self.timeout = timeout
        self.sleep = sleep
        self.page_delay = page_delay
        self.retries = retries

    def _get(self, params: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(self.retries + 1):
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(self.endpoint, params=params)
                if response.status_code == 429 and attempt < self.retries:
                    self.sleep(_retry_after(response, attempt))
                    continue
                response.raise_for_status()
                payload = response.json()
            error = payload.get("error") if isinstance(payload, dict) else None
            if isinstance(error, dict) and error.get("code") == 10028 and attempt < self.retries:
                self.sleep(0.5 * (attempt + 1))
                continue
            return payload
        return payload

    def fetch(
        self,
        *,
        instrument_name: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> list[dict[str, Any]]:
        if end is None:
            end = datetime.now(timezone.utc)
        if start is None:
            start = end - timedelta(days=2)
        start = _as_utc(start)
        end = _as_utc(end)
        params: dict[str, Any] = {
            "instrument_name": str(instrument_name).upper(),
            "start_timestamp": _to_ms(start),
            "end_timestamp": _to_ms(end),
        }
        rows: dict[datetime, dict[str, Any]] = {}
        seen_ends: set[int] = set()
        while True:
            raw_rows = self._get(params).get("result") or []
            if not raw_rows:
                break
            page_first: datetime | None = None
            for item in raw_rows:
                row = _parse_row(item, params["instrument_name"], start, end)
                if row is None:
                    continue
                observed_at = row["observed_at"]
                rows[observed_at] = row
                page_first = observed_at if page_first is None else min(page_first, observed_at)
            if page_first is None or page_first <= start:
                break
            next_end = _to_ms(page_first)
            if next_end in seen_ends:
                break
            seen_ends.add(next_end)
            params["end_timestamp"] = next_end
            if self.page_delay > 0:
                self.sleep(self.page_delay)
        return [rows[key] for key in sorted(rows)]


def _parse_row(
    item: Any,
    instrument_name: str,
    start: datetime,
    end: datetime,
) -> Optional[dict[str, Any]]:
    if not isinstance(item, dict):
        return None
    try:
        observed_at = datetime.fromtimestamp(int(item["timestamp"]) / 1000, tz=timezone.utc)
    except (KeyError, TypeError, ValueError):
        return None
    if observed_at < start or observed_at >= end:
        return None
    interest_1h = _to_float(item.get("interest_1h"))
    if interest_1h is None:
        return None
    return {
        "observed_at": observed_at,
        "published_at": observed_at,
        "value_num": interest_1h,
        "value_text": None,
        "fields": {
            "instrument": instrument_name,
            "interest_8h": _to_float(item.get("interest_8h")),
            "index_price": _to_float(item.get("index_price")),
            "prev_index_price": _to_float(item.get("prev_index_price")),
            "unit": "rate_1h_decimal",
        },
        "quality_status": "raw",
        "raw_payload": item,
    }


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


def _retry_after(response: httpx.Response, attempt: int) -> float:
    try:
        return max(float(response.headers.get("Retry-After", "")), 0.0)
    except ValueError:
        return 0.5 * (attempt + 1)
