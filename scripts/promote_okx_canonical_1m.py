"""Promote the authorized frozen-window OKX BTC/ETH 1m raw rows."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from okx_quant.data.candle_store import CandleStore  # noqa: E402
from scripts._db_writer import resolve_dsn  # noqa: E402
from scripts.market_data.init_db import _apply_migration  # noqa: E402

SOURCE = "okx"
SYMBOLS = ("BTC-USDT-SWAP", "ETH-USDT-SWAP")
BAR = "1m"
START = datetime(2024, 1, 1, tzinfo=timezone.utc)
END_EXCLUSIVE = datetime(2026, 6, 17, tzinfo=timezone.utc)
MIGRATION = ROOT / "src/okx_quant/data/migrations/004_venue_canonical_candles.sql"


async def apply_schema(dsn: str) -> None:
    import asyncpg

    conn = await asyncpg.connect(dsn)
    try:
        await _apply_migration(conn, MIGRATION)
    finally:
        await conn.close()


async def promote(dsn: str) -> dict:
    store = await CandleStore.from_dsn(dsn, min_size=1, max_size=2)
    try:
        rows = {
            symbol: await store.canonicalize_from_raw(
                SOURCE,
                symbol,
                BAR,
                start=START,
                end=END_EXCLUSIVE,
            )
            for symbol in SYMBOLS
        }
    finally:
        await store.close()
    return {
        "status": "COMPLETE",
        "layer": "venue_canonical_candles",
        "source": SOURCE,
        "bar": BAR,
        "window": {"start": START.isoformat(), "end_exclusive": END_EXCLUSIVE.isoformat()},
        "symbols": rows,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", help="Override DATABASE_URL/config DSN")
    args = parser.parse_args(argv)
    dsn = resolve_dsn(args.dsn)
    if not dsn:
        parser.error("no DSN available")
    try:
        asyncio.run(apply_schema(dsn))
        report = asyncio.run(promote(dsn))
    except Exception as exc:
        print(f"FAIL: OKX canonical promotion failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
