"""
Data loader for backtesting.
Loads OKX L2/OHLCV/funding from local Parquet, Tardis format, or PostgreSQL/TimescaleDB.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional

import pandas as pd
import pyarrow.parquet as pq


def _dsn_reachable(dsn: Optional[str], timeout: float = 1.5) -> bool:
    """Fast TCP probe so callers can decide between postgres and parquet.

    Catches the common "DB not running" case before asyncpg does its multi-second
    retry. See routes_backtest._dsn_reachable for the canonical version.
    """
    if not dsn:
        return False
    import socket
    from urllib.parse import urlparse

    try:
        parsed = urlparse(dsn)
        host = parsed.hostname or "localhost"
        port = parsed.port or 5432
    except Exception:
        return False
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False


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
                  Used as canonical `source_primary` for backend='postgres'
                  and exchange filter for backend='market'.
    """
    venue = str(exchange).strip().lower() if exchange else None
    if venue and backend == "parquet":
        backend = "postgres"
    if backend == "postgres":
        # Fallback applies to both "no DSN string" and "DSN string but DB not
        # reachable" — the docs treat connection refusal as the trigger to
        # drop to parquet so backtests don't crash mid-run. Venue-scoped reads
        # are stricter because parquet has no source provenance.
        if not dsn or not _dsn_reachable(dsn):
            if venue:
                raise ValueError(
                    f"Venue-scoped candle load for exchange='{venue}' requires "
                    "a reachable postgres DSN; parquet candles have no source provenance."
                )
            return _load_candles_parquet(inst_id, bar, data_dir, start, end)
        return _load_candles_pg(inst_id, bar, dsn, start, end, include_suspect, venue)
    if backend == "market":
        if not dsn:
            raise ValueError("dsn is required when backend='market'")
        return _load_candles_market(inst_id, bar, dsn, start, end, venue)
    return _load_candles_parquet(inst_id, bar, data_dir, start, end)


def _to_naive_utc_index(df: pd.DataFrame, ts_col: str = "ts") -> pd.DataFrame:
    """Coerce a parquet candle frame to a tz-naive UTC DatetimeIndex.

    Binance downloads write tz-aware (UTC) timestamps while the OKX downloader
    writes tz-naive. Comparing either against `pd.Timestamp(start)` (tz-naive)
    raises TypeError when one side is tz-aware. Normalize everything to
    tz-naive UTC at read time so the rest of the loader is type-clean.
    """
    df[ts_col] = pd.to_datetime(df[ts_col], utc=True, errors="coerce")
    df = df.dropna(subset=[ts_col])
    df = df.set_index(ts_col).sort_index()
    if df.index.tz is not None:
        df.index = df.index.tz_convert("UTC").tz_localize(None)
    return df


def _to_naive_utc_ts(value: Optional[str]) -> Optional[pd.Timestamp]:
    """Convert a start/end bound to a tz-naive UTC Timestamp.

    Mirrors `_to_naive_utc_index` so comparisons against the index always
    have matching tz state regardless of whether the caller passes an
    ISO string with or without an offset.
    """
    if value is None or value == "":
        return None
    ts = pd.Timestamp(value)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    return ts


def _filter_by_time_column(
    df: pd.DataFrame,
    ts_col: str,
    start: Optional[str],
    end: Optional[str],
) -> pd.DataFrame:
    out = df.copy()
    out[ts_col] = pd.to_datetime(out[ts_col], utc=True, errors="coerce")
    out = out.dropna(subset=[ts_col])
    start_ts = _to_naive_utc_ts(start)
    end_ts = _to_naive_utc_ts(end)
    compare = out[ts_col].dt.tz_convert("UTC").dt.tz_localize(None)
    if start_ts is not None:
        out = out[compare >= start_ts]
        compare = compare.loc[out.index]
    if end_ts is not None:
        out = out[compare < end_ts]
    return out


def _to_utc_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return ts.to_pydatetime()


