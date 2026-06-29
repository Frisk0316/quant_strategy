"""
Download historical Binance USDⓈ-M Futures OHLCV data for backtesting.
Uses the public Binance Futures REST API — no API key required for klines.

Saves to Parquet in data/ticks/{instrument}/candles_{bar}.parquet,
matching the same schema used by download_okx_data.py.

Usage:
    python scripts/download_binance_data.py --inst MEME-USDT-SWAP --bar 1m --days 90
    python scripts/download_binance_data.py --inst BTC-USDT-SWAP --bar 1h --days 365
"""
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _db_writer import upsert_candles_to_db  # noqa: E402

BINANCE_FUTURES_BASE = "https://fapi.binance.com"
BINANCE_SPOT_BASE = "https://api.binance.com"
FUTURES_KLINES_ENDPOINT = "/fapi/v1/klines"
SPOT_KLINES_ENDPOINT = "/api/v3/klines"
MAX_LIMIT = 1500  # Binance max per request


@dataclass(frozen=True)
class BinanceMarketConfig:
    base_url: str
    endpoint: str
    max_limit: int


def market_config_for_inst(inst_id: str) -> BinanceMarketConfig:
    parts = inst_id.upper().split("-")
    if parts and parts[-1] in {"SWAP", "PERP", "FUTURES"}:
        return BinanceMarketConfig(BINANCE_FUTURES_BASE, FUTURES_KLINES_ENDPOINT, 1500)
    return BinanceMarketConfig(BINANCE_SPOT_BASE, SPOT_KLINES_ENDPOINT, 1000)

# Map our internal bar notation to Binance interval strings
BAR_MAP = {
    "1m": "1m",
    "3m": "3m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1H": "1h",
    "1h": "1h",
    "2H": "2h",
    "4H": "4h",
    "6H": "6h",
    "8H": "8h",
    "12H": "12h",
    "1D": "1d",
    "1d": "1d",
    "3D": "3d",
    "1W": "1w",
    "1M": "1M",
}

# Bar duration in milliseconds (used for pagination)
BAR_MS = {
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "2h": 7_200_000,
    "4h": 14_400_000,
    "6h": 21_600_000,
    "8h": 28_800_000,
    "12h": 43_200_000,
    "1d": 86_400_000,
    "3d": 259_200_000,
    "1w": 604_800_000,
    "1M": 2_592_000_000,
}


def inst_to_binance_symbol(inst_id: str) -> str:
    """Convert OKX-style inst ID to Binance symbol.

    e.g. MEME-USDT-SWAP → MEMEUSDT
         BTC-USDT-SWAP  → BTCUSDT
         ETH-USDT       → ETHUSDT  (spot — not futures, but kept for completeness)
    """
    parts = inst_id.upper().split("-")
    # Strip trailing SWAP/PERP/etc
    if parts[-1] in ("SWAP", "PERP", "FUTURES"):
        parts = parts[:-1]
    return "".join(parts)


