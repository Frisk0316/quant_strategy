"""Run replay-based AS MM walk-forward/CPCV validation."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "backtesting"))

from backtesting.data_loader import load_candles
from backtesting.replay_validation import (
    ASMMReplayParamGrid,
    evaluate_replay_asmm_cpcv,
    evaluate_replay_asmm_walk_forward,
)
from okx_quant.core.config import load_config


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items() if k != "returns"}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, tuple):
        return [_jsonable(v) for v in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, pd.Series):
        return value.astype(float).tolist()
    if isinstance(value, pd.DataFrame):
        return [_jsonable(row) for row in value.to_dict(orient="records")]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        number = float(value)
        return number if np.isfinite(number) else None
    return value


def _summarize_wf(results: pd.DataFrame) -> list[dict]:
    rows = []
    for row in results.to_dict(orient="records"):
        result = row.get("result", {}) or {}
        rows.append({
            "window": row.get("window"),
            "is_start": row.get("is_start"),
            "is_end": row.get("is_end"),
            "oos_start": row.get("oos_start"),
            "oos_end": row.get("oos_end"),
            "oos_sharpe": row.get("oos_sharpe"),
            "oos_n": row.get("oos_n"),
            "selected_params": result.get("selected_params"),
            "is_score": result.get("is_score"),
            "oos_metrics": result.get("oos_metrics"),
            "oos_order_count": result.get("oos_order_count"),
            "oos_fill_count": result.get("oos_fill_count"),
        })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["cpcv", "wf", "both"], default="both")
    parser.add_argument("--symbol", default="BTC-USDT-SWAP")
    parser.add_argument("--bar", default="1H")
    parser.add_argument("--data-dir", default=str(PROJECT_ROOT / "data" / "ticks"))
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--gamma-grid", nargs="+", type=float, default=[0.05, 0.1, 0.2])
    parser.add_argument("--kappa-grid", nargs="+", type=float, default=[1.0, 1.5])
    parser.add_argument("--beta-vpin-grid", nargs="+", type=float, default=[2.0])
    parser.add_argument("--n-splits", type=int, default=3)
    parser.add_argument("--k-test", type=int, default=1)
    parser.add_argument("--embargo-pct", type=float, default=0.02)
    parser.add_argument("--purge-size", type=int, default=1)
    parser.add_argument("--is-days", type=int, default=30)
    parser.add_argument("--oos-days", type=int, default=7)
    parser.add_argument("--output-dir", default=str(PROJECT_ROOT / "results"))
    args = parser.parse_args()

    cfg = load_config(require_secrets=False)
    candles = load_candles(args.symbol, bar=args.bar, data_dir=args.data_dir, start=args.start, end=args.end)
    grid = ASMMReplayParamGrid(
        gamma=tuple(args.gamma_grid),
        kappa=tuple(args.kappa_grid),
        beta_vpin=tuple(args.beta_vpin_grid),
    )

    payload: dict[str, Any] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "strategy": "as_market_maker",
        "symbol": args.symbol,
        "bar": args.bar,
        "start": candles.index[0].isoformat() if not candles.empty else None,
        "end": candles.index[-1].isoformat() if not candles.empty else None,
        "param_grid": grid.combinations(),
        "backtest_execution": cfg.backtest.model_dump(),
    }

    if args.mode in {"cpcv", "both"}:
        cpcv = evaluate_replay_asmm_cpcv(
            candles,
            cfg=cfg,
            data_dir=args.data_dir,
            bar=args.bar,
            param_grid=grid,
            n_splits=args.n_splits,
            k_test=args.k_test,
            embargo_pct=args.embargo_pct,
            purge_size=args.purge_size,
        )
        payload["cpcv"] = cpcv
        print(
            "Replay CPCV "
            f"combos={cpcv['n_combinations']} paths={cpcv['n_paths']} "
            f"DSR={cpcv['dsr']:.6f} PSR={cpcv['psr']:.6f}"
        )

    if args.mode in {"wf", "both"}:
        wf = evaluate_replay_asmm_walk_forward(
            candles,
            cfg=cfg,
            data_dir=args.data_dir,
            bar=args.bar,
            param_grid=grid,
            is_days=args.is_days,
            oos_days=args.oos_days,
        )
        payload["walk_forward"] = _summarize_wf(wf)
        mean_oos = float(wf["oos_sharpe"].mean()) if not wf.empty else 0.0
        print(f"Replay WF windows={len(wf)} mean_oos_sharpe={mean_oos:.6f}")

    out_root = Path(args.output_dir)
    run_id = "replay_validation_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    run_dir = out_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    out_path = run_dir / "result.json"
    out_path.write_text(json.dumps(_jsonable(payload), indent=2), encoding="utf-8")
    print(f"Output -> {out_path}")


if __name__ == "__main__":
    main()
