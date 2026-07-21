"""Audit DB history coverage and rank plausible backfill ROI without network access."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts._db_writer import resolve_dsn
from scripts.market_data.ingest import DEFAULT_STARTS

YEAR_SECONDS = 365.2425 * 86_400
FIXED_FREQUENCIES = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "30m": 1_800,
    "hourly": 3_600,
    "1h": 3_600,
    "daily": 86_400,
    "1d": 86_400,
}

BACKFILL_PRIORITIES = [
    {
        "priority": "P1",
        "target": "OKX BTC-USDT-SWAP and ETH-USDT-SWAP 1m",
        "unblocks": "H-010 / F-XVENUE-LEADLAG",
        "reason": "Required venue-native leg; I19 forbids Binance substitution.",
    },
    {
        "priority": "P2",
        "target": "Binance/Deribit BTC and ETH 1m plus funding before 2024",
        "unblocks": "long-window F-XVENUE-LEADLAG and F-XVENUE-FUNDING-SPREAD checks",
        "reason": "Adds stress regimes and extends common cross-venue history.",
    },
    {
        "priority": "P3",
        "target": "stablecoin supply and Coinbase premium external features",
        "unblocks": (
            "task key H-016/H-017; registry maps stablecoin to "
            "H-017/F-STABLECOIN-LIQUIDITY and Coinbase premium to "
            "H-018/F-COINBASE-PREMIUM"
        ),
        "reason": "The task IDs conflict with the current registry; H-016 is XS illiquidity.",
    },
]

CANONICAL_SQL = """
SELECT
    c.inst_id,
    c.source_primary,
    c.bar,
    b.interval_ms,
    MIN(c.ts) AS earliest_ts,
    MAX(c.ts) AS latest_ts,
    COUNT(*)::bigint AS row_count
FROM canonical_candles c
JOIN bar_intervals b ON b.bar = c.bar
GROUP BY c.inst_id, c.source_primary, c.bar, b.interval_ms
ORDER BY c.inst_id, c.source_primary, c.bar
"""

EXTERNAL_SQL = """
SELECT
    d.dataset_id,
    d.provider,
    d.frequency,
    MIN(o.observed_at) AS earliest_ts,
    MAX(o.observed_at) AS latest_ts,
    COUNT(o.observed_at)::bigint AS row_count
