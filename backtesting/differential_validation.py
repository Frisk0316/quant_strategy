"""Differential validation against external backtest engines.

This module deliberately treats public engines as reference implementations for
backtest behaviour, not as market-data truth sources. The inputs are existing
backtest artifacts; the outputs are normalized reference artifacts plus
mismatch tables.
"""
from __future__ import annotations

import importlib.util
import json
import math
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable

import numpy as np
import pandas as pd

from okx_quant.analytics.performance import max_drawdown, sharpe


TECHNICAL_STRATEGIES = {"ma_crossover", "ema_crossover", "macd_crossover"}
ENGINE_NAMES = {"vectorbt", "backtrader", "nautilus"}
STRATEGY_VALIDATION_DIR = "strategy_validation"
REFERENCE_ROLES = {
    "reference_signals_only",
    "reference_full",
    "advisory",
    "not_applicable",
    "skipped_dependency",
}
MISMATCH_CATEGORIES = {
    "indicator_mismatch",
    "strategy_logic_mismatch",
    "execution_semantics_mismatch",
    "pnl_accounting_mismatch",
    "metric_formula_mismatch",
    "contract_value_mismatch",
    "unsupported_reference_scope",
}

BAR_PERIODS = {
    "1m": 365 * 24 * 60,
    "3m": 365 * 24 * 20,
    "5m": 365 * 24 * 12,
    "15m": 365 * 24 * 4,
    "30m": 365 * 24 * 2,
    "1H": 365 * 24,
    "2H": 365 * 12,
    "4H": 365 * 6,
    "1D": 365,
}


@dataclass(frozen=True)
class ValidationTolerances:
    timestamp_seconds: float = 0.0
    indicator_abs: float = 1e-8
    indicator_rel: float = 1e-10
    price_abs: float = 1e-8
    price_rel: float = 1e-10
    qty_abs: float = 1e-10
    qty_rel: float = 1e-10
    pnl_abs: float = 1e-6
    pnl_rel: float = 1e-8
    equity_abs: float = 1e-6
    equity_rel: float = 1e-8
    metric_abs: float = 1e-6
    metric_rel: float = 1e-6

    @classmethod
    def from_initial_equity(cls, initial_equity: float) -> "ValidationTolerances":
        equity_tol = max(1e-6, 1e-8 * max(abs(float(initial_equity or 0.0)), 1.0))
        return cls(pnl_abs=equity_tol, equity_abs=equity_tol)


@dataclass
class ArtifactBundle:
    run_dir: Path
    result: dict[str, Any]
    config: dict[str, Any]
    price_series: pd.DataFrame
    indicator_series: pd.DataFrame
    signals: pd.DataFrame
    trades: pd.DataFrame
    fills: pd.DataFrame
    equity_curve: pd.DataFrame

    @property
    def run_id(self) -> str:
        return str(self.result.get("run_id") or self.run_dir.name)

    @property
    def strategies(self) -> list[str]:
        return [str(s) for s in self.result.get("strategies", []) if s]

    @property
    def primary_strategy(self) -> str:
        return self.strategies[0] if self.strategies else ""

    @property
    def symbols(self) -> list[str]:
        symbols = self.result.get("symbols") or []
        return [str(s) for s in symbols if s]

    @property
    def bar(self) -> str:
        return str(self.result.get("bar") or self.config.get("cli_args", {}).get("bar") or "1H")

    @property
    def periods(self) -> int:
        return int(BAR_PERIODS.get(self.bar, 365))

    @property
    def initial_equity(self) -> float:
        system = self.config.get("system") if isinstance(self.config, dict) else {}
        if isinstance(system, dict) and system.get("equity_usd") is not None:
            return _safe_float(system.get("equity_usd"), 1.0)
        if not self.equity_curve.empty and "equity" in self.equity_curve.columns:
            first = _safe_float(self.equity_curve["equity"].iloc[0], float("nan"))
            if math.isfinite(first) and first > 0:
                return first
        return 1.0

    def strategy_params(self, strategy: str | None = None) -> dict[str, Any]:
        name = strategy or self.primary_strategy
        strategies = self.config.get("strategies") if isinstance(self.config, dict) else {}
        params = strategies.get(name, {}) if isinstance(strategies, dict) else {}
        return dict(params) if isinstance(params, dict) else {}


@dataclass
class ReferenceResult:
    engine: str
    status: str
    reason: str = ""
    reference_role: str = "advisory"
    categories: list[str] = field(default_factory=list)
    indicator_series: pd.DataFrame = field(default_factory=pd.DataFrame)
    signals: pd.DataFrame = field(default_factory=pd.DataFrame)
    trades: pd.DataFrame = field(default_factory=pd.DataFrame)
    equity_curve: pd.DataFrame = field(default_factory=pd.DataFrame)
    metrics: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


def load_artifact_bundle(run_dir: str | Path) -> ArtifactBundle:
    root = Path(run_dir)
    if not root.exists():
        raise FileNotFoundError(str(root))
    result = _read_json(root / "result.json")
    config = _read_json(root / "config.json") if (root / "config.json").exists() else {}
    normalized_result = _normalize_embedded_daily_winner(result)
    return ArtifactBundle(
        run_dir=root,
        result=normalized_result,
        config=config,
        price_series=_read_csv(root / "price_series.csv"),
        indicator_series=_read_csv(root / "indicator_series.csv"),
        signals=_read_csv(root / "signals.csv"),
        trades=_load_trades(root, normalized_result),
        fills=_read_csv(root / "fills.csv"),
        equity_curve=_load_equity(root, normalized_result),
    )


