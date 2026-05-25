"""Parameter sweep helpers for lightweight technical-strategy backtests."""
from __future__ import annotations

import csv
import json
import math
import re
import time
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

import pandas as pd

from backtesting.artifacts import save_backtest_artifacts
from backtesting.data_loader import _dsn_reachable as _dsn_probe
from backtesting.replay import (
    ReplayBacktestEngine,
    _apply_post_run_gates,
    _attach_ct_val_provenance,
    _bar_to_seconds,
    _check_data_coverage_gate,
    _compute_data_coverage,
    build_feed_for_strategies,
    run_replay_backtest,
    run_replay_validations,
)
from backtesting.research_controls import (
    apply_fill_all_signal_controls,
    apply_research_risk_overrides,
    summarize_risk_events,
)
from okx_quant.core.config import AppConfig, load_config
from okx_quant.core.symbols import normalize_swap_symbol


TECHNICAL_SWEEP_PARAMS: dict[str, tuple[str, ...]] = {
    "ma_crossover": ("fast_window", "slow_window"),
    "ema_crossover": ("fast_span", "slow_span"),
    "macd_crossover": ("fast_span", "slow_span", "signal_span"),
}

BAR_ROWS_PER_DAY = {
    "1m": 1440,
    "3m": 480,
    "5m": 288,
    "15m": 96,
    "30m": 48,
    "1H": 24,
    "2H": 12,
    "4H": 6,
    "1D": 1,
}

SWEEP_BASE_SECONDS_PER_TRIAL = 0.35
SWEEP_SECONDS_PER_EVENT = {
    # MA recomputes pandas rolling windows on every bar, so it is materially
    # slower than the incremental EMA/MACD implementations.
    "ma_crossover": 0.0018,
    "ema_crossover": 0.00020,
    "macd_crossover": 0.00025,
}

RANK_METRICS = (
    "sharpe",
    "total_return",
    "max_drawdown",
    "order_count",
    "real_fill_count",
    "fill_rate",
    "risk_event_count",
    "bankrupt",
)


class ParameterSweepError(ValueError):
    """Raised when a sweep request cannot be expanded safely."""


def coerce_parameter_values(raw: Any, *, max_values: int = 500) -> list[int]:
    """Parse a list/range parameter specification into positive integer values.

    Accepted forms:
    - ``[7, 14, 21]``
    - ``"7,14,21"``
    - ``"21..100:5"`` or ``"21~100:5"``
    """
    values: list[int] = []

    if isinstance(raw, str):
        parts = [part.strip() for part in raw.split(",") if part.strip()]
    elif isinstance(raw, (list, tuple, set)):
        parts = list(raw)
    else:
        parts = [raw]

    for part in parts:
        if isinstance(part, str):
            values.extend(_parse_parameter_token(part))
        else:
            values.append(_coerce_positive_int(part))

    unique = list(dict.fromkeys(values))
    if not unique:
        raise ParameterSweepError("parameter values cannot be empty")
    if len(unique) > max_values:
        raise ParameterSweepError(f"too many values for one parameter (max {max_values})")
    return unique


def expand_parameter_grid(
    strategy: str,
    parameter_grid: dict[str, Any],
    *,
    max_combinations: int = 5000,
) -> tuple[list[dict[str, int]], list[dict[str, Any]]]:
    """Expand a raw grid into valid parameter combinations and skipped rows."""
    if strategy not in TECHNICAL_SWEEP_PARAMS:
        raise ParameterSweepError(f"parameter sweep is not supported for {strategy}")
    if not parameter_grid:
        raise ParameterSweepError("parameter_grid is required")

    allowed = TECHNICAL_SWEEP_PARAMS[strategy]
    unknown = sorted(set(parameter_grid) - set(allowed))
    if unknown:
        raise ParameterSweepError(f"unsupported parameter(s) for {strategy}: {', '.join(unknown)}")

    keys = [key for key in allowed if key in parameter_grid]
    values_by_key = {key: coerce_parameter_values(parameter_grid[key]) for key in keys}
    candidate_count = math.prod(len(values_by_key[key]) for key in keys)
    candidate_limit = max(max_combinations * 4, max_combinations + 5000)
    if candidate_count > candidate_limit:
        raise ParameterSweepError(
            f"parameter grid expands to {candidate_count} raw combinations; "
            f"max raw candidate count is {candidate_limit}"
        )

    valid: list[dict[str, int]] = []
    skipped: list[dict[str, Any]] = []
    for raw_values in product(*(values_by_key[key] for key in keys)):
        params = dict(zip(keys, raw_values))
        reason = _validate_technical_params(strategy, params)
        if reason:
            skipped.append({"params": params, "reason": reason})
        else:
            valid.append(params)

    if not valid:
        raise ParameterSweepError("parameter grid has no valid combinations")
    if len(valid) > max_combinations:
        raise ParameterSweepError(
            f"parameter grid has {len(valid)} valid combinations; max is {max_combinations}"
        )
    return valid, skipped