FROM external_datasets d
LEFT JOIN external_observations o ON o.dataset_id = d.dataset_id
GROUP BY d.dataset_id, d.provider, d.frequency
ORDER BY d.dataset_id
"""


def _utc(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat().replace("+00:00", "Z") if value else None


def _gap(first: datetime | None, last: datetime | None, rows: int, seconds: float | None) -> dict:
    if first is None or last is None or not seconds:
        return {
            "expected_rows": None,
            "missing_rows": None,
            "coverage_ratio": None,
            "status": "SKIP_UNCONFIRMED_CADENCE",
        }
    expected = int((last - first).total_seconds() // seconds) + 1
    missing = max(0, expected - rows)
    return {
        "expected_rows": expected,
        "missing_rows": missing,
        "coverage_ratio": round(rows / expected, 6) if expected else None,
        "status": "MEASURED",
    }


def _history_fields(kind: str, source: str, first: datetime | None) -> dict:
    configured = DEFAULT_STARTS.get(source, {}).get("klines_1m") if kind == "canonical" else None
    plausible = _utc(configured)
    gap_years = None
    if first is not None and plausible is not None:
        gap_years = round(max(0.0, (first - plausible).total_seconds() / YEAR_SECONDS), 6)
    return {
        "plausible_available_start": _iso(plausible),
        "max_available_history_status": "UNCONFIRMED",
        "availability_basis": (
            "scripts/market_data/ingest.py DEFAULT_STARTS "
            "(not a venue maximum; listing time not applied)"
            if plausible
            else "no repository-authoritative maximum"
        ),
        "history_gap_years": gap_years,
    }


def build_report(canonical_records: Sequence[Any], external_records: Sequence[Any]) -> dict:
    canonical: list[dict] = []
    for record in canonical_records:
        row = dict(record)
        first, last = _utc(row["earliest_ts"]), _utc(row["latest_ts"])
        source = str(row["source_primary"])
        item = {
            "dataset_key": f"canonical:{row['inst_id']}:{source}:{row['bar']}",
            "kind": "canonical_candles",
            "inst_id": str(row["inst_id"]),
            "source_primary": source,
            "bar": str(row["bar"]),
            "earliest_ts": _iso(first),
            "latest_ts": _iso(last),
            "row_count": int(row["row_count"] or 0),
        }
        item["gap_vs_expected"] = _gap(
            first,
            last,
            item["row_count"],
            float(row["interval_ms"]) / 1_000,
        )
        item.update(_history_fields("canonical", source, first))
        canonical.append(item)

    external: list[dict] = []
    for record in external_records:
        row = dict(record)
        first, last = _utc(row["earliest_ts"]), _utc(row["latest_ts"])
        frequency = str(row["frequency"])
        item = {
            "dataset_key": f"external:{row['dataset_id']}",
            "kind": "external_observations",
            "dataset_id": str(row["dataset_id"]),
            "provider": str(row["provider"]),
            "frequency": frequency,
            "earliest_ts": _iso(first),
            "latest_ts": _iso(last),
            "row_count": int(row["row_count"] or 0),
        }
        item["gap_vs_expected"] = _gap(
            first,
            last,
            item["row_count"],
            FIXED_FREQUENCIES.get(frequency.lower()),
        )
        item.update(_history_fields("external", item["provider"], first))
        external.append(item)

    ranked = sorted(
        [*canonical, *external],
        key=lambda row: (
            row["history_gap_years"] is not None,
            row["history_gap_years"] or 0.0,
            row["dataset_key"],
        ),
        reverse=True,
    )
    return {
        "status": "COMPLETE",
        "generated_at": _iso(datetime.now(tz=timezone.utc)),
        "history_gap_definition": (
            "held earliest timestamp minus the repository's plausible venue start; "
            "all venue starts are UNCONFIRMED and late listings may overstate the gap"
        ),
        "canonical_candles": canonical,
        "external_observations": external,
        "ranked_history_gaps": [
            {
                "rank": rank,
                "dataset_key": row["dataset_key"],
                "history_gap_years": row["history_gap_years"],
                "max_available_history_status": row["max_available_history_status"],
            }
            for rank, row in enumerate(ranked, 1)
        ],
        "backfill_priorities": BACKFILL_PRIORITIES,
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# Data-history coverage audit",
        "",
        f"Status: **{report['status']}**",
        "",
    ]
    if report.get("reason"):
        lines += [str(report["reason"]), ""]
    lines += [
        "`history_gap_years` uses repository-configured venue starts as conservative ROI inputs;",
        "every venue maximum is **UNCONFIRMED**. Unknown/event/business-day cadences keep gap",
        "fields null instead of manufacturing expected rows.",
        "Incomplete listing timestamps can overstate late-listed instruments; P1-P3 are the",
        "actionable priority order.",
        "",
        "## Ranked history gaps",
        "",
        "| Rank | Dataset | Earliest | Latest | Rows | Gap vs expected | History gap years | Max history |",
        "| ---: | --- | --- | --- | ---: | --- | ---: | --- |",
    ]
    by_key = {
        row["dataset_key"]: row
        for row in [*report.get("canonical_candles", []), *report.get("external_observations", [])]
    }
    for ranked in report.get("ranked_history_gaps", []):
        row = by_key[ranked["dataset_key"]]
        gap = row["gap_vs_expected"]
        gap_text = (
            f"{gap['missing_rows']}/{gap['expected_rows']} ({gap['coverage_ratio']:.4f})"
            if gap["expected_rows"] is not None
            else "SKIP"
        )
        history_gap = row["history_gap_years"]
        lines.append(
            f"| {ranked['rank']} | `{row['dataset_key']}` | {row['earliest_ts'] or 'n/a'} | "
            f"{row['latest_ts'] or 'n/a'} | {row['row_count']} | {gap_text} | "
            f"{history_gap:.4f} | UNCONFIRMED |"
            if history_gap is not None
            else f"| {ranked['rank']} | `{row['dataset_key']}` | {row['earliest_ts'] or 'n/a'} | "
            f"{row['latest_ts'] or 'n/a'} | {row['row_count']} | {gap_text} | n/a | UNCONFIRMED |"
        )

    lines += ["", "## Prioritized backfills", ""]
    for item in report["backfill_priorities"]:
        lines += [
            f"### {item['priority']} — {item['target']}",
            "",
            f"Unblocks: {item['unblocks']}",
            "",
            item["reason"],
            "",
        ]
    return "\n".join(lines).rstrip() + "\n"


async def _connect(dsn: str):
    import asyncpg

    return await asyncpg.connect(dsn, server_settings={"default_transaction_read_only": "on"})


async def audit(dsn: str) -> dict:
    conn = await _connect(dsn)
    try:
        return build_report(await conn.fetch(CANONICAL_SQL), await conn.fetch(EXTERNAL_SQL))
    finally:
        await conn.close()


def _write_outputs(report: dict, json_out: Path, markdown_out: Path) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_out.write_text(render_markdown(report), encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", help="Override DATABASE_URL/config DSN")
    parser.add_argument("--json-out", type=Path, default=Path("history_coverage_audit.json"))
    parser.add_argument("--markdown-out", type=Path, default=Path("history_coverage_audit.md"))
    args = parser.parse_args(argv)

    dsn = resolve_dsn(args.dsn)
    if not dsn:
        report = {
            "status": "SKIP",
            "reason": "No DSN; audit made no DB or network request.",
            "canonical_candles": [],
            "external_observations": [],
            "ranked_history_gaps": [],
            "backfill_priorities": BACKFILL_PRIORITIES,
        }
        _write_outputs(report, args.json_out, args.markdown_out)
        print("SKIP: no DSN; wrote audit outputs without querying the DB")
        return 0

    try:
        report = asyncio.run(audit(dsn))
    except Exception as exc:
        report = {
            "status": "FAIL",
            "reason": f"DB audit failed closed: {exc}",
            "canonical_candles": [],
            "external_observations": [],
            "ranked_history_gaps": [],
            "backfill_priorities": BACKFILL_PRIORITIES,
        }
        _write_outputs(report, args.json_out, args.markdown_out)
        print(report["reason"], file=sys.stderr)
        return 1

    _write_outputs(report, args.json_out, args.markdown_out)
    print(
        f"COMPLETE: {len(report['canonical_candles'])} canonical and "
        f"{len(report['external_observations'])} external datasets"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
