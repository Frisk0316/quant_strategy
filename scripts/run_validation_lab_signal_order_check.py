"""Run the report's BTC 1H technical signal-to-order check."""
from __future__ import annotations

import json
import os
import sys
import argparse
from pathlib import Path
from types import SimpleNamespace
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from backtesting.artifacts import save_backtest_artifacts
from backtesting.replay import run_replay_backtest
from backtesting.research_controls import (
    EXECUTION_PROFILE_REALISTIC,
    EXECUTION_PROFILE_STRATEGY_FILL,
    apply_execution_profile_controls,
    summarize_risk_events,
)
from loguru import logger
from okx_quant.core.config import load_config


CASES = {
    "ma_crossover": {"fast_window": 10, "slow_window": 200},
    "ema_crossover": {"fast_span": 10, "slow_span": 200},
    "macd_crossover": {"fast_span": 12, "slow_span": 26, "signal_span": 9},
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run BTC 1H technical signal-to-order checks.")
    parser.add_argument("--max-order-notional-usd", type=float, default=None)
    parser.add_argument("--max-pos-pct-equity", type=float, default=None)
    parser.add_argument("--run-suffix", default=None)
    parser.add_argument(
        "--execution-profile",
        choices=[EXECUTION_PROFILE_STRATEGY_FILL, EXECUTION_PROFILE_REALISTIC],
        default=EXECUTION_PROFILE_STRATEGY_FILL,
    )
    return parser.parse_args()


def _suffix(args: argparse.Namespace) -> str:
    if args.run_suffix:
        return args.run_suffix.strip("_")
    parts = []
    if args.max_order_notional_usd is not None:
        parts.append(f"maxord{args.max_order_notional_usd:g}".replace(".", "p"))
    if args.max_pos_pct_equity is not None:
        parts.append(f"pospct{args.max_pos_pct_equity:g}".replace(".", "p"))
    return "_".join(parts)


def _first_rows(rows: Any, limit: int = 3) -> list[dict[str, Any]]:
    if rows is None:
        return []
    if hasattr(rows, "head"):
        return json.loads(rows.head(limit).to_json(orient="records", date_format="iso"))
    return list(rows[:limit]) if isinstance(rows, list) else []


def _case_config(base_cfg: Any, strategy: str, params: dict[str, Any]) -> Any:
    cfg = base_cfg.model_copy(deep=True)
    cfg.storage = cfg.storage.model_copy(update={"primary_exchange": "binance"})
    current = getattr(cfg.strategies, strategy)
    update = dict(params)
    update["symbols"] = ["BTC-USDT-SWAP"]
    setattr(cfg.strategies, strategy, current.model_copy(update=update))
    cfg.system.symbols = ["BTC-USDT-SWAP"]
    return cfg


def _summarize_result(strategy: str, params: dict[str, Any], result: Any, run_dir: Path) -> dict[str, Any]:
    validation = dict(getattr(result, "validation", {}) or {})
    metrics = dict(getattr(result, "metrics", {}) or {})
    signal_log = getattr(result, "signal_log", []) or []
    order_log = getattr(result, "order_log", None)
    fill_log = getattr(result, "fill_log", None)
    rejected_log = getattr(result, "rejected_log", []) or []
    risk_events = getattr(result, "risk_event_log", []) or []
    signal_count = len(signal_log)
    order_count = len(order_log) if order_log is not None else 0
    fill_count = len(fill_log) if fill_log is not None else 0
    real_fill_count = int(metrics.get("real_fill_count", fill_count) or 0)
    rejected_count = len(rejected_log)
    verdict = (
        "PASS_SIGNAL_TO_ORDER"
        if signal_count > 0 and order_count > 0 and real_fill_count > 0
        else "SIGNAL_ONLY_OR_BLOCKED"
        if signal_count > 0
        else "NO_SIGNAL"
    )
    return {
        "strategy": strategy,
        "params": params,
        "run_dir": str(run_dir),
        "verdict": verdict,
        "backend": validation.get("data_backend") or metrics.get("backend"),
        "signal_count": signal_count,
        "submitted_order_count": int(metrics.get("submitted_order_count", order_count) or 0),
        "order_log_rows": order_count,
        "fill_log_rows": fill_count,
        "real_fill_count": real_fill_count,
        "rejected_count": rejected_count,
        "risk_event_count": len(risk_events),
        "risk_summary": validation.get("risk_summary") or summarize_risk_events(risk_events),
        "ct_val_sources": validation.get("ct_val_sources", {}),
        "ct_val_all_authoritative": validation.get("ct_val_all_authoritative"),
        "gate3_data_coverage": validation.get("gate3_data_coverage", {}),
        "first_signals": _first_rows(signal_log),
        "first_orders": _first_rows(order_log),
        "first_fills": _first_rows(fill_log),
        "first_rejections": _first_rows(rejected_log),
        "first_risk_events": _first_rows(risk_events),
    }


def main() -> None:
    args = _parse_args()
    os.environ["BACKTEST_ARTIFACT_MODE"] = "files"
    logger.remove()
    logger.add(sys.stderr, level="WARNING")
    cfg = load_config(require_secrets=False)
    risk_updates: dict[str, Any] = {}
    if args.max_order_notional_usd is not None:
        risk_updates["max_order_notional_usd"] = args.max_order_notional_usd
    if args.max_pos_pct_equity is not None:
        risk_updates["max_pos_pct_equity"] = args.max_pos_pct_equity
    if risk_updates:
        cfg.risk = cfg.risk.model_copy(update=risk_updates)
    start = "2024-01-01"
    end = "2026-04-30"
    bar = "1H"
    output_dir = PROJECT_ROOT / "results"
    suffix = _suffix(args)
    summaries = []
    for strategy, params in CASES.items():
        case_cfg = _case_config(cfg, strategy, params)
        case_cfg, profile_controls = apply_execution_profile_controls(
            case_cfg,
            args.execution_profile,
            allow_internal=True,
        )
        run_id = f"validation_lab_{strategy}_btc_binance_1h_20260622"
        if suffix:
            run_id = f"{run_id}_{suffix}"
        result = run_replay_backtest(
            strategy_names=[strategy],
            cfg=case_cfg,
            data_dir=str(PROJECT_ROOT / "data" / "ticks"),
            start=start,
            end=end,
            bar=bar,
            periods=8760,
        )
        result.validation["execution_profile"] = args.execution_profile
        if profile_controls.get("idealized_fill"):
            result.validation["idealized_fill"] = True
            result.validation["research_fill_all_signals"] = profile_controls.get("research_fill_all_signals", {})
        result.validation["risk_summary"] = summarize_risk_events(result.risk_event_log)
        artifact_args = SimpleNamespace(
            strategy=[strategy],
            start=start,
            end=end,
            bar=bar,
            strategy_params=params,
            risk_overrides=risk_updates,
            execution_profile=args.execution_profile,
        )
        run_dir = save_backtest_artifacts(
            result=result,
            cfg=case_cfg,
            args=artifact_args,
            output_dir=str(output_dir),
            run_id=run_id,
            strategy_names=[strategy],
            start=start,
            end=end,
            bar=bar,
        )
        summaries.append(_summarize_result(strategy, params, result, run_dir))

    report = {
        "symbol": "BTC-USDT-SWAP",
        "exchange": "binance",
        "bar": bar,
        "start": start,
        "end": end,
        "execution_profile": args.execution_profile,
        "risk_defaults": {
            "max_order_notional_usd": cfg.risk.max_order_notional_usd,
            "max_pos_pct_equity": cfg.risk.max_pos_pct_equity,
            "max_leverage": cfg.risk.max_leverage,
        },
        "cases": summaries,
    }
    out_name = "validation_lab_signal_order_check_20260622"
    if suffix:
        out_name = f"{out_name}_{suffix}"
    out = output_dir / f"{out_name}.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"output": str(out), "cases": summaries}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
