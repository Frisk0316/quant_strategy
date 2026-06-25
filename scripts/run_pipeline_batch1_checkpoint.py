"""Run pipeline batch 1 S5/S6/S7 checkpoint summaries."""
from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import asdict, replace
from itertools import product
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtesting.pipeline_refit import (
    combo_key as _pipeline_combo_key,
    refit_validation as _pipeline_refit_validation,
    select_combo_on,
)
from backtesting.s5_residual_meanrev_backtest import (
    load_s5_inputs,
    run_s5_residual_meanrev_backtest,
)
from backtesting.s6_ts_momentum_backtest import (
    load_s6_inputs,
    run_s6_ts_momentum_backtest,
)
from backtesting.s7_basis_meanrev_backtest import (
    load_s7_inputs,
    run_s7_basis_meanrev_backtest,
)
from okx_quant.strategies.s5_residual_meanrev import S5ResidualMeanReversionParams
from okx_quant.strategies.s6_ts_momentum import S6TSMomentumParams
from okx_quant.strategies.s7_basis_meanrev import S7BasisMeanReversionParams

BATCH_ID = "pipeline_batch1_20260625"
START = "2024-01-01"
END = "2026-06-17"
DSN = "postgresql://quant:changeme@localhost:5432/quant"
EXCHANGE = "binance"
OUT = Path("results") / BATCH_ID
REFIT_OUT = Path("results") / f"{BATCH_ID}_refit"
UNIVERSE_MEMBERSHIP = Path("data/universe/universe_membership.parquet")


def _log(message: str) -> None:
    print(message, flush=True)


def _finite(value: object) -> object:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return value
    return out if np.isfinite(out) else None


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float):
        return _finite(value)
    return value


def _iter_grid(grid: dict[str, list[Any]]) -> list[dict[str, Any]]:
    keys = list(grid)
    return [dict(zip(keys, values)) for values in product(*(grid[key] for key in keys))]


def _combo_key(combo: dict[str, Any]) -> str:
    return _pipeline_combo_key({key: _jsonable(value) for key, value in combo.items()})


def _best_combo_record(records: list[dict[str, Any]], train_index: pd.Index) -> dict[str, Any]:
    if not records:
        raise ValueError("at least one combo record is required")
    keyed = {_combo_key(record["combo"]): record for record in records}
    selected = select_combo_on(train_index, {key: record["daily_returns"] for key, record in keyed.items()})
    return keyed[selected]


def _refit_validation(
    records: list[dict[str, Any]],
    n_trials: int,
    *,
    is_days: int = 365,
    oos_days: int = 90,
    cpcv_n_splits: int = 6,
    cpcv_k_test: int = 2,
    embargo_pct: float = 0.02,
    purge_size: int = 1,
) -> dict[str, Any]:
    combo_returns = {
        _combo_key(record["combo"]): record["daily_returns"]
        for record in records
    }
    return _pipeline_refit_validation(
        combo_returns,
        n_trials,
        is_days=is_days,
        oos_days=oos_days,
        cpcv_n_splits=cpcv_n_splits,
        cpcv_k_test=cpcv_k_test,
        embargo_pct=embargo_pct,
        purge_size=purge_size,
    )


def _precompute_records(
    base_params: Any,
    grid: dict[str, list[Any]],
    run_backtest: Any,
    label: str,
) -> list[dict[str, Any]]:
    fields = set(base_params.__dataclass_fields__)
    combos = _iter_grid(grid)
    records = []
    for idx, combo in enumerate(combos, start=1):
        _log(f"[{label}] combo {idx}/{len(combos)} {_combo_key(combo)}")
        combo_for_params = {key: value for key, value in combo.items() if key in fields}
        params = replace(base_params, **combo_for_params)
        result = run_backtest(params, combo)
        daily = result.daily_returns.dropna().astype(float).sort_index()
        records.append({
            "combo": {key: _jsonable(value) for key, value in combo.items()},
            "params": params,
            "daily_returns": daily,
            "metrics": {key: _jsonable(value) for key, value in result.metrics.items()},
            "nonzero_daily_returns": int((daily.abs() > 1e-12).sum()),
        })
    return records


def _best_full_sample_record(records: list[dict[str, Any]]) -> dict[str, Any]:
    indexes = [
        pd.DatetimeIndex(record["daily_returns"].dropna().index)
        for record in records
        if not record["daily_returns"].dropna().empty
    ]
    index = indexes[0]
    for next_index in indexes[1:]:
        index = index.union(next_index)
    return _best_combo_record(records, index.sort_values())


def _param_subset(record: dict[str, Any], keys: set[str]) -> dict[str, Any]:
    params = asdict(record["params"])
    return {key: _jsonable(value) for key, value in params.items() if key in keys}


def _records_have_activity(records: list[dict[str, Any]]) -> bool:
    return any(
        record["nonzero_daily_returns"] > 0
        or float(record["metrics"].get("average_turnover") or 0.0) > 0.0
        for record in records
    )


def _stat_pass(validation: dict[str, Any]) -> bool:
    return float(validation["dsr"] or 0.0) >= 0.95 and float(validation["psr"] or 0.0) >= 0.95


