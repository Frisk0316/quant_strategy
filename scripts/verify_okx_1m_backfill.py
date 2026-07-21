"""Fail closed unless frozen-window OKX 1m coverage and alignment are at least 95%."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtesting.pipeline_stage2_registry import (
    END_EXCLUSIVE,
    START,
    XVENUE_SYMBOLS,
    VenueThresholds,
    _utc,
    probe_xvenue,
)
from scripts._db_writer import resolve_dsn


async def _connect(dsn: str):
    import asyncpg

    return await asyncpg.connect(dsn, server_settings={"default_transaction_read_only": "on"})


def build_verification(result: Any) -> dict:
    thresholds = VenueThresholds()
    check = result.checks[0]
    coverage = check.details.get("venue_coverage") or {}
    symbols: dict[str, dict] = {}
    passed = True
    for symbol in XVENUE_SYMBOLS:
        row = coverage.get(symbol) or {}
        okx = row.get("okx") or {}
        okx_ratio = float(okx.get("coverage_ratio") or 0.0)
        alignment_ratio = float(row.get("alignment_ratio") or 0.0)
        symbol_passed = (
            okx_ratio >= thresholds.min_coverage
            and alignment_ratio >= thresholds.min_alignment
        )
        passed = passed and symbol_passed
        symbols[symbol] = {
            "okx_rows": int(okx.get("row_count") or 0),
            "okx_coverage_ratio": okx_ratio,
            "aligned_rows": int(row.get("aligned_rows") or 0),
            "alignment_ratio": alignment_ratio,
            "passed": symbol_passed,
        }
    return {
        "status": "PASS" if passed else "FAIL",
        "window": {"start": START, "end_exclusive": END_EXCLUSIVE},
        "thresholds": {
            "okx_coverage_ratio": thresholds.min_coverage,
            "alignment_ratio": thresholds.min_alignment,
        },
        "symbols": symbols,
        "probe_reason": check.reason,
    }


async def _fetch_integrity(conn: Any) -> dict[str, dict[str, int]]:
    rows = await conn.fetch(
        """
        WITH raw AS (
            SELECT inst_id, bar, ts, open, high, low, close,
                   vol_contract, vol_base, vol_quote
            FROM raw_candles
            WHERE source = 'okx'
              AND is_closed
              AND inst_id = ANY($1::text[])
              AND bar = '1m'
              AND ts >= $2 AND ts < $3
        ), venue AS (
            SELECT inst_id, bar, ts, open, high, low, close,
                   vol_contract, vol_base, vol_quote
            FROM venue_canonical_candles
            WHERE source_primary = 'okx'
              AND inst_id = ANY($1::text[])
              AND bar = '1m'
              AND ts >= $2 AND ts < $3
        )
        SELECT
            COALESCE(raw.inst_id, venue.inst_id) AS inst_id,
            COUNT(raw.ts)::bigint AS raw_rows,
            COUNT(venue.ts)::bigint AS venue_rows,
            COUNT(*) FILTER (
                WHERE raw.ts IS NULL
                   OR venue.ts IS NULL
                   OR ROW(venue.open, venue.high, venue.low, venue.close,
                          venue.vol_contract, venue.vol_base, venue.vol_quote)
                      IS DISTINCT FROM
                      ROW(raw.open, raw.high, raw.low, raw.close,
                          raw.vol_contract, raw.vol_base, raw.vol_quote)
            )::bigint AS mismatch_rows
        FROM raw
        FULL OUTER JOIN venue USING (inst_id, bar, ts)
        GROUP BY COALESCE(raw.inst_id, venue.inst_id)
        ORDER BY inst_id
        """,
        list(XVENUE_SYMBOLS),
        _utc(START),
        _utc(END_EXCLUSIVE),
    )
    resolved = await conn.fetch(
        """
        SELECT inst_id, COUNT(*)::bigint AS rows
        FROM canonical_candles
        WHERE source_primary = 'okx'
          AND inst_id = ANY($1::text[])
          AND bar = '1m'
          AND ts >= $2 AND ts < $3
        GROUP BY inst_id
        """,
        list(XVENUE_SYMBOLS),
        _utc(START),
        _utc(END_EXCLUSIVE),
    )
    resolved_by_symbol = {str(row["inst_id"]): int(row["rows"] or 0) for row in resolved}
    return {
        str(row["inst_id"]): {
            "raw_rows": int(row["raw_rows"] or 0),
            "venue_rows": int(row["venue_rows"] or 0),
            "mismatch_rows": int(row["mismatch_rows"] or 0),
            "resolved_okx_rows": resolved_by_symbol.get(str(row["inst_id"]), 0),
        }
        for row in rows
    }


async def verify(dsn: str) -> dict:
    conn = await _connect(dsn)
    try:
        result = await probe_xvenue(
            conn,
            start=_utc(START),
            end=_utc(END_EXCLUSIVE),
            thresholds=VenueThresholds(),
        )
        report = build_verification(result)
        integrity = await _fetch_integrity(conn)
        for symbol in XVENUE_SYMBOLS:
            row = integrity.get(symbol) or {
                "raw_rows": 0,
                "venue_rows": 0,
                "mismatch_rows": 0,
                "resolved_okx_rows": 0,
            }
            parity_passed = (
                row["raw_rows"] > 0
                and row["raw_rows"] == row["venue_rows"]
                and row["mismatch_rows"] == 0
                and row["resolved_okx_rows"] == 0
            )
            report["symbols"][symbol].update(row)
            report["symbols"][symbol]["raw_parity_passed"] = parity_passed
            report["symbols"][symbol]["passed"] &= parity_passed
        report["status"] = (
            "PASS" if all(row["passed"] for row in report["symbols"].values()) else "FAIL"
        )
        return report
    finally:
        await conn.close()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", help="Override DATABASE_URL/config DSN")
    args = parser.parse_args(argv)
    dsn = resolve_dsn(args.dsn)
    if not dsn:
        print("FAIL: no DSN; OKX coverage was not verified", file=sys.stderr)
        return 2
    try:
        report = asyncio.run(verify(dsn))
    except Exception as exc:
        print(f"FAIL: OKX coverage probe failed closed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
