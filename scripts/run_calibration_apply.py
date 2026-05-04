"""Read shadow/demo calibration JSONL files and suggest backtest config updates.

Usage:
    python scripts/run_calibration_apply.py [--dir results/calibration] [--apply]

Reads all calib_*.jsonl files in --dir, aggregates fill rate, order latency,
cancel latency, and slippage, then prints suggested values for
config/risk.yaml backtest section. Pass --apply to write the values.

Suggested mappings:
  fill_rate                → queue_fill_fraction
  mean_order_latency_ms    → order_latency_ms
  p95_cancel_latency_ms    → cancel_latency_ms  (conservative: use P95, not mean)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _load_jsonl(path: Path) -> list[dict]:
    records: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


def _aggregate(records: list[dict]) -> dict:
    fill_latencies: list[float] = []
    slippages: list[float] = []
    cancel_latencies: list[float] = []
    n_submitted = 0
    n_filled = 0

    for rec in records:
        t = rec.get("type")
        if t == "submit":
            n_submitted += 1
        elif t == "fill" and rec.get("state") in ("filled", "partially_filled"):
            n_filled += 1
            if "latency_ms" in rec and float(rec["latency_ms"]) >= 0:
                fill_latencies.append(float(rec["latency_ms"]))
            if "slippage_bps" in rec:
                slippages.append(float(rec["slippage_bps"]))
        elif t == "cancel_ack" and "cancel_latency_ms" in rec:
            latency = float(rec["cancel_latency_ms"])
            if latency >= 0:
                cancel_latencies.append(latency)

    fill_rate = n_filled / n_submitted if n_submitted > 0 else 0.0
    return {
        "n_submitted": n_submitted,
        "n_filled": n_filled,
        "fill_rate": round(fill_rate, 4),
        "mean_order_latency_ms": _mean(fill_latencies),
        "p95_order_latency_ms": _percentile(fill_latencies, 95),
        "mean_cancel_latency_ms": _mean(cancel_latencies),
        "p95_cancel_latency_ms": _percentile(cancel_latencies, 95),
        "mean_slippage_bps": _mean(slippages),
        "p95_slippage_bps": _percentile(slippages, 95),
    }


def _suggest_config(stats: dict) -> dict:
    return {
        "queue_fill_fraction": round(min(max(stats["fill_rate"], 0.0), 1.0), 4),
        "order_latency_ms": max(0, int(round(stats["mean_order_latency_ms"]))),
        # Use P95 for cancel latency — conservative, avoids underestimating risk
        "cancel_latency_ms": max(0, int(round(stats["p95_cancel_latency_ms"]))),
    }


def _apply_to_risk_yaml(suggested: dict, risk_path: Path) -> None:
    with open(risk_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    if "backtest" not in raw:
        raw["backtest"] = {}
    raw["backtest"].update(suggested)
    with open(risk_path, "w", encoding="utf-8") as f:
        yaml.dump(raw, f, default_flow_style=False, allow_unicode=True)
    print(f"Updated {risk_path}")


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 1) if values else 0.0


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    sorted_v = sorted(values)
    idx = int(len(sorted_v) * pct / 100)
    return round(sorted_v[min(idx, len(sorted_v) - 1)], 1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply shadow/demo calibration data to backtest config"
    )
    parser.add_argument(
        "--dir",
        default=str(PROJECT_ROOT / "results" / "calibration"),
        help="Directory containing calib_*.jsonl files",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write suggested values to config/risk.yaml",
    )
    parser.add_argument(
        "--risk-yaml",
        default=str(PROJECT_ROOT / "config" / "risk.yaml"),
        help="Path to risk.yaml to update (only used with --apply)",
    )
    parser.add_argument(
        "--min-fills",
        type=int,
        default=10,
        help="Minimum fills required before suggesting a config update",
    )
    args = parser.parse_args()

    calib_dir = Path(args.dir)
    if not calib_dir.exists():
        print(f"Calibration directory not found: {calib_dir}")
        print("Run the engine in shadow or demo mode first to generate fill data.")
        sys.exit(1)

    jsonl_files = sorted(calib_dir.glob("calib_*.jsonl"))
    if not jsonl_files:
        print(f"No calib_*.jsonl files found in {calib_dir}")
        sys.exit(1)

    print(f"Loading {len(jsonl_files)} calibration file(s)...")
    all_records: list[dict] = []
    for path in jsonl_files:
        records = _load_jsonl(path)
        all_records.extend(records)
        print(f"  {path.name}: {len(records)} events")

    stats = _aggregate(all_records)

    print("\n=== Calibration Statistics ===")
    print(f"  Submitted orders    : {stats['n_submitted']}")
    print(f"  Filled orders       : {stats['n_filled']}")
    print(f"  Fill rate           : {stats['fill_rate']:.4f}  → queue_fill_fraction")
    print(f"  Mean order latency  : {stats['mean_order_latency_ms']:.1f} ms  → order_latency_ms")
    print(f"  P95 order latency   : {stats['p95_order_latency_ms']:.1f} ms")
    print(f"  Mean cancel latency : {stats['mean_cancel_latency_ms']:.1f} ms")
    print(f"  P95 cancel latency  : {stats['p95_cancel_latency_ms']:.1f} ms  → cancel_latency_ms")
    print(f"  Mean slippage       : {stats['mean_slippage_bps']:.2f} bps  (informational)")
    print(f"  P95 slippage        : {stats['p95_slippage_bps']:.2f} bps  (informational)")

    if stats["n_filled"] < args.min_fills:
        print(
            f"\nInsufficient fills ({stats['n_filled']} < {args.min_fills} minimum). "
            "Not suggesting config update."
        )
        print("Collect more demo/shadow data before applying.")
        sys.exit(0)

    suggested = _suggest_config(stats)
    print("\n=== Suggested config/risk.yaml backtest section ===")
    print("backtest:")
    for k, v in suggested.items():
        print(f"  {k}: {v}")

    if args.apply:
        risk_path = Path(args.risk_yaml)
        if not risk_path.exists():
            print(f"risk.yaml not found: {risk_path}")
            sys.exit(1)
        _apply_to_risk_yaml(suggested, risk_path)
        print(
            "\nBacktest config updated. Re-run replay validation to verify the "
            "impact on simulated fill rate and metrics."
        )
    else:
        print("\nDry run — pass --apply to write values to config/risk.yaml")


if __name__ == "__main__":
    main()
