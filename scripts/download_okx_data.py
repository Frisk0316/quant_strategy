"""
Download historical OKX market data for backtesting.
Data sources:
  - OKX official: L2 books (from 2023-03), trades, funding, OHLCV
  - Saves to Parquet in data/ticks/{instrument}/{date}/

Usage:
    python scripts/download_okx_data.py --inst BTC-USDT-SWAP --days 30
    python scripts/download_okx_data.py --inst BTC-USDT-SWAP --type candles --bar 1m
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from okx_quant.core.config import load_config
from okx_quant.data.rest_client import OKXRestClient


def download_candles(
    client: OKXRestClient,
    inst_id: str,
    bar: str = "1m",
    days: int = 30,
    out_dir: Path = Path("data/ticks"),
) -> None:
    """Download OHLCV candles and save to Parquet."""
    print(f"Downloading {bar} candles for {inst_id} ({days} days)...")

    all_rows = []
    after = ""  # pagination cursor

    while True:
        params = {"instId": inst_id, "bar": bar, "limit": "300"}
        if after:
            params["after"] = after
        resp = client.get("/api/v5/market/history-candles", params)
        data = resp.get("data", [])
        if not data:
            break
        for row in data:
            all_rows.append({
                "ts": int(row[0]),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "vol": float(row[5]),
                "vol_ccy": float(row[6]) if len(row) > 6 else 0.0,
            })
        after = data[-1][0]  # oldest timestamp for next page
        # Stop if we have enough data (approx)
        oldest_ts = int(data[-1][0]) / 1000
        start_ts = time.time() - days * 86400
        if oldest_ts < start_ts:
            break
        time.sleep(0.1)  # rate limit courtesy

    df = pd.DataFrame(all_rows)
    df["ts"] = pd.to_datetime(df["ts"], unit="ms")
    df.sort_values("ts", inplace=True)

    out = out_dir / inst_id.replace("-", "_") / f"candles_{bar}.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pandas(df), out, compression="snappy")
    print(f"Saved {len(df)} rows → {out}")


def download_funding(
    client: OKXRestClient,
    inst_id: str,
    out_dir: Path = Path("data/ticks"),
) -> None:
    """Download funding rate history."""
    print(f"Downloading funding history for {inst_id}...")
    all_rows = []
    after = ""

    while True:
        params = {"instId": inst_id, "limit": "100"}
        if after:
            params["after"] = after
        resp = client.get("/api/v5/public/funding-rate-history", params)
        data = resp.get("data", [])
        if not data:
            break
        for row in data:
            all_rows.append({
                "ts": int(row.get("fundingTime", 0)),
                "rate": float(row.get("fundingRate", 0)),
                "realized_rate": float(row.get("realizedRate", row.get("fundingRate", 0))),
            })
        if len(data) < 100:
            break
        after = data[-1].get("fundingTime", "")
        time.sleep(0.1)

    df = pd.DataFrame(all_rows)
    df["ts"] = pd.to_datetime(df["ts"], unit="ms")
    df.sort_values("ts", inplace=True)

    out = out_dir / inst_id.replace("-", "_") / "funding.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pandas(df), out, compression="snappy")
    print(f"Saved {len(df)} funding rows → {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download OKX historical data")
    parser.add_argument("--inst", default="BTC-USDT-SWAP", help="Instrument ID")
    parser.add_argument("--type", choices=["candles", "funding", "all"], default="all")
    parser.add_argument("--bar", default="1m", help="Candle bar size (for type=candles)")
    parser.add_argument("--days", type=int, default=30, help="Days of history")
    parser.add_argument("--out", default="data/ticks", help="Output directory")
    args = parser.parse_args()

    cfg = load_config()
    client = OKXRestClient(
        api_key=cfg.secrets.okx_api_key,
        secret=cfg.secrets.okx_secret,
        passphrase=cfg.secrets.okx_passphrase,
        base_url=cfg.okx.base_url,
        demo=False,  # Use real endpoint for historical data
    )
    client.sync_clock()

    out_dir = Path(args.out)

    try:
        if args.type in ("candles", "all"):
            download_candles(client, args.inst, args.bar, args.days, out_dir)
        if args.type in ("funding", "all") and "SWAP" in args.inst:
            download_funding(client, args.inst, out_dir)
    finally:
        client.close()


if __name__ == "__main__":
    main()
