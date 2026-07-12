"""Deribit option-flow trade-tape adapter.

Aggregation definitions:
value_num = pc_taker_premium_imbalance = (put_taker_buy_premium - call_taker_buy_premium) / max(total_taker_buy_premium, EPSILON);
fields = {call_buy_amt, call_sell_amt, put_buy_amt, put_sell_amt,
premium_volume, premium_unit (BTC/ETH for inverse; USDC for linear -- aggregate inverse instruments only in v1 and record the exclusion),
avg_trade_iv, trade_count, liq_trade_count, unit: "imbalance_ratio"}.
Direction = taker side from `direction`; put/call parsed from instrument name.
"""
from __future__ import annotations

import math
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

import httpx

EPSILON = 1e-12


class DeribitOptionFlowClient:
    """Fetch Deribit option trades and aggregate hourly flow rows."""

    history_endpoint = "https://history.deribit.com/api/v2/public/get_last_trades_by_currency_and_time"
    www_endpoint = "https://www.deribit.com/api/v2/public/get_last_trades_by_currency_and_time"

    def __init__(
        self,
        endpoint: str | None = None,
        timeout: float = 30.0,
        *,
        sleep: Callable[[float], None] = time.sleep,
        page_delay: float = 0.2,
        retries: int = 2,
    ) -> None:
        self.endpoint = endpoint or self.history_endpoint
        self.timeout = timeout
        self.sleep = sleep
        self.page_delay = page_delay
        self.retries = retries
        self.last_page_count = 0

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

    def fetch_trades(
        self,
        *,
        currency: str,
        start: datetime,
        end: datetime,
        count: int = 1000,
    ) -> list[dict[str, Any]]:
        start = _as_utc(start)
        end = _as_utc(end)
        params: dict[str, Any] = {
            "currency": str(currency).upper(),
            "kind": "option",
            "start_timestamp": _to_ms(start),
            "end_timestamp": _to_ms(end),
            "count": int(count),
        }
        trades: dict[str, dict[str, Any]] = {}
        seen_ends: set[int] = set()
        pages = 0
        while True:
            result = self._get(params).get("result") or {}
            pages += 1
            page = result.get("trades") or []
            if not page:
                break
            min_ts: int | None = None
            for trade in page:
                ts = _to_int(trade.get("timestamp"))
                if ts is None:
                    continue
                min_ts = ts if min_ts is None else min(min_ts, ts)
                observed_at = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
                if observed_at < start or observed_at >= end:
                    continue
                key = str(trade.get("trade_id") or f"{ts}:{trade.get('instrument_name')}:{trade.get('direction')}")
                trades[key] = trade
            if not result.get("has_more") or min_ts is None or min_ts <= _to_ms(start):
                break
            if min_ts in seen_ends:
                break
            seen_ends.add(min_ts)
            params["end_timestamp"] = min_ts
            if self.page_delay > 0:
                self.sleep(self.page_delay)
        self.last_page_count = pages
        return sorted(trades.values(), key=lambda trade: int(trade.get("timestamp") or 0))

    def fetch(
        self,
        *,
        currency: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> list[dict[str, Any]]:
        if end is None:
            end = datetime.now(timezone.utc)
        if start is None:
            start = end - timedelta(hours=2)
        return aggregate_hourly_option_flow(currency, self.fetch_trades(currency=currency, start=start, end=end))


def parse_option_instrument(instrument_name: str, *, currency: str) -> dict[str, Any]:
    parts = str(instrument_name or "").split("-")
    base = parts[0] if parts else ""
    option_type = parts[-1] if len(parts) >= 4 else ""
    strike = _to_float(parts[-2]) if len(parts) >= 4 else None
    linear_usdc = base.endswith("_USDC")
    clean_base = base.replace("_USDC", "")
    inverse = clean_base == str(currency).upper() and option_type in {"C", "P"} and not linear_usdc
    return {
        "base": clean_base,
        "strike": strike,
        "option_type": option_type,
        "premium_unit": "USDC" if linear_usdc else clean_base,
        "is_inverse": inverse,
    }


def aggregate_hourly_option_flow(currency: str, trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    currency = str(currency).upper()
    buckets: dict[datetime, dict[str, Any]] = defaultdict(_empty_bucket)
    for trade in trades:
        ts = _to_int(trade.get("timestamp"))
        if ts is None:
            continue
        hour = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).replace(minute=0, second=0, microsecond=0)
        meta = parse_option_instrument(str(trade.get("instrument_name") or ""), currency=currency)
        bucket = buckets[hour]
        if not meta["is_inverse"]:
            bucket["excluded_linear_usdc_count"] += 1
            continue
        option_type = meta["option_type"]
        direction = str(trade.get("direction") or "").lower()
        premium = _premium_amount(trade)
        if premium is None or option_type not in {"C", "P"} or direction not in {"buy", "sell"}:
            continue
        field = f"{'call' if option_type == 'C' else 'put'}_{direction}_amt"
        bucket[field] += premium
        bucket["premium_volume"] += premium
        bucket["trade_count"] += 1
        bucket["premium_unit"] = currency
        if trade.get("liquidation"):
            bucket["liq_trade_count"] += 1
        iv = _to_float(trade.get("iv"))
        if iv is not None:
            bucket["iv_sum"] += iv
            bucket["iv_count"] += 1
        if len(bucket["sample"]) < 20:
            bucket["sample"].append(trade)

    rows = []
    for hour, bucket in sorted(buckets.items()):
        if bucket["trade_count"] <= 0 and bucket["excluded_linear_usdc_count"] <= 0:
            continue
        value = None
        if bucket["trade_count"] > 0:
            total_buy = bucket["call_buy_amt"] + bucket["put_buy_amt"]
            value = (bucket["put_buy_amt"] - bucket["call_buy_amt"]) / max(total_buy, EPSILON)
        fields = {
            "call_buy_amt": bucket["call_buy_amt"],
            "call_sell_amt": bucket["call_sell_amt"],
            "put_buy_amt": bucket["put_buy_amt"],
            "put_sell_amt": bucket["put_sell_amt"],
            "premium_volume": bucket["premium_volume"],
            "premium_unit": bucket["premium_unit"],
            "avg_trade_iv": bucket["iv_sum"] / bucket["iv_count"] if bucket["iv_count"] else None,
            "trade_count": bucket["trade_count"],
            "liq_trade_count": bucket["liq_trade_count"],
            "unit": "imbalance_ratio",
            "excluded_linear_usdc_count": bucket["excluded_linear_usdc_count"],
        }
        rows.append({
            "observed_at": hour,
            "published_at": hour + timedelta(hours=1),
            "value_num": value,
            "value_text": None,
            "fields": fields,
            "quality_status": "raw",
            "raw_payload": {
                "sample_rule": "first_20_inverse_trades_in_hour",
                "sample": bucket["sample"],
            },
        })
    return rows


def _empty_bucket() -> dict[str, Any]:
    return {
        "call_buy_amt": 0.0,
        "call_sell_amt": 0.0,
        "put_buy_amt": 0.0,
        "put_sell_amt": 0.0,
        "premium_volume": 0.0,
        "premium_unit": None,
        "iv_sum": 0.0,
        "iv_count": 0,
        "trade_count": 0,
        "liq_trade_count": 0,
        "excluded_linear_usdc_count": 0,
        "sample": [],
    }


def _premium_amount(trade: dict[str, Any]) -> Optional[float]:
    amount = _to_float(trade.get("amount"))
    price = _to_float(trade.get("price"))
    if amount is None or price is None:
        return None
    return amount * price


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
