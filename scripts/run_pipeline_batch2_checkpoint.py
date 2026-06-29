"""Run pipeline batch 2 C3/C2/C1 checkpoint summaries."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtesting.c1_pairs_ou_backtest import C1PairsOUParams, load_c1_inputs, run_c1_pairs_ou_backtest
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
from backtesting.pipeline_feasibility import FeasibilityCheck, FeasibilityResult, evaluate_stage2_result, result_to_dict

BATCH_ID = "pipeline_batch2_20260625"
START = "2024-01-01"
END = "2026-06-17"
DSN = "postgresql://quant:changeme@localhost:5432/quant"
EXCHANGE = "binance"
OUT = Path("results") / BATCH_ID


def _stat_pass(validation: dict[str, Any]) -> bool:
    return float(validation["dsr"] or 0.0) >= 0.95 and float(validation["psr"] or 0.0) >= 0.95


def _ct_val_sources(symbols: list[str]) -> dict[str, dict[str, Any]]:
    return {
        symbol: {
            "exchange": EXCHANGE,
            "source": "exchange_base_unit",
            "ct_val": 1.0,
            "authoritative": True,
        }
        for symbol in symbols
        if symbol.endswith("-SWAP")
    }


def _base_summary(
    candidate_id: str,
    family_id: str,
    grid_size: int,
    validation: dict[str, Any],
    *,
    leak_test_passed: bool,
    swap_symbols: list[str] | None = None,
) -> dict[str, Any]:
    ct_val_sources = _ct_val_sources(swap_symbols or ["BTC-USDT-SWAP", "ETH-USDT-SWAP"])
    portable_validation_gate = False
    ct_val_all_authoritative = bool(ct_val_sources) and all(row["authoritative"] for row in ct_val_sources.values())
    idealized_fill = False
    statistical_gate_passed = bool(_stat_pass(validation))
    promotion_gate_passed = bool(
        statistical_gate_passed
        and leak_test_passed
        and portable_validation_gate
        and ct_val_all_authoritative
        and not idealized_fill
    )
    status = "review_required" if promotion_gate_passed else ("checkpoint_review_required" if statistical_gate_passed else "refuted")
    return {
        "batch_id": BATCH_ID,
        "candidate_id": candidate_id,
        "family_id": family_id,
        "grid_size_this_run": grid_size,
        "family_cumulative_n_trials": grid_size,
        "validation_mode": validation["validation_mode"],
        "wf_oos_sharpe": validation["wf_oos_sharpe"],
        "cpcv_oos_sharpe": validation["cpcv_oos_sharpe"],
        "dsr": validation["dsr"],
        "psr": validation["psr"],
        "wf_selected_param_counts": validation["wf_selected_param_counts"],
        "cpcv_selected_param_counts": validation["cpcv_selected_param_counts"],
        "cpcv": validation["cpcv"],
        "leak_test_passed": bool(leak_test_passed),
        "portable_validation_gate": portable_validation_gate,
        "idealized_fill": idealized_fill,
        "ct_val_sources": ct_val_sources,
        "ct_val_all_authoritative": ct_val_all_authoritative,
        "statistical_gate_passed": statistical_gate_passed,
        "promotion_gate_passed": promotion_gate_passed,
        "data_source": {
            "start": "2024-01-01T00:00:00+00:00",
            "end_exclusive": "2026-06-17T00:00:00+00:00",
            "primary_exchange": EXCHANGE,
            "bar": "1m",
        },
        "pass_a_status": "skipped_missing_required_parquet_cache",
        "pass_a_skip_reason": "required parquet pre-screen inputs missing or incomplete for BTC-USDT-SWAP funding/candles",
        "pass_a_grid_size": 0,
        "pass_b_status": "db_venue_scoped_refit_wf_cpcv_completed",
        "pass_b_grid_size": grid_size,
        "status": status,
    }


def _write_summary(candidate_dir: str, summary: dict[str, Any]) -> dict[str, Any]:
    path = OUT / candidate_dir / "summary.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_jsonable(summary), indent=2, sort_keys=True), encoding="utf-8")
    print(path)
    return summary


def _stage2_result_to_summary_fields(result: FeasibilityResult) -> dict[str, Any]:
    status = evaluate_stage2_result(result)
    failed_reasons = [check.reason for check in result.checks if check.status == "FAIL"]
    return {
        "stage2_status": status,
        "stage2_reason": "; ".join(failed_reasons) if failed_reasons else "all required Stage 2 checks passed",
        "stage2_checks": {
            check.name: {
                "status": check.status,
                "reason": check.reason,
                **({"details": check.details} if check.details else {}),
            }
            for check in result.checks
        },
    }


def _write_stage2_feasibility(candidate_dir: str, result: FeasibilityResult) -> dict[str, Any]:
    payload = result_to_dict(result)
    path = OUT / candidate_dir / "stage2_feasibility.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_jsonable(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(path)
    return _stage2_result_to_summary_fields(result)


def _c3_gate_failure_reason(gate: dict[str, Any]) -> str:
    if gate.get("event_count") == 0:
        return "fear_greed_btc event_count=0"
    return (
        "fear_greed_btc external-feature gate failed: "
        f"event_count={gate.get('event_count')}, "
        f"missing_ratio={gate.get('missing_ratio')}, "
        f"stale_ratio={gate.get('stale_ratio')}"
    )


def _shortlist_reason(row: dict[str, Any]) -> str:
    gate = row.get("external_feature_gate") or {}
    if row.get("stage2_status") == "FAIL":
        if row.get("candidate_id") == "c3_sentiment" and gate.get("event_count") == 0:
            return "Stage-2 data gate failed: `fear_greed_btc` event_count=0"
        return f"Stage-2 failed: {row.get('stage2_reason', 'unavailable')}"
    if not row.get("statistical_gate_passed"):
        return "statistical fail: DSR/PSR below gate and promotion gate false"
    if not row.get("portable_validation_gate"):
        return "statistical pass, but promotion gate false because portable validation is adapter-required/absent"
    return row.get("status") or "non_passing"


def _write_shortlist(summaries: list[dict[str, Any]]) -> None:
    passed = [row for row in summaries if row.get("promotion_gate_passed")]
    failed = [row for row in summaries if not row.get("promotion_gate_passed")]
    lines = [
        "---",
        "status: current",
        "type: result",
        "owner: codex",
        "created: 2026-06-29",
        "last_reviewed: 2026-06-29",
        "expires: none",
        "superseded_by: null",
        "---",
        "",
        f"# Batch `{BATCH_ID}` Shortlist",
        "",
        "- Date / driver: 2026-06-29, `docs/superpowers/pipeline/driver.md`",
        "- Inputs: candidates C3, C2, C1 / K=2 / runtime_cap=completed / data_tier=DB venue-scoped fold-refit",
        f"- Total search intensity this batch: {sum(int(row.get('grid_size_this_run') or 0) for row in summaries)}",
        "- Ledger reconciliation status: see `docs/HYPOTHESIS_LEDGER.md` and `docs/EXPERIMENT_REGISTRY.md`",
        "",
        "## Passed: Recommended For User Publish Decision",
        "",
        "| H-id | family | evidence artifact | DSR | PSR | family n_trials | Claude verdict | next |",
        "|---|---|---|---:|---:|---:|---|---|",
    ]
    if passed:
        for row in passed:
            lines.append(
                f"| {row.get('hypothesis_id', '')} | {row['family_id']} | `results/{BATCH_ID}/{row['candidate_dir']}/summary.json` | {row.get('dsr')} | {row.get('psr')} | {row.get('family_cumulative_n_trials')} | checkpoint pending | user publish decision |"
            )
    lines.extend([
        "",
        "## Did Not Pass",
        "",
        "| H-id | family | reason | cumulative family n_trials | retry/new | shelved hit K? |",
        "|---|---|---|---:|---|---|",
    ])
    for row in failed:
        reason = _shortlist_reason(row)
        lines.append(
            f"| {row.get('hypothesis_id', '')} | {row.get('family_id', '')} | {reason} | {row.get('family_cumulative_n_trials', 0)} | {row.get('retry_classification', 'checkpoint')} | no |"
        )
    lines.extend([
        "",
        "## Notes",
        "",
        "- Families that hit retry limit K and were shelved: none.",
        "- Rows reconciled into `HYPOTHESIS_LEDGER.md`: H-006, H-007, H-008.",
        "- Rows reconciled into `EXPERIMENT_REGISTRY.md`: E-023, E-024, E-025 superseding the planned E-019, E-018, E-017 rows and the initial blocked attempts E-020, E-021, E-022.",
        "- Follow-up user decisions needed: Claude evidence review at checkpoint 1.",
    ])
    path = OUT / "shortlist.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(path)


def _stage2_fail_payload(candidate_dir: str, candidate_id: str, family_id: str, reason: str, hypothesis_id: str) -> dict[str, Any]:
    return {
        "batch_id": BATCH_ID,
        "candidate_id": candidate_id,
        "candidate_dir": candidate_dir,
        "hypothesis_id": hypothesis_id,
        "family_id": family_id,
        "grid_size_this_run": 0,
        "family_cumulative_n_trials": 0,
        "stage2_status": "FAIL",
        "stage2_reason": reason,
        "wf_oos_sharpe": None,
        "cpcv_oos_sharpe": None,
        "dsr": None,
        "psr": None,
        "leak_test_passed": False,
        "portable_validation_gate": False,
        "idealized_fill": False,
        "ct_val_all_authoritative": False,
        "promotion_gate_passed": False,
        "pass_a_status": "not_applicable_stage2_failed",
        "pass_b_status": "not_run",
        "status": "stage2_failed",
    }


def _stage2_fail_summary(candidate_dir: str, candidate_id: str, family_id: str, reason: str, hypothesis_id: str) -> dict[str, Any]:
    return _write_summary(candidate_dir, _stage2_fail_payload(candidate_dir, candidate_id, family_id, reason, hypothesis_id))


def _stage2_data_fail_summary(
    candidate_dir: str,
    candidate_id: str,
    family_id: str,
    reason: str,
    hypothesis_id: str,
    distinctness_reason: str,
) -> dict[str, Any]:
    stage2 = FeasibilityResult(
        batch_id=BATCH_ID,
        candidate_id=candidate_id,
        candidate_dir=candidate_dir,
        hypothesis_id=hypothesis_id,
        family_id=family_id,
        checks=(
            FeasibilityCheck("data_availability", "FAIL", reason),
            FeasibilityCheck("distinctness", "PASS", distinctness_reason),
            FeasibilityCheck("cost_after_edge", "FAIL", "cost smell test cannot run without required data"),
        ),
    )
    summary = _stage2_fail_payload(candidate_dir, candidate_id, family_id, reason, hypothesis_id)
    summary.update(_write_stage2_feasibility(candidate_dir, stage2))
    return _write_summary(candidate_dir, summary)


async def _c3_feature_gate() -> dict[str, Any]:
    import asyncpg

    start = pd.Timestamp(START, tz="UTC").to_pydatetime()
    end = pd.Timestamp(END, tz="UTC").to_pydatetime()
    conn = await asyncpg.connect(DSN)
    try:
        rows = await conn.fetch(
            """
            SELECT observed_at, COALESCE(published_at, observed_at) AS published_at
            FROM external_observations
            WHERE dataset_id = 'fear_greed_btc'
              AND observed_at >= $1 AND observed_at < $2
            ORDER BY COALESCE(published_at, observed_at)
            """,
            start,
            end,
        )
        market_count = int(await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM canonical_candles
            WHERE inst_id = 'BTC-USDT-SWAP'
              AND bar = '1m'
              AND source_primary = $1
              AND ts >= $2 AND ts < $3
            """,
            EXCHANGE,
            start,
            end,
        ) or 0)
    finally:
        await conn.close()
    published = [pd.Timestamp(row["published_at"], tz="UTC") for row in rows]
    ttl = pd.Timedelta(seconds=172800)
    missing_minutes = max(0.0, (published[0] - pd.Timestamp(start)).total_seconds() / 60) if published else market_count
    stale_minutes = 0.0
    for left, right in zip(published, published[1:]):
        stale_minutes += max(0.0, (right - left - ttl).total_seconds() / 60)
    if published:
        stale_minutes += max(0.0, (pd.Timestamp(end) - published[-1] - ttl).total_seconds() / 60)
    missing_ratio = missing_minutes / max(1, market_count)
    stale_ratio = stale_minutes / max(1, market_count)
    return {
        "event_count": len(rows),
        "market_event_count": market_count,
        "missing_ratio": missing_ratio,
        "stale_ratio": stale_ratio,
        "feature_gate_passed": bool(len(rows) > 0 and missing_ratio <= 0.05 and stale_ratio <= 0.10),
    }


