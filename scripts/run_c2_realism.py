"""Run C2 funding-carry realism re-cost and stress summary."""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtesting.c2_funding_carry_backtest import C2FundingCarryParams, load_c2_inputs, run_c2_funding_carry_backtest
from scripts.run_pipeline_batch1_checkpoint import (
    _best_full_sample_record,
    _finite,
    _jsonable,
    _param_subset,
    _precompute_records,
    _records_have_activity,
    _refit_validation,
)
from scripts.run_pipeline_batch2_checkpoint import BATCH_ID, DSN, END, EXCHANGE, OUT, START, _ct_val_sources, _stat_pass

PRIOR_FAMILY_N_TRIALS = 24
CANDIDATE_DIR = "c2_funding_carry_realism"


def _write_summary(summary: dict[str, Any]) -> dict[str, Any]:
    path = OUT / CANDIDATE_DIR / "summary.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_jsonable(summary), indent=2, sort_keys=True), encoding="utf-8")
    print(path)
    print(json.dumps({
        key: summary.get(key)
        for key in ("status", "wf_oos_sharpe", "cpcv_oos_sharpe", "dsr", "psr", "realized_annualized_volatility")
    }, indent=2))
    return summary


def run_c2_realism() -> dict[str, Any]:
    params = C2FundingCarryParams(
        fee_bps=2.0,
        slippage_bps=3.0,
        basis_execution_slippage_bps=2.0,
        carry_cost_bps=1.0,
    )
    grid = {
        "funding_enter_apr": [0.05, 0.10, 0.15],
        "basis_z_max": [2.0, 3.0],
        "exit_funding_apr": [0.0, 0.02],
        "rebalance": ["daily", "weekly"],
    }
    perp_close, spot_close, funding = load_c2_inputs(
        params.pairs,
        start=START,
        end=END,
        backend="postgres",
        dsn=DSN,
        exchange=EXCHANGE,
    )
    records = _precompute_records(
        params,
        grid,
        lambda run_params, _combo: run_c2_funding_carry_backtest(perp_close, spot_close, funding, run_params),
        "c2-realism",
    )
    grid_size = len(records)
    n_trials = PRIOR_FAMILY_N_TRIALS + grid_size
    validation = _refit_validation(records, n_trials)
    best = _best_full_sample_record(records)
    best_metrics = best["metrics"]
    statistical_gate_passed = bool(_stat_pass(validation))
    status = "checkpoint_review_required" if statistical_gate_passed else "refuted_realism_recost"
    summary = {
        "batch_id": BATCH_ID,
        "candidate_id": "c2_funding_carry",
        "candidate_dir": CANDIDATE_DIR,
        "hypothesis_id": "H-007",
        "family_id": "F-FUNDING-CARRY",
        "retry_classification": "retry_existing_funding_carry_family_realism_recost",
        "prior_family_n_trials": PRIOR_FAMILY_N_TRIALS,
        "grid_size_this_run": grid_size,
        "family_cumulative_n_trials": n_trials,
        "validation_mode": validation["validation_mode"],
        "wf_oos_sharpe": validation["wf_oos_sharpe"],
        "cpcv_oos_sharpe": validation["cpcv_oos_sharpe"],
        "dsr": validation["dsr"],
        "psr": validation["psr"],
        "wf_selected_param_counts": validation["wf_selected_param_counts"],
        "cpcv_selected_param_counts": validation["cpcv_selected_param_counts"],
        "cpcv": validation["cpcv"],
        "statistical_gate_passed": statistical_gate_passed,
        "promotion_gate_passed": False,
        "portable_validation_gate": False,
        "idealized_fill": False,
        "ct_val_sources": _ct_val_sources(list(params.pairs)),
        "ct_val_all_authoritative": True,
        "stage2_status": "PASS",
        "pass_a_status": "skipped_missing_required_parquet_cache",
        "pass_b_status": "db_venue_scoped_refit_wf_cpcv_completed",
        "status": status,
        "realism_cost_model": asdict(params),
        "stress_rule": best_metrics.get("stress_evaluation", {}).get("rule"),
        "stress_evaluation": best_metrics.get("stress_evaluation"),
        "realized_daily_volatility": _finite(best_metrics.get("realized_daily_volatility")),
        "realized_annualized_volatility": _finite(best_metrics.get("realized_annualized_volatility")),
        "realized_vol_red_flag_below_2pct": bool(best_metrics.get("realized_vol_red_flag_below_2pct")),
        "nonzero_grid_activity": bool(_records_have_activity(records)),
        "full_sample_best_sharpe": _finite(best_metrics.get("sharpe")),
        "full_sample_best_params": _param_subset(best, set(C2FundingCarryParams.__dataclass_fields__)),
        "selected_params": {"mode": "fold_refit_per_split"},
        "perp_canonical_coverage": {symbol: {"rows": int(perp_close[symbol].dropna().shape[0])} for symbol in perp_close.columns},
        "spot_canonical_coverage": {symbol: {"rows": int(spot_close[symbol].dropna().shape[0])} for symbol in spot_close.columns},
        "funding_coverage": {symbol: {"rows": int(funding[symbol].dropna().shape[0])} for symbol in funding.columns},
        "data_source": {
            "start": "2024-01-01T00:00:00+00:00",
            "end_exclusive": "2026-06-17T00:00:00+00:00",
            "primary_exchange": EXCHANGE,
            "bar": "1m",
        },
        "notes": [
            "Research-only realism re-cost; live funding_carry strategy behavior was not changed.",
            "Stress set is selected mechanically from trailing 7-day funding APR < 0 or abs(basis z) > 3.",
            "Adapter, ct_val, promotion, demo, shadow, and live work remain blocked pending Claude review.",
        ],
    }
    return _write_summary(summary)


if __name__ == "__main__":
    run_c2_realism()