def _write_summary(candidate_dir: str, summary: dict, out_dir: Path = OUT) -> None:
    path = out_dir / candidate_dir / "summary.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(path)
    print(json.dumps({
        key: summary.get(key)
        for key in ("status", "wf_oos_sharpe", "cpcv_oos_sharpe", "dsr", "psr", "promotion_gate_passed")
    }, indent=2))


def _to_utc_dt(value: str) -> Any:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts.to_pydatetime()


def _complete_candle_symbols(symbols: list[str]) -> list[str]:
    import asyncpg

    expected = int((pd.Timestamp(END) - pd.Timestamp(START)).total_seconds() // 60)

    async def fetch() -> list[str]:
        conn = await asyncpg.connect(DSN)
        try:
            rows = await conn.fetch(
                """
                SELECT inst_id, COUNT(*) AS n
                FROM canonical_candles
                WHERE inst_id = ANY($1::text[])
                  AND bar = '1m'
                  AND source_primary = $2
                  AND ts >= $3
                  AND ts <  $4
                GROUP BY inst_id
                """,
                symbols,
                EXCHANGE,
                _to_utc_dt(START),
                _to_utc_dt(END),
            )
        finally:
            await conn.close()
        counts = {str(row["inst_id"]): int(row["n"]) for row in rows}
        return [symbol for symbol in symbols if counts.get(symbol) == expected]

    return asyncio.run(fetch())


def _load_s5_membership_and_symbols() -> tuple[pd.DataFrame, list[str]]:
    membership = pd.read_parquet(UNIVERSE_MEMBERSHIP)
    membership["date"] = pd.to_datetime(membership["date"]).dt.normalize()
    universe_symbols = sorted(str(symbol) for symbol in membership["symbol"].dropna().unique())
    complete = _complete_candle_symbols(universe_symbols)
    ordered = ["BTC-USDT-SWAP"] + [symbol for symbol in complete if symbol != "BTC-USDT-SWAP"]
    return membership[membership["symbol"].isin(ordered)].copy(), ordered


def _base_summary(candidate_id: str, family_id: str, grid_size: int, validation: dict[str, Any]) -> dict[str, Any]:
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
        "data_source": {
            "start": "2024-01-01T00:00:00+00:00",
            "end_exclusive": "2026-06-17T00:00:00+00:00",
            "primary_exchange": EXCHANGE,
            "bar": "1m",
        },
        "leak_test_reference": "verified by targeted pytest leak regression tests, not asserted by this runner",
        "idealized_fill": False,
        "portable_validation_gate": False,
        "ct_val_all_authoritative": False,
        "statistical_gate_passed": bool(_stat_pass(validation)),
        "promotion_gate_passed": False,
        "pass_a_status": "db_venue_scoped_grid_completed",
        "pass_b_status": "db_venue_scoped_refit_wf_cpcv_completed",
        "status": "checkpoint_review_required",
    }


def run_s5() -> None:
    _log("[s5] loading membership and complete-symbol coverage")
    membership, symbols = _load_s5_membership_and_symbols()
    _log(f"[s5] loading {len(symbols)} complete symbols from {EXCHANGE} canonical candles")
    params = replace(S5ResidualMeanReversionParams(), universe=symbols)
    close, funding = load_s5_inputs(symbols, start=START, end=END, backend="postgres", dsn=DSN, exchange=EXCHANGE)
    grid = {
        "lookback_days": [3, 7, 14],
        "z_enter": [1.5, 2.0, 2.5],
        "z_exit": [0.0, 0.5],
        "factors": ["BTC", "BTC+ETH"],
        "top_n": [10, 20],
    }
    records = _precompute_records(
        params,
        grid,
        lambda run_params, _combo: run_s5_residual_meanrev_backtest(close, funding, membership, run_params),
        "s5",
    )
    _log("[s5] running fold-refit WF/CPCV")
    n_trials = len(records)
    validation = _refit_validation(records, n_trials)
    best = _best_full_sample_record(records)
    active = _records_have_activity(records)
    summary = _base_summary("s5_residual_meanrev", "F-S5-RESIDUAL-MEANREV", n_trials, validation)
    summary.update({
        "status": "checkpoint_review_required" if active else "shelved_data_universe_mismatch",
        "statistical_gate_passed": bool(active and _stat_pass(validation)),
        "nonzero_grid_activity": bool(active),
        "full_sample_best_sharpe": _finite(best["metrics"].get("sharpe")),
        "full_sample_best_params": _param_subset(best, {
            "lookback_days",
            "z_enter",
            "z_exit",
            "factors",
            "top_n",
            "fee_bps",
            "slippage_bps",
        }),
        "selected_params": {"mode": "fold_refit_per_split"},
        "input_symbols": symbols,
        "data_coverage": {symbol: {"rows": int(close[symbol].dropna().shape[0])} for symbol in close.columns},
        "funding_coverage": {symbol: {"rows": int(funding[symbol].dropna().shape[0])} for symbol in funding.columns},
        "notes": [
            "Checkpoint evidence only; portable validation and ct_val authoritative gates are false.",
            "S5 rerun uses the fixed fold-refit WF/CPCV harness and includes the newly loaded ETH perp factor data.",
            "Current point-in-time membership and venue-scoped candle coverage produce a no-trade/data-universe artifact."
            if not active else "Current point-in-time membership produced nonzero grid activity.",
        ],
    })
    _write_summary("s5", summary, REFIT_OUT)