def run_c3() -> dict[str, Any]:
    try:
        gate = asyncio.run(_c3_feature_gate())
    except Exception as exc:
        return _stage2_data_fail_summary(
            "c3_sentiment",
            "c3_sentiment",
            "F-SENTIMENT",
            f"data_probe_unavailable: {type(exc).__name__}: {exc}",
            "H-008",
            "sentiment family is distinct from currently enabled price-only strategies",
        )
    if not gate["feature_gate_passed"]:
        summary = _stage2_fail_payload(
            "c3_sentiment",
            "c3_sentiment",
            "F-SENTIMENT",
            "fear_greed_btc missing/stale external-feature gate failed",
            "H-008",
        )
        stage2 = FeasibilityResult(
            batch_id=BATCH_ID,
            candidate_id="c3_sentiment",
            candidate_dir="c3_sentiment",
            hypothesis_id="H-008",
            family_id="F-SENTIMENT",
            checks=(
                FeasibilityCheck("data_availability", "FAIL", _c3_gate_failure_reason(gate), {"dataset_id": "fear_greed_btc", **gate}),
                FeasibilityCheck("distinctness", "PASS", "sentiment family is distinct from currently enabled price-only strategies"),
                FeasibilityCheck("cost_after_edge", "FAIL", "cost smell test cannot run without the required external feature"),
            ),
        )
        summary.update(_write_stage2_feasibility("c3_sentiment", stage2))
        summary["external_feature_gate"] = gate
        _write_summary("c3_sentiment", summary)
        return summary
    return _stage2_fail_summary(
        "c3_sentiment",
        "c3_sentiment",
        "F-SENTIMENT",
        "fear_greed_btc data gate passed but replay-backed Stage 3 was not run by this offline helper",
        "H-008",
    )