def download_klines(
    symbol: str,
    interval: str,
    start_ms: int,
    end_ms: int,
    base_sleep: float = 0.25,
    market: BinanceMarketConfig | None = None,
) -> list[dict]:
    rows: list[dict] = []
    current_start = start_ms
    bar_dur = BAR_MS.get(interval, 60_000)

    market = market or BinanceMarketConfig(BINANCE_FUTURES_BASE, FUTURES_KLINES_ENDPOINT, 1500)
    with httpx.Client(base_url=market.base_url, timeout=30) as client:
        while current_start < end_ms:
            params = {
                "symbol": symbol,
                "interval": interval,
                "startTime": current_start,
                "endTime": end_ms,
                "limit": market.max_limit,
            }

            # retry loop with exponential backoff on 429 / 5xx
            backoff = 2.0
            for attempt in range(8):
                resp = client.get(market.endpoint, params=params)
                if resp.status_code == 429:
                    retry_after = float(resp.headers.get("Retry-After", backoff))
                    wait = max(retry_after, backoff)
                    print(f"  [429] rate-limited — waiting {wait:.0f}s (attempt {attempt+1})")
                    time.sleep(wait)
                    backoff = min(backoff * 2, 60)
                    continue
                if resp.status_code >= 500:
                    print(f"  [{resp.status_code}] server error — retrying in {backoff:.0f}s")
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 60)
                    continue
                resp.raise_for_status()
                break
            else:
                raise RuntimeError(f"Failed after 8 retries at startTime={current_start}")

            data = resp.json()
            if not data:
                break

            for candle in data:
                rows.append({
                    "ts": int(candle[0]),
                    "open": float(candle[1]),
                    "high": float(candle[2]),
                    "low": float(candle[3]),
                    "close": float(candle[4]),
                    "vol": float(candle[5]),
                    "vol_ccy": float(candle[7]),  # quote asset volume
                })

            last_open_ms = int(data[-1][0])
            current_start = last_open_ms + bar_dur

            print(
                f"  fetched {len(data)} candles, "
                f"last={datetime.fromtimestamp(last_open_ms / 1000, tz=timezone.utc).isoformat()}"
                f"  total={len(rows):,}"
            )

            if len(data) < market.max_limit:
                break

            time.sleep(base_sleep)

    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Download Binance Futures OHLCV data")
    parser.add_argument(
        "--inst", default="MEME-USDT-SWAP",
        help="Instrument ID in OKX notation (e.g. MEME-USDT-SWAP)",
    )
    parser.add_argument("--bar", default="1m", help="Bar size (1m, 5m, 1H, 1D, ...)")
    parser.add_argument("--days", type=int, default=90, help="Days of history (ignored if --start given)")
    parser.add_argument(
        "--start", default=None,
        help="Start date in YYYY-MM-DD format (UTC); overrides --days",
    )
    parser.add_argument(
        "--end", default=None,
        help="Exclusive end date in YYYY-MM-DD format (UTC); defaults to now",
    )
    parser.add_argument("--out", default="data/ticks", help="Output root directory")
    parser.add_argument(
        "--write-db", dest="write_db", action="store_true", default=True,
        help="Also upsert the downloaded candles into TimescaleDB canonical_candles (default: on)",
    )
    parser.add_argument(
        "--no-write-db", dest="write_db", action="store_false",
        help="Skip the DB upsert and only write parquet",
    )
    parser.add_argument("--dsn", default=None, help="Override DATABASE_URL / config DSN for the DB upsert")
    args = parser.parse_args()

    binance_symbol = inst_to_binance_symbol(args.inst)
    binance_interval = BAR_MAP.get(args.bar, args.bar)
    market = market_config_for_inst(args.inst)
    out_dir = Path(args.out)

    folder = args.inst.replace("-", "_")
    out_path = out_dir / folder / f"candles_{args.bar}.parquet"

    if args.end:
        end_dt = datetime.strptime(args.end, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        now_ms = int(end_dt.timestamp() * 1000)
    else:
        now_ms = int(time.time() * 1000)

    # Incremental mode: if file exists, resume from last candle + 1 bar.
    # Explicit --start is a repair/backfill window and takes precedence.
    existing_df: pd.DataFrame | None = None
    if out_path.exists():
        existing_df = pq.read_table(out_path).to_pandas()
    if args.start:
        start_dt = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        start_ms = int(start_dt.timestamp() * 1000)
    elif existing_df is not None:
        last_ts = existing_df["ts"].max()
        bar_dur = BAR_MS.get(BAR_MAP.get(args.bar, args.bar), 60_000)
        start_ms = int(last_ts.timestamp() * 1000) + bar_dur
        print(f"Existing file found: {len(existing_df):,} rows, last={last_ts.isoformat()}")
        print(f"Resuming from {datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc).isoformat()}")
    else:
        start_ms = now_ms - args.days * 86_400_000

    start_date = datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc).date()
    end_date = datetime.fromtimestamp(now_ms / 1000, tz=timezone.utc).date()
    total_days = (end_date - start_date).days

    if start_ms >= now_ms:
        print(f"Already up to date ({start_date}). Nothing to download.")
        return

    print(
        f"Downloading {binance_interval} klines for {binance_symbol} "
        f"({total_days} days, {start_date} → {end_date})"
    )

    rows = download_klines(binance_symbol, binance_interval, start_ms, now_ms, market=market)

    if not rows:
        print("No new data returned.")
        return

    new_df = pd.DataFrame(rows)
    new_df["ts"] = pd.to_datetime(new_df["ts"], unit="ms", utc=True).dt.tz_localize(None)
    if args.end:
        end_ts = datetime.fromtimestamp(now_ms / 1000, tz=timezone.utc).replace(tzinfo=None)
        new_df = new_df[new_df["ts"] < end_ts]
        if new_df.empty:
            print("No new data returned before exclusive --end.")
            return

    if existing_df is not None:
        df = pd.concat([existing_df, new_df], ignore_index=True)
    else:
        df = new_df

    df.drop_duplicates("ts", keep="last", inplace=True)
    df.sort_values("ts", inplace=True)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pandas(df), out_path, compression="snappy")
    print(f"\nSaved {len(df):,} rows → {out_path}  (+{len(new_df):,} new)")
    print(f"Date range: {df['ts'].min()} … {df['ts'].max()}")

    if args.write_db:
        db_result = upsert_candles_to_db(
            df=new_df,
            inst_id=args.inst,
            bar=args.bar,
            source="binance",
            dsn=args.dsn,
        )
        status = db_result.get("status")
        if status == "ok":
            print(f"DB upsert: {db_result['written']:,} canonical rows (raw={db_result['raw_written']:,})")
        elif status == "skipped":
            print(f"DB upsert skipped: {db_result.get('reason')}")
        else:
            print(f"DB upsert error (non-fatal): {db_result.get('reason')}")


if __name__ == "__main__":
    main()