def run_differential_validation(
    run_dir: str | Path,
    engines: Iterable[str] | None = None,
    output_dir: str | Path | None = None,
    validation_id: str | None = None,
) -> dict[str, Any]:
    bundle = load_artifact_bundle(run_dir)
    selected_engines = [name.strip().lower() for name in (engines or ENGINE_NAMES) if name]
    unknown = sorted(set(selected_engines) - ENGINE_NAMES)
    if unknown:
        raise ValueError(f"Unsupported differential validation engine(s): {', '.join(unknown)}")

    validation_id = validation_id or _build_validation_id()
    out_dir = Path(output_dir) if output_dir else bundle.run_dir / "validation" / validation_id
    out_dir.mkdir(parents=True, exist_ok=True)
    tolerances = ValidationTolerances.from_initial_equity(bundle.initial_equity)

    adapters = {
        "vectorbt": VectorBTReferenceAdapter(),
        "backtrader": BacktraderReferenceAdapter(),
        "nautilus": NautilusReferenceAdapter(),
    }

    engine_results: dict[str, dict[str, Any]] = {}
    all_mismatches = {
        "indicators": [],
        "signals": [],
        "trades": [],
        "pnl": [],
        "metrics": [],
    }
    for engine in selected_engines:
        ref = adapters[engine].run(bundle)
        _write_reference_artifacts(out_dir, ref)
        engine_summary = _reference_summary(ref)
        if ref.status == "OK":
            comparison = compare_reference(bundle, ref, tolerances)
            engine_summary["comparison"] = comparison["summary"]
            for name, rows in comparison["mismatches"].items():
                all_mismatches[name].extend(rows)
        else:
            engine_summary["comparison"] = _unavailable_comparison_summary(ref)
            all_mismatches["metrics"].append({
                "engine": engine,
                "category": ref.categories[0] if ref.categories else "unsupported_reference_scope",
                "field": "_engine",
                "project_value": "",
                "reference_value": "",
                "abs_diff": "",
                "tolerance": "",
                "status": ref.status,
                "reason": ref.reason,
                "reference_role": ref.reference_role,
                "downstream": False,
            })
        engine_results[engine] = engine_summary

    mismatch_counts = {
        name: _count_rows(rows)
        for name, rows in all_mismatches.items()
    }
    for name, rows in all_mismatches.items():
        _write_csv(out_dir / f"mismatches_{name}.csv", pd.DataFrame(rows))

    failed = any(
        result.get("comparison", {}).get("status") == "FAIL"
        for result in engine_results.values()
    )
    ok_engines = [
        name
        for name, result in engine_results.items()
        if result.get("status") == "OK"
    ]
    signal_gate_engines = [
        name
        for name, result in engine_results.items()
        if name in {"vectorbt", "backtrader"}
        and (result.get("comparison") or {}).get("signal_logic", {}).get("status") == "PASS"
        and int(
            (result.get("comparison") or {}).get("signal_logic", {}).get(
                "actionable_mismatch_count",
                (result.get("comparison") or {}).get("signal_logic", {}).get("actionable", 1),
            )
        ) == 0
    ]
    required_ok_engines = 2
    summary = {
        "validation_id": validation_id,
        "run_id": bundle.run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "FAIL" if failed else ("PASS" if ok_engines else "SKIP"),
        "admissibility": "advisory_only",
        "promotion_gate_evidence": False,
        "engine_quorum": {
            "required_ok_engines": required_ok_engines,
            "ok_engines": ok_engines,
            "met": len(ok_engines) >= required_ok_engines,
        },
        "signal_logic_gate": {
            "required_passing_engines": 1,
            "eligible_engines": ["vectorbt", "backtrader"],
            "passing_engines": signal_gate_engines,
            "passed": len(signal_gate_engines) >= 1,
        },
        "materialized_from_sweep_summary": _materialized_from_sweep_summary(bundle.result),
        "artifact_dir": str(bundle.run_dir),
        "output_dir": str(out_dir),
        "ohlcv_source_validation": "deferred",
        "engines": engine_results,
        "mismatch_counts": mismatch_counts,
        "actionable_mismatch_counts": {
            name: counts["actionable"] for name, counts in mismatch_counts.items()
        },
        "downstream_mismatch_counts": {
            name: counts["downstream"] for name, counts in mismatch_counts.items()
        },
        "actionable_mismatch_count": sum(count["actionable"] for count in mismatch_counts.values()),
        "downstream_mismatch_count": sum(count["downstream"] for count in mismatch_counts.values()),
        "categories": sorted({
            str(row.get("category"))
            for rows in all_mismatches.values()
            for row in rows
            if row.get("category")
        }),
        "tolerances": tolerances.__dict__,
    }
    (out_dir / "validation_result.json").write_text(
        json.dumps(_json_safe(summary), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return summary


def run_strategy_differential_validation(
    results_dir: str | Path,
    strategy: str,
    engines: Iterable[str] | None = None,
    fixture_run_id: str | None = None,
    output_dir: str | Path | None = None,
    validation_id: str | None = None,
) -> dict[str, Any]:
    root = Path(results_dir)
    clean_strategy = Path(strategy).name
    if not clean_strategy:
        raise ValueError("strategy is required")
    fixture_dir = _resolve_strategy_fixture(root, clean_strategy, fixture_run_id)
    validation_id = validation_id or _build_validation_id()
    out_dir = Path(output_dir) if output_dir else root / STRATEGY_VALIDATION_DIR / clean_strategy / validation_id
    summary = run_differential_validation(
        run_dir=fixture_dir,
        engines=engines,
        output_dir=out_dir,
        validation_id=validation_id,
    )
    summary.update({
        "validation_scope": "strategy",
        "strategy": clean_strategy,
        "fixture_run_id": fixture_dir.name,
        "source_run_result_mutated": False,
        "result_json_mutation": "none",
        "evidence_path": str(out_dir / "validation_result.json"),
    })
    (out_dir / "validation_result.json").write_text(
        json.dumps(_json_safe(summary), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return summary


def compare_reference(
    bundle: ArtifactBundle,
    reference: ReferenceResult,
    tolerances: ValidationTolerances,
) -> dict[str, Any]:
    indicator_rows, indicator_failed = _compare_indicators(
        bundle.indicator_series,
        reference.indicator_series,
        reference.engine,
        tolerances,
    )
    signal_rows, signal_failed = _compare_signals(bundle.signals, reference.signals, reference.engine)
    reference_full = reference.reference_role == "reference_full"
    trade_rows, trade_failed = _compare_trades(
        _project_execution_points(bundle),
        _normalize_reference_trades(reference.trades),
        reference.engine,
        tolerances,
        downstream=signal_failed,
    )
    pnl_rows, pnl_failed = _compare_equity(
        _normalize_equity(bundle.equity_curve),
        _normalize_equity(reference.equity_curve),
        reference.engine,
        tolerances,
        downstream=signal_failed or (reference_full and trade_failed),
    )
    metric_rows, metric_failed = _compare_metrics(
        bundle,
        reference,
        tolerances,
        downstream=signal_failed or (reference_full and (trade_failed or pnl_failed)),
    )
    strict_scopes = {"signal_logic"}
    if reference_full:
        strict_scopes.update({"trade_execution", "pnl_semantics", "metrics"})
    failed = signal_failed or (
        reference_full and (trade_failed or pnl_failed or metric_failed)
    )
    indicator_skipped = bundle.indicator_series.empty and reference.indicator_series.empty
    scopes = {
        "indicator_values": _scope_summary(
            "advisory",
            indicator_rows,
            indicator_failed,
            skipped=indicator_skipped,
        ),
        "signal_logic": _scope_summary("reference", signal_rows, signal_failed),
        "trade_execution": _scope_summary(
            "reference" if reference.reference_role == "reference_full" else "advisory",
            trade_rows,
            trade_failed,
        ),
        "pnl_semantics": _scope_summary(
            "reference" if reference.reference_role == "reference_full" else "advisory",
            pnl_rows,
            pnl_failed,
        ),
        "metrics": _scope_summary(
            "reference" if reference.reference_role == "reference_full" else "advisory",
            metric_rows,
            metric_failed,
        ),
    }
    all_rows = {
        "indicators": indicator_rows,
        "signals": signal_rows,
        "trades": trade_rows,
        "pnl": pnl_rows,
        "metrics": metric_rows,
    }
    row_counts = {name: _count_rows(rows) for name, rows in all_rows.items()}
    scope_aliases = {
        name: dict(scopes[name])
        for name in ("signal_logic", "pnl_semantics", "metrics")
        if name in scopes
    }
    return {
        "summary": {
            "status": _comparison_status(scopes, failed),
            "reference_role": reference.reference_role,
            "strict_scopes": sorted(strict_scopes),
            "advisory_scopes": sorted(set(scopes) - strict_scopes),
            "scopes": scopes,
            **scope_aliases,
            "mismatch_counts": row_counts,
            "actionable_mismatch_counts": {
                name: counts["actionable"] for name, counts in row_counts.items()
            },
            "downstream_mismatch_counts": {
                name: counts["downstream"] for name, counts in row_counts.items()
            },
            "actionable_mismatch_count": sum(count["actionable"] for count in row_counts.values()),
            "downstream_mismatch_count": sum(count["downstream"] for count in row_counts.values()),
            "indicator_mismatches": len(indicator_rows),
            "signal_mismatches": len(signal_rows),
            "trade_mismatches": len(trade_rows),
            "pnl_mismatches": len(pnl_rows),
            "metric_mismatches": len(metric_rows),
        },
        "mismatches": all_rows,
    }


class ReferenceAdapter:
    engine = ""
    dependency = ""

    def run(self, bundle: ArtifactBundle) -> ReferenceResult:
        out_of_scope = self._out_of_scope(bundle)
        if out_of_scope is not None:
            return out_of_scope
        if self.dependency and importlib.util.find_spec(self.dependency) is None:
            return ReferenceResult(
                engine=self.engine,
                status="SKIP",
                reason=f"optional dependency '{self.dependency}' is not installed",
                reference_role="skipped_dependency",
                categories=["unsupported_reference_scope"],
                metadata={"dependency": self.dependency},
            )
        try:
            return self._run_available(bundle)
        except Exception as exc:
            return ReferenceResult(
                engine=self.engine,
                status="FAIL",
                reason=str(exc),
                reference_role="advisory",
                categories=["unsupported_reference_scope"],
                metadata={"exception_type": type(exc).__name__},
            )

    def _run_available(self, bundle: ArtifactBundle) -> ReferenceResult:
        raise NotImplementedError

    def _out_of_scope(self, bundle: ArtifactBundle) -> ReferenceResult | None:
        return None


class VectorBTReferenceAdapter(ReferenceAdapter):
    engine = "vectorbt"
    dependency = "vectorbt"

    def _out_of_scope(self, bundle: ArtifactBundle) -> ReferenceResult | None:
        strategy = bundle.primary_strategy
        if strategy not in TECHNICAL_STRATEGIES:
            return ReferenceResult(
                engine=self.engine,
                status="SKIP",
                reason=f"vectorbt v1 adapter supports technical strategies only, got {strategy}",
                reference_role="not_applicable",
                categories=["unsupported_reference_scope"],
            )
        return None

    def _run_available(self, bundle: ArtifactBundle) -> ReferenceResult:
        import vectorbt as vbt

        strategy = bundle.primary_strategy
        indicator_series = _technical_reference_indicator_series(bundle, strategy)
        signals = _technical_reference_signals(bundle, strategy)
        trades, fallback_equity = _simulate_long_flat_trades(bundle, signals)
        prices = _price_frame_for_primary_symbol(bundle)
        close = pd.Series(
            prices["close"].astype(float).to_numpy(),
            index=pd.DatetimeIndex(pd.to_datetime(prices["datetime"], utc=True)),
        )
        entries = pd.Series(False, index=close.index)
        exits = pd.Series(False, index=close.index)
        for _, row in signals.iterrows():
            dt = _to_datetime(row.get("datetime", row.get("ts")))
            if pd.isna(dt) or dt not in close.index:
                continue
            if str(row.get("side")) == "buy":
                entries.loc[dt] = True
            elif str(row.get("side")) == "sell":
                exits.loc[dt] = True
        try:
            portfolio = vbt.Portfolio.from_signals(
                close,
                entries=entries,
                exits=exits,
                init_cash=bundle.initial_equity,
                fees=0.0,
                freq=_bar_freq(bundle.bar),
            )
            value = portfolio.value()
            equity = pd.DataFrame({
                "datetime": [_iso(ts) for ts in pd.DatetimeIndex(value.index)],
                "equity": value.to_numpy(dtype=float),
            })
        except Exception:
            equity = fallback_equity
        metrics = neutral_metrics(equity, bundle.periods)
        return ReferenceResult(
            engine=self.engine,
            status="OK",
            reason="indicator/signal comparison is strict; PnL/equity semantics are advisory in v1",
            reference_role="reference_signals_only",
            indicator_series=indicator_series,
            signals=signals,
            trades=trades,
            equity_curve=equity,
            metrics=metrics,
            metadata={
                "strategy": strategy,
                "portfolio_engine": "vectorbt.Portfolio.from_signals",
                "signal_position_source": _signal_position_source(bundle),
            },
        )


class BacktraderReferenceAdapter(ReferenceAdapter):
    engine = "backtrader"
    dependency = "backtrader"

    def _out_of_scope(self, bundle: ArtifactBundle) -> ReferenceResult | None:
        strategy = bundle.primary_strategy
        if strategy not in TECHNICAL_STRATEGIES:
            return ReferenceResult(
                engine=self.engine,
                status="SKIP",
                reason=f"backtrader v1 adapter supports bar-level technical strategies only, got {strategy}",
                reference_role="not_applicable",
                categories=["unsupported_reference_scope"],
            )
        return None

    def _run_available(self, bundle: ArtifactBundle) -> ReferenceResult:
        import backtrader as bt

        strategy = bundle.primary_strategy
        indicator_series = _technical_reference_indicator_series(bundle, strategy)
        signals, trades, equity = _run_backtrader_technical_reference(bt, bundle, strategy)
        metrics = neutral_metrics(equity, bundle.periods)
        return ReferenceResult(
            engine=self.engine,
            status="OK",
            reason=(
                "signal timing is strict; Backtrader runs project-compatible "
                "indicator state, while PnL/equity semantics are advisory in v1"
            ),
            reference_role="reference_signals_only",
            indicator_series=indicator_series,
            signals=signals,
            trades=trades,
            equity_curve=equity,
            metrics=metrics,
            metadata={
                "strategy": strategy,
                "order_semantics": "backtrader_market_orders",
                "signal_position_source": _signal_position_source(bundle),
            },
        )


class NautilusReferenceAdapter(ReferenceAdapter):
    engine = "nautilus"
    dependency = "nautilus_trader"

    def _out_of_scope(self, bundle: ArtifactBundle) -> ReferenceResult | None:
        strategy = bundle.primary_strategy
        if strategy not in {"as_market_maker", "obi_market_maker"}:
            return ReferenceResult(
                engine=self.engine,
                status="SKIP",
                reason=f"nautilus v1 adapter is reserved for execution-sensitive strategies, got {strategy}",
                reference_role="not_applicable",
                categories=["unsupported_reference_scope"],
            )
        return None

    def _run_available(self, bundle: ArtifactBundle) -> ReferenceResult:
        return ReferenceResult(
            engine=self.engine,
            status="SKIP",
            reason="Nautilus catalog/L2 adapter is not available for this artifact yet",
            reference_role="not_applicable",
            categories=["unsupported_reference_scope"],
            metadata={"required_data": "L1/L2/L3 catalog"},
        )


def neutral_metrics(equity_curve: pd.DataFrame, periods: int) -> dict[str, float]:
    equity = _normalize_equity(equity_curve)
    if equity.empty:
        return {"sharpe": 0.0, "max_drawdown": 0.0, "total_return": 0.0}
    returns = equity["equity"].astype(float).pct_change().fillna(0.0)
    return {
        "sharpe": sharpe(returns, periods=periods),
        "max_drawdown": max_drawdown(returns),
        "total_return": float(equity["equity"].iloc[-1] / equity["equity"].iloc[0] - 1.0)
        if float(equity["equity"].iloc[0]) != 0
        else 0.0,
    }


def list_validation_results(run_dir: str | Path) -> list[dict[str, Any]]:
    root = Path(run_dir) / "validation"
    if not root.exists():
        return []
    rows = []
    for path in sorted(root.glob("*/validation_result.json"), reverse=True):
        try:
            payload = _read_json(path)
        except Exception:
            continue
        rows.append({
            "validation_id": payload.get("validation_id", path.parent.name),
            "run_id": payload.get("run_id", Path(run_dir).name),
            "created_at": payload.get("created_at"),
            "status": payload.get("status"),
            "admissibility": payload.get("admissibility"),
            "promotion_gate_evidence": payload.get("promotion_gate_evidence"),
            "signal_logic_gate": payload.get("signal_logic_gate"),
            "materialized_from_sweep_summary": bool(payload.get("materialized_from_sweep_summary")),
            "engines": list((payload.get("engines") or {}).keys()),
            "mismatch_counts": payload.get("mismatch_counts", {}),
        })
    return rows


def list_strategy_validation_fixtures(results_dir: str | Path, strategy: str | None = None) -> list[dict[str, Any]]:
    root = Path(results_dir)
    clean_strategy = Path(strategy).name if strategy else ""
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    if not root.exists():
        return rows
    for run_dir in sorted(root.iterdir(), key=lambda p: p.stat().st_mtime if p.exists() else 0.0, reverse=True):
        if not run_dir.is_dir() or run_dir.name == STRATEGY_VALIDATION_DIR:
            continue
        row = _strategy_fixture_row(run_dir, clean_strategy)
        if row is not None:
            seen.add(str(row["run_id"]))
            rows.append(row)
    for row in _parameter_sweep_fixture_rows_for_listing(root, clean_strategy):
        run_id = str(row.get("run_id") or "")
        if run_id and run_id not in seen:
            seen.add(run_id)
            rows.append(row)
    return rows


def list_strategy_validation_results(results_dir: str | Path, strategy: str | None = None) -> list[dict[str, Any]]:
    root = Path(results_dir) / STRATEGY_VALIDATION_DIR
    if not root.exists():
        return []
    strategy_dirs = [root / Path(strategy).name] if strategy else [path for path in root.iterdir() if path.is_dir()]
    rows: list[dict[str, Any]] = []
    for strategy_dir in strategy_dirs:
        if not strategy_dir.exists():
            continue
        for path in sorted(strategy_dir.glob("*/validation_result.json"), reverse=True):
            try:
                payload = _read_json(path)
            except Exception:
                continue
            rows.append({
                "validation_id": payload.get("validation_id", path.parent.name),
                "validation_scope": payload.get("validation_scope", "strategy"),
                "strategy": payload.get("strategy", strategy_dir.name),
                "fixture_run_id": payload.get("fixture_run_id"),
                "materialized_from_sweep_summary": bool(payload.get("materialized_from_sweep_summary")),
                "created_at": payload.get("created_at"),
                "status": payload.get("status"),
                "admissibility": payload.get("admissibility"),
                "promotion_gate_evidence": payload.get("promotion_gate_evidence"),
                "signal_logic_gate": payload.get("signal_logic_gate"),
                "engines": list((payload.get("engines") or {}).keys()),
                "mismatch_counts": payload.get("mismatch_counts", {}),
            })
    return rows


def read_validation_result(run_dir: str | Path, validation_id: str) -> dict[str, Any]:
    safe_id = Path(validation_id).name
    path = Path(run_dir) / "validation" / safe_id / "validation_result.json"
    if not path.exists():
        raise FileNotFoundError(str(path))
    return _read_json(path)


def read_strategy_validation_result(results_dir: str | Path, strategy: str, validation_id: str) -> dict[str, Any]:
    safe_strategy = Path(strategy).name
    safe_id = Path(validation_id).name
    path = Path(results_dir) / STRATEGY_VALIDATION_DIR / safe_strategy / safe_id / "validation_result.json"
    if not path.exists():
        raise FileNotFoundError(str(path))
    return _read_json(path)


def read_validation_artifact(run_dir: str | Path, validation_id: str, artifact_name: str) -> list[dict[str, Any]]:
    safe_id = Path(validation_id).name
    safe_name = Path(artifact_name).name
    path = Path(run_dir) / "validation" / safe_id / safe_name
    if not path.exists():
        raise FileNotFoundError(str(path))
    try:
        return _df_records(pd.read_csv(path))
    except pd.errors.EmptyDataError:
        return []


def read_strategy_validation_artifact(
    results_dir: str | Path,
    strategy: str,
    validation_id: str,
    artifact_name: str,
) -> list[dict[str, Any]]:
    safe_strategy = Path(strategy).name
    safe_id = Path(validation_id).name
    safe_name = Path(artifact_name).name
    path = Path(results_dir) / STRATEGY_VALIDATION_DIR / safe_strategy / safe_id / safe_name
    if not path.exists():
        raise FileNotFoundError(str(path))
    try:
        return _df_records(pd.read_csv(path))
    except pd.errors.EmptyDataError:
        return []


def _technical_reference_indicator_series(bundle: ArtifactBundle, strategy: str) -> pd.DataFrame:
    prices = bundle.price_series.copy()
    if prices.empty or "close" not in prices.columns:
        return pd.DataFrame(columns=_indicator_columns())
    if "inst_id" not in prices.columns:
        prices["inst_id"] = bundle.symbols[0] if bundle.symbols else ""
    if "ts" not in prices.columns:
        prices["ts"] = [_ts_ms(_to_datetime(row)) for row in _series_time(prices)]
    prices["datetime"] = [_iso(_to_datetime(row)) for row in _series_time(prices)]
    params = bundle.strategy_params(strategy)
    frames: list[pd.DataFrame] = []
    for inst_id, group in prices.sort_values(["inst_id", "ts"]).groupby("inst_id", sort=False):
        sub = group.reset_index(drop=True)
        close = sub["close"].astype(float)
        fast = pd.Series(float("nan"), index=close.index)
        slow = pd.Series(float("nan"), index=close.index)
        macd = pd.Series(float("nan"), index=close.index)
        macd_signal = pd.Series(float("nan"), index=close.index)
        macd_hist = pd.Series(float("nan"), index=close.index)
        if strategy == "ma_crossover":
            fast_window = int(params.get("fast_window", 20))
            slow_window = int(params.get("slow_window", 50))
            fast = close.rolling(fast_window, min_periods=fast_window).mean()
            slow = close.rolling(slow_window, min_periods=slow_window).mean()
        elif strategy == "ema_crossover":
            fast_span = int(params.get("fast_span", 20))
            slow_span = int(params.get("slow_span", 50))
            fast = close.ewm(span=fast_span, adjust=False).mean()
            slow = close.ewm(span=slow_span, adjust=False).mean()
        elif strategy == "macd_crossover":
            fast_span = int(params.get("fast_span", 12))
            slow_span = int(params.get("slow_span", 26))
            signal_span = int(params.get("signal_span", 9))
            fast_ema = close.ewm(span=fast_span, adjust=False).mean()
            slow_ema = close.ewm(span=slow_span, adjust=False).mean()
            macd = fast_ema - slow_ema
            macd_signal = macd.ewm(span=signal_span, adjust=False).mean()
            macd_hist = macd - macd_signal
            fast = fast_ema
            slow = slow_ema
        else:
            continue
        out = pd.DataFrame({
            "ts": sub["ts"].tolist(),
            "datetime": sub["datetime"].tolist(),
            "inst_id": str(inst_id),
            "strategy": strategy,
            "close": close.to_numpy(dtype=float),
            "fast_value": fast.to_numpy(dtype=float),
            "slow_value": slow.to_numpy(dtype=float),
            "macd": macd.to_numpy(dtype=float),
            "macd_signal": macd_signal.to_numpy(dtype=float),
            "macd_histogram": macd_hist.to_numpy(dtype=float),
            "warmup_source": "reference_cold",
        })
        finite_mask = out["fast_value"].apply(_is_finite_number) | out["slow_value"].apply(_is_finite_number)
        if finite_mask.any():
            out = out.loc[finite_mask[finite_mask].index[0]:]
        frames.append(out)
    if not frames:
        return pd.DataFrame(columns=_indicator_columns())
    return pd.concat(frames, ignore_index=True)[_indicator_columns()]


def _technical_reference_signals(bundle: ArtifactBundle, strategy: str) -> pd.DataFrame:
    prices = _price_frame_for_primary_symbol(bundle)
    params = bundle.strategy_params(strategy)
    close = prices["close"].astype(float)
    position_before = _execution_position_before_by_datetime(bundle, prices)
    has_execution_position = bool(position_before)
    if strategy == "ma_crossover":
        fast_window = int(params.get("fast_window", 20))
        slow_window = int(params.get("slow_window", 50))
        fast = close.rolling(fast_window).mean()
        slow = close.rolling(slow_window).mean()
        warmup = slow_window
    elif strategy == "ema_crossover":
        fast_span = int(params.get("fast_span", 20))
        slow_span = int(params.get("slow_span", 50))
        fast = close.ewm(span=fast_span, adjust=False).mean()
        slow = close.ewm(span=slow_span, adjust=False).mean()
        warmup = slow_span
    else:
        fast_span = int(params.get("fast_span", 12))
        slow_span = int(params.get("slow_span", 26))
        signal_span = int(params.get("signal_span", 9))
        fast_ema = close.ewm(span=fast_span, adjust=False).mean()
        slow_ema = close.ewm(span=slow_span, adjust=False).mean()
        fast = fast_ema - slow_ema
        slow = fast.ewm(span=signal_span, adjust=False).mean()
        warmup = slow_span + signal_span

    rows = []
    in_position = False
    for i in range(len(close)):
        if i < warmup or i == 0:
            continue
        prev_fast = fast.iloc[i - 1]
        prev_slow = slow.iloc[i - 1]
        cur_fast = fast.iloc[i]
        cur_slow = slow.iloc[i]
        if any(pd.isna(v) for v in (prev_fast, prev_slow, cur_fast, cur_slow)):
            continue
        crossed_up = prev_fast <= prev_slow and cur_fast > cur_slow
        crossed_down = prev_fast >= prev_slow and cur_fast < cur_slow
        dt_key = _iso(_to_datetime(prices.iloc[i].get("datetime", prices.iloc[i].get("ts"))))
        effective_in_position = (
            abs(position_before.get(dt_key, 0.0)) > 1e-12
            if has_execution_position
            else in_position
        )
        if crossed_up and not effective_in_position:
            if not has_execution_position:
                in_position = True
            rows.append(_signal_row(prices.iloc[i], strategy, "buy"))
        elif crossed_down and effective_in_position:
            if not has_execution_position:
                in_position = False
            rows.append(_signal_row(prices.iloc[i], strategy, "sell"))
    return pd.DataFrame(rows, columns=["ts", "datetime", "strategy", "inst_id", "side", "fair_value"])


def _signal_position_source(bundle: ArtifactBundle) -> str:
    if not bundle.trades.empty and "size_after" in bundle.trades.columns:
        return "artifact_trades_size_after"
    return "reference_local_long_flat"


def _execution_position_before_by_datetime(
    bundle: ArtifactBundle,
    prices: pd.DataFrame,
) -> dict[str, float]:
    if bundle.trades.empty or "size_after" not in bundle.trades.columns:
        return {}
    trades = bundle.trades.copy()
    if "datetime" not in trades.columns and "ts" not in trades.columns:
        return {}
    symbol = bundle.symbols[0] if bundle.symbols else None
    if symbol and "inst_id" in trades.columns:
        trades = trades[trades["inst_id"].astype(str) == symbol].copy()
    if "strategy" in trades.columns:
        trades = trades[trades["strategy"].astype(str) == bundle.primary_strategy].copy()
    if trades.empty:
        return {}
    trades["_dt"] = [_to_datetime(row) for row in _series_time(trades)]
    trades = trades.dropna(subset=["_dt"]).sort_values("_dt").reset_index(drop=True)
    if trades.empty:
        return {}

    out: dict[str, float] = {}
    trade_idx = 0
    position_size = 0.0
    for _, row in prices.sort_values("datetime").iterrows():
        dt = _to_datetime(row.get("datetime", row.get("ts")))
        if pd.isna(dt):
            continue
        while trade_idx < len(trades) and trades.loc[trade_idx, "_dt"] < dt:
            position_size = _safe_float(trades.loc[trade_idx, "size_after"], position_size)
            trade_idx += 1
        out[_iso(dt)] = position_size
    return out


def _update_ema(previous: float | None, value: float, span: int) -> float:
    if previous is None:
        return float(value)
    alpha = 2.0 / (float(span) + 1.0)
    return alpha * float(value) + (1.0 - alpha) * previous


def _simulate_long_flat_trades(
    bundle: ArtifactBundle,
    signals: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    prices = _price_frame_for_primary_symbol(bundle)
    equity = float(bundle.initial_equity)
    position_qty = 0.0
    entry_price = float("nan")
    trade_rows = []
    equity_rows = []
    signal_by_ts = {
        _to_datetime(row["datetime"] if row.get("datetime") else row["ts"]): row
        for _, row in signals.iterrows()
    }
    for _, price_row in prices.iterrows():
        dt = _to_datetime(price_row["datetime"] if price_row.get("datetime") else price_row["ts"])
        close = _safe_float(price_row.get("close"), float("nan"))
        sig = signal_by_ts.get(dt)
        if sig is not None and str(sig.get("side")) == "buy" and position_qty == 0.0 and close > 0:
            position_qty = equity / close
            entry_price = close
            trade_rows.append({
                "ts": _ts_ms(dt),
                "datetime": _iso(dt),
                "strategy": bundle.primary_strategy,
                "inst_id": price_row.get("inst_id", ""),
                "side": "buy",
                "price": close,
                "qty": position_qty,
                "pnl": 0.0,
                "equity_after": equity,
            })
        elif sig is not None and str(sig.get("side")) == "sell" and position_qty > 0.0:
            pnl = position_qty * (close - entry_price)
            equity += pnl
            trade_rows.append({
                "ts": _ts_ms(dt),
                "datetime": _iso(dt),
                "strategy": bundle.primary_strategy,
                "inst_id": price_row.get("inst_id", ""),
                "side": "sell",
                "price": close,
                "qty": position_qty,
                "pnl": pnl,
                "equity_after": equity,
            })
            position_qty = 0.0
            entry_price = float("nan")
        marked_equity = equity
        if position_qty > 0.0 and math.isfinite(entry_price):
            marked_equity = equity + position_qty * (close - entry_price)
        equity_rows.append({
            "ts": _ts_ms(dt),
            "datetime": _iso(dt),
            "equity": marked_equity,
        })
    return pd.DataFrame(trade_rows), pd.DataFrame(equity_rows)


def _run_backtrader_technical_reference(bt: Any, bundle: ArtifactBundle, strategy_name: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    prices = _price_frame_for_primary_symbol(bundle)
    params = bundle.strategy_params(strategy_name)
    position_before = _execution_position_before_by_datetime(bundle, prices)
    has_execution_position = bool(position_before)
    data = prices.copy()
    data["datetime"] = pd.to_datetime(data["datetime"], utc=True)
    data = data.set_index("datetime")
    data = data.rename(columns={"vol": "volume"})

    signal_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    equity_rows: list[dict[str, Any]] = []

    class TechnicalStrategy(bt.Strategy):
        def __init__(self):
            self.pending_order = None
            self.closes: list[float] = []
            self.prev_fast: float | None = None
            self.prev_slow: float | None = None
            self.signal_in_position = False
            self.fast_ema: float | None = None
            self.slow_ema: float | None = None
            self.signal_ema: float | None = None
            if strategy_name == "ma_crossover":
                self.fast_window = int(params.get("fast_window", 20))
                self.slow_window = int(params.get("slow_window", 50))
                self.warmup = int(params.get("slow_window", 50))
            elif strategy_name == "ema_crossover":
                self.fast_span = int(params.get("fast_span", 20))
                self.slow_span = int(params.get("slow_span", 50))
                self.warmup = int(params.get("slow_span", 50))
            else:
                self.fast_span = int(params.get("fast_span", 12))
                self.slow_span = int(params.get("slow_span", 26))
                self.signal_span = int(params.get("signal_span", 9))
                self.warmup = int(params.get("slow_span", 26)) + int(params.get("signal_span", 9))

        def _indicator_values(self, close_value: float) -> tuple[float, float]:
            self.closes.append(float(close_value))
            if strategy_name == "ma_crossover":
                fast = (
                    float(pd.Series(self.closes[-self.fast_window:], dtype=float).mean())
                    if len(self.closes) >= self.fast_window
                    else float("nan")
                )
                slow = (
                    float(pd.Series(self.closes[-self.slow_window:], dtype=float).mean())
                    if len(self.closes) >= self.slow_window
                    else float("nan")
                )
                return fast, slow
            if strategy_name == "ema_crossover":
                self.fast_ema = _update_ema(self.fast_ema, close_value, self.fast_span)
                self.slow_ema = _update_ema(self.slow_ema, close_value, self.slow_span)
                return self.fast_ema, self.slow_ema

            self.fast_ema = _update_ema(self.fast_ema, close_value, self.fast_span)
            self.slow_ema = _update_ema(self.slow_ema, close_value, self.slow_span)
            macd_value = self.fast_ema - self.slow_ema
            self.signal_ema = _update_ema(self.signal_ema, macd_value, self.signal_span)
            return macd_value, self.signal_ema

        def next(self):
            dt = _ensure_utc_timestamp(pd.Timestamp(bt.num2date(self.datas[0].datetime[0])))
            dt_key = _iso(dt)
            close_value = float(self.datas[0].close[0])
            cur_fast, cur_slow = self._indicator_values(close_value)
            equity_rows.append({
                "ts": _ts_ms(dt),
                "datetime": dt_key,
                "equity": float(self.broker.getvalue()),
            })
            if len(self.closes) < self.warmup:
                return
            prev_fast = self.prev_fast
            prev_slow = self.prev_slow
            self.prev_fast = cur_fast
            self.prev_slow = cur_slow
            if prev_fast is None or prev_slow is None:
                return
            if any(pd.isna(v) for v in (prev_fast, prev_slow, cur_fast, cur_slow)):
                return
            crossed_up = prev_fast <= prev_slow and cur_fast > cur_slow
            crossed_down = prev_fast >= prev_slow and cur_fast < cur_slow
            effective_in_position = (
                abs(position_before.get(dt_key, 0.0)) > 1e-12
                if has_execution_position
                else self.signal_in_position
            )
            inst_id = prices["inst_id"].iloc[0] if "inst_id" in prices.columns and not prices.empty else ""
            if crossed_up and not effective_in_position:
                signal_rows.append({
                    "ts": _ts_ms(dt),
                    "datetime": dt_key,
                    "strategy": strategy_name,
                    "inst_id": inst_id,
                    "side": "buy",
                    "fair_value": close_value,
                })
                if not has_execution_position:
                    self.signal_in_position = True
                if self.pending_order is None:
                    self.pending_order = self.buy()
            elif crossed_down and effective_in_position:
                signal_rows.append({
                    "ts": _ts_ms(dt),
                    "datetime": dt_key,
                    "strategy": strategy_name,
                    "inst_id": inst_id,
                    "side": "sell",
                    "fair_value": close_value,
                })
                if not has_execution_position:
                    self.signal_in_position = False
                if self.pending_order is None and self.position:
                    self.pending_order = self.sell(size=abs(self.position.size))

        def notify_order(self, order):
            if order.status not in {order.Completed, order.Canceled, order.Margin, order.Rejected}:
                return
            if order.status == order.Completed:
                dt = _ensure_utc_timestamp(pd.Timestamp(bt.num2date(order.executed.dt)))
                side = "buy" if order.isbuy() else "sell"
                trade_rows.append({
                    "ts": _ts_ms(dt),
                    "datetime": _iso(dt),
                    "strategy": strategy_name,
                    "inst_id": prices["inst_id"].iloc[0] if "inst_id" in prices.columns and not prices.empty else "",
                    "side": side,
                    "price": float(order.executed.price),
                    "qty": abs(float(order.executed.size)),
                    "pnl": 0.0,
                    "equity_after": float(self.broker.getvalue()),
                })
            self.pending_order = None

        def notify_trade(self, trade):
            if not trade.isclosed or not trade_rows:
                return
            trade_rows[-1]["pnl"] = float(trade.pnlcomm)

    cerebro = bt.Cerebro(stdstats=False)
    cerebro.broker.setcash(float(bundle.initial_equity))
    feed = bt.feeds.PandasData(
        dataname=data,
        open="open",
        high="high",
        low="low",
        close="close",
        volume="volume",
        openinterest=None,
    )
    cerebro.adddata(feed)
    cerebro.addstrategy(TechnicalStrategy)
    cerebro.run()
    return pd.DataFrame(signal_rows), pd.DataFrame(trade_rows), pd.DataFrame(equity_rows)


def _compare_indicators(
    project: pd.DataFrame,
    reference: pd.DataFrame,
    engine: str,
    tolerances: ValidationTolerances,
) -> tuple[list[dict], bool]:
    project_norm = _normalize_indicators(project)
    reference_norm = _normalize_indicators(reference)
    if project_norm.empty and reference_norm.empty:
        return [], False
    key_fields = ["datetime", "inst_id", "strategy", "_sequence"]
    merged = project_norm.merge(
        reference_norm,
        on=key_fields,
        how="outer",
        suffixes=("_project", "_reference"),
        indicator=True,
    )
    rows = []
    indicator_fields = ["close", "fast_value", "slow_value", "macd", "macd_signal", "macd_histogram"]
    for i, row in merged.iterrows():
        if row["_merge"] != "both":
            rows.append(_mismatch(
                engine,
                "indicator_mismatch",
                "indicator_row",
                i,
                row.get("_merge"),
                "",
                "row_mismatch",
            ))
            continue
        for field in indicator_fields:
            pv = _safe_float(row.get(f"{field}_project"), float("nan"))
            rv = _safe_float(row.get(f"{field}_reference"), float("nan"))
            if not _within_tol(pv, rv, tolerances.indicator_abs, tolerances.indicator_rel):
                rows.append(_mismatch(
                    engine,
                    "indicator_mismatch",
                    field,
                    i,
                    pv,
                    rv,
                    "value_mismatch",
                    abs_diff=_abs_diff(pv, rv),
                    tolerance=_tol_label(tolerances.indicator_abs, tolerances.indicator_rel),
                ))
    return rows, bool(rows)


def _compare_signals(project: pd.DataFrame, reference: pd.DataFrame, engine: str) -> tuple[list[dict], bool]:
    project_norm = _normalize_signals(project)
    reference_norm = _normalize_signals(reference)
    rows = []
    max_len = max(len(project_norm), len(reference_norm))
    for i in range(max_len):
        if i >= len(project_norm):
            rows.append(_mismatch(engine, "strategy_logic_mismatch", "signal", i, "missing", "present", "missing_in_project"))
            continue
        if i >= len(reference_norm):
            rows.append(_mismatch(engine, "strategy_logic_mismatch", "signal", i, "present", "missing", "missing_in_reference"))
            continue
        p = project_norm.iloc[i]
        r = reference_norm.iloc[i]
        for field in ("datetime", "inst_id", "side"):
            if str(p.get(field, "")) != str(r.get(field, "")):
                rows.append(_mismatch(
                    engine,
                    "strategy_logic_mismatch",
                    field,
                    i,
                    p.get(field, ""),
                    r.get(field, ""),
                    "value_mismatch",
                ))
    return rows, bool(rows)


def _compare_trades(
    project: pd.DataFrame,
    reference: pd.DataFrame,
    engine: str,
    tolerances: ValidationTolerances,
    downstream: bool = False,
) -> tuple[list[dict], bool]:
    rows = []
    max_len = max(len(project), len(reference))
    for i in range(max_len):
        if i >= len(project):
            rows.append(_mismatch(engine, "execution_semantics_mismatch", "trade", i, "missing", "present", "missing_in_project", downstream=downstream))
            continue
        if i >= len(reference):
            rows.append(_mismatch(engine, "execution_semantics_mismatch", "trade", i, "present", "missing", "missing_in_reference", downstream=downstream))
            continue
        p = project.iloc[i]
        r = reference.iloc[i]
        if str(p.get("side", "")) != str(r.get("side", "")):
            rows.append(_mismatch(engine, "execution_semantics_mismatch", "side", i, p.get("side", ""), r.get("side", ""), "value_mismatch", downstream=downstream))
        for field, abs_tol, rel_tol in (
            ("price", tolerances.price_abs, tolerances.price_rel),
            ("qty", tolerances.qty_abs, tolerances.qty_rel),
            ("pnl", tolerances.pnl_abs, tolerances.pnl_rel),
        ):
            pv = _safe_float(p.get(field), float("nan"))
            rv = _safe_float(r.get(field), float("nan"))
            if field == "pnl" and not (math.isfinite(pv) or math.isfinite(rv)):
                continue
            if not _within_tol(pv, rv, abs_tol, rel_tol):
                rows.append(_mismatch(
                    engine,
                    "pnl_accounting_mismatch" if field == "pnl" else "execution_semantics_mismatch",
                    field,
                    i,
                    pv,
                    rv,
                    "value_mismatch",
                    abs_diff=_abs_diff(pv, rv),
                    tolerance=_tol_label(abs_tol, rel_tol),
                    downstream=downstream,
                ))
    return rows, bool(rows) and not downstream


def _compare_equity(
    project: pd.DataFrame,
    reference: pd.DataFrame,
    engine: str,
    tolerances: ValidationTolerances,
    downstream: bool,
) -> tuple[list[dict], bool]:
    if project.empty or reference.empty:
        if project.empty and reference.empty:
            return [], False
        return [_mismatch(engine, "pnl_accounting_mismatch", "equity_curve", 0, len(project), len(reference), "row_count_mismatch", downstream=downstream)], not downstream
    merged = project[["datetime", "equity"]].merge(
        reference[["datetime", "equity"]],
        on="datetime",
        how="outer",
        suffixes=("_project", "_reference"),
        indicator=True,
    )
    rows = []
    for i, row in merged.iterrows():
        if row["_merge"] != "both":
            rows.append(_mismatch(engine, "pnl_accounting_mismatch", "equity", i, row.get("_merge"), "", "row_mismatch", downstream=downstream))
            continue
        pv = _safe_float(row.get("equity_project"), float("nan"))
        rv = _safe_float(row.get("equity_reference"), float("nan"))
        if not _within_tol(pv, rv, tolerances.equity_abs, tolerances.equity_rel):
            rows.append(_mismatch(
                engine,
                "pnl_accounting_mismatch",
                "equity",
                i,
                pv,
                rv,
                "value_mismatch",
                abs_diff=_abs_diff(pv, rv),
                tolerance=_tol_label(tolerances.equity_abs, tolerances.equity_rel),
                downstream=downstream,
            ))
    return rows, bool(rows) and not downstream


def _compare_metrics(
    bundle: ArtifactBundle,
    reference: ReferenceResult,
    tolerances: ValidationTolerances,
    downstream: bool,
) -> tuple[list[dict], bool]:
    project_metrics = neutral_metrics(bundle.equity_curve, bundle.periods)
    reference_metrics = neutral_metrics(reference.equity_curve, bundle.periods)
    rows = []
    for field in ("sharpe", "max_drawdown", "total_return"):
        pv = _safe_float(project_metrics.get(field), float("nan"))
        rv = _safe_float(reference_metrics.get(field), float("nan"))
        if not _within_tol(pv, rv, tolerances.metric_abs, tolerances.metric_rel):
            rows.append(_mismatch(
                reference.engine,
                "metric_formula_mismatch",
                field,
                0,
                pv,
                rv,
                "value_mismatch",
                abs_diff=_abs_diff(pv, rv),
                tolerance=_tol_label(tolerances.metric_abs, tolerances.metric_rel),
                downstream=downstream,
            ))
    artifact = bundle.result.get("metrics") or {}
    for field in ("sharpe", "max_drawdown", "total_return"):
        pv = _safe_float(artifact.get(field), float("nan"))
        rv = _safe_float(project_metrics.get(field), float("nan"))
        if math.isfinite(pv) and not _within_tol(pv, rv, tolerances.metric_abs, tolerances.metric_rel):
            rows.append(_mismatch(
                reference.engine,
                "metric_formula_mismatch",
                f"artifact_{field}",
                0,
                pv,
                rv,
                "artifact_metric_mismatch",
                abs_diff=_abs_diff(pv, rv),
                tolerance=_tol_label(tolerances.metric_abs, tolerances.metric_rel),
                downstream=False,
            ))
    return rows, bool(rows) and not downstream


def _project_execution_points(bundle: ArtifactBundle) -> pd.DataFrame:
    source = bundle.trades if not bundle.trades.empty else bundle.fills
    if source.empty:
        return pd.DataFrame(columns=["datetime", "side", "price", "qty", "pnl"])
    out = source.copy()
    price_col = "price" if "price" in out.columns else "fill_px"
    qty_col = "qty" if "qty" in out.columns else "fill_sz"
    pnl_col = "pnl" if "pnl" in out.columns else ("net_realized_pnl" if "net_realized_pnl" in out.columns else "realized_pnl")
    return pd.DataFrame({
        "datetime": [_iso(_to_datetime(row)) for row in _series_time(out)],
        "side": out.get("side", pd.Series("", index=out.index)).astype(str).str.lower(),
        "price": _numeric(out.get(price_col, pd.Series(float("nan"), index=out.index))),
        "qty": _numeric(out.get(qty_col, pd.Series(float("nan"), index=out.index))),
        "pnl": _numeric(out.get(pnl_col, pd.Series(float("nan"), index=out.index))),
    }).reset_index(drop=True)


def _normalize_reference_trades(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=["datetime", "side", "price", "qty", "pnl"])
    out = trades.copy()
    return pd.DataFrame({
        "datetime": [_iso(_to_datetime(row)) for row in _series_time(out)],
        "side": out.get("side", pd.Series("", index=out.index)).astype(str).str.lower(),
        "price": _numeric(out.get("price", out.get("fill_px", pd.Series(float("nan"), index=out.index)))),
        "qty": _numeric(out.get("qty", out.get("fill_sz", pd.Series(float("nan"), index=out.index)))),
        "pnl": _numeric(out.get("pnl", out.get("net_realized_pnl", pd.Series(float("nan"), index=out.index)))),
    }).reset_index(drop=True)


def _normalize_signals(signals: pd.DataFrame) -> pd.DataFrame:
    if signals.empty:
        return pd.DataFrame(columns=["datetime", "inst_id", "side"])
    out = signals.copy()
    return pd.DataFrame({
        "datetime": [_iso(_to_datetime(row)) for row in _series_time(out)],
        "inst_id": out.get("inst_id", pd.Series("", index=out.index)).astype(str),
        "side": out.get("side", pd.Series("", index=out.index)).astype(str).str.lower(),
    }).sort_values(["datetime", "inst_id", "side"]).reset_index(drop=True)


def _normalize_indicators(indicators: pd.DataFrame) -> pd.DataFrame:
    columns = ["datetime", "inst_id", "strategy", "_sequence", "close", "fast_value", "slow_value", "macd", "macd_signal", "macd_histogram"]
    if indicators.empty:
        return pd.DataFrame(columns=columns)
    out = indicators.copy()
    normalized = pd.DataFrame({
        "datetime": [_iso(_to_datetime(row)) for row in _series_time(out)],
        "inst_id": out.get("inst_id", pd.Series("", index=out.index)).astype(str),
        "strategy": out.get("strategy", pd.Series("", index=out.index)).astype(str),
        "close": _numeric(out.get("close", pd.Series(float("nan"), index=out.index))),
        "fast_value": _numeric(out.get("fast_value", pd.Series(float("nan"), index=out.index))),
        "slow_value": _numeric(out.get("slow_value", pd.Series(float("nan"), index=out.index))),
        "macd": _numeric(out.get("macd", pd.Series(float("nan"), index=out.index))),
        "macd_signal": _numeric(out.get("macd_signal", pd.Series(float("nan"), index=out.index))),
        "macd_histogram": _numeric(out.get("macd_histogram", pd.Series(float("nan"), index=out.index))),
    }).dropna(subset=["datetime"]).sort_values(["datetime", "inst_id", "strategy"]).reset_index(drop=True)
    normalized["_sequence"] = normalized.groupby(["datetime", "inst_id", "strategy"]).cumcount()
    return normalized[columns]


def _normalize_equity(equity: pd.DataFrame) -> pd.DataFrame:
    if equity.empty or "equity" not in equity.columns:
        return pd.DataFrame(columns=["datetime", "equity"])
    out = equity.copy()
    return pd.DataFrame({
        "datetime": [_iso(_to_datetime(row)) for row in _series_time(out)],
        "equity": _numeric(out["equity"]),
    }).dropna(subset=["datetime", "equity"]).reset_index(drop=True)


def _price_frame_for_primary_symbol(bundle: ArtifactBundle) -> pd.DataFrame:
    prices = bundle.price_series.copy()
    if prices.empty:
        raise ValueError("price_series.csv is required for reference adapters")
    symbol = bundle.symbols[0] if bundle.symbols else None
    if symbol and "inst_id" in prices.columns:
        prices = prices[prices["inst_id"].astype(str) == symbol].copy()
    if prices.empty:
        raise ValueError(f"no price rows found for symbol {symbol}")
    prices["datetime"] = [_iso(_to_datetime(row)) for row in _series_time(prices)]
    prices = prices.sort_values("datetime").reset_index(drop=True)
    return prices


def _signal_row(price_row: pd.Series, strategy: str, side: str) -> dict[str, Any]:
    return {
        "ts": price_row.get("ts"),
        "datetime": price_row.get("datetime", ""),
        "strategy": strategy,
        "inst_id": price_row.get("inst_id", ""),
        "side": side,
        "fair_value": price_row.get("close", price_row.get("price", "")),
    }


def _mismatch(
    engine: str,
    category: str,
    field: str,
    sequence: int,
    project_value: Any,
    reference_value: Any,
    status: str,
    *,
    abs_diff: Any = "",
    tolerance: Any = "",
    downstream: bool = False,
) -> dict[str, Any]:
    return {
        "engine": engine,
        "category": category if category in MISMATCH_CATEGORIES else "unsupported_reference_scope",
        "field": field,
        "sequence": sequence,
        "project_value": project_value,
        "reference_value": reference_value,
        "abs_diff": abs_diff,
        "tolerance": tolerance,
        "status": status,
        "downstream": bool(downstream),
    }


def _scope_summary(role: str, rows: list[dict], failed: bool, *, skipped: bool = False) -> dict[str, Any]:
    counts = _count_rows(rows)
    if skipped:
        status = "SKIP"
    elif role == "advisory" and counts["total"] > 0:
        status = "ADVISORY_MISMATCH"
    elif failed:
        status = "FAIL"
    else:
        status = "PASS"
    return {
        "status": status,
        "role": role,
        **counts,
        "actionable_mismatch_count": counts["actionable"],
        "downstream_mismatch_count": counts["downstream"],
    }


def _comparison_status(scopes: dict[str, dict[str, Any]], failed: bool) -> str:
    statuses = [str(scope.get("status", "")).upper() for scope in scopes.values()]
    if statuses and all(status == "SKIP" for status in statuses):
        return "SKIP"
    return "FAIL" if failed or any(status == "FAIL" for status in statuses) else "PASS"


def _count_rows(rows: list[dict]) -> dict[str, int]:
    downstream = sum(1 for row in rows if bool(row.get("downstream")))
    skipped = sum(1 for row in rows if str(row.get("status", "")).upper() == "SKIP")
    actionable = sum(
        1
        for row in rows
        if not bool(row.get("downstream")) and str(row.get("status", "")).upper() != "SKIP"
    )
    return {
        "total": len(rows),
        "actionable": actionable,
        "downstream": downstream,
        "skipped": skipped,
    }


def _has_actionable(rows: list[dict]) -> bool:
    return _count_rows(rows)["actionable"] > 0


def _indicator_columns() -> list[str]:
    return [
        "ts",
        "datetime",
        "inst_id",
        "strategy",
        "close",
        "fast_value",
        "slow_value",
        "macd",
        "macd_signal",
        "macd_histogram",
        "warmup_source",
    ]


def _is_finite_number(value: Any) -> bool:
    return math.isfinite(_safe_float(value, float("nan")))


def _write_reference_artifacts(out_dir: Path, ref: ReferenceResult) -> None:
    _write_csv(out_dir / f"reference_{ref.engine}_indicator_series.csv", ref.indicator_series)
    _write_csv(out_dir / f"reference_{ref.engine}_signals.csv", ref.signals)
    _write_csv(out_dir / f"reference_{ref.engine}_trades.csv", ref.trades)
    _write_csv(out_dir / f"reference_{ref.engine}_equity_curve.csv", ref.equity_curve)


def _reference_summary(ref: ReferenceResult) -> dict[str, Any]:
    return {
        "status": ref.status,
        "reason": ref.reason,
        "reference_role": ref.reference_role if ref.reference_role in REFERENCE_ROLES else "advisory",
        "categories": ref.categories,
        "metrics": ref.metrics,
        "metadata": ref.metadata,
        "rows": {
            "indicator_series": int(len(ref.indicator_series)),
            "signals": int(len(ref.signals)),
            "trades": int(len(ref.trades)),
            "equity_curve": int(len(ref.equity_curve)),
        },
    }


def _unavailable_comparison_summary(ref: ReferenceResult) -> dict[str, Any]:
    scope = _scope_summary(
        ref.reference_role if ref.reference_role in REFERENCE_ROLES else "advisory",
        [],
        False,
        skipped=True,
    )
    return {
        "status": ref.status,
        "reference_role": ref.reference_role,
        "strict_scopes": ["signal_logic"],
        "advisory_scopes": ["indicator_values", "metrics", "pnl_semantics", "trade_execution"],
        "categories": ref.categories,
        "reason": ref.reason,
        "scopes": {
            "signal_logic": dict(scope),
        },
        "signal_logic": dict(scope),
        "pnl_semantics": dict(scope),
        "metrics": dict(scope),
        "mismatch_counts": {},
        "actionable_mismatch_counts": {},
        "downstream_mismatch_counts": {},
        "actionable_mismatch_count": 0,
        "downstream_mismatch_count": 0,
    }


def _load_trades(root: Path, result: dict[str, Any]) -> pd.DataFrame:
    path = root / "trades.csv"
    if path.exists():
        return _read_csv(path)
    trades = result.get("trades")
    return pd.DataFrame(trades if isinstance(trades, list) else [])


def _load_equity(root: Path, result: dict[str, Any]) -> pd.DataFrame:
    path = root / "equity_curve.csv"
    if path.exists():
        return _read_csv(path)
    equity = result.get("equity")
    return pd.DataFrame(equity if isinstance(equity, list) else [])


def _normalize_embedded_daily_winner(result: dict[str, Any]) -> dict[str, Any]:
    if "equity" in result or "trades" in result:
        return dict(result)
    return result


def _resolve_strategy_fixture(results_dir: Path, strategy: str, fixture_run_id: str | None) -> Path:
    if fixture_run_id:
        safe_id = Path(fixture_run_id).name
        candidate = _resolve_fixture_candidate(results_dir, safe_id)
        if candidate is None or _strategy_fixture_row(candidate, strategy) is None:
            materialized = _materialize_sweep_fixture(results_dir, strategy, safe_id)
            if materialized is not None:
                candidate = materialized
        if candidate is None:
            raise FileNotFoundError(f"strategy fixture run not found: {fixture_run_id}")
        bundle = load_artifact_bundle(candidate)
        if bundle.primary_strategy != strategy:
            raise ValueError(
                f"fixture run {candidate.name} is for strategy {bundle.primary_strategy}, expected {strategy}"
            )
        if _strategy_fixture_row(candidate, strategy) is None:
            raise ValueError(f"fixture run {candidate.name} is not a loadable validation fixture")
        return candidate
    fixtures = list_strategy_validation_fixtures(results_dir, strategy)
    if not fixtures:
        raise FileNotFoundError(f"no fixture run found for strategy {strategy}")
    for row in fixtures:
        run_id = str(row.get("run_id") or "")
        if not run_id:
            continue
        if row.get("validation_ready") is False and not row.get("materialize_ready"):
            continue
        candidate = _resolve_fixture_candidate(results_dir, run_id)
        if candidate is None or _strategy_fixture_row(candidate, strategy) is None:
            materialized = _materialize_sweep_fixture(results_dir, strategy, run_id)
            if materialized is not None:
                candidate = materialized
        if candidate is not None and _strategy_fixture_row(candidate, strategy) is not None:
            return candidate
    raise FileNotFoundError(f"no loadable fixture run found for strategy {strategy}")


def _strategy_fixture_row(run_dir: Path, clean_strategy: str = "") -> dict[str, Any] | None:
    if not run_dir.is_dir() or not (run_dir / "result.json").exists():
        return None
    try:
        bundle = load_artifact_bundle(run_dir)
    except Exception:
        return None
    primary = bundle.primary_strategy
    if clean_strategy and primary != clean_strategy:
        return None
    if primary in TECHNICAL_STRATEGIES and bundle.price_series.empty:
        return None
    result = bundle.result
    validation = result.get("validation") if isinstance(result.get("validation"), dict) else {}
    materialized = _materialized_from_sweep_summary(result)
    return {
        "run_id": result.get("run_id") or run_dir.name,
        "strategy": primary,
        "strategies": bundle.strategies,
        "symbols": bundle.symbols,
        "bar": bundle.bar,
        "start": result.get("start", result.get("start_date", "")),
        "end": result.get("end", result.get("end_date", "")),
        "created_at": result.get("created_at"),
        "artifact_dir": str(run_dir),
        "fixture_role": "strategy_validation_fixture",
        "validation_ready": True,
        "materialize_ready": False,
        "materialized_from_sweep_summary": materialized,
        "missing_artifacts": [],
        "idealized_fill": bool(
            validation.get("idealized_fill") or validation.get("fill_all_signals")
        ),
    }


def _parameter_sweep_fixture_rows_for_listing(results_dir: Path, clean_strategy: str = "") -> list[dict[str, Any]]:
    sweep_dir = results_dir / "parameter_sweeps"
    if not sweep_dir.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(sweep_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            payload = _read_json(path)
        except Exception:
            continue
        strategy = str(payload.get("strategy") or "")
        if clean_strategy and strategy != clean_strategy:
            continue
        for sweep_row in _sweep_fixture_rows(payload):
            run_id = _sweep_row_run_id(sweep_row)
            if not run_id:
                continue
            artifact_dir = _sweep_artifact_path(results_dir, sweep_row, run_id)
            direct_row = _strategy_fixture_row(artifact_dir, clean_strategy)
            if direct_row is not None:
                direct_row.update({
                    "fixture_role": "parameter_sweep_finalist",
                    "sweep_id": payload.get("sweep_id"),
                    "rank": sweep_row.get("rank"),
                    "trial": sweep_row.get("trial"),
                    "params": dict(sweep_row.get("params") or {}),
                })
                rows.append(direct_row)
                continue
            missing = _missing_fixture_artifacts(artifact_dir)
            materialize_ready = _sweep_fixture_can_materialize(payload, sweep_row)
            rows.append({
                "run_id": run_id,
                "strategy": strategy,
                "strategies": [strategy] if strategy else [],
                "symbols": [str(s) for s in (payload.get("symbols") or [])],
                "bar": payload.get("bar") or "",
                "start": payload.get("start") or "",
                "end": payload.get("end") or "",
                "created_at": payload.get("created_at"),
                "artifact_dir": str(artifact_dir),
                "fixture_role": "parameter_sweep_finalist",
                "sweep_id": payload.get("sweep_id"),
                "rank": sweep_row.get("rank"),
                "trial": sweep_row.get("trial"),
                "params": dict(sweep_row.get("params") or {}),
                "idealized_fill": _fill_all_controls_enabled(payload.get("research_fill_all_signals")),
                "validation_ready": False,
                "materialize_ready": materialize_ready,
                "materialized_from_sweep_summary": False,
                "missing_artifacts": missing,
                "unavailable_reason": (
                    "artifact directory is missing; it will be rebuilt from parameter sweep metadata before validation"
                    if materialize_ready
                    else "artifact directory is missing and sweep metadata is insufficient to rebuild it"
                ),
            })
    return rows


def _resolve_fixture_candidate(results_dir: Path, fixture_run_id: str) -> Path | None:
    root = results_dir.resolve()
    safe_id = Path(fixture_run_id).name
    direct = results_dir / safe_id
    if _is_existing_fixture_path(direct, root):
        return direct
    for candidate in _parameter_sweep_fixture_candidates(results_dir, safe_id):
        if _is_existing_fixture_path(candidate, root):
            return candidate
    return None


def _parameter_sweep_fixture_candidates(results_dir: Path, fixture_run_id: str) -> Iterable[Path]:
    sweep_dir = results_dir / "parameter_sweeps"
    if not sweep_dir.is_dir():
        return []
    candidates: list[Path] = []
    for path in sweep_dir.glob("*.json"):
        try:
            payload = _read_json(path)
        except Exception:
            continue
        for row in _sweep_fixture_rows(payload):
            row_run_id = _sweep_row_run_id(row)
            if row_run_id != fixture_run_id:
                continue
            candidates.append(_sweep_artifact_path(results_dir, row, row_run_id))
    return candidates


def _materialize_sweep_fixture(results_dir: Path, strategy: str, fixture_run_id: str) -> Path | None:
    record = _find_sweep_fixture_record(results_dir, strategy, fixture_run_id)
    if record is None:
        return None
    artifact_dir = record["artifact_dir"]
    if _strategy_fixture_row(artifact_dir, strategy) is not None:
        return artifact_dir
    if not _sweep_fixture_can_materialize(record["payload"], record["row"]):
        return None
    return _rerun_sweep_fixture_artifact(
        results_dir=results_dir,
        strategy=strategy,
        fixture_run_id=fixture_run_id,
        artifact_dir=artifact_dir,
        payload=record["payload"],
        row=record["row"],
    )


def _find_sweep_fixture_record(results_dir: Path, strategy: str, fixture_run_id: str) -> dict[str, Any] | None:
    sweep_dir = results_dir / "parameter_sweeps"
    if not sweep_dir.is_dir():
        return None
    safe_id = Path(fixture_run_id).name
    for path in sorted(sweep_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            payload = _read_json(path)
        except Exception:
            continue
        if str(payload.get("strategy") or "") != strategy:
            continue
        for row in _sweep_fixture_rows(payload):
            run_id = _sweep_row_run_id(row)
            if run_id != safe_id:
                continue
            return {
                "payload": payload,
                "row": row,
                "artifact_dir": _sweep_artifact_path(results_dir, row, run_id),
                "sweep_path": path,
            }
    return None


def _rerun_sweep_fixture_artifact(
    *,
    results_dir: Path,
    strategy: str,
    fixture_run_id: str,
    artifact_dir: Path,
    payload: dict[str, Any],
    row: dict[str, Any],
) -> Path:
    from backtesting.artifacts import save_backtest_artifacts
    from backtesting.parameter_sweep import _config_for_params, _prepare_base_config
    from backtesting.replay import run_replay_backtest, run_replay_validations
    from backtesting.research_controls import (
        apply_fill_all_signal_controls,
        apply_research_risk_overrides,
        summarize_risk_events,
    )
    from okx_quant.core.config import load_config
    from okx_quant.core.symbols import normalize_swap_symbol

    params = dict(row.get("params") or {})
    symbols = [normalize_swap_symbol(str(symbol)) for symbol in (payload.get("symbols") or []) if symbol]
    if not symbols:
        raise ValueError(f"sweep fixture {fixture_run_id} cannot be rebuilt without symbols")
    if not params:
        raise ValueError(f"sweep fixture {fixture_run_id} cannot be rebuilt without params")

    cfg = _prepare_base_config(
        load_config(require_secrets=False),
        strategy=strategy,
        symbols=symbols,
        initial_equity=payload.get("initial_equity"),
        exchange=payload.get("exchange"),
    )
    cfg, applied_risk_overrides = apply_research_risk_overrides(
        cfg,
        payload.get("research_risk_overrides") or {},
    )
    cfg, applied_fill_all_controls = apply_fill_all_signal_controls(
        cfg,
        _fill_all_controls_enabled(payload.get("research_fill_all_signals")),
    )
    combo_cfg = _config_for_params(cfg, strategy, params, symbols)

    bar = str(payload.get("bar") or "1H")
    periods = int(payload.get("periods") or BAR_PERIODS.get(bar, 365))
    start = payload.get("start")
    end = payload.get("end")
    data_dir = str(payload.get("data_dir") or "data/ticks")
    liquidate_on_end = payload.get("liquidate_on_end")

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
        "sweep_id": payload.get("sweep_id"),
        "rank": row.get("rank"),
        "trial": row.get("trial"),
        "params": params,
        "materialized_from_sweep_summary": True,
    }
    result.validation["risk_summary"] = summarize_risk_events(result.risk_event_log)
    if applied_risk_overrides:
        result.validation["research_risk_overrides"] = applied_risk_overrides
    if applied_fill_all_controls:
        result.validation["research_fill_all_signals"] = applied_fill_all_controls

    validation_mode = payload.get("finalist_validation")
    validation_results = None
    if validation_mode and validation_mode != "none":
        validation_results = run_replay_validations(
            strategy_names=[strategy],
            cfg=combo_cfg,
            data_dir=data_dir,
            start=start,
            end=end,
            bar=bar,
            periods=periods,
            mode=str(validation_mode),
            liquidate_on_end=liquidate_on_end,
        )

    artifact_root = artifact_dir.parent
    if not _path_within_root(artifact_root, results_dir):
        artifact_root = results_dir
    previous_artifact_mode = os.environ.get("BACKTEST_ARTIFACT_MODE")
    os.environ["BACKTEST_ARTIFACT_MODE"] = "files"
    try:
        run_dir = save_backtest_artifacts(
            result=result,
            cfg=combo_cfg,
            args=SimpleNamespace(strategy=[strategy], start=start, end=end, bar=bar, validate=validation_mode),
            output_dir=str(artifact_root),
            run_id=Path(fixture_run_id).name,
            strategy_names=[strategy],
            start=start,
            end=end,
            bar=bar,
            validation_results=validation_results,
        )
    finally:
        if previous_artifact_mode is None:
            os.environ.pop("BACKTEST_ARTIFACT_MODE", None)
        else:
            os.environ["BACKTEST_ARTIFACT_MODE"] = previous_artifact_mode
    return Path(run_dir)


def _materialized_from_sweep_summary(result: dict[str, Any]) -> bool:
    validation = result.get("validation") if isinstance(result.get("validation"), dict) else {}
    parameter_sweep = (
        validation.get("parameter_sweep")
        if isinstance(validation.get("parameter_sweep"), dict)
        else {}
    )
    return bool(
        validation.get("materialized_from_sweep_summary")
        or parameter_sweep.get("materialized_from_sweep_summary")
    )


def _sweep_row_run_id(row: dict[str, Any]) -> str:
    return Path(str(row.get("run_id") or row.get("finalist_run_id") or "")).name


def _sweep_artifact_path(results_dir: Path, row: dict[str, Any], run_id: str) -> Path:
    artifact_dir = row.get("artifact_dir") or row.get("finalist_artifact_dir")
    candidate = Path(str(artifact_dir)) if artifact_dir else results_dir / run_id
    if not candidate.is_absolute():
        candidate = results_dir / candidate
    if not _path_within_root(candidate, results_dir):
        return results_dir / Path(run_id).name
    return candidate


def _path_within_root(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except Exception:
        return False
    return True


def _missing_fixture_artifacts(run_dir: Path) -> list[str]:
    required = ["result.json", "price_series.csv", "signals.csv"]
    return [name for name in required if not (run_dir / name).exists()]


def _sweep_fixture_can_materialize(payload: dict[str, Any], row: dict[str, Any]) -> bool:
    if str(payload.get("strategy") or "") not in TECHNICAL_STRATEGIES:
        return False
    if str(row.get("status") or "ok").lower() not in {"ok", "pass", "done", ""}:
        return False
    return bool(row.get("params") and payload.get("symbols"))


def _fill_all_controls_enabled(value: Any) -> bool:
    if isinstance(value, dict):
        return bool(value.get("enabled") or value.get("fill_all_signals"))
    return bool(value)


def _sweep_fixture_rows(payload: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for key in ("finalist_results", "top_results", "results"):
        rows = payload.get(key)
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    yield row


def _is_existing_fixture_path(path: Path, root: Path) -> bool:
    try:
        resolved = path.resolve()
        resolved.relative_to(root)
    except Exception:
        return False
    return resolved.is_dir() and (resolved / "result.json").exists()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _write_csv(path: Path, df: pd.DataFrame) -> None:
    if df.empty:
        df = pd.DataFrame()
    df.to_csv(path, index=False)


def _series_time(df: pd.DataFrame) -> pd.Series:
    if "datetime" in df.columns:
        return df["datetime"]
    if "ts" in df.columns:
        return df["ts"]
    return pd.Series([""], index=df.index)


def _to_datetime(value: Any) -> pd.Timestamp:
    if isinstance(value, pd.Series):
        value = value.iloc[0] if not value.empty else ""
    if isinstance(value, pd.Timestamp):
        ts = value
    else:
        numeric = _safe_float(value, float("nan"))
        if math.isfinite(numeric):
            unit = "ms" if abs(numeric) > 1e11 else "s"
            ts = pd.to_datetime(numeric, unit=unit, utc=True, errors="coerce")
        else:
            ts = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(ts):
        return pd.NaT
    if ts.tzinfo is None:
        return ts.tz_localize("UTC")
    return ts.tz_convert("UTC")


def _ensure_utc_timestamp(ts: pd.Timestamp) -> pd.Timestamp:
    if ts.tzinfo is None:
        return ts.tz_localize("UTC")
    return ts.tz_convert("UTC")


def _ts_ms(ts: pd.Timestamp) -> int:
    return int(pd.Timestamp(ts).timestamp() * 1000)


def _iso(ts: pd.Timestamp) -> str:
    if pd.isna(ts):
        return ""
    return pd.Timestamp(ts).tz_convert("UTC").isoformat().replace("+00:00", "Z")


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _within_abs(left: float, right: float, tolerance: float) -> bool:
    if not math.isfinite(left) and not math.isfinite(right):
        return True
    if math.isfinite(left) != math.isfinite(right):
        return False
    return abs(left - right) <= tolerance


def _within_tol(left: float, right: float, abs_tol: float, rel_tol: float = 0.0) -> bool:
    if not math.isfinite(left) and not math.isfinite(right):
        return True
    if math.isfinite(left) != math.isfinite(right):
        return False
    scale = max(abs(left), abs(right), 1.0)
    return abs(left - right) <= max(abs_tol, rel_tol * scale)


def _tol_label(abs_tol: float, rel_tol: float = 0.0) -> str:
    return f"abs<={abs_tol:g};rel<={rel_tol:g}"


def _abs_diff(left: float, right: float) -> float:
    return abs(left - right) if math.isfinite(left) and math.isfinite(right) else float("nan")


def _df_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    return _json_safe(json.loads(df.to_json(orient="records", force_ascii=False)))


def _json_safe(value: Any) -> Any:
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else value
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        f = float(value)
        return None if math.isnan(f) or math.isinf(f) else f
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _build_validation_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"diff_{stamp}_{uuid.uuid4().hex[:8]}"


def _bar_freq(bar: str) -> str:
    return {
        "1m": "1min",
        "3m": "3min",
        "5m": "5min",
        "15m": "15min",
        "30m": "30min",
        "1H": "1h",
        "2H": "2h",
        "4H": "4h",
        "1D": "1D",
    }.get(bar, "1D")


__all__ = [
    "ArtifactBundle",
    "ReferenceResult",
    "ValidationTolerances",
    "compare_reference",
    "list_strategy_validation_fixtures",
    "list_strategy_validation_results",
    "list_validation_results",
    "load_artifact_bundle",
    "neutral_metrics",
    "read_strategy_validation_artifact",
    "read_strategy_validation_result",
    "read_validation_artifact",
    "read_validation_result",
    "run_differential_validation",
    "run_strategy_differential_validation",
]