def _shift_start(value: Optional[str], lookback_seconds: int) -> Optional[str]:
    if not value or lookback_seconds <= 0:
        return value
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return (ts - pd.Timedelta(seconds=int(lookback_seconds))).isoformat()


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
            df_1m = _to_naive_utc_index(pq.read_table(base_path).to_pandas())
            start_ts = _to_naive_utc_ts(start)
            end_ts = _to_naive_utc_ts(end)
            if start_ts is not None:
                df_1m = df_1m[df_1m.index >= start_ts]
            if end_ts is not None:
                df_1m = df_1m[df_1m.index < end_ts]
            return _aggregate_1m_to_bar(df_1m, bar)
        available = sorted(p.name for p in inst_dir.glob("candles_*.parquet")) if inst_dir.exists() else []
        hint = (
            f"Available bar files: {available}" if available
            else f"Run: python scripts/download_okx_data.py --inst {inst_id} --bar {bar}"
        )
        raise FileNotFoundError(
            f"Candle data not found: {path}\n{hint}"
        )
    df = _to_naive_utc_index(pq.read_table(path).to_pandas())
    start_ts = _to_naive_utc_ts(start)
    end_ts = _to_naive_utc_ts(end)
    if start_ts is not None:
        df = df[df.index >= start_ts]
    if end_ts is not None:
        df = df[df.index < end_ts]
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


# Minimum fraction of bars (measured from a symbol's first observed bar to the
# window end) required before a venue-scoped load is treated as a real gap.
VENUE_GAP_MIN_COVERAGE = 0.80


def _raise_on_venue_gap(
    df: pd.DataFrame,
    *,
    inst_id: str,
    bar: str,
    start_dt: Optional[datetime],
    end_dt: Optional[datetime],
    exchange: Optional[str],
) -> None:
    if not exchange:
        return
    # An empty venue frame means the venue has no data at all for this window — keep
    # refusing so a venue-scoped load never silently uses another venue's candles
    # (the whole reason this guard exists).
    if df.empty:
        expected = _expected_bar_count(start_dt, end_dt, bar)
        if expected is None:
            return
        raise ValueError(
            f"Venue-scoped candle gap for {inst_id} {bar} exchange='{exchange}': "
            f"expected {expected} bars, found 0. No cross-venue fallback is allowed."
        )
    # ponytail: a late-listing symbol legitimately has no bars before its first one,
    # so measure coverage from the first observed bar instead of the requested
    # start. This lets multi-symbol backtests mix coins with different listing
    # dates without crashing; an internal hole below VENUE_GAP_MIN_COVERAGE still
    # raises. Loosen the threshold if even sparser venue data should be tolerated.
    first_bar = pd.Timestamp(df.index.min())
    if first_bar.tzinfo is None:
        first_bar = first_bar.tz_localize("UTC")
    effective_start = first_bar if start_dt is None else max(pd.Timestamp(start_dt), first_bar)
    expected = _expected_bar_count(effective_start, end_dt, bar)
    if expected is None:
        return
    actual = int(pd.Index(df.index).nunique())
    if actual < expected * VENUE_GAP_MIN_COVERAGE:
        raise ValueError(
            f"Venue-scoped candle gap for {inst_id} {bar} exchange='{exchange}': "
            f"expected {expected} bars, found {actual}. No cross-venue fallback is allowed."
        )


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
    exchange: Optional[str] = None,
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
                source_primary=exchange,
            )
            if _can_derive_from_1m(bar) and _has_low_bar_coverage(df, start_dt, end_dt, bar):
                df_1m = await store.get_canonical_candles(
                    inst_id=inst_id, bar="1m",
                    start=start_dt, end=end_dt,
                    include_suspect=include_suspect,
                    source_primary=exchange,
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
        empty = pd.DataFrame(columns=["open", "high", "low", "close", "vol"])
        _raise_on_venue_gap(
            empty,
            inst_id=inst_id,
            bar=bar,
            start_dt=start_dt,
            end_dt=end_dt,
            exchange=exchange,
        )
        return empty

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

    out = df[["open", "high", "low", "close", "vol"]]
    _raise_on_venue_gap(
        out,
        inst_id=inst_id,
        bar=bar,
        start_dt=start_dt,
        end_dt=end_dt,
        exchange=exchange,
    )
    return out


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

    async def _fetch() -> tuple[pd.DataFrame, bool]:
        async with await CandleStore.from_dsn(dsn, min_size=1, max_size=2) as store:
            df = await store.get_market_klines(
                normalized_symbol=inst_id,
                bar=bar,
                start=start_dt,
                end=end_dt,
                exchange=exchange,
            )
            if _can_derive_from_1m(bar) and _has_low_bar_coverage(df, start_dt, end_dt, bar):
                df_1m = await store.get_market_klines(
                    normalized_symbol=inst_id,
                    bar="1m",
                    start=start_dt,
                    end=end_dt,
                    exchange=exchange,
                )
                if not df_1m.empty:
                    return df_1m, True
            return df, False

    try:
        asyncio.get_running_loop()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            df, is_1m_fallback = pool.submit(asyncio.run, _fetch()).result()
    except RuntimeError:
        df, is_1m_fallback = asyncio.run(_fetch())

    if df.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "vol"])

    if df.index.tz is not None:
        df.index = df.index.tz_convert("UTC").tz_localize(None)

    df = df.rename(columns={"vol": "vol"})
    if "vol" not in df.columns:
        df["vol"] = float("nan")

    if is_1m_fallback:
        df = _aggregate_1m_to_bar(df[["open", "high", "low", "close", "vol"]], bar)

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
        if not dsn or not _dsn_reachable(dsn):
            # Same DB-primary fallback as load_candles — missing or unreachable
            # DSN drops to parquet so backtests survive when the DB is down.
            backend = "parquet"
        else:
            return _load_funding_pg(inst_id, dsn, start, end)

    path = Path(data_dir) / inst_id.replace("-", "_") / "funding.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Funding data not found: {path}")
    df = _to_naive_utc_index(pq.read_table(path).to_pandas())
    if "apr" not in df.columns and "rate" in df.columns:
        interval = df.get("funding_interval_hours", 8.0)
        if hasattr(interval, "fillna"):
            interval = interval.fillna(8.0)
        df["apr"] = df["rate"] * (365 * 24 / interval)
    start_ts = _to_naive_utc_ts(start)
    end_ts = _to_naive_utc_ts(end)
    if start_ts is not None:
        df = df[df.index >= start_ts]
    if end_ts is not None:
        df = df[df.index < end_ts]
    return df


