"""Build the public strategies snapshot from existing research artifacts.

Reads ONLY frozen experiment artifacts and the H-014 shadow journal counts.
Never publishes signal values, thresholds, or internal experiment codes.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MAX_CURVE_POINTS = 400
# Same category as the public-status page ban: raw signal keys must never
# appear in any published payload.
FORBIDDEN_KEYS = {"dvol", "ivp", "vrp", "rv", "z", "px", "signal", "legs", "intent"}

VOL_DIR = ROOT / "results" / "h014_e052_20260714"
FUNDING_DIR = (
    ROOT / "results" / "strategy_finding_20260726" / "f_funding_xs_dispersion_retry1"
)
SHADOW_DIR = ROOT / "results" / "shadow_h014"


def _missing(reason: str) -> dict[str, Any]:
    return {"available": False, "reason": reason}


def _downsample(rows: list[Any], limit: int = MAX_CURVE_POINTS) -> list[Any]:
    if len(rows) <= limit:
        return rows
    return [rows[round(i * (len(rows) - 1) / (limit - 1))] for i in range(limit)]


def _cumulative_curve(csv_path: Path, column: str) -> list[dict[str, Any]] | dict[str, Any]:
    if not csv_path.is_file():
        return _missing(f"{csv_path.name} not found")
    with csv_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        if column not in header:
            return _missing(f"column {column!r} not in {csv_path.name}")
        idx = header.index(column)
        total = 0.0
        rows = []
        for row in reader:
            total += float(row[idx])
            rows.append({"d": row[0], "cum": round(total, 6)})
    return _downsample(rows)


def _round(value: Any, digits: int = 4) -> Any:
    return round(value, digits) if isinstance(value, (int, float)) else None


def _vol_premium() -> dict[str, Any]:
    strategy: dict[str, Any] = {
        "id": "vol_premium",
        "name": "選擇權波動率收益策略",
        "description": (
            "隱含波動率明顯偏貴時,賣出一個月期備兌買權加下檔保護的賣權價差收取"
            "權利金;不貴則空手。幣本位、部位風險上下限鎖死、分批進場。"
        ),
        "status_label": "通過統計驗證,模擬驗證期進行中",
    }
    summary_path = VOL_DIR / "summary.json"
    if summary_path.is_file():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        validation = summary.get("validation", {})
        combo = summary.get("default_combo_for_minting", "")
        meta = summary.get("combo_meta", {}).get(combo, {})
        strategy["window"] = summary.get("window")
        strategy["passed_statistical_gate"] = bool(summary.get("statistical_gate_passed"))
        strategy["metrics"] = {
            "統計可信度 (DSR)": _round(validation.get("dsr")),
            "統計可信度 (PSR)": _round(validation.get("psr")),
            "WF 樣本外 Sharpe": _round(validation.get("wf_oos_sharpe")),
            "CPCV 樣本外 Sharpe": _round(validation.get("cpcv_oos_sharpe")),
            "交易梯次": meta.get("tranches"),
        }
        strategy["equity"] = _cumulative_curve(
            VOL_DIR / "combo_daily_returns.csv", combo
        )
    else:
        strategy["metrics"] = _missing("summary.json not found")
        strategy["equity"] = _missing("summary.json not found")
    strategy["shadow"] = _shadow_progress()
    return strategy


def _shadow_progress() -> dict[str, Any]:
    """Counts only — never signal payloads (see FORBIDDEN_KEYS)."""
    journal = SHADOW_DIR / "journal.jsonl"
    report_path = SHADOW_DIR / "bias_report.json"
    if not journal.is_file():
        return _missing("journal not found")
    counts: dict[str, int] = {}
    dates: set[str] = set()
    total = 0
    for line in journal.open(encoding="utf-8"):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        total += 1
        counts[str(row.get("status"))] = counts.get(str(row.get("status")), 0) + 1
        if row.get("event_date"):
            dates.add(str(row.get("event_date")))
    progress: dict[str, Any] = {
        "available": True,
        "total_records": total,
        "status_counts": counts,
        "distinct_days": len(dates),
        "last_event_date": max(dates) if dates else None,
    }
    if report_path.is_file():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        criteria = report.get("exit_criteria", report)
        progress["journal_weeks"] = criteria.get("journal_weeks")
        progress["minimum_weeks"] = criteria.get("minimum_weeks", 8)
        progress["eight_week_journal_met"] = criteria.get("eight_week_journal_met")
    return progress


def _funding_ls() -> dict[str, Any]:
    strategy: dict[str, Any] = {
        "id": "funding_ls",
        "name": "資金費率多空策略",
        "description": (
            "每週在主流永續合約中,做多資金費率最低的一批、放空最高的一批,"
            "兩邊金額相等(市場中性),賺取費率收斂價差。"
        ),
        "status_label": "觀察名單:統計可信度未達 95% 門檻,不為過關回調參數",
    }
    summary_path = FUNDING_DIR / "summary.json"
    if summary_path.is_file():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        params = summary.get("full_sample_best_params") or {}
        column = (
            f"lookback_days={params['lookback_days']}|quantile={params['quantile']}"
            if isinstance(params, dict) and {"lookback_days", "quantile"} <= params.keys()
            else None
        )
        strategy["passed_statistical_gate"] = bool(summary.get("statistical_gate_passed"))
        strategy["metrics"] = {
            "統計可信度 (DSR)": _round(summary.get("dsr")),
            "統計可信度 (PSR)": _round(summary.get("psr")),
            "WF 樣本外 Sharpe": _round(summary.get("wf_oos_sharpe")),
            "CPCV 樣本外 Sharpe": _round(summary.get("cpcv_oos_sharpe")),
            "全樣本最佳 Sharpe": _round(summary.get("full_sample_best_sharpe")),
        }
        strategy["equity"] = (
            _cumulative_curve(FUNDING_DIR / "combo_daily_returns.csv", column)
            if column
            else _missing("selected params column unknown")
        )
    else:
        strategy["metrics"] = _missing("summary.json not found")
        strategy["equity"] = _missing("summary.json not found")
    # ponytail: per-rebalance long/short notionals need a holdings log the
    # frozen backtest does not emit yet; a Codex task adds it. Until then this
    # block is honestly unavailable instead of fabricated.
    holdings = FUNDING_DIR / "holdings.json"
    if holdings.is_file():
        data = json.loads(holdings.read_text(encoding="utf-8"))
        strategy["rebalances"] = data.get("rebalances", [])
        strategy["rebalance_notional_note"] = data.get("notional_note")
    else:
        strategy["rebalances"] = _missing("holdings log not yet generated")
    return strategy


def build_snapshot() -> dict[str, Any]:
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "strategies": [_vol_premium(), _funding_ls()],
    }
    serialized = json.dumps(payload, ensure_ascii=False)
    lowered = json.loads(serialized)
    _assert_no_forbidden_keys(lowered)
    return payload


def _assert_no_forbidden_keys(node: Any) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key.lower() in FORBIDDEN_KEYS:
                raise ValueError(f"forbidden key {key!r} in snapshot payload")
            _assert_no_forbidden_keys(value)
    elif isinstance(node, list):
        for item in node:
            _assert_no_forbidden_keys(item)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=ROOT.parent / "quant_worklog" / "strategies.json"
    )
    args = parser.parse_args(argv)
    payload = build_snapshot()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote {args.out} ({len(payload['strategies'])} strategies)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
