"""Deribit option-surface snapshot adapter."""
from __future__ import annotations

import math
import time
from datetime import datetime, timezone
from typing import Any, Callable, Optional

import httpx


class DeribitOptionSurfaceClient:
    """Fetch one aggregate option-surface snapshot per currency."""

    endpoint = "https://www.deribit.com/api/v2/public/get_book_summary_by_currency"

    def __init__(
        self,
        timeout: float = 20.0,
        *,
        sleep: Callable[[float], None] = time.sleep,
        retries: int = 2,
    ) -> None:
        self.timeout = timeout
        self.sleep = sleep
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

    def fetch(self, *, currency: str) -> list[dict[str, Any]]:
        result = self._get({"currency": str(currency).upper(), "kind": "option"}).get("result") or []
        row = aggregate_option_surface(str(currency).upper(), result)
        return [row] if row else []


def aggregate_option_surface(currency: str, rows: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    parsed = [_parse_option(row) for row in rows]
    options = [row for row in parsed if row is not None]
    if not options:
        return None

    put_oi = sum(row["open_interest"] for row in options if row["option_type"] == "P")
    call_oi = sum(row["open_interest"] for row in options if row["option_type"] == "C")
    total_oi = put_oi + call_oi
    iv_weight = sum(row["open_interest"] * row["mark_iv"] for row in options if row["mark_iv"] is not None)
    iv_oi = sum(row["open_interest"] for row in options if row["mark_iv"] is not None)
    timestamps = [row["creation_timestamp"] for row in options if row["creation_timestamp"] is not None]
    if not timestamps:
        return None
    snapshot_ms = max(timestamps)
    observed_at = datetime.fromtimestamp(snapshot_ms / 1000, tz=timezone.utc)

    return {
        "observed_at": observed_at,
        "published_at": observed_at,
        "value_num": total_oi,
        "value_text": None,
        "fields": {
            "put_oi": put_oi,
            "call_oi": call_oi,
            "pc_oi_ratio": put_oi / call_oi if call_oi else None,
            "max_pain_strike": _max_pain_strike(options),
            "oi_weighted_mark_iv": iv_weight / iv_oi if iv_oi else None,
            "spot_index": _first_float(rows, "estimated_delivery_price"),
            "n_instruments": len(options),
            "unit": "base_contracts",
        },
        "quality_status": "raw",
        "raw_payload": _top_open_interest(rows, limit=20),
    }


def _parse_option(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    name = str(row.get("instrument_name") or "")
    parts = name.split("-")
    if len(parts) < 4 or parts[-1] not in {"C", "P"}:
        return None
    open_interest = _to_float(row.get("open_interest"))
    strike = _to_float(parts[-2])
    if open_interest is None or strike is None:
        return None
    return {
        "instrument_name": name,
        "option_type": parts[-1],
        "strike": strike,
        "open_interest": open_interest,
        "mark_iv": _to_float(row.get("mark_iv")),
        "creation_timestamp": _to_int(row.get("creation_timestamp")),
    }


def _max_pain_strike(options: list[dict[str, Any]]) -> Optional[float]:
    strikes = sorted({row["strike"] for row in options})
    if not strikes:
        return None
    pain_by_strike = {}
    for settlement in strikes:
        pain = 0.0
        for row in options:
            if row["option_type"] == "C" and settlement > row["strike"]:
                pain += (settlement - row["strike"]) * row["open_interest"]
            elif row["option_type"] == "P" and settlement < row["strike"]:
                pain += (row["strike"] - settlement) * row["open_interest"]
        pain_by_strike[settlement] = pain
    return min(pain_by_strike, key=lambda strike: (pain_by_strike[strike], strike))


def _top_open_interest(rows: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: _to_float(row.get("open_interest")) or 0.0,
        reverse=True,
    )[:limit]


def _first_float(rows: list[dict[str, Any]], key: str) -> Optional[float]:
    for row in rows:
        value = _to_float(row.get(key))
        if value is not None:
            return value
    return None


def _to_float(value: Any) -> Optional[float]:
    if value in (None, "", "."):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _to_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _retry_after(response: httpx.Response, attempt: int) -> float:
    try:
        return max(float(response.headers.get("Retry-After", "")), 0.0)
    except ValueError:
        return 0.5 * (attempt + 1)
