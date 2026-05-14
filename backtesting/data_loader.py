"""
Data loader for backtesting.
Loads OKX L2/OHLCV/funding from local Parquet, Tardis format, or PostgreSQL/TimescaleDB.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

import pandas as pd
import pyarrow.parquet as pq


def load_candles(
    inst_id: str,
    bar: str = "1m",
    data_dir: str = "data/ticks",
    start: Optional[str] = None,
    end: Optional[str] = None,
    backend: Literal["parquet", "postgres", "market"] = "parquet",
    dsn: Optional[str] = None,
    include_suspect: bool = False,
    exchange: Optional[str] = None,
) -> pd.DataFrame:
    """
    Load OHLCV candles from Parquet, PostgreSQL canonical layer, or market layer.

    Returns:
        DataFrame with columns [open, high, low, close, vol]
        indexed by ts (tz-naive datetime UTC).

    Args:
        backend: 'parquet' (default), 'postgres' (canonical_candles), or
                 'market' (market_klines — multi-exchange raw layer).
        dsn:     PostgreSQL DSN, required when backend='postgres' or 'market'.
        include_suspect: Include candles marked quality_status='suspect'
                         (only applies to backend='postgres').
        exchange: Filter by exchange name, e.g. 'binance'.
                  Only used when backend='market'.
    """
    if backend == "postgres":
        if not dsn:
            raise ValueError("dsn is required when backend='postgres'")
        return _load_candles_pg(inst_id, bar, dsn, start, end, include_suspect)
    if backend == "market":
        if not dsn:
            raise ValueError("dsn is required when backend='market'")
        return _load_candles_market(inst_id, bar, dsn, start, end, exchange)
    return _load_candles_parquet(inst_id, bar, data_dir, start, end)


def _load_candles_parquet(
    inst_id: str,
    bar: str,
    data_dir: str,
    start: Optional[str],
    end: Optional[str],
) -> pd.DataFrame:
    inst_dir = Path(data_dir) / inst_id.replace("-", "_")
    path = inst_dir / f"candles_{bar}.parquet"
    if not path.exists():
        # If the requested bar can be derived by aggregating 1m data, try that first.
        base_path = inst_dir / "candles_1m.parquet"
        if _can_derive_from_1m(bar) and base_path.exists():
            df_1m = pq.read_table(base_path).to_pandas()
            df_1m["ts"] = pd.to_datetime(df_1m["ts"])
            df_1m = df_1m.set_index("ts").sort_index()
            if start:
                df_1m = df_1m[df_1m.index >= pd.Timestamp(start)]
            if end:
                df_1m = df_1m[df_1m.index < pd.Timestamp(end)]
            return _aggregate_1m_to_bar(df_1m, bar)
        available = sorted(p.name for p in inst_dir.glob("candles_*.parquet")) if inst_dir.exists() else []
        hint = (
            f"Available bar files: {available}" if available
            else f"Run: python scripts/download_okx_data.py --inst {inst_id} --bar {bar}"
        )
        raise FileNotFoundError(
            f"Candle data not found: {path}\n{hint}"
        )
    df = pq.read_table(path).to_pandas()
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.set_index("ts").sort_index()
    if start:
        df = df[df.index >= pd.Timestamp(start)]
    if end:
        df = df[df.index < pd.Timestamp(end)]
    return df


_BAR_RESAMPLE_RULES: dict[str, str] = {
    "3m": "3min",
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1H": "1h",
    "2H": "2h",
    "4H": "4h",
    "6H": "6h",
    "12H": "12h",
    "1D": "1D",
}

_BAR_SECONDS: dict[str, int] = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1H": 3600,
    "2H": 7200,
    "4H": 14400,
    "6H": 21600,
    "12H": 43200,
    "1D": 86400,
}


def _can_derive_from_1m(bar: str) -> bool:
    return bar in _BAR_RESAMPLE_RULES


def _expected_bar_count(
    start_dt: Optional[datetime],
    end_dt: Optional[datetime],
    bar: str,
) -> Optional[int]:
    seconds = _BAR_SECONDS.get(bar)
    if seconds is None or start_dt is None or end_dt is None or end_dt <= start_dt:
        return None
    return max(1, int((end_dt - start_dt).total_seconds() // seconds))


def _has_low_bar_coverage(
    df: pd.DataFrame,
    start_dt: Optional[datetime],
    end_dt: Optional[datetime],
    bar: str,
    threshold: float = 0.80,
) -> bool:
    if df.empty:
        return True
    expected = _expected_bar_count(start_dt, end_dt, bar)
    if expected is None:
        return False
    actual = int(pd.Index(df.index).nunique())
    return (actual / expected) < threshold


def _aggregate_1m_to_bar(df: pd.DataFrame, bar: str) -> pd.DataFrame:
    rule = _BAR_RESAMPLE_RULES.get(bar)
    if rule is None or df.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "vol"])
    if not isinstance(df.index, pd.DatetimeIndex):
        return pd.DataFrame(columns=["open", "high", "low", "close", "vol"])
    resampled = df.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "vol": "sum"}
    )
    return resampled.dropna(subset=["open", "close"])


def _load_candles_pg(
    inst_id: str,
    bar: str,
    dsn: str,
    start: Optional[str],
    end: Optional[str],
    include_suspect: bool,
) -> pd.DataFrame:
    """
    Synchronous wrapper around CandleStore.get_canonical_candles().
    Returns tz-naive DatetimeIndex (UTC) to match the Parquet contract.
    Exposes 'vol' column mapped from vol_quote → vol_base → vol_contract.
    """
    import sys
    from pathlib import Path as _Path
    src_root = str(_Path(__file__).parent.parent / "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)
    from okx_quant.data.candle_store import CandleStore

    def _to_utc_dt(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        ts = pd.Timestamp(value)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        else:
            ts = ts.tz_convert("UTC")
        return ts.to_pydatetime()

    start_dt = _to_utc_dt(start)
    end_dt = _to_utc_dt(end)

    async def _fetch() -> tuple[pd.DataFrame, bool]:
        async with await CandleStore.from_dsn(dsn, min_size=1, max_size=2) as store:
            df = await store.get_canonical_candles(
                inst_id=inst_id, bar=bar,
                start=start_dt, end=end_dt,
                include_suspect=include_suspect,
            )
            if _can_derive_from_1m(bar) and _has_low_bar_coverage(df, start_dt, end_dt, bar):
                df_1m = await store.get_canonical_candles(
                    inst_id=inst_id, bar="1m",
                    start=start_dt, end=end_dt,
                    include_suspect=include_suspect,
                )
                if not df_1m.empty:
                    return df_1m, True
            return df, False

    # Handle already-running event loops (e.g. Jupyter)
    try:
        loop = asyncio.get_running_loop()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, _fetch())
            df, is_1m_fallback = future.result()
    except RuntimeError:
        df, is_1m_fallback = asyncio.run(_fetch())

    if df.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "vol"])

    # Strip timezone to match Parquet contract
    if df.index.tz is not None:
        df.index = df.index.tz_convert("UTC").tz_localize(None)

    # Map vol: prefer vol_quote → vol_base → vol_contract
    if "vol_quote" in df.columns and df["vol_quote"].notna().any():
        df["vol"] = df["vol_quote"]
    elif "vol_base" in df.columns and df["vol_base"].notna().any():
        df["vol"] = df["vol_base"]
    elif "vol_contract" in df.columns:
        df["vol"] = df["vol_contract"]
    else:
        df["vol"] = float("nan")

    if is_1m_fallback:
        df = _aggregate_1m_to_bar(df[["open", "high", "low", "close", "vol"]], bar)

    return df[["open", "high", "low", "close", "vol"]]


def _load_candles_market(
    inst_id: str,
    bar: str,
    dsn: str,
    start: Optional[str],
    end: Optional[str],
    exchange: Optional[str],
) -> pd.DataFrame:
    """
    Load candles directly from market_klines (multi-exchange raw layer).
    inst_id is treated as normalized_symbol (e.g. 'BTC-USDT-SWAP').
    Returns tz-naive DatetimeIndex (UTC), columns [open, high, low, close, vol].
    When multiple exchanges have data for the same ts, all rows are returned
    unless exchange= is specified to filter to a single source.
    """
    import sys
    from pathlib import Path as _Path
    src_root = str(_Path(__file__).parent.parent / "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)
    from okx_quant.data.candle_store import CandleStore

    def _to_utc_dt(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        ts = pd.Timestamp(value)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        else:
            ts = ts.tz_convert("UTC")
        return ts.to_pydatetime()

    start_dt = _to_utc_dt(start)
    end_dt = _to_utc_dt(end)

    async def _fetch() -> pd.DataFrame:
        async with await CandleStore.from_dsn(dsn, min_size=1, max_size=2) as store:
            return await store.get_market_klines(
                normalized_symbol=inst_id,
                bar=bar,
                start=start_dt,
                end=end_dt,
                exchange=exchange,
            )

    try:
        asyncio.get_running_loop()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            df = pool.submit(asyncio.run, _fetch()).result()
    except RuntimeError:
        df = asyncio.run(_fetch())

    if df.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "vol"])

    if df.index.tz is not None:
        df.index = df.index.tz_convert("UTC").tz_localize(None)

    df = df.rename(columns={"vol": "vol"})
    if "vol" not in df.columns:
        df["vol"] = float("nan")

    return df[["open", "high", "low", "close", "vol"]]


def write_candles_parquet(
    inst_id: str,
    bar: str,
    df: pd.DataFrame,
    data_dir: str = "data/ticks",
) -> Path:
    """
    Upsert OHLCV candles into the canonical parquet file for inst_id/bar.

    df must have a DatetimeIndex (tz-naive UTC) and columns including
    [open, high, low, close, vol].  Rows whose timestamp already exists in the
    parquet are overwritten; rows outside the new range are preserved.

    Returns the path written.
    """
    path = Path(data_dir) / inst_id.replace("-", "_") / f"candles_{bar}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)

    cols = ["open", "high", "low", "close", "vol"]
    new = df[cols].copy()
    if getattr(new.index, "tz", None) is not None:
        new.index = new.index.tz_convert("UTC").tz_localize(None)
    new.index.name = "ts"

    if path.exists():
        existing = pq.read_table(path).to_pandas()
        existing["ts"] = pd.to_datetime(existing["ts"])
        existing = existing.set_index("ts")
        merged = pd.concat([existing[cols], new])
        merged = merged[~merged.index.duplicated(keep="last")].sort_index()
    else:
        merged = new.sort_index()

    merged.reset_index().to_parquet(path, index=False, compression="snappy")
    return path


def load_funding(
    inst_id: str,
    data_dir: str = "data/ticks",
    start: Optional[str] = None,
    end: Optional[str] = None,
    backend: Literal["parquet", "postgres"] = "parquet",
    dsn: Optional[str] = None,
) -> pd.DataFrame:
    """Load funding rate history from Parquet or PostgreSQL and derive APR when absent."""
    if backend == "postgres":
        if not dsn:
            raise ValueError("dsn is required when backend='postgres'")
        return _load_funding_pg(inst_id, dsn, start, end)

    path = Path(data_dir) / inst_id.replace("-", "_") / "funding.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Funding data not found: {path}")
    df = pq.read_table(path).to_pandas()
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.set_index("ts").sort_index()
    if "apr" not in df.columns and "rate" in df.columns:
        interval = df.get("funding_interval_hours", 8.0)
        if hasattr(interval, "fillna"):
            interval = interval.fillna(8.0)
        df["apr"] = df["rate"] * (365 * 24 / interval)
    if start:
        df = df[df.index >= pd.Timestamp(start)]
    if end:
        df = df[df.index < pd.Timestamp(end)]
    return df


# def _load_funding_pg(
#     inst_id: str,
#     dsn: str,
#     start: Optional[str],
#     end: Optional[str],
# ) -> pd.DataFrame:
#     """Synchronous wrapper around CandleStore.get_funding_rates()."""
#     import sys
#     from pathlib import Path as _Path
#     src_root = str(_Path(__file__).parent.parent / "src")
#     if src_root not in sys.path:
#         sys.path.insert(0, src_root)
#     from okx_quant.data.candle_store import CandleStore

#     def _to_utc_dt(value: Optional[str]) -> Optional[datetime]:
#         if not value:
#             return None
#         ts = pd.Timestamp(value)
#         if ts.tzinfo is None:
#             ts = ts.tz_localize("UTC")
#         else:
#             ts = ts.tz_convert("UTC")
#         return ts.to_pydatetime()

#     async def _fetch() -> pd.DataFrame:
#         async with await CandleStore.from_dsn(dsn, min_size=1, max_size=2) as store:
#             return await store.get_funding_rates(
#                 inst_id=inst_id,
#                 start=_to_utc_dt(start),
#                 end=_to_utc_dt(end),
#             )

#     try:
#         asyncio.get_running_loop()
#         import concurrent.futures
#         with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
#             df = pool.submit(asyncio.run, _fetch()).result()
#     except RuntimeError:
#         df = asyncio.run(_fetch())

#     if df.empty:
#         return pd.DataFrame(columns=["rate", "realized_rate", "nextFundingTime", "apr"])

#     if df.index.tz is not None:
#         df.index = df.index.tz_convert("UTC").tz_localize(None)
#     if "apr" not in df.columns and "rate" in df.columns:
#         interval = df.get("funding_interval_hours", 8.0)
#         if hasattr(interval, "fillna"):
#             interval = interval.fillna(8.0)
#         df["apr"] = df["rate"] * (365 * 24 / interval)
#     return df

def _load_funding_pg(
    inst_id: str,
    dsn: str,
    start: Optional[str],
    end: Optional[str],
) -> pd.DataFrame:
    """
    Load funding rates directly from legacy funding_rates.

    This intentionally bypasses CandleStore.get_funding_rates() because the
    current multi-exchange ingestion mirrors market_funding_rates into the
    legacy funding_rates table with source='binance' and inst_id='BTC-USDT-SWAP'.
    """
    import asyncio
    import concurrent.futures
    import asyncpg

    def _to_utc_dt(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        ts = pd.Timestamp(value)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        else:
            ts = ts.tz_convert("UTC")
        return ts.to_pydatetime()

    start_dt = _to_utc_dt(start)
    end_dt = _to_utc_dt(end)

    async def _fetch() -> pd.DataFrame:
        conn = await asyncpg.connect(dsn)
        try:
            rows = await conn.fetch(
                """
                SELECT
                    ts,
                    funding_rate AS rate,
                    realized_rate,
                    next_funding_ts AS "nextFundingTime",
                    funding_interval_hours,
                    mark_price,
                    source
                FROM funding_rates
                WHERE inst_id = $1
                  AND ($2::timestamptz IS NULL OR ts >= $2)
                  AND ($3::timestamptz IS NULL OR ts <  $3)
                ORDER BY ts
                """,
                inst_id,
                start_dt,
                end_dt,
            )
        finally:
            await conn.close()

        if not rows:
            return pd.DataFrame(
                columns=[
                    "rate",
                    "realized_rate",
                    "nextFundingTime",
                    "funding_interval_hours",
                    "mark_price",
                    "source",
                    "apr",
                ]
            )

        df = pd.DataFrame([dict(r) for r in rows])
        df["ts"] = pd.to_datetime(df["ts"], utc=True)
        df = df.set_index("ts").sort_index()

        if df.index.tz is not None:
            df.index = df.index.tz_convert("UTC").tz_localize(None)

        interval = df["funding_interval_hours"].fillna(8.0)
        interval = interval.replace(0, 8.0)
        df["apr"] = df["rate"] * (365 * 24 / interval)

        return df[
            [
                "rate",
                "realized_rate",
                "nextFundingTime",
                "funding_interval_hours",
                "mark_price",
                "source",
                "apr",
            ]
        ]

    try:
        asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, _fetch()).result()
    except RuntimeError:
        return asyncio.run(_fetch())

def load_tardis_books(
    path: str,
    inst_id: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> pd.DataFrame:
    """
    Load Tardis L2 book snapshot data.
    Tardis CSV format: timestamp_ms,is_snapshot,side,price,amount

    Returns:
        DataFrame with tick-level book snapshots.
    """
    df = pd.read_csv(path)
    if "timestamp_ms" in df.columns:
        df["ts"] = pd.to_datetime(df["timestamp_ms"], unit="ms")
    elif "timestamp" in df.columns:
        df["ts"] = pd.to_datetime(df["timestamp"])
    df = df.set_index("ts").sort_index()
    if start:
        df = df[df.index >= pd.Timestamp(start)]
    if end:
        df = df[df.index < pd.Timestamp(end)]
    return df


def compute_returns(
    candles: pd.DataFrame,
    col: str = "close",
    method: str = "simple",
) -> pd.Series:
    """
    Compute simple or log returns from OHLCV candles.

    Args:
        candles: OHLCV DataFrame.
        col: Price column to use.
        method: Either "simple" or "log".
    """
    import numpy as np

    price = candles[col].astype(float)
    if method == "simple":
        returns = price.pct_change()
        name = "simple_return"
    elif method == "log":
        returns = np.log(price).diff()
        name = "log_return"
    else:
        raise ValueError("method must be either 'simple' or 'log'")

    return pd.Series(returns.dropna(), name=name)