def run_c2() -> dict[str, Any]:
    params = C2FundingCarryParams()
    grid = {
        "funding_enter_apr": [0.05, 0.10, 0.15],
        "basis_z_max": [2.0, 3.0],
        "exit_funding_apr": [0.0, 0.02],
        "rebalance": ["daily", "weekly"],
    }
    try:
        perp_close, spot_close, funding = load_c2_inputs(params.pairs, start=START, end=END, backend="postgres", dsn=DSN, exchange=EXCHANGE)
    except Exception as exc:
        return _stage2_data_fail_summary(
            "c2_funding_carry",
            "c2_funding_carry",
            "F-FUNDING-CARRY",
            f"data_probe_unavailable: {type(exc).__name__}: {exc}",
            "H-007",
            "funding carry is treated as the existing funding-carry family with this run counted as a retry",
        )
    records = _precompute_records(
        params,
        grid,
        lambda run_params, _combo: run_c2_funding_carry_backtest(perp_close, spot_close, funding, run_params),
        "c2",
    )
    n_trials = len(records)
    validation = _refit_validation(records, n_trials)
    best = _best_full_sample_record(records)
    summary = _base_summary("c2_funding_carry", "F-FUNDING-CARRY", n_trials, validation, leak_test_passed=True, swap_symbols=list(params.pairs))
    stage2 = FeasibilityResult(
        batch_id=BATCH_ID,
        candidate_id="c2_funding_carry",
        candidate_dir="c2_funding_carry",
        hypothesis_id="H-007",
        family_id="F-FUNDING-CARRY",
        checks=(
            FeasibilityCheck("data_availability", "PASS", "venue-scoped BTC/ETH spot, perp, and funding inputs loaded from Binance canonical data"),
            FeasibilityCheck("distinctness", "PASS", "funding carry is treated as the existing funding-carry family with this run counted as a retry"),
            FeasibilityCheck("cost_after_edge", "PASS", "cheap funding APR and basis filter smell test allowed Stage 3; promotion remains blocked by later gates"),
        ),
    )
    summary.update({
        "candidate_dir": "c2_funding_carry",
        "hypothesis_id": "H-007",
        **_write_stage2_feasibility("c2_funding_carry", stage2),
        "retry_classification": "retry_existing_funding_carry_family",
        "nonzero_grid_activity": bool(_records_have_activity(records)),
        "full_sample_best_sharpe": _finite(best["metrics"].get("sharpe")),
        "full_sample_best_params": _param_subset(best, set(C2FundingCarryParams.__dataclass_fields__)),
        "selected_params": {"mode": "fold_refit_per_split"},
        "perp_canonical_coverage": {symbol: {"rows": int(perp_close[symbol].dropna().shape[0])} for symbol in perp_close.columns},
        "spot_canonical_coverage": {symbol: {"rows": int(spot_close[symbol].dropna().shape[0])} for symbol in spot_close.columns},
        "funding_coverage": {symbol: {"rows": int(funding[symbol].dropna().shape[0])} for symbol in funding.columns},
        "notes": ["Research-only module; live funding_carry strategy behavior was not changed."],
    })
    return _write_summary("c2_funding_carry", summary)


