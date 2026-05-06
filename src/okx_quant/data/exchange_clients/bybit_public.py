"""
Bybit public REST client for OHLCV cross-validation.
No authentication required. Uses Bybit v5 unified API.
"""
from __future__ import annotations

import time
from typing import Optional
from urllib.parse import urlencode

import httpx
from loguru import logger

_BASE_URL = "https://api.bybit.com"
_KLINE_PATH = "/v5/market/kline"
_FUNDING_PATH = "/v5/market/funding/history"
_RATE_SLEEP = 0.1

# OKX bar → Bybit interval string (minutes as string for <1H, or specific labels)
_INTERVAL_MAP: dict[str, str] = {
    "1m":  "1",
    "3m":  "3",
    "5m":  "5",
    "15m": "15",
    "30m": "30",
    "1H":  "60",
    "2H":  "120",
    "4H":  "240",
    "1D":  "D",
}


class BybitPublicClient:
    """
    Bybit public v5 REST client.
    category='linear'  → USDT-margined perpetuals (same as OKX SWAP)
    category='spot'    → spot pairs
    """

    def __init__(self, timeout: float = 15.0, rate_sleep: float = _RATE_SLEEP) -> None:
        self._client = httpx.Client(base_url=_BASE_URL, timeout=timeout)
        self._rate_sleep = rate_sleep

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "BybitPublicClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _get(self, path: str, params: dict) -> list:
        qs = urlencode({k: v for k, v in params.items() if v is not None})
        url = f"{_BASE_URL}{path}?{qs}"
        try:
            resp = self._client.get(url)
            resp.raise_for_status()
            data = resp.json()
            if data.get("retCode") != 0:
                logger.warning("Bybit API error", code=data.get("retCode"),
                               msg=data.get("retMsg"))
                return []
            return data.get("result", {}).get("list", [])
        except Exception as exc:
            logger.warning("Bybit fetch error", error=str(exc))
            return []

    def get_kline(
        self,
        symbol: str,
        bar: str,
        start_ms: Optional[int] = None,
        end_ms: Optional[int] = None,
        limit: int = 200,
        category: str = "linear",
    ) -> list[dict]:
        """
        Fetch OHLCV from Bybit v5 /v5/market/kline.

        Args:
            symbol:   Bybit symbol, e.g. 'BTCUSDT'.
            bar:      OKX bar string, e.g. '1H'.
            category: 'linear' (USDT perp) or 'spot'.
        Returns:
            Normalized dicts ascending (oldest first).
        """
        interval = _INTERVAL_MAP.get(bar)
        if not interval:
            logger.warning("Bybit: unsupported bar", bar=bar)
            return []

        params: dict = {
            "category": category,
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
        }
        if start_ms is not None:
            params["start"] = start_ms
        if end_ms is not None:
            params["end"] = end_ms

        time.sleep(self._rate_sleep)
        raw = self._get(_KLINE_PATH, params)
        if not raw:
            return []

        # Bybit returns descending order; each entry: [startTime, open, high, low, close, volume, turnover]
        rows = []
        for r in raw:
            rows.append({
                "ts_ms":        int(r[0]),
                "open":         float(r[1]),
                "high":         float(r[2]),
                "low":          float(r[3]),
                "close":        float(r[4]),
                "vol_contract": None,
                "vol_base":     float(r[5]),
                "vol_quote":    float(r[6]) if len(r) > 6 else None,
                "raw_payload":   {"exchange": "bybit", "symbol": symbol, "raw": r},
                "is_closed":    True,
            })
        rows.sort(key=lambda x: x["ts_ms"])
        return rows

    def get_funding_rates(
        self,
        symbol: str,
        start_ms: Optional[int],
        end_ms: Optional[int],
        limit: int = 200,
        category: str = "linear",
    ) -> list[dict]:
        """
        Fetch Bybit funding history. Bybit requires both startTime and endTime
        when startTime is provided.
        """
        params: dict = {
            "category": category,
            "symbol": symbol,
            "limit": limit,
        }
        if start_ms is not None:
            params["startTime"] = start_ms
        if end_ms is not None:
            params["endTime"] = end_ms

        time.sleep(self._rate_sleep)
        raw = self._get(_FUNDING_PATH, params)
        rows = []
        for r in raw:
            ts_ms = int(r["fundingRateTimestamp"])
            rows.append({
                "ts_ms": ts_ms,
                "funding_rate": float(r["fundingRate"]),
                "realized_rate": float(r["fundingRate"]),
                "mark_price": None,
                "next_funding_ts_ms": None,
                "raw_payload": r,
            })
        rows.sort(key=lambda x: x["ts_ms"])
        return rows

    def get_kline_range(
        self,
        symbol: str,
        bar: str,
        start_ms: int,
        end_ms: int,
        limit: int = 200,
        category: str = "linear",
    ) -> list[dict]:
        """Paginate Bybit klines across a time range. Returns ascending."""
        all_rows: list[dict] = []
        cursor = start_ms
        while cursor < end_ms:
            time.sleep(self._rate_sleep)
            page = self.get_kline(symbol, bar, start_ms=cursor, end_ms=end_ms,
                                  limit=limit, category=category)
            if not page:
                break
            all_rows.extend(page)
            cursor = page[-1]["ts_ms"] + 1
        return [r for r in all_rows if start_ms <= r["ts_ms"] <= end_ms]
