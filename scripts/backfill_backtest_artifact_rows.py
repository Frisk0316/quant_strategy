"""Backfill derived backtest_artifact_rows for saved backtest artifacts."""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from backtesting.artifact_rows import (  # noqa: E402
    ROW_INDEX_ARTIFACT_TYPES,
    build_artifact_row_records,
    normalized_records_hash,
    read_artifact_rows,
    resolve_artifact_child,
    resolve_artifact_path,
    upsert_artifact_rows,
    validate_artifact_id,
    validation_artifact_type,
)


ARTIFACT_FILES = {
    "price_series": "price_series.csv",
    "indicator_series": "indicator_series.csv",
    "equity": "equity_curve.csv",
    "returns": "returns.csv",
    "drawdown": "drawdown.csv",
    "fills": "fills.csv",
    "trades": "trades.csv",
    "orders": "orders.csv",
    "signals": "signals.csv",
    "execution_markers": "execution_markers.csv",
    "risk_events": "risk_events.csv",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", default=os.environ.get("DATABASE_URL"), help="Postgres DSN; defaults to DATABASE_URL")
    parser.add_argument("--results-dir", default="results", help="Filesystem artifact root")
    parser.add_argument("--dry-run", action="store_true", help="Report derived row counts without writing")
    parser.add_argument("--run-id", action="append", default=[], help="Run ID to backfill; may be repeated")
    parser.add_argument("--all", action="store_true", help="Backfill all discovered runs")
    parser.add_argument("--artifact-type", action="append", default=[], help="Artifact type to backfill; may be repeated")
    parser.add_argument("--limit-runs", type=int, default=0, help="Limit discovered runs for smoke testing")
    parser.add_argument("--verify", action="store_true", help="Compare row counts and normalized row hashes after write")
    parser.add_argument("--include-validation", action="store_true", help="Also index run-scoped differential validation CSV artifacts")
    return parser.parse_args(argv)


async def main_async(args: argparse.Namespace) -> int:
    results_dir = Path(args.results_dir)
    explicit_run_ids = [validate_artifact_id(run_id, "run_id") for run_id in args.run_id]
    artifact_types = set(args.artifact_type or sorted(ROW_INDEX_ARTIFACT_TYPES))
    unknown = sorted(artifact_types - ROW_INDEX_ARTIFACT_TYPES)
    if unknown:
        raise SystemExit(f"Unsupported row-index artifact type(s): {', '.join(unknown)}")
    if not args.dsn and not args.dry_run:
        raise SystemExit("DATABASE_URL or --dsn is required unless --dry-run is used")

    conn = await _connect(args.dsn) if args.dsn else None
    try:
        run_ids = await _discover_run_ids(
            conn=conn,
            results_dir=results_dir,
            explicit=explicit_run_ids,
            include_all=args.all,
            limit=args.limit_runs,
        )
        if not run_ids:
            raise SystemExit("No runs selected; pass --run-id or --all")

        summary = {
            "dry_run": bool(args.dry_run),
            "verify": bool(args.verify),
            "runs": [],
            "run_count": 0,
            "artifact_count": 0,
            "row_count": 0,
            "verification_failures": [],
        }
        for run_id in run_ids:
            artifacts = await _load_artifacts(conn, results_dir, run_id, artifact_types)
            if args.include_validation:
                artifacts.update(_load_validation_artifacts(results_dir, run_id))
            counts = {
                artifact_type: len(build_artifact_row_records(run_id, artifact_type, payload))
                for artifact_type, payload in artifacts.items()
            }
            if not args.dry_run and artifacts:
                await upsert_artifact_rows(
                    dsn=args.dsn,
                    run_id=run_id,
                    artifacts=artifacts,
                    artifact_types=set(artifacts),
                )
            verification = {}
            if args.verify and args.dsn:
                verification = await _verify_artifacts(args.dsn, run_id, artifacts)
                for artifact_type, result in verification.items():
                    if not result["ok"]:
                        summary["verification_failures"].append(
                            {"run_id": run_id, "artifact_type": artifact_type, **result}
                        )
            run_summary = {
                "run_id": run_id,
                "artifacts": sorted(artifacts),
                "row_counts": counts,
                "verification": verification,
            }
            summary["runs"].append(run_summary)
            summary["run_count"] += 1
            summary["artifact_count"] += len(artifacts)
            summary["row_count"] += sum(counts.values())

        print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
        return 1 if summary["verification_failures"] else 0
    finally:
        if conn is not None:
            await conn.close()


async def _connect(dsn: str):
    import asyncpg

    return await asyncpg.connect(dsn)


async def _discover_run_ids(
    *,
    conn: Any | None,
    results_dir: Path,
    explicit: list[str],
    include_all: bool,
    limit: int,
) -> list[str]:
    if explicit:
        run_ids = list(dict.fromkeys(validate_artifact_id(value, "run_id") for value in explicit))
    elif include_all:
        run_ids = []
        if conn is not None:
            rows = await conn.fetch(
                """
                SELECT run_id
                FROM backtest_runs
                ORDER BY created_at DESC
                """
            )
            run_ids.extend(validate_artifact_id(str(row["run_id"]), "run_id") for row in rows)
        if results_dir.exists():
            for path in sorted(results_dir.iterdir(), reverse=True):
                if path.is_dir() and (path / "result.json").exists() and path.name not in run_ids:
                    run_ids.append(validate_artifact_id(path.name, "run_id"))
    else:
        return []
    return run_ids[:limit] if limit > 0 else run_ids


async def _load_artifacts(
    conn: Any | None,
    results_dir: Path,
    run_id: str,
    artifact_types: set[str],
) -> dict[str, list[dict[str, Any]]]:
    run_id = validate_artifact_id(run_id, "run_id")
    artifacts: dict[str, list[dict[str, Any]]] = {}
    if conn is not None:
        rows = await conn.fetch(
            """
            SELECT artifact_type, payload
            FROM backtest_artifacts
            WHERE run_id = $1 AND artifact_type = ANY($2::text[])
            """,
            run_id,
            sorted(artifact_types),
        )
        for row in rows:
            payload = _decode_payload(row["payload"])
            if isinstance(payload, list):
                artifacts[str(row["artifact_type"])] = [dict(item) for item in payload if isinstance(item, dict)]

    run_dir = resolve_artifact_child(results_dir, run_id, "run_id")
    for artifact_type in sorted(artifact_types - set(artifacts)):
        filename = ARTIFACT_FILES.get(artifact_type)
        if not filename:
            continue
        path = run_dir / filename
        if path.exists():
            artifacts[artifact_type] = _read_csv_records(path)
    return artifacts


async def _verify_artifacts(
    dsn: str,
    run_id: str,
    artifacts: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for artifact_type, payload in artifacts.items():
        rows = await read_artifact_rows(dsn=dsn, run_id=run_id, artifact_type=artifact_type)
        source_hash = normalized_records_hash(payload)
        row_hash = normalized_records_hash(rows)
        results[artifact_type] = {
            "ok": len(rows) == len(payload) and row_hash == source_hash,
            "source_count": len(payload),
            "row_count": len(rows),
            "source_hash": source_hash,
            "row_hash": row_hash,
        }
    return results


def _decode_payload(value: Any) -> Any:
    if isinstance(value, str):
        return json.loads(value)
    return value


def _read_csv_records(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _load_validation_artifacts(results_dir: Path, run_id: str) -> dict[str, list[dict[str, Any]]]:
    validation_root = resolve_artifact_path(
        results_dir,
        (run_id, "run_id"),
        ("validation", "artifact_namespace"),
    )
    artifacts: dict[str, list[dict[str, Any]]] = {}
    if not validation_root.is_dir():
        return artifacts
    for candidate in sorted(path for path in validation_root.iterdir() if path.is_dir()):
        try:
            validation_dir = resolve_artifact_path(
                results_dir,
                (run_id, "run_id"),
                ("validation", "artifact_namespace"),
                (candidate.name, "validation_id"),
            )
        except ValueError:
            continue
        for candidate_path in sorted(validation_dir.glob("*.csv")):
            try:
                path = resolve_artifact_path(
                    results_dir,
                    (run_id, "run_id"),
                    ("validation", "artifact_namespace"),
                    (validation_dir.name, "validation_id"),
                    (candidate_path.name, "artifact_name"),
                )
            except ValueError:
                continue
            artifacts[validation_artifact_type(validation_dir.name, path.name)] = _read_csv_records(path)
    return artifacts


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(main_async(parse_args(argv)))


if __name__ == "__main__":
    raise SystemExit(main())