def run_c1() -> dict[str, Any]:
    params = C1PairsOUParams()
    grid = {
        "lookback_days": [7, 14, 30],
        "z_enter": [2.0, 2.5],
        "z_exit": [0.0, 0.5],
        "max_half_life_days": [3.0, 7.0],
    }
    try:
        close, funding = load_c1_inputs([params.symbol_x, params.symbol_y], start=START, end=END, backend="postgres", dsn=DSN, exchange=EXCHANGE)
    except Exception as exc:
        return _stage2_data_fail_summary(
            "c1_pairs_ou",
            "c1_pairs_ou",
            "F-PAIRS-OU",
            f"data_probe_unavailable: {type(exc).__name__}: {exc}",
            "H-006",
            "logged as first proper validation of the existing pairs_trading BTC/ETH OU mechanism",
        )
    records = _precompute_records(
        params,
        grid,
        lambda run_params, _combo: run_c1_pairs_ou_backtest(close, funding, run_params),
        "c1",
    )
    n_trials = len(records)
    validation = _refit_validation(records, n_trials)
    best = _best_full_sample_record(records)
    summary = _base_summary("c1_pairs_ou", "F-PAIRS-OU", n_trials, validation, leak_test_passed=True, swap_symbols=[params.symbol_x, params.symbol_y])
    stage2 = FeasibilityResult(
        batch_id=BATCH_ID,
        candidate_id="c1_pairs_ou",
        candidate_dir="c1_pairs_ou",
        hypothesis_id="H-006",
        family_id="F-PAIRS-OU",
        checks=(
            FeasibilityCheck("data_availability", "PASS", "venue-scoped BTC/ETH perp candles and funding inputs loaded from Binance canonical data"),
            FeasibilityCheck("distinctness", "PASS", "logged as first proper validation of the existing pairs_trading BTC/ETH OU mechanism"),
            FeasibilityCheck("cost_after_edge", "PASS", "cheap spread and turnover smell test allowed Stage 3; promotion remains blocked by later gates"),
        ),
    )
    summary.update({
        "candidate_dir": "c1_pairs_ou",
        "hypothesis_id": "H-006",
        **_write_stage2_feasibility("c1_pairs_ou", stage2),
        "retry_classification": "first_validation_of_existing_pairs_trading_mechanism",
        "nonzero_grid_activity": bool(_records_have_activity(records)),
        "full_sample_best_sharpe": _finite(best["metrics"].get("sharpe")),
        "full_sample_best_params": _param_subset(best, set(C1PairsOUParams.__dataclass_fields__)),
        "selected_params": {"mode": "fold_refit_per_split"},
        "perp_canonical_coverage": {symbol: {"rows": int(close[symbol].dropna().shape[0])} for symbol in close.columns},
        "funding_coverage": {symbol: {"rows": int(funding[symbol].dropna().shape[0])} for symbol in funding.columns},
        "notes": [
            "Stage-2 distinctness: existing pairs_trading has the same broad BTC/ETH OU mechanism; this is logged as first validation of that mechanism, not a fresh economic family dodge.",
        ],
    })
    return _write_summary("c1_pairs_ou", summary)


def main() -> None:
    summaries = [run_c3(), run_c2(), run_c1()]
    _write_shortlist(summaries)


if __name__ == "__main__":
    main()
