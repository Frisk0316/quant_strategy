"""Create one dated portfolio snapshot from replay artifacts."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


MAX_EQUITY_POINTS = 400


def downsample(rows: list[dict[str, Any]], limit: int = MAX_EQUITY_POINTS):
    if len(rows) <= limit:
        return rows
    return [rows[round(index * (len(rows) - 1) / (limit - 1))] for index in range(limit)]


def _missing(path: Path) -> dict[str, Any]:
    return {"available": False, "reason": f"{path.name} not found"}


def _strategies(config_path: Path) -> list[str]:
    if not config_path.is_file():
        return []
    config = json.loads(config_path.read_text(encoding="utf-8"))
    cli_names = config.get("cli_args", {}).get("strategy", [])
    if isinstance(cli_names, str):
        return [cli_names]
    if isinstance(cli_names, list):
        return [str(name) for name in cli_names]
    configured = config.get("strategies", {})
    if isinstance(configured, dict):
        return [
            str(name)
            for name, values in configured.items()
            if isinstance(values, dict) and values.get("enabled") is True
        ]
    return []


def _equity(path: Path) -> list[dict[str, Any]] | dict[str, Any]:
    if not path.is_file():
        return _missing(path)
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"ts", "equity", "drawdown"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("equity_curve.csv must contain ts, equity, and drawdown")
        rows = [
            {
                "ts": row["ts"],
                "equity": float(row["equity"]),
                "drawdown": float(row["drawdown"]),
            }
            for row in reader
        ]
    return downsample(rows)


def build_snapshot(run_dir: Path, *, date: str | None = None) -> dict[str, Any]:
    metrics_path = run_dir / "metrics.json"
    if metrics_path.is_file():
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        if not isinstance(metrics, dict):
            raise ValueError("metrics.json must contain an object")
    else:
        metrics = _missing(metrics_path)
    return {
        "date": date or datetime.now().astimezone().date().isoformat(),
        "run_id": run_dir.name,
        "strategies": _strategies(run_dir / "config.json"),
        "metrics": metrics,
        "equity": _equity(run_dir / "equity_curve.csv"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def write_snapshot(
    run_dir: Path, out_dir: Path, *, date: str | None = None
) -> Path:
    snapshot = build_snapshot(run_dir, date=date)
    path = out_dir / "snapshots" / f"{snapshot['date']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=Path("."))
    parser.add_argument("--date")
    args = parser.parse_args(argv)
    path = write_snapshot(args.run_dir, args.out_dir, date=args.date)
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
