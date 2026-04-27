"""Minute-bar data loading and regular-session filtering for TW/US stocks."""
from __future__ import annotations

from datetime import time
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from okx_quant.stocks.models import StockMarket


REQUIRED_OHLCV = ("open", "high", "low", "close", "volume")


def exchange_timezone(market: StockMarket) -> ZoneInfo:
    if market == StockMarket.TW:
        return ZoneInfo("Asia/Taipei")
    if market == StockMarket.US:
        return ZoneInfo("America/New_York")
    raise ValueError(f"Unsupported stock market: {market}")


def regular_session(market: StockMarket) -> tuple[time, time]:
    if market == StockMarket.TW:
        return time(9, 0), time(13, 30)
    if market == StockMarket.US:
        return time(9, 30), time(16, 0)
    raise ValueError(f"Unsupported stock market: {market}")


def annualization_periods(market: StockMarket) -> int:
    minutes_per_day = 270 if market == StockMarket.TW else 390
    return 252 * minutes_per_day


def is_regular_session(ts: pd.Timestamp, market: StockMarket) -> bool:
    local_ts = _as_exchange_timestamp(ts, market)
    if local_ts.weekday() >= 5:
        return False
    session_open, session_close = regular_session(market)
    current = local_ts.time()
    return session_open <= current < session_close


def filter_regular_session(df: pd.DataFrame, market: StockMarket) -> pd.DataFrame:
    if df.empty:
        return df
    mask = [is_regular_session(ts, market) for ts in df.index]
    return df.loc[mask].copy()


def load_minute_bars(
    path: str | Path,
    market: StockMarket | str,
    symbol: str | None = None,
    session_filter: bool = True,
) -> pd.DataFrame:
    """Load 1-minute OHLCV bars from parquet or CSV.

    The loader accepts ``ts``, ``timestamp``, ``datetime``, or a DatetimeIndex
    and returns a timezone-aware DatetimeIndex in the exchange timezone.
    """

    market = StockMarket(market)
    path = Path(path)
    if path.suffix.lower() == ".parquet":
        data = pd.read_parquet(path)
    elif path.suffix.lower() in {".csv", ".txt"}:
        data = pd.read_csv(path)
    else:
        raise ValueError("Minute bars must be stored as parquet or CSV")

    data = _normalize_columns(data)
    data.index = _build_datetime_index(data, market)
    data = data.sort_index()

    missing = [col for col in REQUIRED_OHLCV if col not in data.columns]
    if missing:
        raise ValueError(f"Minute bars missing required columns: {missing}")

    data = data.loc[:, [*REQUIRED_OHLCV, *(["symbol"] if "symbol" in data.columns else [])]]
    for col in REQUIRED_OHLCV:
        data[col] = pd.to_numeric(data[col], errors="coerce")
    data = data.dropna(subset=list(REQUIRED_OHLCV))
    if symbol is not None:
        data["symbol"] = symbol
    if session_filter:
        data = filter_regular_session(data, market)
    return data


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()
    data.columns = [str(col).strip().lower() for col in data.columns]
    aliases = {
        "date": "ts",
        "datetime": "ts",
        "timestamp": "ts",
        "time": "ts",
        "vol": "volume",
    }
    return data.rename(columns={old: new for old, new in aliases.items() if old in data.columns})


def _build_datetime_index(df: pd.DataFrame, market: StockMarket) -> pd.DatetimeIndex:
    tz = exchange_timezone(market)
    if "ts" in df.columns:
        raw = pd.to_datetime(df["ts"], errors="coerce")
        if raw.isna().any():
            raise ValueError("Minute bars contain invalid timestamps")
        if raw.dt.tz is None:
            return pd.DatetimeIndex(raw.dt.tz_localize(tz))
        return pd.DatetimeIndex(raw.dt.tz_convert(tz))
    elif isinstance(df.index, pd.DatetimeIndex):
        raw = pd.to_datetime(df.index, errors="coerce")
        if raw.isna().any():
            raise ValueError("Minute bars contain invalid timestamps")
        if raw.tz is None:
            return pd.DatetimeIndex(raw.tz_localize(tz))
        return pd.DatetimeIndex(raw.tz_convert(tz))
    else:
        raise ValueError("Minute bars need a ts/timestamp/datetime column or DatetimeIndex")


def _as_exchange_timestamp(ts: pd.Timestamp, market: StockMarket) -> pd.Timestamp:
    tz = exchange_timezone(market)
    ts = pd.Timestamp(ts)
    if ts.tzinfo is None:
        return ts.tz_localize(tz)
    return ts.tz_convert(tz)