def estimate_sweep_runtime(
    *,
    strategy: str,
    bar: str,
    start: str | None,
    end: str | None,
    symbols: list[str],
    combinations: int,
    finalist_count: int = 0,
    finalist_validation: str | None = None,
) -> dict[str, Any]:
    """Return a conservative pre-run runtime estimate for a parameter sweep."""
    days = _date_span_days(start, end)
    rows_per_symbol = max(1, int(days * BAR_ROWS_PER_DAY.get(bar, 24)))
    symbols_count = max(1, len(symbols))
    events_per_trial = rows_per_symbol * symbols_count
    seconds_per_trial = _estimate_seconds_per_trial(strategy, events_per_trial)
    screening_seconds = seconds_per_trial * max(1, combinations)
    replay_count = _validation_replay_count(days, finalist_validation)
    finalist_seconds = seconds_per_trial * max(0, finalist_count) * replay_count
    total_seconds = screening_seconds + finalist_seconds
    return {
        "bar": bar,
        "calendar_days": days,
        "symbols": symbols_count,
        "rows_per_symbol": rows_per_symbol,
        "events_per_trial": events_per_trial,
        "combinations": combinations,
        "estimated_seconds_per_trial": seconds_per_trial,
        "estimated_screening_seconds": screening_seconds,
        "finalist_count": finalist_count,
        "finalist_validation": finalist_validation or "none",
        "estimated_full_rerun_replay_count": replay_count,
        "estimated_full_rerun_seconds": finalist_seconds,
        "estimated_total_seconds": total_seconds,
    }


