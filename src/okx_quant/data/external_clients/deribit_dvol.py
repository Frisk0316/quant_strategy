"""Deribit DVOL volatility-index adapter."""
from __future__ import annotations

import math
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

import httpx


class DeribitDVOLClient:
    """Fetch Deribit volatility index OHLC rows."""

    endpoint = "https://www.deribit.com/api/v2/public/get_volatility_index_data"

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
        currency: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        resolution: str = "1D",
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "currency": str(currency).upper(),
            "resolution": str(resolution),
        }
        publish_delta = _resolution_delta(str(resolution))
        if start:
            params["start_timestamp"] = _to_ms(start)
        if end:
            params["end_timestamp"] = _to_ms(end)

        rows: dict[datetime, dict[str, Any]] = {}
        seen_continuations: set[str] = set()
        while True:
            result = (self._get(params).get("result") or {})
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
                rows[observed_at] = {
                    "observed_at": observed_at,
                    "published_at": observed_at + publish_delta,
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
                }
            continuation = result.get("continuation")
            if not continuation:
                break
            continuation = str(continuation)
            if continuation in seen_continuations:
                break
            seen_continuations.add(continuation)
            try:
                continuation_ms = int(continuation)
            except ValueError:
                params["continuation"] = continuation
                continue
            if start and continuation_ms <= _to_ms(start):
                break
            params.pop("continuation", None)
            params["end_timestamp"] = continuation_ms
            if self.page_delay > 0:
                self.sleep(self.page_delay)
        return [rows[key] for key in sorted(rows)]


class DeribitHistoricalVolatilityClient(DeribitDVOLClient):
    """Fetch Deribit's recent rolling historical-volatility series."""

    endpoint = "https://www.deribit.com/api/v2/public/get_historical_volatility"

    def fetch(
        self,
        *,
        currency: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> list[dict[str, Any]]:
        currency = str(currency).upper()
        rows: dict[datetime, dict[str, Any]] = {}
        for item in self._get({"currency": currency}).get("result") or []:
            parsed = _parse_historical_volatility_item(item)
            if not parsed:
                continue
            observed_at, value = parsed
            if start and observed_at < _as_utc(start):
                continue
            if end and observed_at >= _as_utc(end):
                continue
            rows[observed_at] = {
                "observed_at": observed_at,
                "published_at": observed_at,
                "value_num": value,
                "value_text": None,
                "fields": {
                    "currency": currency,
                    "unit": "annualized_percent",
                    "value_unit": "annualized_percent",
                    "source_value_field": "value",
                },
                "quality_status": "raw",
                "raw_payload": item,
            }
        return [rows[key] for key in sorted(rows)]


class DeribitRealizedVolatilityClient(DeribitDVOLClient):
    """Derive rolling realized volatility from Deribit perpetual hourly closes."""

    endpoint = "https://www.deribit.com/api/v2/public/get_tradingview_chart_data"

    def fetch(
        self,
        *,
        currency: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        window_hours: int = 30 * 24,
    ) -> list[dict[str, Any]]:
        if window_hours < 2:
            raise ValueError("window_hours must be >= 2")
        currency = str(currency).upper()
        instrument_name = f"{currency}-PERPETUAL"
        end = _as_utc(end or datetime.now(timezone.utc))
        start = _as_utc(start or end - timedelta(days=30))
        fetch_start = start - timedelta(hours=window_hours)
        prices: dict[datetime, float] = {}
        cursor_ms = _to_ms(fetch_start)
        end_ms = _to_ms(end)
        page_hours = 5_000
        while cursor_ms < end_ms:
            page_end_ms = min(cursor_ms + (page_hours - 1) * 3_600_000, end_ms - 1)
            result = self._get(
                {
                    "instrument_name": instrument_name,
                    "start_timestamp": cursor_ms,
                    "end_timestamp": page_end_ms,
                    "resolution": "60",
                }
            ).get("result") or {}
            if result.get("status") not in {"ok", "no_data"}:
                raise RuntimeError(f"Deribit chart status: {result.get('status')!r}")
            ticks = result.get("ticks") or []
            closes = result.get("close") or []
            if len(ticks) != len(closes):
                raise RuntimeError("Deribit chart response has mismatched ticks and closes")
            for tick, close in zip(ticks, closes):
                parsed = _parse_price_item(tick, close)
                if parsed:
                    prices[parsed[0]] = parsed[1]
            cursor_ms = page_end_ms + 3_600_000
            if cursor_ms < end_ms and self.page_delay > 0:
                self.sleep(self.page_delay)

        rows: list[dict[str, Any]] = []
        returns: deque[float] = deque()
        return_sum = 0.0
        return_square_sum = 0.0
        previous: tuple[datetime, float] | None = None
        for observed_at, price in sorted(prices.items()):
            if previous is None or observed_at - previous[0] != timedelta(hours=1):
                returns.clear()
                return_sum = 0.0
                return_square_sum = 0.0
            else:
                hourly_return = math.log(price / previous[1])
                returns.append(hourly_return)
                return_sum += hourly_return
                return_square_sum += hourly_return * hourly_return
                if len(returns) > window_hours:
                    removed = returns.popleft()
                    return_sum -= removed
                    return_square_sum -= removed * removed
            previous = (observed_at, price)

            if len(returns) != window_hours:
                continue
            if observed_at < start:
                continue
            if observed_at >= end:
                continue
            variance = max(
                (return_square_sum - return_sum * return_sum / window_hours)
                / (window_hours - 1),
                0.0,
            )
            value = math.sqrt(variance * 365 * 24) * 100
            rows.append(
                {
                    "observed_at": observed_at,
                    "published_at": observed_at + timedelta(hours=1),
                    "value_num": value,
                    "value_text": None,
                    "fields": {
                        "currency": currency,
                        "unit": "annualized_percent",
                        "value_unit": "annualized_percent",
                        "source_instrument": instrument_name,
                        "source_value_field": "perpetual_close",
                        "method": "close_to_close_hourly_log_return_sample_std",
                        "window_hours": window_hours,
                        "annualization_hours": 365 * 24,
                        "derived": True,
                    },
                    "quality_status": "raw",
                    "raw_payload": {
                        "timestamp": int(observed_at.timestamp() * 1000),
                        "instrument_name": instrument_name,
                        "perpetual_close": price,
                    },
                }
            )
        return rows


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


def _parse_historical_volatility_item(item: Any) -> Optional[tuple[datetime, float]]:
    if not isinstance(item, (list, tuple)) or len(item) < 2:
        return None
    try:
        observed_at = datetime.fromtimestamp(int(item[0]) / 1000, tz=timezone.utc)
    except (TypeError, ValueError):
        return None
    value = _to_float(item[1])
    return (observed_at, value) if value is not None and value >= 0 else None


def _parse_price_item(timestamp: Any, price: Any) -> Optional[tuple[datetime, float]]:
    try:
        observed_at = datetime.fromtimestamp(int(timestamp) / 1000, tz=timezone.utc)
    except (TypeError, ValueError):
        return None
    value = _to_float(price)
    return (observed_at, value) if value is not None and value > 0 else None


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _to_ms(value: datetime) -> int:
    return int(_as_utc(value).timestamp() * 1000)


def _resolution_delta(resolution: str) -> timedelta:
    if resolution == "3600":
        return timedelta(hours=1)
    if resolution == "1D":
        return timedelta(days=1)
    raise ValueError(f"unsupported DVOL resolution: {resolution}")


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