def load_trade_ticks(
    inst_id: str,
    data_dir: str = "data/ticks",
    start: Optional[str] = None,
    end: Optional[str] = None,
    backend: Literal["parquet", "postgres"] = "parquet",
    dsn: Optional[str] = None,
) -> pd.DataFrame:
    """Load raw trade ticks from FeedStore parquet or a per-instrument Timescale table."""
    if backend == "postgres":
        if not dsn or not _dsn_reachable(dsn):
            backend = "parquet"
        else:
            return _load_trade_ticks_pg(inst_id, dsn, start, end)

    inst_dir = Path(data_dir) / inst_id.replace("-", "_")
    frames = _read_trade_tick_parquet_frames(inst_dir)
    if not frames:
        raise FileNotFoundError(f"Trade tick data not found under: {inst_dir}")
    df = pd.concat(frames, ignore_index=True)
    ts_col = "ts" if "ts" in df.columns else ("timestamp" if "timestamp" in df.columns else "")
    if not ts_col:
        raise ValueError("Trade tick parquet data must include ts or timestamp column")
    df = _filter_by_time_column(df, ts_col=ts_col, start=start, end=end)
    price_col = "price" if "price" in df.columns else ("px" if "px" in df.columns else "")
    size_col = "size" if "size" in df.columns else ("sz" if "sz" in df.columns else "")
    if not price_col or not size_col:
        raise ValueError("Trade tick parquet data must include price/px and size/sz columns")
    out = pd.DataFrame({
        "ts": pd.to_datetime(df[ts_col], utc=True, errors="coerce"),
        "trade_id": df.get("trade_id", df.get("tradeId", "")),
        "price": pd.to_numeric(df[price_col], errors="coerce"),
        "size": pd.to_numeric(df[size_col], errors="coerce"),
        "side": df.get("side", ""),
    }).dropna(subset=["ts", "price", "size"])
    if not out.empty:
        out["ts"] = out["ts"].dt.tz_convert("UTC").dt.tz_localize(None)
    return out.sort_values("ts").reset_index(drop=True)