def rank_sweep_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rank completed sweep rows by Sharpe, then return, then drawdown."""
    ranked = sorted(rows, key=_rank_key, reverse=True)
    for idx, row in enumerate(ranked, start=1):
        row["rank"] = idx
    return ranked


def run_parameter_sweep(
    *,
    strategy: str,
    parameter_grid: dict[str, Any],
    symbols: list[str],
    bar: str = "1H",
    periods: int | None = None,
    start: str | None = None,
    end: str | None = None,
    data_dir: str = "data/ticks",
    output_dir: str | Path = "results/parameter_sweeps",
    sweep_id: str | None = None,
    cfg: AppConfig | None = None,
    initial_equity: float | None = None,
    exchange: str | None = None,
    max_combinations: int = 5000,
    liquidate_on_end: bool | None = None,
    risk_overrides: dict[str, Any] | None = None,
    fill_all_signals: bool = False,
    run_finalists: bool = True,
    finalist_top_pct: float = 0.10,
    max_finalists: int = 20,
    finalist_validation: str | None = None,
    full_output_dir: str | Path = "results",
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Run a lightweight parameter sweep and write summary JSON/CSV artifacts."""
    combinations, skipped = expand_parameter_grid(
        strategy,
        parameter_grid,
        max_combinations=max_combinations,
    )
    normalized_symbols = [normalize_swap_symbol(symbol) for symbol in symbols]
    if not normalized_symbols:
        raise ParameterSweepError("at least one symbol is required")

    cfg = _prepare_base_config(
        cfg or load_config(require_secrets=False),
        strategy=strategy,
        symbols=normalized_symbols,
        initial_equity=initial_equity,
        exchange=exchange,
    )
    cfg, applied_risk_overrides = apply_research_risk_overrides(cfg, risk_overrides)
    cfg, applied_fill_all_controls = apply_fill_all_signal_controls(cfg, fill_all_signals)
    effective_periods = periods or _annualization_periods(bar)
    finalist_count_estimate = _estimate_finalist_count(
        len(combinations),
        run_finalists=run_finalists,
        finalist_top_pct=finalist_top_pct,
        max_finalists=max_finalists,
    )
    estimate = estimate_sweep_runtime(
        strategy=strategy,
        bar=bar,
        start=start,
        end=end,
        symbols=normalized_symbols,
        combinations=len(combinations),
        finalist_count=finalist_count_estimate,
        finalist_validation=finalist_validation,
    )

    sweep_started = time.perf_counter()
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    sweep_id = sweep_id or f"sweep_{strategy}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    if progress_callback:
        progress_callback({
            "progress": 5,
            "message": "Loading historical feed",
            "estimate": estimate,
            "elapsed_seconds": time.perf_counter() - sweep_started,
        })

    feed = build_feed_for_strategies(
        cfg,
        strategy_names=[strategy],
        data_dir=data_dir,
        start=start,
        end=end,
        bar=bar,
    )
    coverage = _compute_data_coverage(feed, start, end, bar)
    _check_data_coverage_gate(coverage)

    rows: list[dict[str, Any]] = []
    total = len(combinations)
    for idx, params in enumerate(combinations, start=1):
        if progress_callback:
            completed = idx - 1
            progress_callback({
                "progress": 5 + int((idx - 1) / total * 90),
                "message": f"Screening parameter set {idx}/{total}",
                "current_params": params,
                "completed_trials": completed,
                "total_trials": total,
                "elapsed_seconds": time.perf_counter() - sweep_started,
                "estimated_remaining_seconds": _estimate_remaining_seconds(
                    elapsed_seconds=time.perf_counter() - sweep_started,
                    completed_trials=completed,
                    total_trials=total,
                    fallback_seconds=estimate["estimated_screening_seconds"],
                ),
            })
        combo_started = time.perf_counter()
        try:
            combo_cfg = _config_for_params(cfg, strategy, params, normalized_symbols)
            engine = ReplayBacktestEngine(
                combo_cfg,
                strategy_names=[strategy],
                periods=effective_periods,
                bar_seconds=_bar_to_seconds(bar),
                liquidate_on_end=liquidate_on_end,
            )
            result = engine.run_sync(feed)
            _attach_ct_val_provenance(result, engine)
            _apply_post_run_gates(result, [strategy], coverage)
            result.validation["risk_summary"] = summarize_risk_events(result.risk_event_log)
            if applied_risk_overrides:
                result.validation["research_risk_overrides"] = applied_risk_overrides
            if applied_fill_all_controls:
                result.validation["research_fill_all_signals"] = applied_fill_all_controls
            elapsed = time.perf_counter() - combo_started
            rows.append(_summarize_trial(idx, params, result.metrics, result.validation, elapsed))
            if progress_callback:
                progress_callback({
                    "progress": 5 + int(idx / total * 90),
                    "message": f"Screened parameter set {idx}/{total}",
                    "current_params": params,
                    "completed_trials": idx,
                    "total_trials": total,
                    "trial_elapsed_seconds": elapsed,
                    "elapsed_seconds": time.perf_counter() - sweep_started,
                    "estimated_remaining_seconds": _estimate_remaining_seconds(
                        elapsed_seconds=time.perf_counter() - sweep_started,
                        completed_trials=idx,
                        total_trials=total,
                        fallback_seconds=estimate["estimated_screening_seconds"],
                    ),
                })
        except Exception as exc:  # noqa: BLE001 - keep the sweep moving and report failed combos.
            elapsed = time.perf_counter() - combo_started
            rows.append({
                "trial": idx,
                "params": dict(params),
                "status": "error",
                "error": str(exc),
                "elapsed_seconds": elapsed,
            })
            if progress_callback:
                progress_callback({
                    "progress": 5 + int(idx / total * 90),
                    "message": f"Parameter set {idx}/{total} failed",
                    "current_params": params,
                    "completed_trials": idx,
                    "total_trials": total,
                    "trial_elapsed_seconds": elapsed,
                    "elapsed_seconds": time.perf_counter() - sweep_started,
                    "estimated_remaining_seconds": _estimate_remaining_seconds(
                        elapsed_seconds=time.perf_counter() - sweep_started,
                        completed_trials=idx,
                        total_trials=total,
                        fallback_seconds=estimate["estimated_screening_seconds"],
                    ),
                })

    completed_rows = [row for row in rows if row.get("status") == "ok"]
    ranked = rank_sweep_rows(completed_rows)
    failed_rows = [row for row in rows if row.get("status") != "ok"]
    finalist_results = _run_finalist_backtests(
        ranked,
        strategy=strategy,
        cfg=cfg,
        symbols=normalized_symbols,
        data_dir=data_dir,
        start=start,
        end=end,
        bar=bar,
        periods=effective_periods,
        output_dir=full_output_dir,
        sweep_id=sweep_id,
        liquidate_on_end=liquidate_on_end,
        risk_overrides=applied_risk_overrides,
        fill_all_controls=applied_fill_all_controls,
        run_finalists=run_finalists,
        finalist_top_pct=finalist_top_pct,
        max_finalists=max_finalists,
        finalist_validation=finalist_validation,
        progress_callback=progress_callback,
    )
    _attach_finalist_status(ranked, finalist_results)
    elapsed_total = time.perf_counter() - sweep_started

    summary = {
        "sweep_id": sweep_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "strategy": strategy,
        "symbols": normalized_symbols,
        "bar": bar,
        "start": start,
        "end": end,
        "periods": effective_periods,
        "parameter_grid": parameter_grid,
        "combination_count": len(combinations),
        "completed_count": len(completed_rows),
        "failed_count": len(failed_rows),
        "skipped_count": len(skipped),
        "elapsed_seconds": elapsed_total,
        "estimate": estimate,
        "research_risk_overrides": applied_risk_overrides,
        "research_fill_all_signals": applied_fill_all_controls,
        "finalist_top_pct": finalist_top_pct,
        "max_finalists": max_finalists,
        "finalist_validation": finalist_validation or "none",
        "finalist_results": finalist_results,
        "top_results": ranked[:20],
        "results": ranked + failed_rows,
        "skipped": skipped,
        "data_coverage": coverage,
    }

    json_path = output_path / f"{sweep_id}.json"
    csv_path = output_path / f"{sweep_id}.csv"
    _write_json(json_path, summary)
    _write_csv(csv_path, summary["results"], strategy)
    summary["artifacts"] = {
        "summary_json": str(json_path),
        "summary_csv": str(csv_path),
    }

    # Persist artifact paths inside the JSON too.
    _write_json(json_path, summary)

    if progress_callback:
        progress_callback({
            "progress": 100,
            "message": "Parameter sweep complete",
            "artifacts": summary["artifacts"],
            "top_results": summary["top_results"],
        })

    return summary


