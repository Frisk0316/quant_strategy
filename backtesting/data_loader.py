"""
Data loader for backtesting.
Loads OKX L2/OHLCV/funding from local Parquet or Tardis format.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd
import pyarrow.parquet as pq


def load_candles(
    inst_id: str,
    bar: str = "1m",
    data_dir: str = "data/ticks",
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> pd.DataFrame:
    """
    Load OHLCV candles from Parquet.

    Returns:
        DataFrame with columns [ts, open, high, low, close, vol]
        indexed by ts (datetime).
    """
    path = Path(data_dir) / inst_id.replace("-", "_") / f"candles_{bar}.parquet"
    if not path.exists():
        raise FileNotFoundError(
            f"Candle data not found: {path}\n"
            f"Run: python scripts/download_okx_data.py --inst {inst_id} --bar {bar}"
        )
    df = pq.read_table(path).to_pandas()
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.set_index("ts").sort_index()
    if start:
        df = df[df.index >= pd.Timestamp(start)]
    if end:
        df = df[df.index < pd.Timestamp(end)]
    return df


def load_funding(
    inst_id: str,
    data_dir: str = "data/ticks",
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> pd.DataFrame:
    """Load funding rate history and derive APR when absent."""
    path = Path(data_dir) / inst_id.replace("-", "_") / "funding.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Funding data not found: {path}")
    df = pq.read_table(path).to_pandas()
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.set_index("ts").sort_index()
    if "apr" not in df.columns and "rate" in df.columns:
        df["apr"] = df["rate"] * (365 * 24 / 8)
    if start:
        df = df[df.index >= pd.Timestamp(start)]
    if end:
        df = df[df.index < pd.Timestamp(end)]
    return df


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
