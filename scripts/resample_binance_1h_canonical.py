"""Resample existing Binance 1m canonical candles into 1H canonical candles."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import asyncpg

from okx_quant.data.canonical_policy import canonical_conflict_where


def _utc_day(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)


async def _counts(conn: asyncpg.Connection, inst_id: str) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        """
        SELECT source_primary, bar, COUNT(1) AS rows, MIN(ts) AS min_ts, MAX(ts) AS max_ts
        FROM canonical_candles
        WHERE inst_id=$1
        GROUP BY source_primary, bar
        ORDER BY source_primary, bar
        """,
        inst_id,
    )
    return [
        {
            "source_primary": row["source_primary"],
            "bar": row["bar"],
            "rows": int(row["rows"]),
            "min_ts": row["min_ts"].isoformat() if row["min_ts"] else None,
            "max_ts": row["max_ts"].isoformat() if row["max_ts"] else None,
        }
        for row in rows
    ]


async def _resample(conn: asyncpg.Connection, inst_id: str, start: datetime, end: datetime) -> int:
    rows = await conn.fetch(
        f"""
        WITH hourly AS (
            SELECT
                date_trunc('hour', ts) AS hour_ts,
                (array_agg(open ORDER BY ts))[1] AS open,
                MAX(high) AS high,
                MIN(low) AS low,
                (array_agg(close ORDER BY ts DESC))[1] AS close,
                SUM(vol_contract) AS vol_contract,
                SUM(vol_base) AS vol_base,
                SUM(vol_quote) AS vol_quote,
                COUNT(1) AS minute_rows
            FROM canonical_candles
            WHERE inst_id=$1
              AND bar='1m'
              AND source_primary='binance'
              AND ts >= $2
              AND ts < $3
            GROUP BY hour_ts
            HAVING COUNT(1) = 60
        )
        INSERT INTO canonical_candles
            (ts, inst_id, bar, open, high, low, close,
             vol_contract, vol_base, vol_quote, source_primary, quality_status, updated_at)
        SELECT
            hour_ts, $1, '1H', open, high, low, close,
            vol_contract, vol_base, vol_quote, 'binance', 'raw', NOW()
        FROM hourly
        ON CONFLICT (inst_id, bar, ts) DO UPDATE SET
            open=EXCLUDED.open,
            high=EXCLUDED.high,
            low=EXCLUDED.low,
            close=EXCLUDED.close,
            vol_contract=EXCLUDED.vol_contract,
            vol_base=EXCLUDED.vol_base,
            vol_quote=EXCLUDED.vol_quote,
            source_primary=EXCLUDED.source_primary,
            quality_status=EXCLUDED.quality_status,
            updated_at=NOW(),
            version=canonical_candles.version + 1
        WHERE {canonical_conflict_where()}
        RETURNING 1
        """,
        inst_id,
        start,
        end,
    )
    return len(rows)


async def run(args: argparse.Namespace) -> dict[str, Any]:
    dsn = args.dsn or os.environ.get("DATABASE_URL")
    if not dsn:
        raise SystemExit("Provide --dsn or DATABASE_URL")
    start = _utc_day(args.start)
    end = _utc_day(args.end)
    conn = await asyncpg.connect(dsn)
    try:
        before = await _counts(conn, args.inst)
        changed = 0 if args.dry_run else await _resample(conn, args.inst, start, end)
        after = await _counts(conn, args.inst)
    finally:
        await conn.close()
    return {
        "inst_id": args.inst,
        "source_primary": "binance",
        "from_bar": "1m",
        "to_bar": "1H",
        "start": start.isoformat(),
        "end_exclusive": end.isoformat(),
        "dry_run": bool(args.dry_run),
        "changed_rows": changed,
        "before": before,
        "after": after,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resample Binance 1m canonical candles to 1H.")
    parser.add_argument("--inst", default="BTC-USDT-SWAP")
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default="2026-05-01", help="Exclusive end date in YYYY-MM-DD")
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    report = asyncio.run(run(parse_args(argv or sys.argv[1:])))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