def _validation_replay_count(days: float, mode: str | None) -> int:
    """Approximate full-rerun replay count including validation passes."""
    if not mode or mode == "none":
        return 1
    normalized = mode.lower()
    wf_windows = max(0, int(max(0.0, days - 30.0) // 7.0) + 1)
    cpcv_combos = 15
    count = 1
    if normalized in {"wf", "both"}:
        count += wf_windows
    if normalized in {"cpcv", "both"}:
        count += cpcv_combos
    return count


def _estimate_seconds_per_trial(strategy: str, events_per_trial: int) -> float:
    coefficient = SWEEP_SECONDS_PER_EVENT.get(strategy, 0.00025)
    return max(0.6, SWEEP_BASE_SECONDS_PER_TRIAL + events_per_trial * coefficient)


def _estimate_remaining_seconds(
    *,
    elapsed_seconds: float,
    completed_trials: int,
    total_trials: int,
    fallback_seconds: float,
) -> float:
    remaining_trials = max(0, total_trials - completed_trials)
    if completed_trials <= 0:
        return max(0.0, fallback_seconds)
    avg_seconds = max(0.0, elapsed_seconds) / max(1, completed_trials)
    return max(0.0, avg_seconds * remaining_trials)


def _estimate_finalist_count(
    total: int,
    *,
    run_finalists: bool,
    finalist_top_pct: float,
    max_finalists: int,
) -> int:
    if not run_finalists or total <= 0 or max_finalists <= 0 or finalist_top_pct <= 0:
        return 0
    return min(max_finalists, max(1, math.ceil(total * finalist_top_pct)))


def _run_finalist_backtests(
    ranked: list[dict[str, Any]],
    *,
    strategy: str,
    cfg: AppConfig,
    symbols: list[str],
    data_dir: str,
    start: str | None,
    end: str | None,
    bar: str,
    periods: int,
    output_dir: str | Path,
    sweep_id: str,
    liquidate_on_end: bool | None,
    risk_overrides: dict[str, float],
    fill_all_controls: dict[str, Any],
    run_finalists: bool,
    finalist_top_pct: float,
    max_finalists: int,
    finalist_validation: str | None,
    progress_callback: Callable[[dict[str, Any]], None] | None,
) -> list[dict[str, Any]]:
    finalist_count = _estimate_finalist_count(
        len(ranked),
        run_finalists=run_finalists,
        finalist_top_pct=finalist_top_pct,
        max_finalists=max_finalists,
    )
    if finalist_count <= 0:
        return []

    finalists = ranked[:finalist_count]
    results: list[dict[str, Any]] = []
    for idx, row in enumerate(finalists, start=1):
        params = dict(row.get("params") or {})
        run_id = f"{sweep_id}_rank_{idx:03d}"
        if progress_callback:
            progress_callback({
                "progress": 95 + int((idx - 1) / max(finalist_count, 1) * 4),
                "message": f"Rerunning finalist {idx}/{finalist_count}",
                "current_params": params,
                "current_finalist_run_id": run_id,
            })
        started = time.perf_counter()
        try:
            combo_cfg = _config_for_params(cfg, strategy, params, symbols)
            result = run_replay_backtest(
                strategy_names=[strategy],
                cfg=combo_cfg,
                data_dir=data_dir,
                start=start,
                end=end,
                bar=bar,
                periods=periods,
                liquidate_on_end=liquidate_on_end,
            )
            result.validation["parameter_sweep"] = {
                "sweep_id": sweep_id,
                "rank": row.get("rank"),
                "params": params,
            }
            result.validation["risk_summary"] = summarize_risk_events(result.risk_event_log)
            if risk_overrides:
                result.validation["research_risk_overrides"] = risk_overrides
            if fill_all_controls:
                result.validation["research_fill_all_signals"] = fill_all_controls

            validation_results = None
            if finalist_validation and finalist_validation != "none":
                validation_results = run_replay_validations(
                    strategy_names=[strategy],
                    cfg=combo_cfg,
                    data_dir=data_dir,
                    start=start,
                    end=end,
                    bar=bar,
                    periods=periods,
                    mode=finalist_validation,
                    liquidate_on_end=liquidate_on_end,
                )
            args = SimpleNamespace(
                strategy=[strategy],
                start=start,
                end=end,
                bar=bar,
                validate=finalist_validation,
            )
            run_dir = save_backtest_artifacts(
                result=result,
                cfg=combo_cfg,
                args=args,
                output_dir=str(output_dir),
                run_id=run_id,
                strategy_names=[strategy],
                start=start,
                end=end,
                bar=bar,
                validation_results=validation_results,
            )
            results.append({
                "rank": row.get("rank"),
                "trial": row.get("trial"),
                "params": params,
                "status": "ok",
                "run_id": run_dir.name,
                "artifact_dir": str(run_dir),
                "elapsed_seconds": time.perf_counter() - started,
            })
        except Exception as exc:  # noqa: BLE001 - keep sweep summary useful.
            results.append({
                "rank": row.get("rank"),
                "trial": row.get("trial"),
                "params": params,
                "status": "error",
                "run_id": run_id,
                "error": str(exc),
                "elapsed_seconds": time.perf_counter() - started,
            })
    return results


def _attach_finalist_status(
    ranked: list[dict[str, Any]],
    finalist_results: list[dict[str, Any]],
) -> None:
    by_rank = {item.get("rank"): item for item in finalist_results}
    for row in ranked:
        result = by_rank.get(row.get("rank"))
        if not result:
            continue
        row["finalist_run_id"] = result.get("run_id")
        row["finalist_status"] = result.get("status")
        row["finalist_artifact_dir"] = result.get("artifact_dir")


def _parse_parameter_token(token: str) -> list[int]:
    token = token.strip()
    range_match = re.match(r"^(\d+(?:\.\d+)?)\s*(?:\.\.|~|-)\s*(\d+(?:\.\d+)?)(?::(\d+(?:\.\d+)?))?$", token)
    if range_match:
        start = _coerce_positive_int(range_match.group(1))
        end = _coerce_positive_int(range_match.group(2))
        step = _coerce_positive_int(range_match.group(3) or 1)
        if start > end:
            raise ParameterSweepError(f"range start must be <= end: {token}")
        return list(range(start, end + 1, step))
    return [_coerce_positive_int(token)]


def _coerce_positive_int(value: Any) -> int:
    try:
        num = float(value)
    except (TypeError, ValueError) as exc:
        raise ParameterSweepError(f"invalid integer parameter value: {value}") from exc
    if not math.isfinite(num) or num <= 0 or int(num) != num:
        raise ParameterSweepError(f"parameter values must be positive integers: {value}")
    return int(num)


def _validate_technical_params(strategy: str, params: dict[str, int]) -> str | None:
    del strategy
    fast = params.get("fast_window", params.get("fast_span"))
    slow = params.get("slow_window", params.get("slow_span"))
    if fast is not None and slow is not None and fast >= slow:
        return "fast parameter must be smaller than slow parameter"
    return None


def _date_span_days(start: str | None, end: str | None) -> float:
    if not start or not end:
        return 365.0
    try:
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
    except Exception:
        return 365.0
    seconds = max((end_ts - start_ts).total_seconds(), 86400.0)
    return seconds / 86400.0


def _annualization_periods(bar: str) -> int:
    return int(BAR_ROWS_PER_DAY.get(bar, 24) * 365)


def _prepare_base_config(
    cfg: AppConfig,
    *,
    strategy: str,
    symbols: list[str],
    initial_equity: float | None,
    exchange: str | None,
) -> AppConfig:
    cfg = cfg.model_copy(deep=True)
    if exchange:
        cfg.storage = cfg.storage.model_copy(update={"primary_exchange": exchange})
    if cfg.storage.candle_backend == "postgres" and (
        not cfg.storage.timescale_dsn or not _dsn_probe(cfg.storage.timescale_dsn)
    ):
        cfg.storage = cfg.storage.model_copy(update={"candle_backend": "parquet"})
    if initial_equity:
        cfg.system = cfg.system.model_copy(update={"equity_usd": float(initial_equity)})
    cfg.system = cfg.system.model_copy(update={"symbols": list(symbols)})
    current = getattr(cfg.strategies, strategy)
    setattr(cfg.strategies, strategy, current.model_copy(update={"symbols": list(symbols)}))
    return cfg


def _config_for_params(
    cfg: AppConfig,
    strategy: str,
    params: dict[str, int],
    symbols: list[str],
) -> AppConfig:
    combo_cfg = cfg.model_copy(deep=True)
    current = getattr(combo_cfg.strategies, strategy)
    updates = dict(params)
    updates["symbols"] = list(symbols)
    setattr(combo_cfg.strategies, strategy, current.model_copy(update=updates))
    combo_cfg.system = combo_cfg.system.model_copy(update={"symbols": list(symbols)})
    return combo_cfg


def _summarize_trial(
    trial: int,
    params: dict[str, int],
    metrics: dict[str, Any],
    validation: dict[str, Any],
    elapsed: float,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "trial": trial,
        "params": dict(params),
        "status": "ok",
        "elapsed_seconds": elapsed,
        "ct_val_gate_passed": validation.get("ct_val_gate_passed"),
    }
    for key in RANK_METRICS:
        if key == "risk_event_count":
            row[key] = (validation.get("risk_summary") or {}).get("total", 0)
        else:
            row[key] = metrics.get(key)
    return row


def _rank_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("status") == "ok",
        not bool(row.get("bankrupt", False)),
        _finite_or(row.get("sharpe"), -1e18),
        _finite_or(row.get("total_return"), -1e18),
        _finite_or(row.get("max_drawdown"), -1e18),
        _finite_or(row.get("real_fill_count"), -1e18),
    )


def _finite_or(value: Any, fallback: float) -> float:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return fallback
    return num if math.isfinite(num) else fallback


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, default=_json_default), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]], strategy: str) -> None:
    param_keys = TECHNICAL_SWEEP_PARAMS[strategy]
    fieldnames = [
        "rank",
        "trial",
        "status",
        *param_keys,
        "sharpe",
        "total_return",
        "max_drawdown",
        "order_count",
        "real_fill_count",
        "fill_rate",
        "risk_event_count",
        "bankrupt",
        "finalist_run_id",
        "finalist_status",
        "finalist_artifact_dir",
        "elapsed_seconds",
        "ct_val_gate_passed",
        "error",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            flat = {key: row.get(key) for key in fieldnames}
            for key in param_keys:
                flat[key] = (row.get("params") or {}).get(key)
            writer.writerow(flat)


def _json_default(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    return str(value)
