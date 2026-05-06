"""
Cross-exchange OHLCV validator.
Compares OKX canonical candles against Binance and Bybit to detect outliers.
Validation is manual-only: called explicitly by scripts/market_data/validate.py.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd
from loguru import logger

from okx_quant.data.candle_store import CandleStore
from okx_quant.data.exchange_clients.binance_public import BinancePublicClient
from okx_quant.data.exchange_clients.bybit_public import BybitPublicClient


# ──────────────────────────────────────────────────────────────
# Symbol and interval mapping tables
# ──────────────────────────────────────────────────────────────

SYMBOL_MAP: dict[str, dict[str, str]] = {
    "BTC-USDT-SWAP":  {"binance": "BTCUSDT",  "binance_type": "futures", "bybit": "BTCUSDT",  "bybit_cat": "linear"},
    "ETH-USDT-SWAP":  {"binance": "ETHUSDT",  "binance_type": "futures", "bybit": "ETHUSDT",  "bybit_cat": "linear"},
    "BNB-USDT-SWAP":  {"binance": "BNBUSDT",  "binance_type": "futures", "bybit": "BNBUSDT",  "bybit_cat": "linear"},
    "SOL-USDT-SWAP":  {"binance": "SOLUSDT",  "binance_type": "futures", "bybit": "SOLUSDT",  "bybit_cat": "linear"},
    "XRP-USDT-SWAP":  {"binance": "XRPUSDT",  "binance_type": "futures", "bybit": "XRPUSDT",  "bybit_cat": "linear"},
    "ADA-USDT-SWAP":  {"binance": "ADAUSDT",  "binance_type": "futures", "bybit": "ADAUSDT",  "bybit_cat": "linear"},
    "DOGE-USDT-SWAP": {"binance": "DOGEUSDT", "binance_type": "futures", "bybit": "DOGEUSDT", "bybit_cat": "linear"},
    "TON-USDT-SWAP":  {"binance": None,        "binance_type": "futures", "bybit": "TONUSDT",  "bybit_cat": "linear"},
    "TRX-USDT-SWAP":  {"binance": "TRXUSDT",  "binance_type": "futures", "bybit": "TRXUSDT",  "bybit_cat": "linear"},
    "LINK-USDT-SWAP": {"binance": "LINKUSDT", "binance_type": "futures", "bybit": "LINKUSDT", "bybit_cat": "linear"},
    "AVAX-USDT-SWAP": {"binance": "AVAXUSDT", "binance_type": "futures", "bybit": "AVAXUSDT", "bybit_cat": "linear"},
    "MATIC-USDT-SWAP":{"binance": "MATICUSDT","binance_type": "futures", "bybit": "MATICUSDT","bybit_cat": "linear"},
    "DOT-USDT-SWAP":  {"binance": "DOTUSDT",  "binance_type": "futures", "bybit": "DOTUSDT",  "bybit_cat": "linear"},
    "SHIB-USDT-SWAP": {"binance": "SHIBUSDT", "binance_type": "futures", "bybit": "SHIBUSDT", "bybit_cat": "linear"},
    "LTC-USDT-SWAP":  {"binance": "LTCUSDT",  "binance_type": "futures", "bybit": "LTCUSDT",  "bybit_cat": "linear"},
}

# Fields validated across exchanges
_OHLC_FIELDS = ["open", "high", "low", "close"]


class CrossExchangeValidator:
    """
    Validates canonical OKX candles by comparing against Binance and Bybit.

    Algorithm per (timestamp, field):
        sources = [okx_val, binance_val, bybit_val]  (drop None)
        if len(sources) < 2: skip
        reference = median(sources)
        scale = MAD(sources) or abs(reference) * 0.001  (avoid zero-division)
        z = abs(okx_val - reference) / scale
        if z > sigma_threshold: flag / optionally replace with reference

    Validation is manual-only. Never called automatically during fetch.
    """

    def __init__(
        self,
        store: CandleStore,
        sigma_threshold: float = 3.0,
        replace_outliers: bool = False,
    ) -> None:
        self._store = store
        self._sigma = sigma_threshold
        self._replace = replace_outliers
        self._binance = BinancePublicClient()
        self._bybit = BybitPublicClient()

    def close(self) -> None:
        self._binance.close()
        self._bybit.close()

    def __enter__(self) -> "CrossExchangeValidator":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    async def validate_window(
        self,
        inst_id: str,
        bar: str,
        start: datetime,
        end: datetime,
        replace: bool = False,
        job_id: Optional[str] = None,
    ) -> dict:
        """
        Validate canonical candles in [start, end) against Binance and Bybit.

        Returns:
            {checked, flagged, replaced, partial_sources, skipped_no_map}
        """
        if inst_id not in SYMBOL_MAP:
            logger.info("No cross-exchange mapping", inst_id=inst_id)
            return {"checked": 0, "flagged": 0, "replaced": 0,
                    "partial_sources": [], "skipped_no_map": True}

        mapping = SYMBOL_MAP[inst_id]
        start_ms = int(start.timestamp() * 1000)
        end_ms   = int(end.timestamp() * 1000)

        # Load canonical candles
        canonical_df = await self._store.get_canonical_candles(
            inst_id, bar, start=start, end=end, include_suspect=True
        )
        if canonical_df.empty:
            logger.info("No canonical candles to validate", inst_id=inst_id, bar=bar)
            return {"checked": 0, "flagged": 0, "replaced": 0,
                    "partial_sources": [], "skipped_no_map": False}

        # Fetch Binance
        binance_df = pd.DataFrame()
        partial_sources: list[str] = []
        if mapping.get("binance"):
            try:
                rows = self._binance.get_klines_range(
                    symbol=mapping["binance"],
                    bar=bar,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    market_type=mapping.get("binance_type", "futures"),
                )
                if rows:
                    binance_df = _rows_to_df(rows)
            except Exception as exc:
                logger.warning("Binance fetch failed", inst_id=inst_id, error=str(exc))
                partial_sources.append("binance_failed")
        else:
            partial_sources.append("binance_no_map")

        # Fetch Bybit
        bybit_df = pd.DataFrame()
        if mapping.get("bybit"):
            try:
                rows = self._bybit.get_kline_range(
                    symbol=mapping["bybit"],
                    bar=bar,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    category=mapping.get("bybit_cat", "linear"),
                )
                if rows:
                    bybit_df = _rows_to_df(rows)
            except Exception as exc:
                logger.warning("Bybit fetch failed", inst_id=inst_id, error=str(exc))
                partial_sources.append("bybit_failed")
        else:
            partial_sources.append("bybit_no_map")

        total_sources = 1  # OKX is always present
        if not binance_df.empty:
            total_sources += 1
        if not bybit_df.empty:
            total_sources += 1

        if total_sources < 2:
            logger.warning("Insufficient exchange sources for validation",
                           inst_id=inst_id, bar=bar, sources=total_sources)
            return {"checked": 0, "flagged": 0, "replaced": 0,
                    "partial_sources": partial_sources, "skipped_no_map": False}

        # Detect outliers
        flagged = 0
        replaced_rows: list[dict] = []
        effective_replace = replace and self._replace or replace

        for ts, okx_row in canonical_df.iterrows():
            for field in _OHLC_FIELDS:
                okx_val = float(okx_row.get(field, float("nan")))
                if np.isnan(okx_val):
                    continue

                values: list[float] = [okx_val]
                if not binance_df.empty and ts in binance_df.index:
                    v = binance_df.at[ts, field]
                    if not np.isnan(v):
                        values.append(float(v))
                if not bybit_df.empty and ts in bybit_df.index:
                    v = bybit_df.at[ts, field]
                    if not np.isnan(v):
                        values.append(float(v))

                if len(values) < 2:
                    continue

                reference = float(np.median(values))
                mad = float(np.median(np.abs(np.array(values) - reference)))
                scale = mad if mad > 0 else abs(reference) * 0.001 or 1e-8
                z = abs(okx_val - reference) / scale

                if z > self._sigma:
                    flagged += 1
                    action = "outlier_replaced" if effective_replace else "outlier_flagged"
                    await self._store.log_quality_event(
                        inst_id=inst_id, bar=bar,
                        issue_type=action,
                        severity="warning" if z < 10 else "critical",
                        source="okx",
                        window_start=ts if isinstance(ts, datetime) else ts.to_pydatetime(),
                        window_end=ts if isinstance(ts, datetime) else ts.to_pydatetime(),
                        affected_count=1,
                        field=field,
                        observed_value=okx_val,
                        reference_value=reference,
                        z_score=z,
                        action_taken=action,
                        job_id=job_id,
                    )
                    if effective_replace:
                        ts_ms = int(ts.timestamp() * 1000)
                        row_dict = {
                            "ts_ms": ts_ms,
                            **{f: float(okx_row.get(f, 0)) for f in _OHLC_FIELDS},
                            "vol_contract": okx_row.get("vol_contract"),
                            "vol_base":     okx_row.get("vol_base"),
                            "vol_quote":    okx_row.get("vol_quote"),
                        }
                        row_dict[field] = reference
                        replaced_rows.append(row_dict)

        if replaced_rows:
            await self._store.upsert_canonical_candles(
                replaced_rows, inst_id=inst_id, bar=bar,
                source_primary="okx", quality_status="corrected",
            )

        return {
            "checked":         len(canonical_df),
            "flagged":         flagged,
            "replaced":        len(replaced_rows),
            "partial_sources": partial_sources,
            "skipped_no_map":  False,
        }


def _rows_to_df(rows: list[dict]) -> pd.DataFrame:
    """Convert normalized row dicts to DataFrame indexed by UTC datetime."""
    df = pd.DataFrame(rows)
    df["ts"] = pd.to_datetime(df["ts_ms"], unit="ms", utc=True)
    df = df.set_index("ts").sort_index()
    return df[["open", "high", "low", "close"]].astype(float)