def _read_trade_tick_parquet_frames(inst_dir: Path) -> list[pd.DataFrame]:
    paths = []
    flat = inst_dir / "trades.parquet"
    if flat.exists():
        paths.append(flat)
    if inst_dir.exists():
        paths.extend(sorted(inst_dir.glob("*/trades.parquet")))
    return [pq.read_table(path).to_pandas() for path in paths if path.exists()]


def _trade_ticks_table_name(inst_id: str) -> str:
    table = inst_id.lower().replace("-", "_") + "_trades"
    if not table.replace("_", "").isalnum():
        raise ValueError(f"Unsafe trade tick table name for {inst_id!r}")
    return table


def _load_trade_ticks_pg(
    inst_id: str,
    dsn: str,
    start: Optional[str],
    end: Optional[str],
) -> pd.DataFrame:
    import asyncio
    import concurrent.futures
    import asyncpg

    table = _trade_ticks_table_name(inst_id)
    start_dt = _to_utc_dt(start)
    end_dt = _to_utc_dt(end)

    async def _fetch() -> pd.DataFrame:
        conn = await asyncpg.connect(dsn)
        try:
            exists = await conn.fetchval("SELECT to_regclass($1)", table)
            if not exists:
                return pd.DataFrame(columns=["ts", "trade_id", "price", "size", "side"])
            rows = await conn.fetch(
                f"""
                SELECT ts, trade_id, price, size, side
                FROM {table}
                WHERE ($1::timestamptz IS NULL OR ts >= $1)
                  AND ($2::timestamptz IS NULL OR ts <  $2)
                ORDER BY ts
                """,
                start_dt,
                end_dt,
            )
        finally:
            await conn.close()
        if not rows:
            return pd.DataFrame(columns=["ts", "trade_id", "price", "size", "side"])
        df = pd.DataFrame([dict(row) for row in rows])
        df["ts"] = pd.to_datetime(df["ts"], utc=True, errors="coerce").dt.tz_convert("UTC").dt.tz_localize(None)
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        df["size"] = pd.to_numeric(df["size"], errors="coerce")
        return df.dropna(subset=["ts", "price", "size"]).sort_values("ts").reset_index(drop=True)

    try:
        asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, _fetch()).result()
    except RuntimeError:
        return asyncio.run(_fetch())


def load_external_observations(
    dataset_id: str,
    data_dir: str = "data/external",
    start: Optional[str] = None,
    end: Optional[str] = None,
    backend: Literal["postgres", "parquet"] = "postgres",
    dsn: Optional[str] = None,
    lookback_seconds: int = 0,
) -> pd.DataFrame:
    """Load external feature observations from PostgreSQL.

    The ``data_dir`` argument is reserved for a future local fixture backend so
    callers can keep the same signature as other loaders.
    """
    del data_dir
    if backend != "postgres" or not dsn or not _dsn_reachable(dsn):
        return pd.DataFrame(columns=[
            "dataset_id", "observed_at", "published_at", "value_num",
            "value_text", "fields", "quality_status", "raw_payload", "ingested_at",
        ])
    return _load_external_observations_pg(
        dataset_id,
        dsn,
        _shift_start(start, lookback_seconds),
        end,
    )


def _load_external_observations_pg(
    dataset_id: str,
    dsn: str,
    start: Optional[str],
    end: Optional[str],
) -> pd.DataFrame:
    from okx_quant.data.external_store import ExternalDataStore

    start_dt = _to_utc_dt(start)
    end_dt = _to_utc_dt(end)

    async def _fetch() -> pd.DataFrame:
        async with await ExternalDataStore.from_dsn(dsn, min_size=1, max_size=2) as store:
            return await store.get_observations(dataset_id, start=start_dt, end=end_dt)

    try:
        asyncio.get_running_loop()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, _fetch()).result()
    except RuntimeError:
        return asyncio.run(_fetch())


