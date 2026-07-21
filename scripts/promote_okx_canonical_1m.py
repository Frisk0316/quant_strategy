"""Promote an authorized window of OKX BTC/ETH 1m raw rows."""
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


def _parse_date(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected YYYY-MM-DD") from exc


async def apply_schema(dsn: str) -> None:
    import asyncpg

    conn = await asyncpg.connect(dsn)
    try:
        await _apply_migration(conn, MIGRATION)
    finally:
        await conn.close()


async def _promote_on_connection(
    conn: object,
    start: datetime,
    end: datetime,
) -> tuple[dict, dict]:
    preflight_rows = await conn.fetch(
        """
        WITH raw_stats AS (
            SELECT inst_id, COUNT(*)::bigint AS row_count, MIN(ts) AS first_ts,
                   MAX(ts) AS last_ts,
                   SUM(hashtextextended(ts::text, 0)::numeric) AS hash_0,
                   SUM(hashtextextended(ts::text, 8675309)::numeric) AS hash_1
            FROM raw_candles
            WHERE source = $1
              AND inst_id = ANY($2::text[])
              AND bar = $3
              AND is_closed
              AND ts >= $4 AND ts < $5
            GROUP BY inst_id
        ), resolved_stats AS (
            SELECT inst_id, COUNT(*)::bigint AS row_count, MIN(ts) AS first_ts,
                   MAX(ts) AS last_ts,
                   SUM(hashtextextended(ts::text, 0)::numeric) AS hash_0,
                   SUM(hashtextextended(ts::text, 8675309)::numeric) AS hash_1
            FROM canonical_candles
            WHERE inst_id = ANY($2::text[])
              AND bar = $3
              AND ts >= $4 AND ts < $5
              AND (
                  quality_status NOT IN ('raw', 'suspect')
                  OR (quality_status = 'raw' AND source_primary IN ('manual', 'binance'))
              )
            GROUP BY inst_id
        )
        SELECT r.inst_id, r.row_count AS raw_rows,
               ROW(r.row_count, r.first_ts, r.last_ts, r.hash_0, r.hash_1)
               IS DISTINCT FROM
               ROW(c.row_count, c.first_ts, c.last_ts, c.hash_0, c.hash_1)
               AS resolved_guard_mismatch
        FROM raw_stats r
        LEFT JOIN resolved_stats c USING (inst_id)
        ORDER BY r.inst_id
        """,
        SOURCE,
        list(SYMBOLS),
        BAR,
        start,
        end,
    )
    preflight = {
        symbol: {"raw_rows": 0, "resolved_guard_mismatch": False}
        for symbol in SYMBOLS
    }
    for row in preflight_rows:
        preflight[str(row["inst_id"])] = {
            "raw_rows": int(row["raw_rows"] or 0),
            "resolved_guard_mismatch": bool(row["resolved_guard_mismatch"]),
        }
    unsafe = [
        symbol for symbol, row in preflight.items() if row["resolved_guard_mismatch"]
    ]
    if unsafe:
        raise RuntimeError(f"resolved canonical preflight failed: {unsafe}")

    scoped_store = CandleStore(conn)
    rows = {
        symbol: await scoped_store.canonicalize_from_raw(
            SOURCE,
            symbol,
            BAR,
            start=start,
            end=end,
        )
        for symbol in SYMBOLS
    }
    resolved_changes = {
        symbol: int(row["promoted"])
        for symbol, row in rows.items()
        if int(row["promoted"])
    }
    if resolved_changes:
        raise RuntimeError(
            f"resolved canonical mutation detected; transaction rolled back: {resolved_changes}"
        )
    return rows, preflight


async def promote(
    dsn: str,
    start: datetime = START,
    end: datetime = END_EXCLUSIVE,
) -> dict:
    store = await CandleStore.from_dsn(dsn, min_size=1, max_size=2)
    try:
        async with store._pool.acquire() as conn:
            async with conn.transaction():
                rows, preflight = await _promote_on_connection(conn, start, end)
    finally:
        await store.close()
    return {
        "status": "COMPLETE",
        "layer": "venue_canonical_candles",
        "source": SOURCE,
        "bar": BAR,
        "window": {"start": start.isoformat(), "end_exclusive": end.isoformat()},
        "resolved_preflight": preflight,
        "symbols": rows,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", help="Override DATABASE_URL/config DSN")
    parser.add_argument("--start", type=_parse_date, default=START)
    parser.add_argument("--end", type=_parse_date, default=END_EXCLUSIVE)
    args = parser.parse_args(argv)
    if args.start >= args.end:
        parser.error("--start must be earlier than --end")
    dsn = resolve_dsn(args.dsn)
    if not dsn:
        parser.error("no DSN available")
    try:
        asyncio.run(apply_schema(dsn))
        report = asyncio.run(promote(dsn, args.start, args.end))
    except Exception as exc:
        print(f"FAIL: OKX canonical promotion failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