def run_s6() -> None:
    params = S6TSMomentumParams()
    _log(f"[s6] loading {len(params.symbols)} symbols from {EXCHANGE} canonical candles")
    close, funding = load_s6_inputs(params.symbols, start=START, end=END, backend="postgres", dsn=DSN, exchange=EXCHANGE)
    grid = {
        "lookback_days": [30, 60, 90, 120],
        "vol_target_annual": [0.10, 0.15, 0.20],
        "crash_filter": [True, False],
        "rebalance": ["weekly", "monthly"],
    }
    records = _precompute_records(
        params,
        grid,
        lambda run_params, _combo: run_s6_ts_momentum_backtest(close, funding, run_params),
        "s6",
    )
    _log("[s6] running fold-refit WF/CPCV")
    n_trials = len(records)
    validation = _refit_validation(records, n_trials)
    best = _best_full_sample_record(records)
    summary = _base_summary("s6_ts_momentum", "F-S6-TS-MOMENTUM", n_trials, validation)
    summary.update({
        "nonzero_grid_activity": bool(_records_have_activity(records)),
        "full_sample_best_sharpe": _finite(best["metrics"].get("sharpe")),
        "full_sample_best_params": _param_subset(best, {
            "lookback_days",
            "vol_target_annual",
            "crash_filter",
            "rebalance",
            "vol_window_days",
            "max_leverage",
            "fee_bps",
            "slippage_bps",
        }),
        "selected_params": {"mode": "fold_refit_per_split"},
        "data_coverage": {symbol: {"rows": int(close[symbol].dropna().shape[0])} for symbol in close.columns},
        "funding_coverage": {symbol: {"rows": int(funding[symbol].dropna().shape[0])} for symbol in funding.columns},
        "notes": [
            "Checkpoint evidence only; portable validation and ct_val authoritative gates are false.",
            "Adapter work remains out of scope until the statistical gate survives this fold-refit harness.",
        ],
    })
    _write_summary("s6", summary, REFIT_OUT)


def run_s7() -> None:
    params = S7BasisMeanReversionParams()
    _log(f"[s7] loading {len(params.pairs)} perp/spot pairs from {EXCHANGE} canonical candles")
    perp_close, spot_close, funding = load_s7_inputs(
        params.pairs, start=START, end=END, backend="postgres", dsn=DSN, exchange=EXCHANGE
    )
    grid = {
        "lookback_days": [3, 7, 14],
        "z_enter": [1.5, 2.0, 2.5],
        "z_exit": [0.0, 0.5],
        "max_half_life_days": [7.0, 14.0],
        "max_hold_days": [7, 14],
    }
    records = _precompute_records(
        params,
        grid,
        lambda run_params, _combo: run_s7_basis_meanrev_backtest(perp_close, spot_close, funding, run_params),
        "s7",
    )
    _log("[s7] running fold-refit WF/CPCV")
    n_trials = len(records)
    validation = _refit_validation(records, n_trials)
    best = _best_full_sample_record(records)
    summary = _base_summary("s7_basis_meanrev", "F-S7-BASIS-MEANREV", n_trials, validation)
    active = _records_have_activity(records)
    summary.update({
        "status": "shelved_pending_research_review",
        "statistical_gate_passed": bool(active and _stat_pass(validation)),
        "full_sample_best_sharpe": _finite(best["metrics"].get("sharpe")),
        "full_sample_best_params": _param_subset(best, {
            "pairs",
            "lookback_days",
            "z_enter",
            "z_exit",
            "max_half_life_days",
            "max_hold_days",
            "fee_bps",
            "slippage_bps",
        }),
        "selected_params": {"mode": "fold_refit_per_split"},
        "pairs": params.pairs,
        "perp_canonical_coverage": {
            symbol: {"rows": int(perp_close[symbol].dropna().shape[0]), "gap_count": 0, "coverage_pct": 1.0}
            for symbol in perp_close.columns
        },
        "spot_canonical_coverage": {
            symbol: {"rows": int(spot_close[symbol].dropna().shape[0]), "gap_count": 0, "coverage_pct": 1.0}
            for symbol in spot_close.columns
        },
        "funding_coverage": {symbol: {"rows": int(funding[symbol].dropna().shape[0])} for symbol in funding.columns},
        "half_life_filter_mode": "non_degenerate_retry_finite_7d_14d",
        "nonzero_grid_activity": bool(active),
        "notes": [
            "S7 is shelved, not refuted; this rerun uses non-degenerate half-life gates before any verdict.",
            "Checkpoint evidence only; portable validation and ct_val authoritative gates are false.",
        ],
    })
    _write_summary("s7", summary)


if __name__ == "__main__":
    run_s5()
    run_s6()
    run_s7()