def load_feature_events(
    dataset_id: str,
    data_dir: str = "data/external",
    start: Optional[str] = None,
    end: Optional[str] = None,
    backend: Literal["postgres", "parquet"] = "postgres",
    dsn: Optional[str] = None,
    lookback_seconds: int = 0,
) -> pd.DataFrame:
    """Return feature observations as replay event rows.

    Event time is ``published_at`` when present, otherwise ``observed_at``.
    This keeps the replay from seeing values before the configured publication
    policy allows them.
    """
    observations = load_external_observations(
        dataset_id,
        data_dir=data_dir,
        start=start,
        end=end,
        backend=backend,
        dsn=dsn,
        lookback_seconds=lookback_seconds,
    )
    if observations.empty:
        return pd.DataFrame(columns=[
            "ts", "dataset_id", "observed_at", "published_at", "value_num",
            "value_text", "fields", "quality_status",
        ])
    frame = observations.copy()
    frame["observed_at"] = pd.to_datetime(frame["observed_at"], utc=True, errors="coerce")
    frame["published_at"] = pd.to_datetime(frame.get("published_at"), utc=True, errors="coerce")
    frame = frame.dropna(subset=["observed_at"])
    event_ts = frame["published_at"].where(frame["published_at"].notna(), frame["observed_at"])
    frame["ts"] = event_ts.map(_timestamp_to_ms).astype("int64")
    frame["dataset_id"] = dataset_id
    frame["fields"] = frame["fields"].apply(lambda value: value if isinstance(value, dict) else {})
    return frame[[
        "ts", "dataset_id", "observed_at", "published_at", "value_num",
        "value_text", "fields", "quality_status",
    ]].sort_values("ts")


def _timestamp_to_ms(value: Any) -> int:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return int(ts.timestamp() * 1000)


def asof_join_features(
    timestamps: pd.Series | pd.DatetimeIndex | list[Any],
    observations: pd.DataFrame,
    *,
    max_age_seconds: int,
    prefix: str,
) -> pd.DataFrame:
    """Backward as-of join observations onto event timestamps with TTL."""
    left = pd.DataFrame({"ts": pd.to_datetime(timestamps, utc=True, errors="coerce")}).dropna()
    if left.empty:
        return pd.DataFrame(columns=["ts"])
    if observations.empty:
        out = left.copy()
        out[f"{prefix}_fresh"] = False
        out[f"{prefix}_missing"] = True
        out[f"{prefix}_stale"] = False
        return out

    right = observations.copy()
    right["observed_at"] = pd.to_datetime(right["observed_at"], utc=True, errors="coerce")
    right["published_at"] = pd.to_datetime(right.get("published_at"), utc=True, errors="coerce")
    right["feature_ts"] = right["published_at"].where(right["published_at"].notna(), right["observed_at"])
    right = right.dropna(subset=["feature_ts"]).sort_values("feature_ts")
    merged = pd.merge_asof(
        left.sort_values("ts"),
        right[["feature_ts", "observed_at", "published_at", "value_num", "value_text", "fields"]],
        left_on="ts",
        right_on="feature_ts",
        direction="backward",
    )
    age_seconds = (merged["ts"] - merged["feature_ts"]).dt.total_seconds()
    missing = merged["feature_ts"].isna()
    stale = ~missing & (age_seconds > int(max_age_seconds))
    merged[f"{prefix}_fresh"] = ~missing & ~stale
    merged[f"{prefix}_missing"] = missing
    merged[f"{prefix}_stale"] = stale
    merged[f"{prefix}_age_seconds"] = age_seconds
    rename = {
        "value_num": f"{prefix}_value_num",
        "value_text": f"{prefix}_value_text",
        "fields": f"{prefix}_fields",
        "observed_at": f"{prefix}_observed_at",
        "published_at": f"{prefix}_published_at",
    }
    return merged.rename(columns=rename)


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
