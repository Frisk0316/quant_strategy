"""Offline signal-logic smoke for frozen Binance 1H engine fixtures."""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from backtesting.differential_validation import run_differential_validation


FIXTURES = {
    "ma_crossover": "engine_consistency_ma_crossover_btc_binance_1h",
    "ema_crossover": "engine_consistency_ema_crossover_btc_binance_1h",
    "macd_crossover": "engine_consistency_macd_crossover_btc_binance_1h",
}
ENGINES = ("vectorbt", "backtrader")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _csv_row_count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def _price_window(path: Path) -> dict[str, Any]:
    first = ""
    last = ""
    rows = 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            value = str(row.get("datetime") or row.get("ts") or "")
            first = first or value
            last = value
            rows += 1
    return {"start": first, "end": last, "price_rows": rows}


def _force_offline_env() -> None:
    os.environ["NUMBA_DISABLE_JIT"] = "1"
    os.environ.pop("DATABASE_URL", None)
    os.environ.pop("DIFF_VALIDATION_DB_DSN", None)
    os.environ["DIFF_VALIDATION_ENABLE_DB_PARITY"] = "0"


def _engine_signal_logic(summary: dict[str, Any], engine: str) -> dict[str, Any]:
    engine_payload = summary.get("engines", {}).get(engine, {})
    comparison = engine_payload.get("comparison") if isinstance(engine_payload, dict) else {}
    signal_logic = comparison.get("signal_logic") if isinstance(comparison, dict) else {}
    return signal_logic if isinstance(signal_logic, dict) else {}


def _assert_summary(strategy: str, summary: dict[str, Any], signal_count: int, min_signals: int) -> None:
    if signal_count < min_signals:
        raise AssertionError(f"{strategy}: expected at least {min_signals} signals, got {signal_count}")
    gate = summary.get("portable_validation_gate") if isinstance(summary.get("portable_validation_gate"), dict) else {}
    if gate.get("passed") is not True:
        raise AssertionError(f"{strategy}: portable_validation_gate.passed is not true")
    for engine in ENGINES:
        signal_logic = _engine_signal_logic(summary, engine)
        status = signal_logic.get("status")
        mismatches = int(signal_logic.get("actionable_mismatch_count", signal_logic.get("actionable", 1)) or 0)
        if status != "PASS" or mismatches != 0:
            raise AssertionError(
                f"{strategy}/{engine}: signal_logic={status}, actionable_mismatch_count={mismatches}"
            )


def run_smoke(fixture_root: Path, *, min_signals: int) -> dict[str, Any]:
    _force_offline_env()
    started = time.perf_counter()
    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="engine_consistency_smoke_") as tmp:
        tmp_root = Path(tmp)
        for strategy, run_id in FIXTURES.items():
            run_dir = fixture_root / run_id
            try:
                result = _read_json(run_dir / "result.json")
                window = _price_window(run_dir / "price_series.csv")
                signal_count = _csv_row_count(run_dir / "signals.csv")
                summary = run_differential_validation(
                    run_dir=run_dir,
                    engines=ENGINES,
                    output_dir=tmp_root / strategy,
                    validation_id="engine_consistency_smoke",
                )
                _assert_summary(strategy, summary, signal_count, min_signals)
                rows.append({
                    "strategy": strategy,
                    "run_id": run_id,
                    "status": "PASS",
                    "signal_count": signal_count,
                    "window": {
                        "start": result.get("start") or window["start"],
                        "end": result.get("end") or window["end"],
                        "price_rows": window["price_rows"],
                    },
                    "scope": "signal_logic_only_not_promotion_evidence",
                    "engines": list(ENGINES),
                })
            except Exception as exc:
                failures.append(f"{strategy}: {exc}")
                rows.append({
                    "strategy": strategy,
                    "run_id": run_id,
                    "status": "FAIL",
                    "reason": str(exc),
                })
    elapsed = time.perf_counter() - started
    return {
        "status": "FAIL" if failures else "PASS",
        "fixture_root": str(fixture_root),
        "engines": list(ENGINES),
        "offline": True,
        "elapsed_seconds": round(elapsed, 3),
        "scope": "signal-logic engine consistency only; not edge, promotion, or live-readiness evidence",
        "rows": rows,
        "failures": failures,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the offline engine-consistency smoke.")
    parser.add_argument(
        "--fixture-root",
        default=str(PROJECT_ROOT / "tests" / "fixtures" / "engine_consistency"),
        help="Directory containing frozen engine consistency fixture runs.",
    )
    parser.add_argument("--min-signals", type=int, default=3)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    report = run_smoke(Path(args.fixture_root), min_signals=args.min_signals)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
