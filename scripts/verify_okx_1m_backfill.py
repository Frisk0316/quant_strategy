"""Fail closed unless requested-window OKX 1m coverage and alignment are at least 95%."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
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


def _parse_date(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected YYYY-MM-DD") from exc


async def _connect(dsn: str):
    import asyncpg

    return await asyncpg.connect(dsn, server_settings={"default_transaction_read_only": "on"})


def build_verification(result: Any, start: datetime, end: datetime) -> dict:
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
        "window": {
            "start": start.date().isoformat(),
            "end_exclusive": end.date().isoformat(),
        },
        "thresholds": {
            "okx_coverage_ratio": thresholds.min_coverage,
            "alignment_ratio": thresholds.min_alignment,
        },
        "symbols": symbols,
        "probe_reason": check.reason,
    }


def _raw_gap_ranges(
    rows: Sequence[Any],
    start: datetime,
    end: datetime,
) -> dict[str, list[dict[str, int | str]]]:
    counts = {
        (str(row["inst_id"]), row["day"]): int(row["row_count"] or 0)
        for row in rows
    }
    gaps: dict[str, list[dict[str, int | str]]] = {
        symbol: [] for symbol in XVENUE_SYMBOLS
    }
    for symbol in XVENUE_SYMBOLS:
        day = start.date()
        while day < end.date():
            observed = counts.get((symbol, day), 0)
            missing = max(0, 1440 - observed)
            if missing:
                if gaps[symbol] and gaps[symbol][-1]["end_exclusive"] == day.isoformat():
                    gap = gaps[symbol][-1]
                    gap["end_exclusive"] = (day + timedelta(days=1)).isoformat()
                    gap["expected_rows"] += 1440
                    gap["observed_rows"] += observed
                    gap["missing_rows"] += missing
                else:
                    gaps[symbol].append(
                        {
                            "start": day.isoformat(),
                            "end_exclusive": (day + timedelta(days=1)).isoformat(),
                            "expected_rows": 1440,
                            "observed_rows": observed,
                            "missing_rows": missing,
                        }
                    )
            day += timedelta(days=1)
    return gaps


async def _fetch_integrity(
    conn: Any,
    start: datetime,
    end: datetime,
) -> dict[str, dict[str, Any]]:
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
        start,
        end,
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
        start,
        end,
    )
    raw_daily = await conn.fetch(
        """
        SELECT inst_id, date_trunc('day', ts)::date AS day, COUNT(*)::bigint AS row_count
        FROM raw_candles
        WHERE source = 'okx'
          AND is_closed
          AND inst_id = ANY($1::text[])
          AND bar = '1m'
          AND ts >= $2 AND ts < $3
        GROUP BY inst_id, date_trunc('day', ts)::date
        ORDER BY inst_id, day
        """,
        list(XVENUE_SYMBOLS),
        start,
        end,
    )
    resolved_by_symbol = {str(row["inst_id"]): int(row["rows"] or 0) for row in resolved}
    joined_by_symbol = {str(row["inst_id"]): row for row in rows}
    gap_ranges = _raw_gap_ranges(raw_daily, start, end)
    return {
        symbol: {
            "raw_rows": int((joined_by_symbol.get(symbol) or {}).get("raw_rows") or 0),
            "venue_rows": int((joined_by_symbol.get(symbol) or {}).get("venue_rows") or 0),
            "mismatch_rows": int(
                (joined_by_symbol.get(symbol) or {}).get("mismatch_rows") or 0
            ),
            "resolved_okx_rows": resolved_by_symbol.get(symbol, 0),
            "raw_gap_ranges": gap_ranges[symbol],
            "raw_missing_rows": sum(gap["missing_rows"] for gap in gap_ranges[symbol]),
        }
        for symbol in XVENUE_SYMBOLS
    }


async def verify(
    dsn: str,
    start: datetime | None = None,
    end: datetime | None = None,
) -> dict:
    start = start or _utc(START)
    end = end or _utc(END_EXCLUSIVE)
    conn = await _connect(dsn)
    try:
        result = await probe_xvenue(
            conn,
            start=start,
            end=end,
            thresholds=VenueThresholds(),
        )
        report = build_verification(result, start, end)
        integrity = await _fetch_integrity(conn, start, end)
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
    parser.add_argument("--start", type=_parse_date, default=_utc(START))
    parser.add_argument("--end", type=_parse_date, default=_utc(END_EXCLUSIVE))
    args = parser.parse_args(argv)
    if args.start >= args.end:
        parser.error("--start must be earlier than --end")
    dsn = resolve_dsn(args.dsn)
    if not dsn:
        print("FAIL: no DSN; OKX coverage was not verified", file=sys.stderr)
        return 2
    try:
        report = asyncio.run(verify(dsn, args.start, args.end))
    except Exception as exc:
        print(f"FAIL: OKX coverage probe failed closed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
