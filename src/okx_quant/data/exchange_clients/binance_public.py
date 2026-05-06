"""
Binance public REST client for OHLCV cross-validation.
No authentication required.
Routes spot requests to api.binance.com and futures to fapi.binance.com.
"""
from __future__ import annotations

import time
from typing import Optional
from urllib.parse import urlencode

import httpx
from loguru import logger

_SPOT_BASE = "https://api.binance.com"
_FUTURES_BASE = "https://fapi.binance.com"
_SPOT_KLINES_PATH = "/api/v3/klines"
_FUTURES_KLINES_PATH = "/fapi/v1/klines"
_FUTURES_FUNDING_PATH = "/fapi/v1/fundingRate"

# Binance public rate limit: 1200 weight/min; klines = 1 weight/request
_RATE_SLEEP = 0.1

# OKX bar → Binance interval string
_INTERVAL_MAP: dict[str, str] = {
    "1m":  "1m",
    "3m":  "3m",
    "5m":  "5m",
    "15m": "15m",
    "30m": "30m",
    "1H":  "1h",
    "2H":  "2h",
    "4H":  "4h",
    "1D":  "1d",
}


class BinancePublicClient:
    """
    Binance public REST client.
    market_type='spot'    → api.binance.com/api/v3/klines
    market_type='futures' → fapi.binance.com/fapi/v1/klines
    """

    def __init__(self, timeout: float = 15.0, rate_sleep: float = _RATE_SLEEP) -> None:
        self._client = httpx.Client(timeout=timeout)
        self._rate_sleep = rate_sleep

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "BinancePublicClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _get(self, base: str, path: str, params: dict) -> list:
        qs = urlencode({k: v for k, v in params.items() if v is not None})
        url = f"{base}{path}?{qs}"
        try:
            resp = self._client.get(url)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning("Binance fetch error", url=url, error=str(exc))
            return []

    def get_klines(
        self,
        symbol: str,
        bar: str,
        start_ms: Optional[int] = None,
        end_ms: Optional[int] = None,
        limit: int = 1500,
        market_type: str = "futures",
    ) -> list[dict]:
        """
        Fetch OHLCV candles from Binance.

        Args:
            symbol:      Binance symbol, e.g. 'BTCUSDT'.
            bar:         OKX bar string, e.g. '1H'. Mapped to Binance interval.
            market_type: 'spot' or 'futures'.
        Returns:
            Normalized dicts ascending (oldest first).
        """
        interval = _INTERVAL_MAP.get(bar)
        if not interval:
            logger.warning("Binance: unsupported bar", bar=bar)
            return []

        base = _FUTURES_BASE if market_type == "futures" else _SPOT_BASE
        path = _FUTURES_KLINES_PATH if market_type == "futures" else _SPOT_KLINES_PATH

        params: dict = {"symbol": symbol, "interval": interval, "limit": limit}
        if start_ms is not None:
            params["startTime"] = start_ms
        if end_ms is not None:
            params["endTime"] = end_ms

        time.sleep(self._rate_sleep)
        raw = self._get(base, path, params)
        if not raw:
            return []

        rows = []
        for r in raw:
            # Binance kline: [open_time, open, high, low, close, volume, ...]
            rows.append({
                "ts_ms":       int(r[0]),
                "open":        float(r[1]),
                "high":        float(r[2]),
                "low":         float(r[3]),
                "close":       float(r[4]),
                "vol_contract": None,
                "vol_base":    float(r[5]),
                "vol_quote":   float(r[7]) if len(r) > 7 else None,
                "trade_count":  int(r[8]) if len(r) > 8 else None,
                "taker_buy_base_volume": float(r[9]) if len(r) > 9 else None,
                "taker_buy_quote_volume": float(r[10]) if len(r) > 10 else None,
                "is_closed":   True,
                "raw_payload":  {"exchange": "binance", "symbol": symbol, "raw": r},
            })
        return rows

    def get_funding_rates(
        self,
        symbol: str,
        start_ms: Optional[int] = None,
        end_ms: Optional[int] = None,
        limit: int = 1000,
    ) -> list[dict]:
        """Fetch Binance USD-M funding rates in ascending order."""
        params: dict = {"symbol": symbol, "limit": limit}
        if start_ms is not None:
            params["startTime"] = start_ms
        if end_ms is not None:
            params["endTime"] = end_ms

        time.sleep(self._rate_sleep)
        raw = self._get(_FUTURES_BASE, _FUTURES_FUNDING_PATH, params)
        rows = []
        for r in raw:
            rows.append({
                "ts_ms": int(r["fundingTime"]),
                "funding_rate": float(r["fundingRate"]),
                "realized_rate": float(r["fundingRate"]),
                "mark_price": float(r["markPrice"]) if r.get("markPrice") else None,
                "next_funding_ts_ms": None,
                "raw_payload": r,
            })
        rows.sort(key=lambda x: x["ts_ms"])
        return rows

    def get_klines_range(
        self,
        symbol: str,
        bar: str,
        start_ms: int,
        end_ms: int,
        limit: int = 500,
        market_type: str = "futures",
    ) -> list[dict]:
        """Paginate Binance klines across a time range. Returns ascending."""
        all_rows: list[dict] = []
        cursor = start_ms
        while cursor < end_ms:
            time.sleep(self._rate_sleep)
            page = self.get_klines(symbol, bar, start_ms=cursor, end_ms=end_ms,
                                   limit=limit, market_type=market_type)
            if not page:
                break
            all_rows.extend(page)
            cursor = page[-1]["ts_ms"] + 1
        return [r for r in all_rows if start_ms <= r["ts_ms"] <= end_ms]
