"""Gate differential-validation evidence for real-data source provenance."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from backtesting.differential_validation import ENGINE_NAMES, run_differential_validation


def _status(value: Any) -> str:
    if not isinstance(value, dict):
        return "MISSING"
    return str(value.get("status") or "MISSING").upper()


def evaluate_source_provenance(
    summary: dict[str, Any],
    *,
    validation_result_path: str | Path | None = None,
) -> dict[str, Any]:
    source = summary.get("source_data_validation")
    source_data = source if isinstance(source, dict) else {}
    checks = source_data.get("checks") if isinstance(source_data.get("checks"), dict) else {}
    ct_val = checks.get("ct_val_provenance") if isinstance(checks.get("ct_val_provenance"), dict) else {}
    db_parity = checks.get("db_parity") if isinstance(checks.get("db_parity"), dict) else {}
    ohlcv_source = str(
        source_data.get("ohlcv_source_validation")
        or summary.get("ohlcv_source_validation")
        or "MISSING"
    )

    required_checks = {
        "source_data_validation": _status(source_data),
        "ct_val_provenance": _status(ct_val),
        "db_parity": _status(db_parity),
        "ohlcv_source_validation": ohlcv_source,
    }
    blocking_reasons: list[str] = []
    if required_checks["source_data_validation"] != "PASS":
        blocking_reasons.append("source_data_validation_not_pass")
    if required_checks["ct_val_provenance"] != "PASS":
        blocking_reasons.append("ct_val_provenance_not_pass")
    if required_checks["db_parity"] != "PASS":
        blocking_reasons.append("db_parity_not_pass")
    if required_checks["ohlcv_source_validation"] != "db_parity_pass":
        blocking_reasons.append("ohlcv_source_validation_not_db_parity_pass")

    return {
        "status": "FAIL" if blocking_reasons else "PASS",
        "scope": "real_data_source_provenance",
        "validation_id": summary.get("validation_id", ""),
        "run_id": summary.get("run_id", ""),
        "strategy": summary.get("strategy", ""),
        "required_checks": required_checks,
        "blocking_reasons": blocking_reasons,
        "evidence": {
            "validation_result_path": str(validation_result_path or ""),
            "artifact_dir": str(summary.get("artifact_dir") or ""),
            "output_dir": str(summary.get("output_dir") or ""),
        },
        "source_data_validation": source_data,
        "limitations": [
            "Requires differential validation output with source_data_validation.",
            "Requires DB candle parity PASS; fixture artifact checks with DB parity SKIP do not qualify.",
            "Does not prove Nautilus full execution parity, PnL parity, or live-readiness.",
        ],
    }


def _load_validation_result(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _parse_engines(value: str) -> list[str]:
    engines = [item.strip().lower() for item in value.split(",") if item.strip()]
    unknown = sorted(set(engines) - ENGINE_NAMES)
    if unknown:
        raise ValueError(f"unsupported engine(s): {', '.join(unknown)}")
    return engines


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate that differential-validation evidence is DB-backed real-data provenance.",
    )
    parser.add_argument(
        "--validation-result",
        default=None,
        help="Existing validation_result.json to gate without re-running validation.",
    )
    parser.add_argument("--run-id", default=None, help="Saved run ID under --results-dir to validate first.")
    parser.add_argument("--results-dir", default="results", help="Directory containing saved backtest runs.")
    parser.add_argument(
        "--engines",
        default="vectorbt,backtrader,nautilus",
        help="Comma-separated engines used when --run-id triggers differential validation.",
    )
    parser.add_argument("--validation-id", default=None, help="Optional stable validation ID for --run-id mode.")
    parser.add_argument("--output-dir", default=None, help="Optional differential-validation output directory.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if bool(args.validation_result) == bool(args.run_id):
        print("ERROR: provide exactly one of --validation-result or --run-id", file=sys.stderr)
        return 2

    try:
        if args.validation_result:
            result_path = Path(args.validation_result)
            summary = _load_validation_result(result_path)
        else:
            engines = _parse_engines(args.engines)
            run_dir = Path(args.results_dir) / Path(args.run_id).name
            summary = run_differential_validation(
                run_dir=run_dir,
                engines=engines,
                output_dir=args.output_dir,
                validation_id=args.validation_id,
            )
            result_path = Path(str(summary.get("output_dir") or "")) / "validation_result.json"
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    report = evaluate_source_provenance(summary, validation_result_path=result_path)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
