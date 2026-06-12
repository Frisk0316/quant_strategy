"""
OKX public REST client for OHLCV data (no authentication required).
Wraps the public history-candles endpoint and normalizes output
to the common dict shape used by CandleStore.upsert_raw_candles().
"""
from __future__ import annotations

import time
from typing import Callable, Optional
from urllib.parse import urlencode

import httpx
from loguru import logger

# OKX bar label → interval in milliseconds
_BAR_MS: dict[str, int] = {
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1H": 3_600_000,
    "2H": 7_200_000,
    "4H": 14_400_000,
    "1D": 86_400_000,
}

_BASE_URL = "https://www.okx.com"
_HISTORY_CANDLES_PATH = "/api/v5/market/history-candles"
_RECENT_CANDLES_PATH = "/api/v5/market/candles"
_PUBLIC_TIME_PATH = "/api/v5/public/time"
_INSTRUMENTS_PATH = "/api/v5/public/instruments"
_FUNDING_RATE_PATH = "/api/v5/public/funding-rate"
_FUNDING_RATE_HISTORY_PATH = "/api/v5/public/funding-rate-history"

# Rate-limit: OKX allows 40 public requests per 2 seconds
# 0.12s sleep keeps us safely under the limit
_RATE_SLEEP = 0.12


class OKXPublicClient:
    """
    Public OKX REST client — no API key required.
    Provides paginated historical candle fetching with normalized output.
    """

    def __init__(
        self,
        base_url: str = _BASE_URL,
        timeout: float = 15.0,
        rate_sleep: float = _RATE_SLEEP,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._client = httpx.Client(timeout=timeout)
        self._rate_sleep = rate_sleep

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "OKXPublicClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ──────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────

    def _get(self, path: str, params: dict) -> list:
        qs = urlencode({k: v for k, v in params.items() if v is not None})
        url = f"{self._base}{path}?{qs}"
        resp = self._client.get(url)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != "0":
            raise RuntimeError(f"OKX API error {data.get('code')}: {data.get('msg')}")
        return data.get("data", [])

    @staticmethod
    def _normalize(raw_row: list, inst_id: str, bar: str) -> dict:
        """
        Convert OKX candle array to normalized dict.
        OKX format: [ts_ms, open, high, low, close, vol, volCcy, volCcyQuote, confirm]
        Indices 6 (volCcy) and 7 (volCcyQuote) may be absent in older history.
        """
        ts_ms = int(raw_row[0])
        return {
            "ts_ms": ts_ms,
            "open": float(raw_row[1]),
            "high": float(raw_row[2]),
            "low": float(raw_row[3]),
            "close": float(raw_row[4]),
            "vol_contract": float(raw_row[5]) if raw_row[5] else None,
            "vol_base":     float(raw_row[6]) if len(raw_row) > 6 and raw_row[6] else None,
            "vol_quote":    float(raw_row[7]) if len(raw_row) > 7 and raw_row[7] else None,
            "is_closed":    raw_row[8] == "1" if len(raw_row) > 8 else True,
            "raw_payload":  {"source": "okx", "inst_id": inst_id, "bar": bar},
        }

    # ──────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────

    def get_history_candles(
        self,
        inst_id: str,
        bar: str,
        after_ms: Optional[int] = None,
        before_ms: Optional[int] = None,
        limit: int = 100,
    ) -> list[dict]:
        """
        Fetch a single page of historical candles (max 100 per request).
        OKX returns candles in descending order (newest first).

        Args:
            after_ms:  OKX 'after' cursor; returns records earlier than this timestamp.
            before_ms: OKX 'before' cursor; returns records later than this timestamp.
        Returns:
            List of normalized dicts, ascending order (oldest first).
        """
        params: dict = {"instId": inst_id, "bar": bar, "limit": limit}
        if after_ms is not None:
            params["after"] = str(after_ms)
        if before_ms is not None:
            params["before"] = str(before_ms)

        raw = self._get(_HISTORY_CANDLES_PATH, params)
        rows = [self._normalize(r, inst_id, bar) for r in raw]
        rows.sort(key=lambda x: x["ts_ms"])
        return rows

    def get_recent_candles(
        self,
        inst_id: str,
        bar: str,
        limit: int = 300,
    ) -> list[dict]:
        """
        Fetch up to 300 most recent candles from the non-history endpoint.
        Returns ascending order (oldest first).
        """
        raw = self._get(_RECENT_CANDLES_PATH, {"instId": inst_id, "bar": bar, "limit": limit})
        rows = [self._normalize(r, inst_id, bar) for r in raw]
        rows.sort(key=lambda x: x["ts_ms"])
        return rows

    def paginate_history(
        self,
        inst_id: str,
        bar: str,
        start_ms: int,
        end_ms: int,
        page_size: int = 100,
        should_cancel: Callable[[], bool] | None = None,
    ) -> list[dict]:
        """
        Paginate backwards from end_ms to start_ms, yielding all candles.
        Handles rate limiting automatically. Returns ascending order.

        Uses OKX 'after' cursor pagination. OKX's 'after' returns records
        earlier than the cursor timestamp, so we walk backward from end_ms.
        """
        all_rows: list[dict] = []
        cursor = end_ms + _BAR_MS.get(bar, 60_000)
        bar_ms = _BAR_MS.get(bar, 60_000)

        while True:
            if should_cancel and should_cancel():
                break
            time.sleep(self._rate_sleep)
            try:
                page = self.get_history_candles(
                    inst_id=inst_id,
                    bar=bar,
                    after_ms=cursor,
                    limit=page_size,
                )
            except Exception as exc:
                logger.warning("OKX fetch error", inst_id=inst_id, bar=bar,
                               cursor=cursor, error=str(exc))
                break

            if not page:
                break

            all_rows.extend(page)
            if should_cancel and should_cancel():
                break
            oldest_ts = page[0]["ts_ms"]

            if oldest_ts <= start_ms:
                break

            cursor = oldest_ts  # next page ends just before this candle

        # Filter to requested range and sort ascending
        all_rows = [r for r in all_rows if start_ms <= r["ts_ms"] < end_ms]
        all_rows.sort(key=lambda x: x["ts_ms"])
        # Deduplicate by ts_ms
        seen: set[int] = set()
        deduped = []
        for r in all_rows:
            if r["ts_ms"] not in seen:
                seen.add(r["ts_ms"])
                deduped.append(r)
        return deduped

    def get_instruments(self, inst_type: str = "SWAP") -> list[dict]:
        """Fetch instrument metadata for a given instrument type."""
        raw = self._get(_INSTRUMENTS_PATH, {"instType": inst_type})
        return raw

    def get_funding_rate(self, inst_id: str) -> Optional[dict]:
        """Fetch current funding rate for a SWAP instrument."""
        try:
            raw = self._get(_FUNDING_RATE_PATH, {"instId": inst_id})
            return raw[0] if raw else None
        except Exception as exc:
            logger.warning("Failed to get funding rate", inst_id=inst_id, error=str(exc))
            return None

    @staticmethod
    def _normalize_funding(raw_row: dict) -> dict:
        funding_time = int(raw_row.get("fundingTime", 0))
        return {
            "ts_ms": funding_time,
            "funding_rate": float(raw_row.get("fundingRate", 0.0)),
            "realized_rate": float(raw_row.get("realizedRate", raw_row.get("fundingRate", 0.0))),
            "next_funding_ts_ms": None,
            "raw_payload": raw_row,
        }

    def get_funding_rate_history(
        self,
        inst_id: str,
        after_ms: Optional[int] = None,
        before_ms: Optional[int] = None,
        limit: int = 100,
    ) -> list[dict]:
        """
        Fetch a page of funding-rate history.

        OKX returns newest first. The 'after' cursor returns records earlier
        than that timestamp; 'before' returns records later than that timestamp.
        """
        params: dict = {"instId": inst_id, "limit": str(limit)}
        if after_ms is not None:
            params["after"] = str(after_ms)
        if before_ms is not None:
            params["before"] = str(before_ms)
        raw = self._get(_FUNDING_RATE_HISTORY_PATH, params)
        rows = [self._normalize_funding(r) for r in raw]
        rows.sort(key=lambda x: x["ts_ms"])
        return rows

    def paginate_funding_history(
        self,
        inst_id: str,
        start_ms: int,
        end_ms: int,
        page_size: int = 100,
    ) -> list[dict]:
        """Paginate funding history backward from end_ms to start_ms."""
        all_rows: list[dict] = []
        cursor = end_ms + 1

        while True:
            time.sleep(self._rate_sleep)
            try:
                page = self.get_funding_rate_history(
                    inst_id=inst_id,
                    after_ms=cursor,
                    limit=page_size,
                )
            except Exception as exc:
                logger.warning("OKX funding fetch error", inst_id=inst_id,
                               cursor=cursor, error=str(exc))
                break

            if not page:
                break

            all_rows.extend(page)
            oldest_ts = page[0]["ts_ms"]
            if oldest_ts <= start_ms:
                break
            cursor = oldest_ts

        all_rows = [r for r in all_rows if start_ms <= r["ts_ms"] < end_ms]
        all_rows.sort(key=lambda x: x["ts_ms"])

        seen: set[int] = set()
        deduped = []
        for r in all_rows:
            if r["ts_ms"] not in seen:
                seen.add(r["ts_ms"])
                deduped.append(r)
        return deduped
