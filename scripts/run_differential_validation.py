"""Run differential backtest validation for a saved artifact run."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from backtesting.differential_validation import (
    ENGINE_NAMES,
    run_differential_validation,
    run_strategy_differential_validation,
)
from backtesting.artifact_rows import resolve_artifact_child, validate_artifact_id


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a backtest run against public reference engines.")
    parser.add_argument("--run-id", default=None, help="Saved run ID under --results-dir")
    parser.add_argument("--strategy", default=None, help="Validate strategy evidence instead of a run-scoped artifact")
    parser.add_argument("--fixture-run-id", default=None, help="Fixture run ID used as strategy validation input")
    parser.add_argument("--results-dir", default="results", help="Directory containing saved backtest runs")
    parser.add_argument(
        "--engines",
        default="vectorbt,backtrader,nautilus",
        help="Comma-separated engines: vectorbt,backtrader,nautilus",
    )
    parser.add_argument("--validation-id", default=None, help="Optional stable validation ID")
    parser.add_argument("--output-dir", default=None, help="Override output directory")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    engines = [item.strip().lower() for item in args.engines.split(",") if item.strip()]
    unknown = sorted(set(engines) - ENGINE_NAMES)
    if unknown:
        print(f"ERROR: unsupported engine(s): {', '.join(unknown)}", file=sys.stderr)
        return 2

    if args.strategy:
        summary = run_strategy_differential_validation(
            results_dir=args.results_dir,
            strategy=args.strategy,
            engines=engines,
            fixture_run_id=args.fixture_run_id,
            output_dir=args.output_dir,
            validation_id=args.validation_id,
        )
    elif args.run_id:
        run_id = validate_artifact_id(args.run_id, "run_id")
        run_dir = resolve_artifact_child(args.results_dir, run_id, "run_id")
        summary = run_differential_validation(
            run_dir=run_dir,
            engines=engines,
            output_dir=args.output_dir,
            validation_id=args.validation_id,
        )
    else:
        print("ERROR: provide either --strategy or --run-id", file=sys.stderr)
        return 2
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 1 if summary.get("status") == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
