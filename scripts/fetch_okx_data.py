"""
Download real OKX OHLCV + funding data via public API (no API key needed).

Saves to data/ticks/{inst_id}/candles_{bar}.parquet and funding.parquet.

Usage:
    python scripts/fetch_okx_data.py
    python scripts/fetch_okx_data.py --start 2024-01-01 --end 2026-04-18 --bar 1H
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import httpx
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

BASE_URL  = "https://www.okx.com"
SLEEP_S   = 0.12   # 100 ms between requests (~8 req/s, well under 40 req/2s limit)


def _ts_ms(date_str: str) -> int:
    """Convert 'YYYY-MM-DD' → Unix ms."""
    return int(pd.Timestamp(date_str, tz="UTC").timestamp() * 1000)


def fetch_candles(
    inst_id: str,
    bar: str,
    start_ms: int,
    end_ms: int,
) -> pd.DataFrame:
    """
    Download OHLCV from OKX history-candles (paginated, no auth).

    Returns DataFrame with DatetimeIndex (UTC) and columns:
        open, high, low, close, vol
    """
    client = httpx.Client(base_url=BASE_URL, timeout=15.0)
    rows = []
    after_ms: int | None = end_ms   # paginate backwards from end

    print(f"  Fetching {inst_id} {bar} candles …", end="", flush=True)

    while True:
        params: dict = {"instId": inst_id, "bar": bar, "limit": "100"}
        if after_ms is not None:
            params["after"] = str(after_ms)

        resp = client.get("/api/v5/market/history-candles", params=params)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        if not data:
            break

        for row in data:
            ts_ms = int(row[0])
            if ts_ms < start_ms:
                # Reached start boundary — done
                data = []
                break
            rows.append({
                "ts":    ts_ms,
                "open":  float(row[1]),
                "high":  float(row[2]),
                "low":   float(row[3]),
                "close": float(row[4]),
                "vol":   float(row[5]),
            })

        if not data:
            break

        # Oldest timestamp in this page → cursor for next page
        after_ms = int(data[-1][0]) - 1  # exclusive
        print(".", end="", flush=True)
        time.sleep(SLEEP_S)

    client.close()
    print(f" {len(rows):,} bars")

    if not rows:
        raise RuntimeError(f"No candle data returned for {inst_id} {bar}")

    df = (
        pd.DataFrame(rows)
        .assign(ts=lambda d: pd.to_datetime(d["ts"], unit="ms", utc=True))
        .set_index("ts")
        .sort_index()
    )
    # Trim to exact range
    df = df.loc[pd.Timestamp(start_ms, unit="ms", tz="UTC"):
                pd.Timestamp(end_ms,   unit="ms", tz="UTC")]
    return df


def fetch_funding(
    inst_id: str,
    start_ms: int,
    end_ms: int,
) -> pd.DataFrame:
    """
    Download funding rate history from OKX (paginated, no auth).
    Returns DataFrame with DatetimeIndex (UTC) and columns: rate, realized_rate
    """
    client = httpx.Client(base_url=BASE_URL, timeout=15.0)
    rows = []
    after_ms: int | None = end_ms

    print(f"  Fetching {inst_id} funding rates …", end="", flush=True)

    while True:
        params: dict = {"instId": inst_id, "limit": "100"}
        if after_ms is not None:
            params["after"] = str(after_ms)

        resp = client.get("/api/v5/public/funding-rate-history", params=params)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        if not data:
            break

        for row in data:
            ts_ms = int(row.get("fundingTime", 0))
            if ts_ms < start_ms:
                data = []
                break
            rows.append({
                "ts":            ts_ms,
                "rate":          float(row.get("fundingRate",   0)),
                "realized_rate": float(row.get("realizedRate",  row.get("fundingRate", 0))),
            })

        if not data:
            break

        after_ms = int(rows[-1]["ts"]) - 1
        print(".", end="", flush=True)
        time.sleep(SLEEP_S)

    client.close()
    print(f" {len(rows):,} settlements")

    if not rows:
        raise RuntimeError(f"No funding data returned for {inst_id}")

    df = (
        pd.DataFrame(rows)
        .assign(ts=lambda d: pd.to_datetime(d["ts"], unit="ms", utc=True))
        .set_index("ts")
        .sort_index()
    )
    df = df.loc[pd.Timestamp(start_ms, unit="ms", tz="UTC"):
                pd.Timestamp(end_ms,   unit="ms", tz="UTC")]
    return df


def save_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Reset index so 'ts' becomes a column (matches data_loader.py expectation)
    out = df.reset_index()
    # Strip timezone for parquet compatibility with data_loader
    if hasattr(out["ts"].dtype, "tz") and out["ts"].dtype.tz is not None:
        out["ts"] = out["ts"].dt.tz_convert("UTC").dt.tz_localize(None)
    pq.write_table(pa.Table.from_pandas(out, preserve_index=False), path, compression="snappy")
    print(f"    → saved {len(out):,} rows to {path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end",   default="2026-04-18")
    parser.add_argument("--bar",   default="1H")
    args = parser.parse_args()

    root    = Path(__file__).parent.parent
    out_dir = root / "data" / "ticks"
    start_ms = _ts_ms(args.start)
    end_ms   = _ts_ms(args.end)

    print(f"\nDownloading OKX data: {args.start} → {args.end}  bar={args.bar}")

    # ── BTC-USDT-SWAP candles ────────────────────────────────────────────────
    btc_candles = fetch_candles("BTC-USDT-SWAP", args.bar, start_ms, end_ms)
    save_parquet(btc_candles, out_dir / "BTC_USDT_SWAP" / f"candles_{args.bar}.parquet")

    # ── ETH-USDT-SWAP candles ────────────────────────────────────────────────
    eth_candles = fetch_candles("ETH-USDT-SWAP", args.bar, start_ms, end_ms)
    save_parquet(eth_candles, out_dir / "ETH_USDT_SWAP" / f"candles_{args.bar}.parquet")

    # ── BTC-USDT-SWAP funding rates ──────────────────────────────────────────
    funding = fetch_funding("BTC-USDT-SWAP", start_ms, end_ms)
    # Add APR column for convenience
    funding["apr"] = funding["rate"] * (365 * 24 / 8)
    save_parquet(funding, out_dir / "BTC_USDT_SWAP" / "funding.parquet")

    print("\nDone. Re-run run_backtest.py to use real data.\n")


if __name__ == "__main__":
    main()
