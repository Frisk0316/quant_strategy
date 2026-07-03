"""Differential validation against external backtest engines.

This module deliberately treats public engines as reference implementations for
backtest behaviour, not as market-data truth sources. The inputs are existing
backtest artifacts; the outputs are normalized reference artifacts plus
mismatch tables.
"""
from __future__ import annotations

import ast
import contextlib
import importlib.util
import io
import json
import math
import os
import re
import uuid
from collections import deque
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
SIGNAL_POINT_ENGINE_ORDER = ["vectorbt", "backtrader", "nautilus"]
SIGNAL_POINT_SCOPE = ["timestamp_or_bar", "symbol", "side", "action_or_entry_exit"]
SIGNAL_POINT_ADVISORY_SCOPE = ["pnl", "fee", "slippage", "funding", "metrics"]
STRATEGY_VALIDATION_DIR = "strategy_validation"
REFERENCE_VALIDATION_CONTRACTS: dict[str, dict[str, Any]] = {
    "ma_crossover": {
        "strategy_class": "technical_indicator",
        "minimum_reference_engines": 1,
        "portable_validation_required": True,
        "engines": {
            "vectorbt": {
                "status": "implemented",
                "role": "reference_signals_only",
                "strict_scopes": ["signal_logic"],
                "required_artifacts": ["result.json", "price_series.csv", "signals.csv"],
                "limitation": "PnL, equity, and metrics remain advisory in v1.",
            },
            "backtrader": {
                "status": "implemented",
                "role": "reference_signals_only",
                "strict_scopes": ["signal_logic"],
                "required_artifacts": ["result.json", "price_series.csv", "signals.csv"],
                "limitation": "Backtrader order/PnL semantics are advisory in v1.",
            },
            "nautilus": {
                "status": "implemented",
                "role": "advisory",
                "required_artifacts": ["result.json", "price_series.csv", "signals.csv"],
                "limitation": "Exports Nautilus-compatible advisory replay evidence only; full Nautilus engine execution is not run.",
            },
        },
    },
    "ema_crossover": {
        "strategy_class": "technical_indicator",
        "minimum_reference_engines": 1,
        "portable_validation_required": True,
        "engines": {
            "vectorbt": {
                "status": "implemented",
                "role": "reference_signals_only",
                "strict_scopes": ["signal_logic"],
                "required_artifacts": ["result.json", "price_series.csv", "signals.csv"],
                "limitation": "PnL, equity, and metrics remain advisory in v1.",
            },
            "backtrader": {
                "status": "implemented",
                "role": "reference_signals_only",
                "strict_scopes": ["signal_logic"],
                "required_artifacts": ["result.json", "price_series.csv", "signals.csv"],
                "limitation": "Backtrader order/PnL semantics are advisory in v1.",
            },
            "nautilus": {
                "status": "implemented",
                "role": "advisory",
                "required_artifacts": ["result.json", "price_series.csv", "signals.csv"],
                "limitation": "Exports Nautilus-compatible advisory replay evidence only; full Nautilus engine execution is not run.",
            },
        },
    },
    "macd_crossover": {
        "strategy_class": "technical_indicator",
        "minimum_reference_engines": 1,
        "portable_validation_required": True,
        "engines": {
            "vectorbt": {
                "status": "implemented",
                "role": "reference_signals_only",
                "strict_scopes": ["signal_logic"],
                "required_artifacts": ["result.json", "price_series.csv", "signals.csv"],
                "limitation": "PnL, equity, and metrics remain advisory in v1.",
            },
            "backtrader": {
                "status": "implemented",
                "role": "reference_signals_only",
                "strict_scopes": ["signal_logic"],
                "required_artifacts": ["result.json", "price_series.csv", "signals.csv"],
                "limitation": "Backtrader order/PnL semantics are advisory in v1.",
            },
            "nautilus": {
                "status": "implemented",
                "role": "advisory",
                "required_artifacts": ["result.json", "price_series.csv", "signals.csv"],
                "limitation": "Exports Nautilus-compatible advisory replay evidence only; full Nautilus engine execution is not run.",
            },
        },
    },
    "funding_carry": {
        "strategy_class": "carry",
        "minimum_reference_engines": 1,
        "portable_validation_required": True,
        "engines": {
            "backtrader": {
                "status": "implemented",
                "role": "reference_signals_only",
                "strict_scopes": ["signal_logic"],
                "required_artifacts": ["result.json", "price_series.csv", "signals.csv", "funding_rates.csv"],
                "limitation": "Independently recomputes funding-rate entry/exit signal timing; funding cashflows, spot/perp dual-leg accounting, ct_val-aware PnL, and Backtrader order semantics remain advisory.",
            },
            "nautilus": {
                "status": "implemented",
                "role": "advisory",
                "required_artifacts": ["result.json", "price_series.csv", "signals.csv", "funding_rates.csv"],
                "limitation": "Exports Nautilus-compatible funding signal recompute evidence only; full Nautilus funding settlement, dual-leg execution, and matching-engine replay are not run.",
            },
            "vectorbt": {
                "status": "implemented",
                "role": "reference_signals_only",
                "strict_scopes": ["signal_logic"],
                "required_artifacts": ["result.json", "price_series.csv", "signals.csv", "funding_rates.csv"],
                "limitation": "Independently recomputes funding-rate entry/exit signal timing; funding cashflows, spot/perp dual-leg accounting, ct_val-aware PnL, and vectorbt portfolio semantics remain advisory.",
            },
        },
    },
    "pairs_trading": {
        "strategy_class": "stat_arb",
        "minimum_reference_engines": 1,
        "portable_validation_required": True,
        "engines": {
            "backtrader": {
                "status": "implemented",
                "role": "reference_signals_only",
                "strict_scopes": ["signal_logic"],
                "required_artifacts": ["result.json", "price_series.csv", "signals.csv", "fills.csv"],
                "limitation": "Independently recomputes Kalman/OU y-leg signal timing from price_series; paired hedge-leg fills, latency, and PnL remain advisory.",
            },
            "vectorbt": {
                "status": "implemented",
                "role": "reference_signals_only",
                "strict_scopes": ["signal_logic"],
                "required_artifacts": ["result.json", "price_series.csv", "signals.csv", "fills.csv"],
                "limitation": "Independently recomputes Kalman/OU y-leg signal timing from price_series; spread accounting, hedge-leg fills, and PnL remain advisory.",
            },
            "nautilus": {
                "status": "implemented",
                "role": "advisory",
                "required_artifacts": ["result.json", "price_series.csv", "signals.csv", "trades.csv"],
                "limitation": "Exports Nautilus-compatible pairs signal evidence only; full Nautilus catalog execution, paired leg fills, and spread accounting are not run.",
            },
        },
    },
    "ohlcv_rotation": {
        "strategy_class": "cross_sectional_momentum",
        "minimum_reference_engines": 1,
        "portable_validation_required": True,
        "engines": {
            "vectorbt": {
                "status": "implemented",
                "role": "reference_signals_only",
                "strict_scopes": ["signal_logic"],
                "required_artifacts": ["result.json", "price_series.csv", "target_weights.csv"],
                "limitation": "Independently recomputes cross-sectional ranking and rebalance target signals; PnL and multi-asset fill semantics remain advisory.",
            },
            "backtrader": {
                "status": "implemented",
                "role": "reference_signals_only",
                "strict_scopes": ["signal_logic"],
                "required_artifacts": ["result.json", "price_series.csv", "target_weights.csv"],
                "limitation": "Independently recomputes rebalance target signals; Backtrader multi-data order/PnL semantics remain advisory in v1.",
            },
            "nautilus": {
                "status": "implemented",
                "role": "advisory",
                "required_artifacts": ["result.json", "price_series.csv", "target_weights.csv"],
                "limitation": "Exports Nautilus-compatible rotation signal evidence only; full Nautilus multi-instrument execution is not run.",
            },
        },
    },
    "daily_winner": {
        "strategy_class": "validation_rotation",
        "minimum_reference_engines": 1,
        "portable_validation_required": True,
        "validation_only": True,
        "engines": {
            "vectorbt": {
                "status": "implemented",
                "role": "reference_signals_only",
                "strict_scopes": ["signal_logic"],
                "required_artifacts": ["result.json", "price_series.csv"],
                "limitation": "Independently recomputes prior-day winner selection; synthetic fill costs and PnL remain advisory.",
            },
            "backtrader": {
                "status": "implemented",
                "role": "reference_signals_only",
                "strict_scopes": ["signal_logic"],
                "required_artifacts": ["result.json", "price_series.csv"],
                "limitation": "Independently recomputes daily rotation signals; Backtrader order/PnL semantics remain advisory in v1.",
            },
            "nautilus": {
                "status": "implemented",
                "role": "advisory",
                "required_artifacts": ["result.json", "price_series.csv"],
                "limitation": "Exports Nautilus-compatible daily-winner signal evidence only; full Nautilus engine execution and synthetic costs are not independently validated.",
            },
        },
    },
    "turtle": {
        "strategy_class": "validation_research_runner",
        "minimum_reference_engines": 0,
        "portable_validation_required": False,
        "validation_only": True,
        "engines": {
            "vectorbt": {
                "status": "implemented",
                "role": "advisory",
                "required_artifacts": ["result.json", "price_series.csv"],
                "limitation": "Research-only standalone Turtle reference port; portable external-engine validation is not targeted.",
            },
            "backtrader": {
                "status": "implemented",
                "role": "advisory",
                "required_artifacts": ["result.json", "price_series.csv"],
                "limitation": "Research-only standalone Turtle reference port; Backtrader parity validation is not targeted.",
            },
            "nautilus": {
                "status": "implemented",
                "role": "advisory",
                "required_artifacts": ["result.json", "price_series.csv"],
                "limitation": "Research-only standalone Turtle reference port; Nautilus execution validation is not targeted.",
            },
        },
    },
    "fear_greed_sentiment": {
        "strategy_class": "external_feature",
        "minimum_reference_engines": 1,
        "portable_validation_required": True,
        "engines": {
            "vectorbt": {
                "status": "implemented",
                "role": "reference_signals_only",
                "strict_scopes": ["signal_logic"],
                "required_artifacts": ["result.json", "price_series.csv", "signals.csv", "external_observations.csv"],
                "limitation": "Independently recomputes Fear & Greed as-of feature signal timing; fill state, PnL, and metrics remain advisory.",
            },
            "backtrader": {
                "status": "implemented",
                "role": "reference_signals_only",
                "strict_scopes": ["signal_logic"],
                "required_artifacts": ["result.json", "price_series.csv", "signals.csv", "external_observations.csv"],
                "limitation": "Independently recomputes Fear & Greed as-of feature signal timing; Backtrader order/PnL semantics remain advisory.",
            },
            "nautilus": {
                "status": "implemented",
                "role": "advisory",
                "required_artifacts": ["result.json", "price_series.csv", "signals.csv", "external_observations.csv"],
                "limitation": "Exports Nautilus-compatible Fear & Greed signal evidence only; full Nautilus feature feed and matching engine execution are not run.",
            },
        },
    },
    "cme_gap_fill": {
        "strategy_class": "external_feature",
        "minimum_reference_engines": 1,
        "portable_validation_required": True,
        "engines": {
            "vectorbt": {
                "status": "implemented",
                "role": "reference_signals_only",
                "strict_scopes": ["signal_logic"],
                "required_artifacts": ["result.json", "price_series.csv", "signals.csv", "external_observations.csv"],
                "limitation": "Independently recomputes delayed CME gap event and y-leg signal timing; fill state, PnL, and metrics remain advisory.",
            },
            "backtrader": {
                "status": "implemented",
                "role": "reference_signals_only",
                "strict_scopes": ["signal_logic"],
                "required_artifacts": ["result.json", "price_series.csv", "signals.csv", "external_observations.csv"],
                "limitation": "Independently recomputes delayed CME gap entry/exit signal timing; Backtrader order/PnL semantics remain advisory.",
            },
            "nautilus": {
                "status": "implemented",
                "role": "advisory",
                "required_artifacts": ["result.json", "price_series.csv", "signals.csv", "external_observations.csv"],
                "limitation": "Exports Nautilus-compatible CME gap signal evidence only; full Nautilus feature feed and matching engine execution are not run.",
            },
        },
    },
    "s5_residual_meanrev": {
        "strategy_class": "residual_mean_reversion",
        "minimum_reference_engines": 1,
        "portable_validation_required": True,
        "engines": {
            "vectorbt": {
                "status": "adapter_required",
                "role": "reference_signals_only",
                "strict_scopes": ["signal_logic"],
                "required_artifacts": ["result.json", "price_series.csv", "target_weights.csv"],
                "limitation": "Adapter must independently recompute residual mean-reversion target signals before this can pass the portable gate.",
            },
            "backtrader": {
                "status": "adapter_required",
                "role": "reference_signals_only",
                "strict_scopes": ["signal_logic"],
                "required_artifacts": ["result.json", "price_series.csv", "target_weights.csv"],
                "limitation": "Adapter must independently recompute residual mean-reversion target signals before this can pass the portable gate.",
            },
            "nautilus": {
                "status": "adapter_required",
                "role": "advisory",
                "required_artifacts": ["result.json", "price_series.csv", "target_weights.csv"],
                "limitation": "Nautilus export/replay adapter is not implemented for this research family.",
            },
        },
    },
    "s6_ts_momentum": {
        "strategy_class": "time_series_momentum",
        "minimum_reference_engines": 1,
        "portable_validation_required": True,
        "engines": {
            "vectorbt": {
                "status": "adapter_required",
                "role": "reference_signals_only",
                "strict_scopes": ["signal_logic"],
                "required_artifacts": ["result.json", "price_series.csv", "target_weights.csv"],
                "limitation": "Adapter must independently recompute slow time-series momentum target signals before this can pass the portable gate.",
            },
            "backtrader": {
                "status": "adapter_required",
                "role": "reference_signals_only",
                "strict_scopes": ["signal_logic"],
                "required_artifacts": ["result.json", "price_series.csv", "target_weights.csv"],
                "limitation": "Adapter must independently recompute slow time-series momentum target signals before this can pass the portable gate.",
            },
            "nautilus": {
                "status": "adapter_required",
                "role": "advisory",
                "required_artifacts": ["result.json", "price_series.csv", "target_weights.csv"],
                "limitation": "Nautilus export/replay adapter is not implemented for this research family.",
            },
        },
    },
    "s7_basis_meanrev": {
        "strategy_class": "basis_mean_reversion",
        "minimum_reference_engines": 1,
        "portable_validation_required": True,
        "engines": {
            "vectorbt": {
                "status": "adapter_required",
                "role": "reference_signals_only",
                "strict_scopes": ["signal_logic"],
                "required_artifacts": ["result.json", "price_series.csv", "target_weights.csv", "funding_rates.csv"],
                "limitation": "Adapter must independently recompute perp-vs-spot basis target signals before this can pass the portable gate.",
            },
            "backtrader": {
                "status": "adapter_required",
                "role": "reference_signals_only",
                "strict_scopes": ["signal_logic"],
                "required_artifacts": ["result.json", "price_series.csv", "target_weights.csv", "funding_rates.csv"],
                "limitation": "Adapter must independently recompute perp-vs-spot basis target signals before this can pass the portable gate.",
            },
            "nautilus": {
                "status": "adapter_required",
                "role": "advisory",
                "required_artifacts": ["result.json", "price_series.csv", "target_weights.csv", "funding_rates.csv"],
                "limitation": "Nautilus export/replay adapter is not implemented for this research family.",
            },
        },
    },
    "c2_funding_carry": {
        "strategy_class": "carry",
        "minimum_reference_engines": 1,
        "portable_validation_required": True,
        "engines": {
            "vectorbt": {
                "status": "adapter_required",
                "role": "reference_signals_only",
                "strict_scopes": ["signal_logic"],
                "required_artifacts": ["result.json", "price_series.csv", "target_weights.csv", "funding_rates.csv"],
                "limitation": "Adapter must independently recompute funding-APR plus basis-z carry targets before this can pass the portable gate.",
            },
            "backtrader": {
                "status": "adapter_required",
                "role": "reference_signals_only",
                "strict_scopes": ["signal_logic"],
                "required_artifacts": ["result.json", "price_series.csv", "target_weights.csv", "funding_rates.csv"],
                "limitation": "Adapter must independently recompute funding-APR plus basis-z carry targets before this can pass the portable gate.",
            },
            "nautilus": {
                "status": "adapter_required",
                "role": "advisory",
                "required_artifacts": ["result.json", "price_series.csv", "target_weights.csv", "funding_rates.csv"],
                "limitation": "Nautilus export/replay adapter is not implemented for this research family.",
            },
        },
    },
    "c1_pairs_ou": {
        "strategy_class": "stat_arb",
        "minimum_reference_engines": 1,
        "portable_validation_required": True,
        "engines": {
            "vectorbt": {
                "status": "adapter_required",
                "role": "reference_signals_only",
                "strict_scopes": ["signal_logic"],
                "required_artifacts": ["result.json", "price_series.csv", "target_weights.csv", "funding_rates.csv"],
                "limitation": "Adapter must independently recompute rolling hedge-ratio, z-score, and OU half-life targets before this can pass the portable gate.",
            },
            "backtrader": {
                "status": "adapter_required",
                "role": "reference_signals_only",
                "strict_scopes": ["signal_logic"],
                "required_artifacts": ["result.json", "price_series.csv", "target_weights.csv", "funding_rates.csv"],
                "limitation": "Adapter must independently recompute rolling hedge-ratio, z-score, and OU half-life targets before this can pass the portable gate.",
            },
            "nautilus": {
                "status": "adapter_required",
                "role": "advisory",
                "required_artifacts": ["result.json", "price_series.csv", "target_weights.csv", "funding_rates.csv"],
                "limitation": "Nautilus export/replay adapter is not implemented for this research family.",
            },
        },
    },
}
REFERENCE_ROLES = {
    "reference_signals_only",
    "reference_full",
    "advisory",
    "not_applicable",
    "skipped_dependency",
}
INDEPENDENT_REFERENCE_ROLES = {"reference_signals_only", "reference_full"}
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


def _slug_part(value: Any, fallback: str = "unknown") -> str:
    text = str(value or "").strip()
    if not text:
        text = fallback
    text = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")
    return text.lower() or fallback


def _validation_display_name(bundle: "ArtifactBundle", created_at: datetime | None = None) -> str:
    ts = created_at or datetime.now(timezone.utc)
    day = ts.strftime("%Y/%m/%d")
    strategy = _slug_part(bundle.primary_strategy or "strategy")
    symbols = bundle.symbols
    symbol = _slug_part("_".join(symbols[:3]) if symbols else "multi_symbol")
    if len(symbols) > 3:
        symbol = f"{symbol}_plus{len(symbols) - 3}"
    return f"{day}_{strategy}_{symbol}"


def _fixture_display_name(row: dict[str, Any] | None, fallback_id: str = "") -> str:
    if not row:
        return fallback_id
    created = row.get("created_at") or row.get("start")
    try:
        ts = pd.Timestamp(created) if created else pd.Timestamp.now(tz="UTC")
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        day = ts.tz_convert("UTC").strftime("%Y/%m/%d")
    except Exception:
        day = datetime.now(timezone.utc).strftime("%Y/%m/%d")
    strategy = _slug_part(row.get("strategy") or "_".join(row.get("strategies") or []) or "strategy")
    symbols = [str(s) for s in (row.get("symbols") or []) if s]
    symbol = _slug_part("_".join(symbols[:3]) if symbols else "multi_symbol")
    if len(symbols) > 3:
        symbol = f"{symbol}_plus{len(symbols) - 3}"
    return f"{day}_{strategy}_{symbol}"


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


def strategy_reference_validation_contract(strategy: str) -> dict[str, Any]:
    clean = str(strategy or "").strip()
    contract = REFERENCE_VALIDATION_CONTRACTS.get(clean)
    if contract is None:
        return {
            "strategy": clean,
            "contract_status": "missing",
            "portable_validation_required": True,
            "minimum_reference_engines": 1,
            "engines": {},
        }
    out = json.loads(json.dumps(contract))
    out["strategy"] = clean
    out["contract_status"] = "declared"
    out.setdefault("portable_validation_required", True)
    out.setdefault("minimum_reference_engines", 1)
    out.setdefault("engines", {})
    return out


def _engine_reference_capability(strategy: str, engine: str) -> dict[str, Any]:
    contract = strategy_reference_validation_contract(strategy)
    capability = (contract.get("engines") or {}).get(engine)
    if capability is None:
        return {
            "status": "not_targeted",
            "role": "not_applicable",
            "limitation": f"{engine} is not declared as a reference target for {strategy}",
        }
    return dict(capability)


def _adapter_unavailable_result(engine: str, strategy: str, capability: dict[str, Any]) -> ReferenceResult:
    status = str(capability.get("status") or "adapter_required")
    role = str(capability.get("role") or "not_applicable")
    if status == "adapter_required":
        reason = (
            f"{engine} adapter required for {strategy}: "
            f"{capability.get('limitation') or 'no runnable reference adapter exists yet'}"
        )
    elif status == "not_targeted":
        reason = (
            f"{engine} is not a target reference engine for {strategy}: "
            f"{capability.get('limitation') or 'another reference engine is required by contract'}"
        )
    else:
        reason = f"{engine} reference capability for {strategy} is not runnable: {status}"
    return ReferenceResult(
        engine=engine,
        status="SKIP",
        reason=reason,
        reference_role=role if role in REFERENCE_ROLES else "not_applicable",
        categories=["unsupported_reference_scope"],
        metadata={
            "strategy": strategy,
            "adapter_required": status == "adapter_required",
            "engine_contract": capability,
        },
    )


def _reference_portability_gate(
    contract: dict[str, Any],
    engine_results: dict[str, dict[str, Any]],
    selected_engines: list[str],
) -> dict[str, Any]:
    engines = contract.get("engines") if isinstance(contract.get("engines"), dict) else {}
    minimum = int(contract.get("minimum_reference_engines") or 1)
    implemented = [
        name for name, capability in engines.items()
        if str((capability or {}).get("status")) == "implemented"
    ]
    adapter_required = [
        name for name, capability in engines.items()
        if str((capability or {}).get("status")) == "adapter_required"
    ]
    not_targeted = [
        name for name, capability in engines.items()
        if str((capability or {}).get("status")) == "not_targeted"
    ]
    ok_engines = [
        name for name, result in engine_results.items()
        if result.get("status") == "OK"
    ]
    passing_engines = [
        name
        for name, result in engine_results.items()
        if result.get("status") == "OK"
        and (result.get("comparison") or {}).get("status") == "PASS"
    ]
    independent_passing_engines = [
        name
        for name in passing_engines
        if str(engine_results.get(name, {}).get("reference_role") or "") in INDEPENDENT_REFERENCE_ROLES
    ]
    advisory_passing_engines = [
        name
        for name in passing_engines
        if name not in independent_passing_engines
    ]
    selected_targets = [
        name for name in selected_engines
        if name in implemented or name in adapter_required
    ]
    has_declared_path = bool(implemented or adapter_required)
    passed = len(independent_passing_engines) >= minimum
    if contract.get("contract_status") == "missing":
        blocked_reason = "missing_reference_validation_contract"
    elif not has_declared_path:
        blocked_reason = "no_declared_reference_engine_path"
    elif not selected_targets:
        blocked_reason = "selected_engines_do_not_include_declared_reference_target"
    elif advisory_passing_engines and not independent_passing_engines:
        blocked_reason = "only_advisory_reference_replay_completed"
    elif not passing_engines:
        blocked_reason = "no_reference_engine_completed"
    elif not passed:
        blocked_reason = "insufficient_passing_reference_engines"
    else:
        blocked_reason = ""
    return {
        "required": bool(contract.get("portable_validation_required", True)),
        "passed": passed,
        "contract_status": contract.get("contract_status", "missing"),
        "minimum_reference_engines": minimum,
        "implemented_engines": implemented,
        "adapter_required_engines": adapter_required,
        "not_targeted_engines": not_targeted,
        "selected_engines": selected_engines,
        "selected_target_engines": selected_targets,
        "ok_engines": ok_engines,
        "passing_engines": passing_engines,
        "independent_passing_engines": independent_passing_engines,
        "advisory_passing_engines": advisory_passing_engines,
        "blocked_reason": blocked_reason,
    }


def _source_data_validation(
    bundle: ArtifactBundle,
    contract: dict[str, Any],
    selected_engines: list[str],
) -> dict[str, Any]:
    required_artifacts = _required_artifacts_for_selection(contract, selected_engines)
    required_check = _validate_required_artifacts(bundle.run_dir, required_artifacts)
    price_check = _validate_price_series(bundle)
    ct_val_check = _validate_ct_val_provenance(bundle)
    funding_check = _validate_funding_artifact(bundle, required_artifacts)
    funding_formula_check = _validate_funding_cashflow_formula(bundle, required_artifacts)
    external_check = _validate_external_observations_artifact(bundle, required_artifacts)
    book_snapshot_check = _validate_book_snapshots_artifact(bundle, required_artifacts)
    trade_tick_check = _validate_trade_ticks_artifact(bundle, required_artifacts)
    db_parity_check = _db_parity_validation(bundle)
    funding_db_parity_check = _funding_db_parity_validation(bundle, required_artifacts)
    external_db_parity_check = _external_observations_db_parity_validation(bundle, required_artifacts)
    trade_ticks_db_parity_check = _trade_ticks_db_parity_validation(bundle, required_artifacts)
    checks = {
        "required_artifacts": required_check,
        "price_series": price_check,
        "ct_val_provenance": ct_val_check,
        "funding": funding_check,
        "funding_cashflow_formula": funding_formula_check,
        "external_observations": external_check,
        "book_snapshots": book_snapshot_check,
        "trade_ticks": trade_tick_check,
        "db_parity": db_parity_check,
        "funding_db_parity": funding_db_parity_check,
        "external_observations_db_parity": external_db_parity_check,
        "trade_ticks_db_parity": trade_ticks_db_parity_check,
    }
    statuses = [str(check.get("status") or "SKIP").upper() for check in checks.values()]
    if "FAIL" in statuses:
        status = "FAIL"
    elif "WARN" in statuses:
        status = "WARN"
    else:
        status = "PASS"
    if price_check.get("status") == "PASS" and db_parity_check.get("status") == "SKIP":
        ohlcv_status = "artifact_pass_db_skipped"
    elif price_check.get("status") == "PASS" and db_parity_check.get("status") == "PASS":
        ohlcv_status = "db_parity_pass"
    elif price_check.get("status") == "FAIL":
        ohlcv_status = "artifact_fail"
    else:
        ohlcv_status = "artifact_warn"
    limitations = [
        check.get("reason")
        for check in checks.values()
        if check.get("status") in {"WARN", "SKIP"} and check.get("reason")
    ]
    return {
        "status": status,
        "exchange": ct_val_check.get("exchange"),
        "ohlcv_source_validation": ohlcv_status,
        "checks": checks,
        "limitations": limitations,
    }


def _validation_conclusion(
    source_data_validation: dict[str, Any],
    portability_gate: dict[str, Any],
    engine_results: dict[str, dict[str, Any]],
    failed: bool,
) -> dict[str, Any]:
    data_status = str(source_data_validation.get("status") or "SKIP").upper()
    ok_engines = [
        name for name, result in engine_results.items()
        if result.get("status") == "OK"
    ]
    advisory_engines = [
        name for name, result in engine_results.items()
        if result.get("status") == "OK"
        and str(result.get("reference_role") or "") not in INDEPENDENT_REFERENCE_ROLES
    ]
    if failed or data_status == "FAIL":
        status = "FAIL"
    elif portability_gate.get("passed"):
        status = "REFERENCE_PASS"
    elif ok_engines:
        status = "ADVISORY_ONLY"
    else:
        status = "SKIP"
    blocking_reasons = []
    if data_status == "FAIL":
        blocking_reasons.append("source_data_validation_failed")
    if portability_gate.get("blocked_reason"):
        blocking_reasons.append(str(portability_gate.get("blocked_reason")))
    if not ok_engines:
        blocking_reasons.append("no_external_reference_engine_completed")
    return {
        "status": status,
        "data_validation": data_status,
        "external_engines_completed": ok_engines,
        "advisory_engines": advisory_engines,
        "portable_validation_passed": bool(portability_gate.get("passed")),
        "blocking_reasons": sorted(set(blocking_reasons)),
        "ready_for_promotion_evidence": False,
        "summary": _conclusion_text(status, data_status, portability_gate, ok_engines),
    }


def _engine_execution_matrix(
    bundle: ArtifactBundle,
    contract: dict[str, Any],
    engine_results: dict[str, dict[str, Any]],
    selected_engines: list[str],
    source_data_validation: dict[str, Any],
) -> list[dict[str, Any]]:
    capabilities = contract.get("engines") if isinstance(contract.get("engines"), dict) else {}
    source_status = str(source_data_validation.get("status") or "SKIP").upper()
    rows: list[dict[str, Any]] = []
    for engine in selected_engines:
        capability = capabilities.get(engine, {}) if isinstance(capabilities, dict) else {}
        result = engine_results.get(engine, {})
        metadata = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
        execution_metadata = metadata.get("nautilus_engine_smoke") if isinstance(metadata.get("nautilus_engine_smoke"), dict) else {}
        signal_replay_coverage = (
            execution_metadata.get("signal_replay_coverage")
            if isinstance(execution_metadata.get("signal_replay_coverage"), dict)
            else {}
        )
        comparison = result.get("comparison") if isinstance(result.get("comparison"), dict) else {}
        signal_logic = comparison.get("signal_logic") if isinstance(comparison.get("signal_logic"), dict) else {}
        required_artifacts = [str(item) for item in capability.get("required_artifacts") or []]
        resolved_artifacts, missing_artifacts = _resolve_required_artifacts(bundle.run_dir, required_artifacts)
        dependency = str(metadata.get("dependency") or _engine_dependency_name(engine) or "")
        dependency_available = _engine_dependency_available(result, metadata, dependency)
        reference_role = str(result.get("reference_role") or capability.get("role") or "not_applicable")
        execution_state = _engine_execution_state(result.get("status"), reference_role)
        trigger_status = _engine_trigger_status(result.get("status"), dependency_available, missing_artifacts)
        limitations = _engine_limitations(capability, metadata)
        actionable_signal_mismatches = int(signal_logic.get("actionable_mismatch_count", signal_logic.get("actionable", 0)) or 0)
        signal_pass = signal_logic.get("status") == "PASS" and actionable_signal_mismatches == 0
        portable_gate_eligible = (
            result.get("status") == "OK"
            and reference_role in INDEPENDENT_REFERENCE_ROLES
            and signal_pass
        )
        gate_role = (
            "not_eligible"
            if result.get("status") != "OK"
            else ("independent_reference" if reference_role in INDEPENDENT_REFERENCE_ROLES else "advisory_only")
        )
        rows.append({
            "engine": engine,
            "selected": True,
            "contract_status": capability.get("status", "missing"),
            "contract_role": capability.get("role", "not_applicable"),
            "status": result.get("status", "SKIP"),
            "reason": result.get("reason", ""),
            "reference_role": reference_role,
            "gate_role": gate_role,
            "execution_state": execution_state,
            "trigger_status": trigger_status,
            "trigger_conditions": _engine_trigger_conditions(
                engine,
                capability,
                dependency,
                dependency_available,
                required_artifacts,
                missing_artifacts,
                str(capability.get("role") or reference_role),
            ),
            "dependency": dependency,
            "dependency_available": dependency_available,
            "required_artifacts": required_artifacts,
            "resolved_artifacts": resolved_artifacts,
            "missing_artifacts": missing_artifacts,
            "required_artifacts_present": not missing_artifacts,
            "comparison_status": comparison.get("status", result.get("status", "SKIP")),
            "signal_logic_status": signal_logic.get("status", "SKIP"),
            "signal_logic_actionable_mismatch_count": actionable_signal_mismatches,
            "portable_gate_eligible": portable_gate_eligible,
            "source_data_status": source_status,
            "reference_mode": metadata.get("reference_mode", ""),
            "engine_execution": metadata.get("engine_execution", execution_state),
            "signals_available": execution_metadata.get("signals_available", ""),
            "signals_replayed": execution_metadata.get("signals_replayed", ""),
            "signal_replay_coverage": signal_replay_coverage,
            "scope_limit": metadata.get("scope_limit", ""),
            "limitations": limitations,
        })
    return rows


def _coerce_count(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _comparison_dict(result: dict[str, Any]) -> dict[str, Any]:
    comparison = result.get("comparison")
    return comparison if isinstance(comparison, dict) else {}


def _signal_logic_dict(result: dict[str, Any]) -> dict[str, Any]:
    comparison = _comparison_dict(result)
    signal_logic = comparison.get("signal_logic")
    return signal_logic if isinstance(signal_logic, dict) else {}


def _signal_mismatch_examples(
    all_mismatches: dict[str, list[dict[str, Any]]],
    engine: str,
    limit: int = 3,
) -> list[dict[str, Any]]:
    examples = []
    for row in all_mismatches.get("signals", []):
        if str(row.get("engine") or "") != engine:
            continue
        examples.append({
            "field": row.get("field", ""),
            "sequence": row.get("sequence", ""),
            "project_value": row.get("project_value", ""),
            "reference_value": row.get("reference_value", ""),
            "status": row.get("status", ""),
        })
        if len(examples) >= limit:
            break
    return examples


def _advisory_difference_counts(comparison: dict[str, Any]) -> dict[str, Any]:
    mismatch_counts = comparison.get("mismatch_counts")
    if not isinstance(mismatch_counts, dict):
        mismatch_counts = {}
    return {
        "advisory_scope": list(SIGNAL_POINT_ADVISORY_SCOPE),
        "trades": mismatch_counts.get("trades", {}),
        "pnl": mismatch_counts.get("pnl", {}),
        "metrics": mismatch_counts.get("metrics", {}),
        "indicators": mismatch_counts.get("indicators", {}),
    }


def _signal_point_correctness_matrix(
    engine_results: dict[str, dict[str, Any]],
    selected_engines: list[str],
    all_mismatches: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    ordered_selected = [
        engine for engine in SIGNAL_POINT_ENGINE_ORDER
        if engine in selected_engines
    ]
    ordered_selected.extend(
        engine for engine in selected_engines
        if engine not in SIGNAL_POINT_ENGINE_ORDER
    )
    missing_target_engines = [
        engine for engine in SIGNAL_POINT_ENGINE_ORDER
        if engine not in selected_engines
    ]
    rows: list[dict[str, Any]] = []
    missing_or_failed = list(missing_target_engines)
    for engine in ordered_selected:
        result = engine_results.get(engine, {})
        comparison = _comparison_dict(result)
        signal_logic = _signal_logic_dict(result)
        actionable = _coerce_count(
            signal_logic.get("actionable_mismatch_count", signal_logic.get("actionable", 0))
        )
        downstream = _coerce_count(
            signal_logic.get("downstream_mismatch_count", signal_logic.get("downstream", 0))
        )
        result_status = str(result.get("status") or "SKIP").upper()
        signal_status = str(signal_logic.get("status") or comparison.get("status") or result_status).upper()
        if result_status == "OK" and signal_status == "PASS" and actionable == 0:
            point_status = "PASS"
        elif result_status == "SKIP" or signal_status == "SKIP":
            point_status = "SKIP"
        else:
            point_status = "FAIL"
        if engine in SIGNAL_POINT_ENGINE_ORDER and point_status != "PASS":
            missing_or_failed.append(engine)
        reference_role = str(result.get("reference_role") or "not_applicable")
        rows.append({
            "engine": engine,
            "point_correctness_status": point_status,
            "status": point_status,
            "reference_role": reference_role,
            "portable_gate_eligible": (
                result_status == "OK"
                and reference_role in INDEPENDENT_REFERENCE_ROLES
                and point_status == "PASS"
            ),
            "strict_fields": list(SIGNAL_POINT_SCOPE),
            "mismatch_count": actionable,
            "actionable_mismatch_count": actionable,
            "downstream_mismatch_count": downstream,
            "comparison_status": comparison.get("status", result.get("status", "SKIP")),
            "signal_logic_status": signal_logic.get("status", "SKIP"),
            "mismatch_examples": _signal_mismatch_examples(all_mismatches, engine),
            "advisory_differences": _advisory_difference_counts(comparison),
        })
    missing_or_failed = _unique_strings(missing_or_failed)
    return {
        "status": "PASS" if not missing_or_failed else "FAIL",
        "passed": not missing_or_failed,
        "target_engines": list(SIGNAL_POINT_ENGINE_ORDER),
        "selected_engines": list(selected_engines),
        "missing_target_engines": missing_target_engines,
        "missing_or_failed_target_engines": missing_or_failed,
        "strict_fields": list(SIGNAL_POINT_SCOPE),
        "advisory_scope": list(SIGNAL_POINT_ADVISORY_SCOPE),
        "rows": rows,
    }


def _nautilus_order_fill_parity(
    engine_results: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    result = engine_results.get("nautilus")
    if not isinstance(result, dict):
        return {
            "engine": "nautilus",
            "scope": "signal_replay_order_fill",
            "status": "SKIP",
            "passed": False,
            "reason": "Nautilus engine was not selected for this validation run.",
            "checks": [],
            "promotion_gate_evidence": False,
            "full_project_strategy_parity_passed": False,
        }

    metadata = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
    smoke = metadata.get("nautilus_engine_smoke") if isinstance(metadata.get("nautilus_engine_smoke"), dict) else {}
    coverage = smoke.get("signal_replay_coverage") if isinstance(smoke.get("signal_replay_coverage"), dict) else {}
    backtest_result = smoke.get("backtest_result") if isinstance(smoke.get("backtest_result"), dict) else {}

    smoke_status = str(smoke.get("status") or result.get("status") or "SKIP").upper()
    engine_execution = str(smoke.get("engine_execution") or metadata.get("engine_execution") or "not_run")
    signals_available = _coerce_count(smoke.get("signals_available", coverage.get("total_signal_rows", 0)))
    buy_sell_signal_rows = _coerce_count(coverage.get("buy_sell_signal_rows", signals_available))
    signals_replayed = _coerce_count(smoke.get("signals_replayed", coverage.get("replayable_signal_rows", 0)))
    order_attempts = _coerce_count(backtest_result.get("strategy_order_attempts", 0))
    total_orders = _coerce_count(backtest_result.get("total_orders", 0))
    fills = _coerce_count(backtest_result.get("strategy_fills", 0))
    skipped_replay_rows = sum(
        _coerce_count(coverage.get(field, 0))
        for field in (
            "skipped_unmapped_symbol",
            "skipped_unsupported_side",
            "skipped_invalid_timestamp",
        )
    )

    checks = [
        {
            "name": "engine_signal_replay_run",
            "status": "PASS" if smoke_status == "OK" and engine_execution == "signal_replay_run" else "FAIL",
            "expected": "status=OK and engine_execution=signal_replay_run",
            "actual": f"status={smoke_status} engine_execution={engine_execution}",
        },
        {
            "name": "signal_rows_available",
            "status": "PASS" if buy_sell_signal_rows > 0 else "FAIL",
            "expected": "at least one buy/sell signal row",
            "actual": buy_sell_signal_rows,
        },
        {
            "name": "signal_replay_coverage",
            "status": "PASS" if signals_replayed == buy_sell_signal_rows and skipped_replay_rows == 0 else "FAIL",
            "expected": {
                "signals_replayed": buy_sell_signal_rows,
                "skipped_replay_rows": 0,
            },
            "actual": {
                "signals_replayed": signals_replayed,
                "skipped_replay_rows": skipped_replay_rows,
                "skipped_symbols": coverage.get("skipped_symbols", []),
            },
        },
        {
            "name": "order_attempt_coverage",
            "status": "PASS" if order_attempts == signals_replayed and signals_replayed > 0 else "FAIL",
            "expected": signals_replayed,
            "actual": order_attempts,
        },
        {
            "name": "order_acceptance",
            "status": "PASS" if total_orders >= order_attempts and order_attempts > 0 else "FAIL",
            "expected": f">= {order_attempts}",
            "actual": total_orders,
        },
        {
            "name": "fill_coverage",
            "status": "PASS" if fills == order_attempts and order_attempts > 0 else "FAIL",
            "expected": order_attempts,
            "actual": fills,
        },
    ]
    failed_checks = [row["name"] for row in checks if row["status"] != "PASS"]
    status = "PASS" if not failed_checks else ("SKIP" if smoke_status == "SKIP" else "FAIL")
    return {
        "engine": "nautilus",
        "scope": "signal_replay_order_fill",
        "status": status,
        "passed": status == "PASS",
        "signals_available": signals_available,
        "buy_sell_signal_rows": buy_sell_signal_rows,
        "signals_replayed": signals_replayed,
        "order_attempts": order_attempts,
        "orders_accepted": total_orders,
        "fills": fills,
        "failed_checks": failed_checks,
        "checks": checks,
        "signal_replay_coverage": coverage,
        "backtest_result": backtest_result,
        "promotion_gate_evidence": False,
        "full_project_strategy_parity_passed": False,
        "full_project_strategy_parity_gap": (
            "Nautilus parity currently validates generated signal-replay orders and fills; "
            "project strategy source execution, L2/L3 queue priority, funding settlement, "
            "and production exchange adapter behavior are not covered."
        ),
    }


def _external_validation_conclusion(
    validation_conclusion: dict[str, Any],
    source_data_validation: dict[str, Any],
    portability_gate: dict[str, Any],
    engine_execution_matrix: list[dict[str, Any]],
) -> dict[str, Any]:
    checks = source_data_validation.get("checks") if isinstance(source_data_validation.get("checks"), dict) else {}
    check_statuses = {
        name: {
            "status": check.get("status", "SKIP"),
            "reason": check.get("reason", ""),
        }
        for name, check in checks.items()
        if isinstance(check, dict)
    }
    completed = [row["engine"] for row in engine_execution_matrix if row.get("status") == "OK"]
    independent_attempted = [
        row["engine"]
        for row in engine_execution_matrix
        if row.get("status") == "OK" and row.get("reference_role") in INDEPENDENT_REFERENCE_ROLES
    ]
    independent = [
        row["engine"]
        for row in engine_execution_matrix
        if row.get("gate_role") == "independent_reference" and row.get("portable_gate_eligible")
    ]
    advisory = [
        row["engine"]
        for row in engine_execution_matrix
        if row.get("status") == "OK" and row.get("gate_role") == "advisory_only"
    ]
    skipped = [row["engine"] for row in engine_execution_matrix if row.get("status") == "SKIP"]
    failed = [row["engine"] for row in engine_execution_matrix if row.get("status") == "FAIL"]

    blocking_gaps: list[str] = []
    next_required_actions: list[str] = []
    for name, payload in check_statuses.items():
        status = str(payload.get("status") or "SKIP").upper()
        if status == "FAIL":
            blocking_gaps.append(f"source_data.{name} failed")
            next_required_actions.append(f"Fix source-data validation check: {name}.")
        elif status == "WARN":
            blocking_gaps.append(f"source_data.{name} warning")
        elif status == "SKIP" and name.endswith("db_parity"):
            blocking_gaps.append(f"source_data.{name} skipped")
            next_required_actions.append("Enable DIFF_VALIDATION_ENABLE_DB_PARITY=1 with a reachable DB DSN for DB parity checks.")

    if not independent:
        blocking_gaps.append("no independent reference engine passed signal_logic")
        next_required_actions.append("Run at least one independent vectorbt/backtrader reference path with signal_logic PASS and zero actionable signal mismatches.")

    for row in engine_execution_matrix:
        engine = row.get("engine")
        if row.get("trigger_status") == "missing_dependency":
            dependency = row.get("dependency") or engine
            blocking_gaps.append(f"{engine} dependency missing")
            next_required_actions.append(f"Install optional dependency for {engine}: {dependency}.")
        missing = row.get("missing_artifacts") or []
        if missing:
            blocking_gaps.append(f"{engine} missing artifacts: {', '.join(missing)}")
            next_required_actions.append(f"Provide required artifacts for {engine}: {', '.join(missing)}.")
        if (
            row.get("status") == "OK"
            and row.get("reference_role") in INDEPENDENT_REFERENCE_ROLES
            and not row.get("portable_gate_eligible")
        ):
            blocking_gaps.append(f"{engine} independent reference did not pass signal_logic")
            next_required_actions.append(f"Inspect {engine} signal_logic mismatches and fix strategy/reference parity before promotion.")
        coverage = row.get("signal_replay_coverage") if isinstance(row.get("signal_replay_coverage"), dict) else {}
        total_signals = int(coverage.get("total_signal_rows") or 0)
        replayable_signals = int(coverage.get("replayable_signal_rows") or 0)
        if row.get("engine") == "nautilus" and total_signals > replayable_signals:
            blocking_gaps.append(f"nautilus signal replay partial coverage: {replayable_signals}/{total_signals} signals")
            next_required_actions.append("Extend Nautilus instrument/data mapping so all exported/reference signals can be replayed.")
        if row.get("engine") == "nautilus" and row.get("gate_role") == "advisory_only":
            blocking_gaps.append("nautilus full project-strategy/matching-engine parity not implemented")
            next_required_actions.append("Implement Nautilus catalog/strategy/order/fill mapping before treating Nautilus as reference_full evidence.")

    return {
        "status": validation_conclusion.get("status", "SKIP"),
        "summary": validation_conclusion.get("summary", ""),
        "data_correctness": {
            "status": source_data_validation.get("status", "SKIP"),
            "ohlcv_source_validation": source_data_validation.get("ohlcv_source_validation", "unknown"),
            "checks": check_statuses,
        },
        "external_engines": {
            "selected": [row.get("engine") for row in engine_execution_matrix],
            "completed": completed,
            "independent_attempted": independent_attempted,
            "independent_reference": independent,
            "advisory_only": advisory,
            "skipped": skipped,
            "failed": failed,
        },
        "comparison": {
            "portable_gate_passed": bool(portability_gate.get("passed")),
            "blocked_reason": portability_gate.get("blocked_reason", ""),
            "promotion_gate_evidence": False,
        },
        "blocking_gaps": _unique_strings(blocking_gaps),
        "next_required_actions": _unique_strings(next_required_actions),
    }


def _unique_strings(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _resolve_required_artifacts(root: Path, required_artifacts: list[str]) -> tuple[dict[str, str], list[str]]:
    resolved = {}
    missing = []
    for artifact in required_artifacts:
        path = _resolve_artifact_path(root, artifact)
        if path is None:
            missing.append(artifact)
        else:
            resolved[artifact] = str(path.name if path.parent == root else path.relative_to(root))
    return resolved, missing


def _engine_dependency_name(engine: str) -> str:
    return {
        "vectorbt": "vectorbt",
        "backtrader": "backtrader",
        "nautilus": "nautilus_trader",
    }.get(engine, "")


def _engine_dependency_available(
    result: dict[str, Any],
    metadata: dict[str, Any],
    dependency: str,
) -> bool | None:
    if not dependency:
        return None
    if metadata.get("dependency_available") is not None:
        return bool(metadata.get("dependency_available"))
    if result.get("reference_role") == "skipped_dependency":
        return False
    if result.get("status") == "OK":
        return True
    return None


def _engine_execution_state(status: Any, reference_role: str) -> str:
    status_text = str(status or "SKIP").upper()
    if status_text == "OK" and reference_role == "reference_full":
        return "reference_full_run"
    if status_text == "OK" and reference_role in INDEPENDENT_REFERENCE_ROLES:
        return "reference_signal_run"
    if status_text == "OK":
        return "advisory_run"
    if status_text == "FAIL":
        return "failed"
    return "skipped"


def _engine_trigger_status(
    status: Any,
    dependency_available: bool | None,
    missing_artifacts: list[str],
) -> str:
    status_text = str(status or "SKIP").upper()
    if status_text == "FAIL":
        return "failed"
    if dependency_available is False:
        return "missing_dependency"
    if missing_artifacts:
        return "missing_artifacts"
    if status_text == "OK":
        return "completed"
    return "skipped"


def _engine_trigger_conditions(
    engine: str,
    capability: dict[str, Any],
    dependency: str,
    dependency_available: bool | None,
    required_artifacts: list[str],
    missing_artifacts: list[str],
    reference_role: str,
) -> list[str]:
    dependency_status = "not_required"
    if dependency:
        dependency_status = "available" if dependency_available is True else (
            "missing" if dependency_available is False else "unknown"
        )
    conditions = [
        f"{engine} selected for validation",
        f"contract status is {capability.get('status', 'missing')}",
        f"dependency {dependency or 'none'} is {dependency_status}",
    ]
    if required_artifacts:
        artifact_status = "present" if not missing_artifacts else "missing: " + ", ".join(missing_artifacts)
        conditions.append("required artifacts " + artifact_status)
    if reference_role in INDEPENDENT_REFERENCE_ROLES:
        conditions.append("strict comparison scope includes signal_logic")
    else:
        conditions.append("advisory comparison only; portable gate needs independent reference evidence")
    return conditions


def _engine_limitations(capability: dict[str, Any], metadata: dict[str, Any]) -> list[str]:
    limitations = []
    if capability.get("limitation"):
        limitations.append(str(capability.get("limitation")))
    if metadata.get("scope_limit"):
        limitations.append(str(metadata.get("scope_limit")))
    manifest = metadata.get("export_manifest") if isinstance(metadata.get("export_manifest"), dict) else {}
    for item in manifest.get("limitations") or []:
        text = str(item)
        if text not in limitations:
            limitations.append(text)
    return limitations


def _conclusion_text(
    status: str,
    data_status: str,
    portability_gate: dict[str, Any],
    ok_engines: list[str],
) -> str:
    if status == "FAIL":
        return "Validation failed; inspect source-data checks and strict reference mismatches before using this artifact."
    if status == "REFERENCE_PASS":
        return (
            "Independent reference signal validation passed, but promotion still depends on "
            "ct_val, idealized-fill, walk-forward/CPCV, and deployment gates."
        )
    if status == "ADVISORY_ONLY":
        blocked = portability_gate.get("blocked_reason") or "independent_reference_not_completed"
        return (
            f"External replay completed for {', '.join(ok_engines)}, but evidence is advisory only "
            f"({blocked}); not promotion evidence."
        )
    if data_status == "WARN":
        return "Source-data validation has warnings; inspect limitations before relying on this artifact."
    return "No external reference engine completed."


def _required_artifacts_for_selection(contract: dict[str, Any], selected_engines: list[str]) -> list[str]:
    engines = contract.get("engines") if isinstance(contract.get("engines"), dict) else {}
    artifacts = {"result.json", "price_series.csv"}
    for engine in selected_engines:
        capability = engines.get(engine) if isinstance(engines, dict) else None
        for name in (capability or {}).get("required_artifacts") or []:
            artifacts.add(str(name))
    return sorted(artifacts)


def _validate_required_artifacts(root: Path, required_artifacts: list[str]) -> dict[str, Any]:
    resolved = {}
    missing = []
    for artifact in required_artifacts:
        path = _resolve_artifact_path(root, artifact)
        if path is None:
            missing.append(artifact)
        else:
            resolved[artifact] = str(path.name if path.parent == root else path.relative_to(root))
    fatal_missing = [name for name in missing if name in {"result.json", "price_series.csv"}]
    status = "FAIL" if fatal_missing else ("WARN" if missing else "PASS")
    reason = ""
    if missing:
        reason = "Missing required artifact(s): " + ", ".join(missing)
    return {
        "status": status,
        "required": required_artifacts,
        "resolved": resolved,
        "missing": missing,
        "reason": reason,
    }


def _resolve_artifact_path(root: Path, artifact: str) -> Path | None:
    aliases = {
        "funding_cashflows.csv": ["funding_cashflows.csv", "funding.csv"],
        "funding_rates.csv": ["funding_rates.csv", "funding.csv"],
        "order_log.csv": ["order_log.csv", "orders.csv"],
        "book_snapshots": ["book_snapshots", "book_snapshots.csv"],
        "trade_ticks": ["trade_ticks", "trade_ticks.csv"],
    }
    candidates = aliases.get(artifact, [artifact])
    for candidate in candidates:
        path = root / candidate
        if path.exists():
            return path
    return None


def _validate_price_series(bundle: ArtifactBundle) -> dict[str, Any]:
    df = bundle.price_series
    required_columns = ["datetime", "inst_id", "open", "high", "low", "close"]
    missing_columns = [column for column in required_columns if column not in df.columns]
    if df.empty:
        return {
            "status": "FAIL",
            "rows": 0,
            "missing_columns": missing_columns,
            "reason": "price_series.csv is empty or missing",
        }
    if missing_columns:
        return {
            "status": "FAIL",
            "rows": int(len(df)),
            "missing_columns": missing_columns,
            "reason": "price_series.csv is missing required column(s): " + ", ".join(missing_columns),
        }

    work = df.copy()
    work["_dt"] = [_to_datetime(value) for value in _series_time(work)]
    invalid_timestamps = int(work["_dt"].isna().sum())
    symbol_column = "inst_id" if "inst_id" in work.columns else None
    duplicate_rows = int(
        work.duplicated(subset=[column for column in [symbol_column, "_dt"] if column]).sum()
    )
    monotonic_violations = 0
    cadence_gaps = 0
    expected_delta = _bar_timedelta(bundle.bar)
    groups = work.groupby(symbol_column, dropna=False) if symbol_column else [("", work)]
    for _, group in groups:
        ordered = group.dropna(subset=["_dt"]).sort_values("_dt")
        if not group["_dt"].dropna().is_monotonic_increasing:
            monotonic_violations += 1
        if expected_delta is not None and len(ordered) > 1:
            diffs = ordered["_dt"].drop_duplicates().diff().dropna()
            cadence_gaps += int((diffs > expected_delta * 1.5).sum())

    numeric_columns = ["open", "high", "low", "close"]
    numeric = work[numeric_columns].apply(pd.to_numeric, errors="coerce")
    invalid_ohlc_rows = int(numeric.isna().any(axis=1).sum())
    high_too_low = int((numeric["high"] < numeric[["open", "close"]].max(axis=1)).sum())
    low_too_high = int((numeric["low"] > numeric[["open", "close"]].min(axis=1)).sum())
    negative_volume_rows = 0
    if "vol" in work.columns:
        volume = pd.to_numeric(work["vol"], errors="coerce")
        negative_volume_rows = int((volume < 0).sum())

    failures = {
        "invalid_timestamps": invalid_timestamps,
        "duplicate_rows": duplicate_rows,
        "invalid_ohlc_rows": invalid_ohlc_rows,
        "high_too_low": high_too_low,
        "low_too_high": low_too_high,
        "negative_volume_rows": negative_volume_rows,
    }
    warnings = {
        "monotonic_symbol_violations": monotonic_violations,
        "cadence_gap_count": cadence_gaps,
    }
    status = "FAIL" if any(failures.values()) else ("WARN" if any(warnings.values()) else "PASS")
    reason = ""
    if status == "FAIL":
        reason = "price_series.csv failed structural OHLCV checks"
    elif status == "WARN":
        reason = "price_series.csv has ordering or cadence warnings"
    return {
        "status": status,
        "rows": int(len(df)),
        "symbols": sorted(str(value) for value in work.get("inst_id", pd.Series(dtype=str)).dropna().unique()),
        "start": _iso(work["_dt"].min()) if not work["_dt"].dropna().empty else "",
        "end": _iso(work["_dt"].max()) if not work["_dt"].dropna().empty else "",
        "bar": bundle.bar,
        "failures": failures,
        "warnings": warnings,
        "reason": reason,
    }


def _validate_ct_val_provenance(bundle: ArtifactBundle) -> dict[str, Any]:
    validation = bundle.result.get("validation") if isinstance(bundle.result, dict) else {}
    exchange = validation.get("exchange") if isinstance(validation, dict) else None
    symbols = bundle.symbols
    swap_symbols = [symbol for symbol in symbols if symbol.endswith("-SWAP")]
    if not swap_symbols:
        return {"status": "PASS", "exchange": exchange, "reason": "No SWAP symbols require ct_val provenance."}
    if not isinstance(validation, dict) or "ct_val_all_authoritative" not in validation:
        return {
            "status": "FAIL",
            "exchange": exchange,
            "symbols": swap_symbols,
            "reason": "ct_val provenance is missing from result.validation.",
        }
    authoritative = bool(validation.get("ct_val_all_authoritative"))
    return {
        "status": "PASS" if authoritative else "FAIL",
        "exchange": exchange,
        "symbols": swap_symbols,
        "sources": validation.get("ct_val_sources") or {},
        "reason": "" if authoritative else "ct_val provenance is not authoritative for all SWAP symbols.",
    }


def _validate_funding_artifact(bundle: ArtifactBundle, required_artifacts: list[str]) -> dict[str, Any]:
    funding_required = _funding_required(bundle, required_artifacts)
    rate_required = "funding_rates.csv" in set(required_artifacts) or bundle.primary_strategy == "funding_carry"
    rate_path = _resolve_artifact_path(bundle.run_dir, "funding_rates.csv")
    cashflow_path = _resolve_artifact_path(bundle.run_dir, "funding_cashflows.csv")
    if not funding_required:
        return {"status": "PASS", "required": False, "rows": 0}
    if rate_required and rate_path is not None:
        rows = len(_read_csv(rate_path))
        return {
            "status": "PASS" if rows > 0 else "WARN",
            "required": True,
            "rows": int(rows),
            "artifact": str(rate_path.name),
            "artifact_role": "funding_rates",
            "cashflow_artifact": str(cashflow_path.name) if cashflow_path is not None else "",
            "reason": "" if rows > 0 else "Funding-rate artifact exists but has no rows.",
        }
    if cashflow_path is not None:
        rows = len(_read_csv(cashflow_path))
        return {
            "status": "PASS" if rows > 0 else "WARN",
            "required": True,
            "rows": int(rows),
            "artifact": str(cashflow_path.name),
            "artifact_role": "funding_cashflows",
            "reason": "" if rows > 0 else "Funding cashflow artifact exists but has no rows.",
        }
    if rate_required:
        return {
            "status": "WARN",
            "required": True,
            "rows": 0,
            "reason": "Funding-rate validation requires funding_rates.csv or funding.csv.",
        }
    return {
        "status": "WARN",
        "required": True,
        "rows": 0,
        "reason": "Funding validation requires funding_cashflows.csv or funding.csv.",
    }


def _validate_funding_cashflow_formula(
    bundle: ArtifactBundle,
    required_artifacts: list[str],
) -> dict[str, Any]:
    if not _funding_required(bundle, required_artifacts):
        return {"status": "PASS", "required": False, "rows": 0}
    df = _funding_artifact_frame(bundle)
    if df.empty:
        return {
            "status": "SKIP",
            "required": True,
            "rows": 0,
            "reason": "Funding artifact is missing or empty; artifact presence check reports the warning.",
        }
    if "funding_fee" not in df.columns and "cashflow" not in df.columns:
        return {
            "status": "WARN",
            "required": True,
            "rows": int(len(df)),
            "reason": "Funding artifact has no funding_fee/cashflow column to validate.",
        }
    if "funding_rate" not in df.columns:
        return {
            "status": "WARN",
            "required": True,
            "rows": int(len(df)),
            "reason": "Funding artifact has no funding_rate/rate column to validate.",
        }

    work = df.copy()
    if "funding_fee" not in work.columns and "cashflow" in work.columns:
        work["funding_fee"] = work["cashflow"]
    actual = pd.to_numeric(work["funding_fee"], errors="coerce")
    rate = pd.to_numeric(work["funding_rate"], errors="coerce")
    expected, basis = _expected_funding_fee(work)
    comparable = actual.notna() & rate.notna() & expected.notna()
    missing_formula_inputs = int((~comparable).sum())
    if comparable.sum() == 0:
        return {
            "status": "WARN",
            "required": True,
            "rows": int(len(work)),
            "comparable_rows": 0,
            "missing_formula_inputs": missing_formula_inputs,
            "basis": basis,
            "reason": "Funding artifact lacks notional or size/mark/ct_val inputs for formula validation.",
        }
    diffs = (actual[comparable] - expected[comparable]).abs()
    tolerances = np.maximum(1e-8, np.abs(expected[comparable].to_numpy(dtype=float)) * 1e-8)
    mismatches = int((diffs.to_numpy(dtype=float) > tolerances).sum())
    status = "FAIL" if mismatches else ("WARN" if missing_formula_inputs else "PASS")
    reason = ""
    if mismatches:
        reason = "Funding cashflow formula mismatch."
    elif missing_formula_inputs:
        reason = "Some funding rows lacked inputs for formula validation."
    return {
        "status": status,
        "required": True,
        "rows": int(len(work)),
        "comparable_rows": int(comparable.sum()),
        "missing_formula_inputs": missing_formula_inputs,
        "mismatch_count": mismatches,
        "max_abs_diff": float(diffs.max()) if len(diffs) else 0.0,
        "basis": basis,
        "formula": "funding_fee = -position_size * ct_val * funding_rate * mark_price",
        "reason": reason,
    }


def _expected_funding_fee(df: pd.DataFrame) -> tuple[pd.Series, str]:
    index = df.index
    rate = pd.to_numeric(df.get("funding_rate", pd.Series(np.nan, index=index)), errors="coerce")
    if "position_notional" in df.columns:
        signed_notional = pd.to_numeric(df["position_notional"], errors="coerce")
        if signed_notional.notna().any():
            return -signed_notional * rate, "position_notional"
    if {"position_size", "mark_price"}.issubset(df.columns):
        size = pd.to_numeric(df["position_size"], errors="coerce")
        mark = pd.to_numeric(df["mark_price"], errors="coerce")
        ct_val = _ct_val_series(df)
        return -size * ct_val * rate * mark, "position_size_ct_val_mark_price"
    return pd.Series(np.nan, index=index, dtype=float), "missing_notional_inputs"


def _ct_val_series(df: pd.DataFrame) -> pd.Series:
    if "ct_val" in df.columns:
        return pd.to_numeric(df["ct_val"], errors="coerce")
    if "contract_value" in df.columns:
        return pd.to_numeric(df["contract_value"], errors="coerce")
    return pd.Series(np.nan, index=df.index, dtype=float)


def _funding_required(bundle: ArtifactBundle, required_artifacts: list[str]) -> bool:
    return (
        bundle.primary_strategy == "funding_carry"
        or "funding_cashflows.csv" in set(required_artifacts)
        or "funding_rates.csv" in set(required_artifacts)
    )


def _external_observations_required(bundle: ArtifactBundle, required_artifacts: list[str]) -> bool:
    return (
        bundle.primary_strategy in {"fear_greed_sentiment", "cme_gap_fill"}
        or "external_observations.csv" in set(required_artifacts)
    )


def _book_snapshots_required(bundle: ArtifactBundle, required_artifacts: list[str]) -> bool:
    required = set(required_artifacts)
    return "book_snapshots" in required or "book_snapshots.csv" in required


def _trade_ticks_required(bundle: ArtifactBundle, required_artifacts: list[str]) -> bool:
    required = set(required_artifacts)
    return "trade_ticks" in required or "trade_ticks.csv" in required


def _external_dataset_id(bundle: ArtifactBundle) -> str:
    params = bundle.strategy_params()
    configured = str(params.get("dataset_id") or "").strip()
    if configured:
        return configured
    defaults = {
        "fear_greed_sentiment": "fear_greed_btc",
        "cme_gap_fill": "cme_btc1_continuous",
    }
    return defaults.get(bundle.primary_strategy, "")


def _validate_external_observations_artifact(
    bundle: ArtifactBundle,
    required_artifacts: list[str],
) -> dict[str, Any]:
    if not _external_observations_required(bundle, required_artifacts):
        return {"status": "PASS", "required": False, "rows": 0}
    path = _resolve_artifact_path(bundle.run_dir, "external_observations.csv")
    dataset_id = _external_dataset_id(bundle)
    if path is None:
        return {
            "status": "WARN",
            "required": True,
            "dataset_id": dataset_id,
            "rows": 0,
            "reason": "External-feature validation requires external_observations.csv.",
        }
    df = _external_observations_artifact_frame(bundle)
    if df.empty:
        return {
            "status": "WARN",
            "required": True,
            "dataset_id": dataset_id,
            "rows": 0,
            "artifact": str(path.name),
            "reason": "external_observations.csv exists but has no usable rows.",
        }
    missing = [
        name for name in ["dataset_id", "observed_at"]
        if name not in df.columns
    ]
    has_value = any(name in df.columns for name in ["value_num", "value_text"])
    if not has_value:
        missing.append("value_num_or_value_text")
    dataset_mismatches = 0
    if dataset_id and "dataset_id" in df.columns:
        dataset_mismatches = int((df["dataset_id"].astype(str) != dataset_id).sum())
    status = "FAIL" if missing or dataset_mismatches else "PASS"
    reason = ""
    if missing:
        reason = "external_observations.csv missing required column(s): " + ", ".join(missing)
    elif dataset_mismatches:
        reason = "external_observations.csv contains rows for a different dataset_id."
    return {
        "status": status,
        "required": True,
        "dataset_id": dataset_id,
        "rows": int(len(df)),
        "artifact": str(path.name),
        "missing_columns": missing,
        "dataset_mismatches": dataset_mismatches,
        "start": _iso(df["_observed_at"].min()) if "_observed_at" in df.columns and not df["_observed_at"].empty else "",
        "end": _iso(df["_observed_at"].max()) if "_observed_at" in df.columns and not df["_observed_at"].empty else "",
        "reason": reason,
    }


def _external_observations_artifact_frame(bundle: ArtifactBundle) -> pd.DataFrame:
    path = _resolve_artifact_path(bundle.run_dir, "external_observations.csv")
    if path is None:
        return pd.DataFrame()
    df = _read_csv(path)
    if df.empty:
        return df
    df = df.copy()
    if "observed_at" not in df.columns:
        if "datetime" in df.columns:
            df["observed_at"] = df["datetime"]
        elif "ts" in df.columns:
            df["observed_at"] = df["ts"]
    if "dataset_id" not in df.columns:
        dataset_id = _external_dataset_id(bundle)
        if dataset_id:
            df["dataset_id"] = dataset_id
    if "observed_at" in df.columns:
        df["_observed_at"] = [_to_datetime(value) for value in df["observed_at"]]
        df = df.dropna(subset=["_observed_at"]).sort_values("_observed_at")
    return df


def _validate_book_snapshots_artifact(
    bundle: ArtifactBundle,
    required_artifacts: list[str],
) -> dict[str, Any]:
    if not _book_snapshots_required(bundle, required_artifacts):
        return {"status": "PASS", "required": False, "rows": 0}
    path = _resolve_artifact_path(bundle.run_dir, "book_snapshots")
    if path is None:
        return {
            "status": "WARN",
            "required": True,
            "rows": 0,
            "reason": "Order-book validation requires book_snapshots.csv.",
        }
    df = _read_csv(path)
    if df.empty:
        return {
            "status": "WARN",
            "required": True,
            "rows": 0,
            "artifact": str(path.name),
            "reason": "book_snapshots.csv exists but has no rows.",
        }

    required_columns = ["inst_id", "side", "level", "px", "sz"]
    missing_columns = [column for column in required_columns if column not in df.columns]
    if "ts" not in df.columns and "datetime" not in df.columns:
        missing_columns.append("ts_or_datetime")
    if missing_columns:
        return {
            "status": "FAIL",
            "required": True,
            "rows": int(len(df)),
            "artifact": str(path.name),
            "missing_columns": missing_columns,
            "reason": "book_snapshots.csv missing required column(s): " + ", ".join(missing_columns),
        }

    work = df.copy()
    work["_dt"] = [_to_datetime(value) for value in _series_time(work)]
    sides = work["side"].astype(str).str.lower()
    levels = pd.to_numeric(work["level"], errors="coerce")
    px = pd.to_numeric(work["px"], errors="coerce")
    sz = pd.to_numeric(work["sz"], errors="coerce")
    invalid_timestamp_rows = int(work["_dt"].isna().sum())
    invalid_side_rows = int((~sides.isin({"bid", "ask"})).sum())
    invalid_level_rows = int((levels.isna() | (levels < 0)).sum())
    invalid_price_rows = int((px.isna() | (px <= 0)).sum())
    invalid_size_rows = int((sz.isna() | (sz <= 0)).sum())
    duplicate_subset = ["inst_id", "_dt", "_side", "level"]
    if "seq_id" in work.columns:
        duplicate_subset.insert(3, "seq_id")
    duplicate_rows = int(
        work.assign(_side=sides).duplicated(subset=duplicate_subset).sum()
    )
    symbols = sorted(str(value) for value in work["inst_id"].dropna().unique())
    side_set = set(sides.dropna().unique())
    missing_sides = sorted({"bid", "ask"} - side_set)
    max_depth_by_side = {
        side: int(levels[sides == side].max()) + 1
        for side in ["bid", "ask"]
        if not levels[sides == side].dropna().empty
    }
    failures = {
        "invalid_timestamp_rows": invalid_timestamp_rows,
        "invalid_side_rows": invalid_side_rows,
        "invalid_level_rows": invalid_level_rows,
        "invalid_price_rows": invalid_price_rows,
        "invalid_size_rows": invalid_size_rows,
        "duplicate_level_rows": duplicate_rows,
        "missing_required_sides": len(missing_sides),
    }
    status = "FAIL" if any(failures.values()) else "PASS"
    reason = ""
    if status == "FAIL":
        reason = "book_snapshots.csv failed structural order-book checks."
    return {
        "status": status,
        "required": True,
        "rows": int(len(work)),
        "artifact": str(path.name),
        "symbols": symbols,
        "start": _iso(work["_dt"].min()) if not work["_dt"].dropna().empty else "",
        "end": _iso(work["_dt"].max()) if not work["_dt"].dropna().empty else "",
        "sides": sorted(str(value) for value in side_set),
        "missing_sides": missing_sides,
        "max_depth_by_side": max_depth_by_side,
        "failures": failures,
        "reason": reason,
    }


def _validate_trade_ticks_artifact(
    bundle: ArtifactBundle,
    required_artifacts: list[str],
) -> dict[str, Any]:
    if not _trade_ticks_required(bundle, required_artifacts):
        return {"status": "PASS", "required": False, "rows": 0}
    path = _resolve_artifact_path(bundle.run_dir, "trade_ticks")
    if path is None:
        return {
            "status": "WARN",
            "required": True,
            "rows": 0,
            "reason": "AS VPIN validation uses default VPIN unless trade_ticks.csv is available.",
        }
    df = _read_csv(path)
    if df.empty:
        return {
            "status": "WARN",
            "required": True,
            "rows": 0,
            "artifact": str(path.name),
            "reason": "trade_ticks.csv exists but has no rows; AS VPIN uses default state.",
        }
    required_columns = ["inst_id", "price", "size"]
    missing_columns = [column for column in required_columns if column not in df.columns]
    if "ts" not in df.columns and "datetime" not in df.columns:
        missing_columns.append("ts_or_datetime")
    if missing_columns:
        return {
            "status": "FAIL",
            "required": True,
            "rows": int(len(df)),
            "artifact": str(path.name),
            "missing_columns": missing_columns,
            "reason": "trade_ticks.csv missing required column(s): " + ", ".join(missing_columns),
        }
    work = df.copy()
    work["_dt"] = [_to_datetime(value) for value in _series_time(work)]
    price = pd.to_numeric(work["price"], errors="coerce")
    size = pd.to_numeric(work["size"], errors="coerce")
    sides = work["side"].astype(str).str.lower() if "side" in work.columns else pd.Series("", index=work.index)
    invalid_timestamp_rows = int(work["_dt"].isna().sum())
    invalid_price_rows = int((price.isna() | (price <= 0)).sum())
    invalid_size_rows = int((size.isna() | (size <= 0)).sum())
    invalid_side_rows = int((~sides.isin({"", "buy", "sell"})).sum())
    failures = {
        "invalid_timestamp_rows": invalid_timestamp_rows,
        "invalid_price_rows": invalid_price_rows,
        "invalid_size_rows": invalid_size_rows,
        "invalid_side_rows": invalid_side_rows,
    }
    status = "FAIL" if any(failures.values()) else "PASS"
    reason = "trade_ticks.csv failed structural trade-tick checks." if status == "FAIL" else ""
    return {
        "status": status,
        "required": True,
        "rows": int(len(work)),
        "artifact": str(path.name),
        "symbols": sorted(str(value) for value in work["inst_id"].dropna().unique()),
        "start": _iso(work["_dt"].min()) if not work["_dt"].dropna().empty else "",
        "end": _iso(work["_dt"].max()) if not work["_dt"].dropna().empty else "",
        "failures": failures,
        "reason": reason,
    }


def _external_observations_db_parity_validation(
    bundle: ArtifactBundle,
    required_artifacts: list[str],
) -> dict[str, Any]:
    if not _external_observations_required(bundle, required_artifacts):
        return {"status": "PASS", "required": False}
    artifact = _external_observations_artifact_frame(bundle)
    dataset_id = _external_dataset_id(bundle)
    if artifact.empty:
        return {
            "status": "SKIP",
            "required": True,
            "dataset_id": dataset_id,
            "reason": "External observations artifact is missing or empty; artifact presence check reports the warning.",
        }
    if os.environ.get("DIFF_VALIDATION_ENABLE_DB_PARITY") != "1":
        return {
            "status": "SKIP",
            "required": True,
            "dataset_id": dataset_id,
            "artifact_rows": int(len(artifact)),
            "reason": (
                "External-observation DB parity not requested; set DIFF_VALIDATION_ENABLE_DB_PARITY=1 "
                "with DIFF_VALIDATION_DB_DSN or DATABASE_URL to compare external_observations."
            ),
        }
    dsn = os.environ.get("DIFF_VALIDATION_DB_DSN") or os.environ.get("DATABASE_URL")
    if not dsn:
        return {
            "status": "SKIP",
            "required": True,
            "dataset_id": dataset_id,
            "artifact_rows": int(len(artifact)),
            "reason": "External-observation DB parity requested but no DIFF_VALIDATION_DB_DSN or DATABASE_URL is configured.",
        }
    try:
        from backtesting.data_loader import _dsn_reachable, load_external_observations
    except Exception as exc:
        return {
            "status": "SKIP",
            "required": True,
            "dataset_id": dataset_id,
            "reason": f"External-observation DB parity loader unavailable: {type(exc).__name__}: {exc}",
        }
    if not _dsn_reachable(dsn):
        return {
            "status": "SKIP",
            "required": True,
            "dataset_id": dataset_id,
            "artifact_rows": int(len(artifact)),
            "reason": "External-observation DB parity requested but PostgreSQL/TimescaleDB is not reachable.",
        }
    start = _iso(artifact["_observed_at"].min()) if "_observed_at" in artifact.columns else None
    end = _iso(artifact["_observed_at"].max() + pd.Timedelta(milliseconds=1)) if "_observed_at" in artifact.columns else None
    try:
        db = load_external_observations(
            dataset_id,
            backend="postgres",
            dsn=dsn,
            start=start,
            end=end,
        )
    except Exception as exc:
        return {
            "status": "FAIL",
            "required": True,
            "dataset_id": dataset_id,
            "artifact_rows": int(len(artifact)),
            "reason": f"DB external_observations query failed: {type(exc).__name__}: {exc}",
        }
    return _compare_external_observations_to_db(dataset_id, artifact, db)


def _compare_external_observations_to_db(
    dataset_id: str,
    artifact: pd.DataFrame,
    db: pd.DataFrame,
) -> dict[str, Any]:
    if db.empty:
        return {
            "status": "FAIL",
            "required": True,
            "dataset_id": dataset_id,
            "artifact_rows": int(len(artifact)),
            "db_rows": 0,
            "reason": "DB external_observations returned no rows for artifact window.",
        }
    db_norm = db.copy()
    if "observed_at" not in db_norm.columns:
        return {
            "status": "FAIL",
            "required": True,
            "dataset_id": dataset_id,
            "artifact_rows": int(len(artifact)),
            "db_rows": int(len(db_norm)),
            "reason": "DB external observations have no observed_at column.",
        }
    db_norm["_observed_at"] = pd.to_datetime(db_norm["observed_at"], utc=True, errors="coerce")
    db_norm = db_norm.dropna(subset=["_observed_at"]).sort_values("_observed_at")
    artifact_norm = artifact.copy()
    if "_observed_at" not in artifact_norm.columns and "observed_at" in artifact_norm.columns:
        artifact_norm["_observed_at"] = pd.to_datetime(artifact_norm["observed_at"], utc=True, errors="coerce")
    fields = [field for field in ["value_num", "value_text"] if field in artifact_norm.columns and field in db_norm.columns]
    merged = artifact_norm[["_observed_at", *fields]].merge(
        db_norm[["_observed_at", *fields]],
        on="_observed_at",
        how="outer",
        suffixes=("_artifact", "_db"),
        indicator=True,
    )
    missing_in_db = int((merged["_merge"] == "left_only").sum())
    extra_in_db = int((merged["_merge"] == "right_only").sum())
    value_mismatches = 0
    both = merged[merged["_merge"] == "both"]
    if "value_num" in fields:
        artifact_value = pd.to_numeric(both["value_num_artifact"], errors="coerce")
        db_value = pd.to_numeric(both["value_num_db"], errors="coerce")
        value_mismatches += int((~np.isclose(artifact_value, db_value, rtol=1e-10, atol=1e-12, equal_nan=True)).sum())
    if "value_text" in fields:
        value_mismatches += int((both["value_text_artifact"].fillna("").astype(str) != both["value_text_db"].fillna("").astype(str)).sum())
    if not fields:
        value_mismatches = int(len(both))
    status = "FAIL" if missing_in_db or value_mismatches else ("WARN" if extra_in_db else "PASS")
    reason = ""
    if status == "FAIL":
        reason = "Artifact external observations differ from DB external_observations."
    elif status == "WARN":
        reason = "DB contains extra external observations in the artifact window."
    return {
        "status": status,
        "required": True,
        "dataset_id": dataset_id,
        "artifact_rows": int(len(artifact_norm)),
        "db_rows": int(len(db_norm)),
        "missing_in_db": missing_in_db,
        "extra_in_db": extra_in_db,
        "value_mismatches": value_mismatches,
        "compared_fields": fields,
        "reason": reason,
    }


def _trade_ticks_db_parity_validation(
    bundle: ArtifactBundle,
    required_artifacts: list[str],
) -> dict[str, Any]:
    if not _trade_ticks_required(bundle, required_artifacts):
        return {"status": "PASS", "required": False}
    artifact = _trade_tick_frame(bundle)
    if artifact.empty:
        return {
            "status": "SKIP",
            "required": True,
            "reason": "Trade tick artifact is missing or empty; artifact presence check reports the warning.",
        }
    if os.environ.get("DIFF_VALIDATION_ENABLE_DB_PARITY") != "1":
        return {
            "status": "SKIP",
            "required": True,
            "artifact_rows": int(len(artifact)),
            "reason": (
                "Trade-tick DB parity not requested; set DIFF_VALIDATION_ENABLE_DB_PARITY=1 "
                "with DIFF_VALIDATION_DB_DSN or DATABASE_URL to compare trade_ticks."
            ),
        }
    dsn = os.environ.get("DIFF_VALIDATION_DB_DSN") or os.environ.get("DATABASE_URL")
    if not dsn:
        return {
            "status": "SKIP",
            "required": True,
            "artifact_rows": int(len(artifact)),
            "reason": "Trade-tick DB parity requested but no DIFF_VALIDATION_DB_DSN or DATABASE_URL is configured.",
        }
    try:
        from backtesting.data_loader import _dsn_reachable, load_trade_ticks
    except Exception as exc:
        return {
            "status": "SKIP",
            "required": True,
            "artifact_rows": int(len(artifact)),
            "reason": f"Trade-tick DB parity loader unavailable: {type(exc).__name__}: {exc}",
        }
    if not _dsn_reachable(dsn):
        return {
            "status": "SKIP",
            "required": True,
            "artifact_rows": int(len(artifact)),
            "reason": "Trade-tick DB parity requested but PostgreSQL/TimescaleDB is not reachable.",
        }

    symbol_results = []
    for symbol in sorted(str(value) for value in artifact["inst_id"].dropna().unique()):
        symbol_artifact = artifact[artifact["inst_id"].astype(str) == symbol].copy()
        start = _iso(symbol_artifact["dt"].min())
        end = _iso(symbol_artifact["dt"].max() + pd.Timedelta(milliseconds=1))
        try:
            db = load_trade_ticks(
                symbol,
                backend="postgres",
                dsn=dsn,
                start=start,
                end=end,
            )
        except Exception as exc:
            symbol_results.append({
                "symbol": symbol,
                "status": "FAIL",
                "artifact_rows": int(len(symbol_artifact)),
                "reason": f"DB trade tick query failed: {type(exc).__name__}: {exc}",
            })
            continue
        symbol_results.append(_compare_trade_ticks_to_db(symbol, symbol_artifact, db))

    failed = [row for row in symbol_results if row.get("status") == "FAIL"]
    warned = [row for row in symbol_results if row.get("status") == "WARN"]
    status = "FAIL" if failed else ("WARN" if warned else "PASS")
    return {
        "status": status,
        "required": True,
        "backend": "postgres",
        "artifact_rows": int(len(artifact)),
        "symbols": symbol_results,
        "reason": "" if status == "PASS" else "DB trade tick parity mismatches were detected.",
    }


def _compare_trade_ticks_to_db(
    symbol: str,
    artifact: pd.DataFrame,
    db: pd.DataFrame,
) -> dict[str, Any]:
    if db.empty:
        return {
            "symbol": symbol,
            "status": "FAIL",
            "artifact_rows": int(len(artifact)),
            "db_rows": 0,
            "reason": "DB trade ticks returned no rows for artifact window.",
        }
    db_norm = db.copy()
    if "ts" not in db_norm.columns:
        return {
            "symbol": symbol,
            "status": "FAIL",
            "artifact_rows": int(len(artifact)),
            "db_rows": int(len(db_norm)),
            "reason": "DB trade ticks have no ts column.",
        }
    db_norm["_dt"] = [_to_datetime(value) for value in db_norm["ts"]]
    db_norm["price"] = pd.to_numeric(db_norm.get("price", pd.Series(np.nan, index=db_norm.index)), errors="coerce")
    db_norm["size"] = pd.to_numeric(db_norm.get("size", pd.Series(np.nan, index=db_norm.index)), errors="coerce")
    db_norm["side"] = db_norm.get("side", pd.Series("", index=db_norm.index)).fillna("").astype(str).str.lower()
    db_norm["trade_id"] = db_norm.get("trade_id", pd.Series("", index=db_norm.index)).fillna("").astype(str)
    db_norm = db_norm.dropna(subset=["_dt", "price", "size"]).sort_values("_dt")

    art = artifact.copy()
    art["_dt"] = [_to_datetime(value) for value in art["dt"]]
    art["side"] = art.get("side", pd.Series("", index=art.index)).fillna("").astype(str).str.lower()
    art["trade_id"] = art.get("trade_id", pd.Series("", index=art.index)).fillna("").astype(str)
    use_trade_id = bool(art["trade_id"].str.len().gt(0).any() and db_norm["trade_id"].str.len().gt(0).any())
    key = ["trade_id"] if use_trade_id else ["_dt"]
    fields = ["price", "size", "side"]
    merged = art[key + fields].merge(
        db_norm[key + fields],
        on=key,
        how="outer",
        suffixes=("_artifact", "_db"),
        indicator=True,
    )
    missing_in_db = int((merged["_merge"] == "left_only").sum())
    extra_in_db = int((merged["_merge"] == "right_only").sum())
    value_mismatches = 0
    both = merged[merged["_merge"] == "both"]
    for field in ["price", "size"]:
        a = pd.to_numeric(both[f"{field}_artifact"], errors="coerce")
        b = pd.to_numeric(both[f"{field}_db"], errors="coerce")
        value_mismatches += int((~np.isclose(a, b, rtol=1e-10, atol=1e-12, equal_nan=True)).sum())
    value_mismatches += int((both["side_artifact"].fillna("").astype(str) != both["side_db"].fillna("").astype(str)).sum())
    status = "FAIL" if missing_in_db or value_mismatches else ("WARN" if extra_in_db else "PASS")
    reason = ""
    if status == "FAIL":
        reason = "Artifact trade ticks differ from DB trade ticks."
    elif status == "WARN":
        reason = "DB contains extra trade ticks in the artifact window."
    return {
        "symbol": symbol,
        "status": status,
        "artifact_rows": int(len(art)),
        "db_rows": int(len(db_norm)),
        "key": "trade_id" if use_trade_id else "timestamp",
        "missing_in_db": missing_in_db,
        "extra_in_db": extra_in_db,
        "value_mismatches": value_mismatches,
        "reason": reason,
    }


def _db_parity_validation(bundle: ArtifactBundle) -> dict[str, Any]:
    validation = bundle.result.get("validation") if isinstance(bundle.result, dict) else {}
    exchange = validation.get("exchange") if isinstance(validation, dict) else None
    if os.environ.get("DIFF_VALIDATION_ENABLE_DB_PARITY") != "1":
        return {
            "status": "SKIP",
            "exchange": exchange,
            "canonical_source_primary": exchange,
            "reason": (
                "DB parity check not requested; set DIFF_VALIDATION_ENABLE_DB_PARITY=1 "
                "with DIFF_VALIDATION_DB_DSN or DATABASE_URL to compare canonical candles."
            ),
        }
    dsn = os.environ.get("DIFF_VALIDATION_DB_DSN") or os.environ.get("DATABASE_URL")
    if not dsn:
        return {
            "status": "SKIP",
            "exchange": exchange,
            "canonical_source_primary": exchange,
            "reason": "DB parity requested but no DIFF_VALIDATION_DB_DSN or DATABASE_URL is configured.",
        }
    try:
        from backtesting.data_loader import _dsn_reachable, load_candles
    except Exception as exc:
        return {
            "status": "SKIP",
            "exchange": exchange,
            "canonical_source_primary": exchange,
            "reason": f"DB parity loader unavailable: {type(exc).__name__}: {exc}",
        }
    if not _dsn_reachable(dsn):
        return {
            "status": "SKIP",
            "exchange": exchange,
            "canonical_source_primary": exchange,
            "reason": "DB parity requested but PostgreSQL/TimescaleDB is not reachable.",
        }

    symbol_results = []
    for symbol in bundle.symbols:
        artifact = _artifact_price_frame_for_symbol(bundle, symbol)
        if artifact.empty:
            symbol_results.append({
                "symbol": symbol,
                "status": "FAIL",
                "reason": "artifact price_series has no rows for symbol",
            })
            continue
        start = _iso(artifact["_dt"].min())
        end_ts = artifact["_dt"].max()
        expected_delta = _bar_timedelta(bundle.bar)
        end = _iso(end_ts + expected_delta) if expected_delta is not None else _iso(end_ts)
        try:
            db = load_candles(
                symbol,
                bar=bundle.bar,
                backend="postgres",
                dsn=dsn,
                start=start,
                end=end,
                exchange=exchange,
                include_suspect=False,
            )
        except Exception as exc:
            symbol_results.append({
                "symbol": symbol,
                "status": "FAIL",
                "reason": f"DB candle query failed: {type(exc).__name__}: {exc}",
            })
            continue
        symbol_results.append(_compare_artifact_prices_to_db(symbol, artifact, db))

    failed = [row for row in symbol_results if row.get("status") == "FAIL"]
    warned = [row for row in symbol_results if row.get("status") == "WARN"]
    status = "FAIL" if failed else ("WARN" if warned else "PASS")
    return {
        "status": status,
        "backend": "postgres",
        "exchange": exchange,
        "canonical_source_primary": exchange,
        "symbols": symbol_results,
        "reason": "" if status == "PASS" else "DB canonical candle parity mismatches were detected.",
    }


def _artifact_price_frame_for_symbol(bundle: ArtifactBundle, symbol: str) -> pd.DataFrame:
    df = bundle.price_series.copy()
    if symbol and "inst_id" in df.columns:
        df = df[df["inst_id"].astype(str) == str(symbol)].copy()
    if df.empty:
        return df
    df["_dt"] = [_to_datetime(value) for value in _series_time(df)]
    df = df.dropna(subset=["_dt"]).sort_values("_dt")
    return df


def _compare_artifact_prices_to_db(
    symbol: str,
    artifact: pd.DataFrame,
    db: pd.DataFrame,
) -> dict[str, Any]:
    if db.empty:
        return {
            "symbol": symbol,
            "status": "FAIL",
            "artifact_rows": int(len(artifact)),
            "db_rows": 0,
            "reason": "DB canonical candles returned no rows for artifact window.",
        }
    db_norm = db.copy().reset_index()
    first_col = db_norm.columns[0]
    db_norm = db_norm.rename(columns={first_col: "datetime"})
    db_norm["_dt"] = pd.to_datetime(db_norm["datetime"], utc=True, errors="coerce")
    db_norm = db_norm.dropna(subset=["_dt"]).sort_values("_dt")
    fields = ["close"]
    artifact_norm = artifact[["_dt", *[field for field in fields if field in artifact.columns]]].copy()
    merged = artifact_norm.merge(
        db_norm[["_dt", *[field for field in fields if field in db_norm.columns]]],
        on="_dt",
        how="outer",
        suffixes=("_artifact", "_db"),
        indicator=True,
    )
    missing_in_db = int((merged["_merge"] == "left_only").sum())
    extra_in_db = int((merged["_merge"] == "right_only").sum())
    value_mismatches = 0
    both = merged[merged["_merge"] == "both"]
    for field in fields:
        artifact_col = f"{field}_artifact"
        db_col = f"{field}_db"
        if artifact_col not in both.columns or db_col not in both.columns:
            continue
        a = pd.to_numeric(both[artifact_col], errors="coerce")
        b = pd.to_numeric(both[db_col], errors="coerce")
        value_mismatches += int((~np.isclose(a, b, rtol=1e-9, atol=1e-8, equal_nan=True)).sum())
    status = "FAIL" if missing_in_db or value_mismatches else ("WARN" if extra_in_db else "PASS")
    reason = ""
    if status == "FAIL":
        reason = "Artifact close prices differ from DB canonical close prices."
    elif status == "WARN":
        reason = "DB contains extra candles in the artifact window."
    return {
        "symbol": symbol,
        "status": status,
        "artifact_rows": int(len(artifact)),
        "db_rows": int(len(db_norm)),
        "missing_in_db": missing_in_db,
        "extra_in_db": extra_in_db,
        "value_mismatches": value_mismatches,
        "reason": reason,
    }


def _reference_price_input_metadata(bundle: ArtifactBundle) -> dict[str, Any]:
    meta = getattr(bundle, "_reference_price_input_metadata", None)
    if isinstance(meta, dict):
        return dict(meta)
    return {
        "source": "artifact_price_series",
        "reason": "Reference price input has not been materialized yet.",
    }


def _set_reference_price_input_metadata(bundle: ArtifactBundle, metadata: dict[str, Any]) -> None:
    setattr(bundle, "_reference_price_input_metadata", dict(metadata))


def _reference_price_frame_for_symbol(
    bundle: ArtifactBundle,
    symbol: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    artifact = _artifact_price_frame_for_symbol(bundle, symbol)
    if artifact.empty:
        return artifact, {
            "source": "artifact_price_series",
            "symbol": symbol,
            "reason": "artifact price_series has no rows for symbol",
        }
    if os.environ.get("DIFF_VALIDATION_ENABLE_DB_PARITY") != "1":
        return artifact, {
            "source": "artifact_price_series",
            "symbol": symbol,
            "rows": int(len(artifact)),
            "reason": "DB parity not requested; reference engine uses artifact price_series.csv.",
        }
    dsn = os.environ.get("DIFF_VALIDATION_DB_DSN") or os.environ.get("DATABASE_URL")
    if not dsn:
        return artifact, {
            "source": "artifact_price_series",
            "symbol": symbol,
            "rows": int(len(artifact)),
            "reason": "DB parity requested but no DSN is configured; fell back to artifact price_series.csv.",
        }
    try:
        from backtesting.data_loader import _dsn_reachable, load_candles
    except Exception as exc:
        return artifact, {
            "source": "artifact_price_series",
            "symbol": symbol,
            "rows": int(len(artifact)),
            "reason": f"DB candle loader unavailable; fell back to artifact price_series.csv: {type(exc).__name__}: {exc}",
        }
    if not _dsn_reachable(dsn):
        return artifact, {
            "source": "artifact_price_series",
            "symbol": symbol,
            "rows": int(len(artifact)),
            "reason": "PostgreSQL/TimescaleDB is not reachable; fell back to artifact price_series.csv.",
        }
    start = _iso(artifact["_dt"].min())
    end_ts = artifact["_dt"].max()
    expected_delta = _bar_timedelta(bundle.bar)
    end = _iso(end_ts + expected_delta) if expected_delta is not None else _iso(end_ts)
    try:
        db = load_candles(
            symbol,
            bar=bundle.bar,
            backend="postgres",
            dsn=dsn,
            start=start,
            end=end,
            include_suspect=False,
        )
    except Exception as exc:
        return artifact, {
            "source": "artifact_price_series",
            "symbol": symbol,
            "rows": int(len(artifact)),
            "reason": f"DB canonical candle query failed; fell back to artifact price_series.csv: {type(exc).__name__}: {exc}",
        }
    if db.empty:
        return artifact, {
            "source": "artifact_price_series",
            "symbol": symbol,
            "rows": int(len(artifact)),
            "reason": "DB canonical candles returned no rows; fell back to artifact price_series.csv.",
        }
    frame = _db_candles_to_reference_price_frame(db, symbol)
    return frame, {
        "source": "db_canonical_candles",
        "symbol": symbol,
        "rows": int(len(frame)),
        "start": frame["datetime"].iloc[0] if not frame.empty else "",
        "end": frame["datetime"].iloc[-1] if not frame.empty else "",
        "reason": "Reference engine price input loaded from DB canonical_candles.",
    }


def _db_candles_to_reference_price_frame(db: pd.DataFrame, symbol: str) -> pd.DataFrame:
    frame = db.copy().reset_index()
    first_col = frame.columns[0]
    frame = frame.rename(columns={first_col: "datetime"})
    frame["datetime"] = [_iso(_to_datetime(value)) for value in frame["datetime"]]
    frame = frame.dropna(subset=["datetime"]).sort_values("datetime").reset_index(drop=True)
    frame["ts"] = [_ts_ms(_to_datetime(value)) for value in frame["datetime"]]
    frame["inst_id"] = symbol
    for column in ["open", "high", "low", "close", "vol"]:
        if column not in frame.columns:
            frame[column] = float("nan")
    return frame[["ts", "datetime", "inst_id", "open", "high", "low", "close", "vol"]]


def _funding_db_parity_validation(bundle: ArtifactBundle, required_artifacts: list[str]) -> dict[str, Any]:
    if not _funding_required(bundle, required_artifacts):
        return {"status": "PASS", "required": False}
    artifact = _funding_rate_artifact_frame(bundle)
    if artifact.empty:
        artifact = _funding_artifact_frame(bundle)
    if artifact.empty:
        return {
            "status": "SKIP",
            "required": True,
            "reason": "Funding artifact is missing or empty; artifact presence check reports the warning.",
        }
    if os.environ.get("DIFF_VALIDATION_ENABLE_DB_PARITY") != "1":
        return {
            "status": "SKIP",
            "required": True,
            "artifact_rows": int(len(artifact)),
            "reason": (
                "Funding DB parity not requested; set DIFF_VALIDATION_ENABLE_DB_PARITY=1 "
                "with DIFF_VALIDATION_DB_DSN or DATABASE_URL to compare funding rates."
            ),
        }
    dsn = os.environ.get("DIFF_VALIDATION_DB_DSN") or os.environ.get("DATABASE_URL")
    if not dsn:
        return {
            "status": "SKIP",
            "required": True,
            "artifact_rows": int(len(artifact)),
            "reason": "Funding DB parity requested but no DIFF_VALIDATION_DB_DSN or DATABASE_URL is configured.",
        }
    try:
        from backtesting.data_loader import _dsn_reachable, load_funding
    except Exception as exc:
        return {
            "status": "SKIP",
            "required": True,
            "reason": f"Funding DB parity loader unavailable: {type(exc).__name__}: {exc}",
        }
    if not _dsn_reachable(dsn):
        return {
            "status": "SKIP",
            "required": True,
            "artifact_rows": int(len(artifact)),
            "reason": "Funding DB parity requested but PostgreSQL/TimescaleDB is not reachable.",
        }

    symbols = _funding_symbols(bundle, artifact)
    symbol_results = []
    for symbol in symbols:
        symbol_artifact = artifact
        if "inst_id" in symbol_artifact.columns:
            symbol_artifact = symbol_artifact[symbol_artifact["inst_id"].astype(str) == str(symbol)].copy()
        if symbol_artifact.empty:
            symbol_results.append({
                "symbol": symbol,
                "status": "FAIL",
                "reason": "funding artifact has no rows for symbol",
            })
            continue
        start = _iso(symbol_artifact["_dt"].min())
        end = _iso(symbol_artifact["_dt"].max() + pd.Timedelta(milliseconds=1))
        try:
            db = load_funding(
                symbol,
                backend="postgres",
                dsn=dsn,
                start=start,
                end=end,
            )
        except Exception as exc:
            symbol_results.append({
                "symbol": symbol,
                "status": "FAIL",
                "reason": f"DB funding query failed: {type(exc).__name__}: {exc}",
            })
            continue
        symbol_results.append(_compare_artifact_funding_to_db(symbol, symbol_artifact, db))

    failed = [row for row in symbol_results if row.get("status") == "FAIL"]
    warned = [row for row in symbol_results if row.get("status") == "WARN"]
    status = "FAIL" if failed else ("WARN" if warned else "PASS")
    return {
        "status": status,
        "required": True,
        "backend": "postgres",
        "artifact_rows": int(len(artifact)),
        "symbols": symbol_results,
        "reason": "" if status == "PASS" else "DB funding-rate parity mismatches were detected.",
    }


def _funding_artifact_frame(bundle: ArtifactBundle) -> pd.DataFrame:
    path = _resolve_artifact_path(bundle.run_dir, "funding_cashflows.csv")
    if path is None:
        return pd.DataFrame()
    df = _read_csv(path)
    if df.empty:
        return df
    df = df.copy()
    if "funding_rate" not in df.columns and "rate" in df.columns:
        df["funding_rate"] = df["rate"]
    df["_dt"] = [_to_datetime(value) for value in _series_time(df)]
    df = df.dropna(subset=["_dt"]).sort_values("_dt")
    return df


def _funding_rate_artifact_frame(bundle: ArtifactBundle) -> pd.DataFrame:
    path = _resolve_artifact_path(bundle.run_dir, "funding_rates.csv")
    if path is None:
        return pd.DataFrame()
    df = _read_csv(path)
    if df.empty:
        return df
    df = df.copy()
    if "funding_rate" not in df.columns and "rate" in df.columns:
        df["funding_rate"] = df["rate"]
    if "next_funding_time" not in df.columns and "nextFundingTime" in df.columns:
        df["next_funding_time"] = df["nextFundingTime"]
    df["_dt"] = [_to_datetime(value) for value in _series_time(df)]
    df = df.dropna(subset=["_dt"]).sort_values("_dt")
    return df


def _funding_symbols(bundle: ArtifactBundle, artifact: pd.DataFrame) -> list[str]:
    if "inst_id" in artifact.columns:
        symbols = sorted(str(value) for value in artifact["inst_id"].dropna().unique() if str(value))
        if symbols:
            return symbols
    swaps = [symbol for symbol in bundle.symbols if symbol.endswith("-SWAP")]
    return swaps or bundle.symbols


def _compare_artifact_funding_to_db(
    symbol: str,
    artifact: pd.DataFrame,
    db: pd.DataFrame,
) -> dict[str, Any]:
    if db.empty:
        return {
            "symbol": symbol,
            "status": "FAIL",
            "artifact_rows": int(len(artifact)),
            "db_rows": 0,
            "reason": "DB funding_rates returned no rows for artifact window.",
        }
    if "funding_rate" not in artifact.columns:
        return {
            "symbol": symbol,
            "status": "FAIL",
            "artifact_rows": int(len(artifact)),
            "db_rows": int(len(db)),
            "reason": "Funding artifact has no funding_rate/rate column.",
        }

    db_norm = db.copy().reset_index()
    first_col = db_norm.columns[0]
    db_norm = db_norm.rename(columns={first_col: "datetime"})
    db_norm["_dt"] = pd.to_datetime(db_norm["datetime"], utc=True, errors="coerce")
    if "funding_rate" not in db_norm.columns and "rate" in db_norm.columns:
        db_norm["funding_rate"] = db_norm["rate"]
    db_norm = db_norm.dropna(subset=["_dt"]).sort_values("_dt")
    if "funding_rate" not in db_norm.columns:
        return {
            "symbol": symbol,
            "status": "FAIL",
            "artifact_rows": int(len(artifact)),
            "db_rows": int(len(db_norm)),
            "reason": "DB funding data has no funding_rate/rate column.",
        }

    artifact_norm = artifact[["_dt", "funding_rate"]].copy()
    merged = artifact_norm.merge(
        db_norm[["_dt", "funding_rate"]],
        on="_dt",
        how="outer",
        suffixes=("_artifact", "_db"),
        indicator=True,
    )
    missing_in_db = int((merged["_merge"] == "left_only").sum())
    extra_in_db = int((merged["_merge"] == "right_only").sum())
    both = merged[merged["_merge"] == "both"]
    artifact_rate = pd.to_numeric(both["funding_rate_artifact"], errors="coerce")
    db_rate = pd.to_numeric(both["funding_rate_db"], errors="coerce")
    rate_mismatches = int((~np.isclose(artifact_rate, db_rate, rtol=1e-10, atol=1e-12, equal_nan=True)).sum())
    status = "FAIL" if missing_in_db or rate_mismatches else ("WARN" if extra_in_db else "PASS")
    reason = ""
    if status == "FAIL":
        reason = "Artifact funding rates differ from DB funding_rates."
    elif status == "WARN":
        reason = "DB contains extra funding rows in the artifact window."
    return {
        "symbol": symbol,
        "status": status,
        "artifact_rows": int(len(artifact_norm)),
        "db_rows": int(len(db_norm)),
        "missing_in_db": missing_in_db,
        "extra_in_db": extra_in_db,
        "rate_mismatches": rate_mismatches,
        "reason": reason,
    }


def _bar_timedelta(bar: str) -> pd.Timedelta | None:
    match = re.fullmatch(r"(\d+)([mMhHdD])", str(bar or "").strip())
    if not match:
        return None
    value = int(match.group(1))
    unit = match.group(2)
    if unit in {"m", "M"}:
        return pd.Timedelta(minutes=value)
    if unit in {"h", "H"}:
        return pd.Timedelta(hours=value)
    return pd.Timedelta(days=value)


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
        signals=_load_signals(root, normalized_result),
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

    created_at_dt = datetime.now(timezone.utc)
    validation_id = validation_id or _build_validation_id(bundle, created_at_dt)
    out_dir = Path(output_dir) if output_dir else bundle.run_dir / "validation" / validation_id
    out_dir.mkdir(parents=True, exist_ok=True)
    tolerances = ValidationTolerances.from_initial_equity(bundle.initial_equity)
    reference_contract = strategy_reference_validation_contract(bundle.primary_strategy)

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

    source_data_validation = _source_data_validation(
        bundle,
        reference_contract,
        selected_engines,
    )
    failed = any(
        result.get("comparison", {}).get("status") == "FAIL"
        for result in engine_results.values()
    ) or str(source_data_validation.get("status") or "").upper() == "FAIL"
    ok_engines = [
        name
        for name, result in engine_results.items()
        if result.get("status") == "OK"
    ]
    signal_gate_engines = [
        name
        for name, result in engine_results.items()
        if name in {"vectorbt", "backtrader"}
        and str(result.get("reference_role") or "") in INDEPENDENT_REFERENCE_ROLES
        and (result.get("comparison") or {}).get("signal_logic", {}).get("status") == "PASS"
        and int(
            (result.get("comparison") or {}).get("signal_logic", {}).get(
                "actionable_mismatch_count",
                (result.get("comparison") or {}).get("signal_logic", {}).get("actionable", 1),
            )
        ) == 0
    ]
    required_ok_engines = 2
    portability_gate = _reference_portability_gate(
        reference_contract,
        engine_results,
        selected_engines,
    )
    engine_execution_matrix = _engine_execution_matrix(
        bundle,
        reference_contract,
        engine_results,
        selected_engines,
        source_data_validation,
    )
    signal_point_correctness = _signal_point_correctness_matrix(
        engine_results,
        selected_engines,
        all_mismatches,
    )
    nautilus_order_fill_parity = _nautilus_order_fill_parity(engine_results)
    validation_conclusion = _validation_conclusion(
        source_data_validation,
        portability_gate,
        engine_results,
        failed,
    )
    external_validation_conclusion = _external_validation_conclusion(
        validation_conclusion,
        source_data_validation,
        portability_gate,
        engine_execution_matrix,
    )
    summary = {
        "validation_id": validation_id,
        "display_name": _validation_display_name(bundle, created_at_dt),
        "run_id": bundle.run_id,
        "created_at": created_at_dt.isoformat(),
        "strategy": bundle.primary_strategy,
        "strategies": bundle.strategies,
        "symbols": bundle.symbols,
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
        "reference_validation_contract": reference_contract,
        "portable_validation_gate": portability_gate,
        "engine_execution_matrix": engine_execution_matrix,
        "signal_point_correctness": signal_point_correctness,
        "nautilus_order_fill_parity": nautilus_order_fill_parity,
        "source_data_validation": source_data_validation,
        "validation_conclusion": validation_conclusion,
        "external_validation_conclusion": external_validation_conclusion,
        "conclusion": validation_conclusion["summary"],
        "materialized_from_sweep_summary": _materialized_from_sweep_summary(bundle.result),
        "artifact_dir": str(bundle.run_dir),
        "output_dir": str(out_dir),
        "ohlcv_source_validation": source_data_validation.get("ohlcv_source_validation", "unknown"),
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
    fixture_row = _strategy_fixture_row(fixture_dir, clean_strategy)
    validation_id = validation_id or _build_validation_id(load_artifact_bundle(fixture_dir))
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
        "fixture_display_name": _fixture_display_name(fixture_row, fixture_dir.name),
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
    signal_scope_role = (
        "reference" if reference.reference_role in INDEPENDENT_REFERENCE_ROLES else "advisory"
    )
    strict_scopes = {"signal_logic"} if reference.reference_role in INDEPENDENT_REFERENCE_ROLES else set()
    if reference_full:
        strict_scopes.update({"trade_execution", "pnl_semantics", "metrics"})
    failed = (signal_failed and "signal_logic" in strict_scopes) or (
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
        "signal_logic": _scope_summary(signal_scope_role, signal_rows, signal_failed),
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
        capability = _engine_reference_capability(strategy, self.engine)
        if capability.get("status") != "implemented":
            return _adapter_unavailable_result(self.engine, strategy, capability)
        return None

    def _run_available(self, bundle: ArtifactBundle) -> ReferenceResult:
        strategy = bundle.primary_strategy
        if strategy == "daily_winner":
            return _daily_winner_reference_result(bundle, self.engine)
        if strategy == "ohlcv_rotation":
            return _ohlcv_rotation_reference_result(bundle, self.engine)
        if strategy == "pairs_trading":
            return _pairs_trading_reference_result(bundle, self.engine)
        if strategy == "funding_carry":
            return _funding_carry_reference_result(bundle, self.engine)
        if strategy in {"fear_greed_sentiment", "cme_gap_fill"}:
            return _external_feature_reference_result(bundle, self.engine)

        import vectorbt as vbt

        technical = strategy in TECHNICAL_STRATEGIES
        indicator_series = (
            _technical_reference_indicator_series(bundle, strategy)
            if technical else pd.DataFrame(columns=_indicator_columns())
        )
        signals = (
            _technical_reference_signals(bundle, strategy)
            if technical else _artifact_reference_signals(bundle)
        )
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
        reference_role = "reference_signals_only" if technical else "advisory"
        mode = "technical_indicator_recompute" if technical else "artifact_signal_replay"
        return ReferenceResult(
            engine=self.engine,
            status="OK",
            reason=(
                "indicator/signal comparison is strict; PnL/equity semantics are advisory in v1"
                if technical
                else "artifact signal replay is advisory; strategy logic is not independently recomputed"
            ),
            reference_role=reference_role,
            indicator_series=indicator_series,
            signals=signals,
            trades=trades,
            equity_curve=equity,
            metrics=metrics,
            metadata={
                "strategy": strategy,
                "reference_mode": mode,
                "portfolio_engine": "vectorbt.Portfolio.from_signals",
                "price_input": _reference_price_input_metadata(bundle),
                "signal_position_source": _signal_position_source(bundle),
                "scope_limit": "primary-symbol OHLCV replay" if not technical else "technical-indicator signal recompute",
            },
        )


class BacktraderReferenceAdapter(ReferenceAdapter):
    engine = "backtrader"
    dependency = "backtrader"

    def _out_of_scope(self, bundle: ArtifactBundle) -> ReferenceResult | None:
        strategy = bundle.primary_strategy
        capability = _engine_reference_capability(strategy, self.engine)
        if capability.get("status") != "implemented":
            return _adapter_unavailable_result(self.engine, strategy, capability)
        return None

    def _run_available(self, bundle: ArtifactBundle) -> ReferenceResult:
        strategy = bundle.primary_strategy
        if strategy == "daily_winner":
            return _daily_winner_reference_result(bundle, self.engine)
        if strategy == "ohlcv_rotation":
            return _ohlcv_rotation_reference_result(bundle, self.engine)
        if strategy == "pairs_trading":
            return _pairs_trading_reference_result(bundle, self.engine)
        if strategy == "funding_carry":
            return _funding_carry_reference_result(bundle, self.engine)
        if strategy in {"fear_greed_sentiment", "cme_gap_fill"}:
            return _external_feature_reference_result(bundle, self.engine)

        import backtrader as bt

        technical = strategy in TECHNICAL_STRATEGIES
        indicator_series = (
            _technical_reference_indicator_series(bundle, strategy)
            if technical else pd.DataFrame(columns=_indicator_columns())
        )
        if technical:
            signals, trades, equity = _run_backtrader_technical_reference(bt, bundle, strategy)
        else:
            signals, trades, equity = _run_backtrader_signal_replay_reference(bt, bundle)
        metrics = neutral_metrics(equity, bundle.periods)
        reference_role = "reference_signals_only" if technical else "advisory"
        mode = "technical_indicator_recompute" if technical else "artifact_signal_replay"
        return ReferenceResult(
            engine=self.engine,
            status="OK",
            reason=(
                "signal timing is strict; Backtrader runs project-compatible "
                "indicator state, while PnL/equity semantics are advisory in v1"
                if technical
                else "artifact signal replay is advisory; strategy logic is not independently recomputed"
            ),
            reference_role=reference_role,
            indicator_series=indicator_series,
            signals=signals,
            trades=trades,
            equity_curve=equity,
            metrics=metrics,
            metadata={
                "strategy": strategy,
                "reference_mode": mode,
                "order_semantics": "backtrader_market_orders",
                "price_input": _reference_price_input_metadata(bundle),
                "signal_position_source": _signal_position_source(bundle),
                "scope_limit": "primary-symbol OHLCV replay" if not technical else "technical-indicator signal recompute",
            },
        )


class NautilusReferenceAdapter(ReferenceAdapter):
    engine = "nautilus"
    dependency = ""

    def _out_of_scope(self, bundle: ArtifactBundle) -> ReferenceResult | None:
        strategy = bundle.primary_strategy
        capability = _engine_reference_capability(strategy, self.engine)
        if capability.get("status") != "implemented":
            return _adapter_unavailable_result(self.engine, strategy, capability)
        return None

    def _run_available(self, bundle: ArtifactBundle) -> ReferenceResult:
        if bundle.primary_strategy == "daily_winner":
            signals, trades, equity, price_input = _daily_winner_reference_components(bundle)
            reference_mode = "nautilus_daily_winner_recompute_export"
            scope_limit = "daily winner signal recompute/export only; no Nautilus catalog or matching engine execution"
        elif bundle.primary_strategy == "ohlcv_rotation":
            signals, trades, equity, price_input = _ohlcv_rotation_reference_components(bundle)
            reference_mode = "nautilus_ohlcv_rotation_recompute_export"
            scope_limit = "ohlcv rotation signal recompute/export only; no Nautilus catalog or multi-instrument matching engine execution"
        elif bundle.primary_strategy == "pairs_trading":
            signals, trades, equity, price_input = _pairs_trading_reference_components(bundle)
            reference_mode = "nautilus_pairs_trading_recompute_export"
            scope_limit = "pairs Kalman/OU y-leg signal recompute/export only; no Nautilus catalog or paired-leg matching engine execution"
        elif bundle.primary_strategy == "funding_carry":
            signals, trades, equity, price_input = _funding_carry_reference_components(bundle)
            reference_mode = "nautilus_funding_carry_recompute_export"
            scope_limit = "funding carry signal recompute/export only; no Nautilus funding settlement or dual-leg matching engine execution"
        elif bundle.primary_strategy in {"fear_greed_sentiment", "cme_gap_fill"}:
            signals, trades, equity, price_input = _external_feature_reference_components(bundle)
            reference_mode = f"nautilus_{bundle.primary_strategy}_recompute_export"
            scope_limit = "external feature signal recompute/export only; no Nautilus feature feed or matching engine execution"
        else:
            signals = _artifact_reference_signals(bundle)
            trades, equity = _simulate_long_flat_trades(bundle, signals)
            price_input = _reference_price_input_metadata(bundle)
            reference_mode = "nautilus_artifact_replay_export"
            scope_limit = "artifact signal replay/export only; no Nautilus catalog or matching engine execution"
        metrics = neutral_metrics(equity, bundle.periods)
        dependency_available = importlib.util.find_spec("nautilus_trader") is not None
        engine_smoke = _nautilus_engine_smoke(bundle, signals=signals)
        engine_execution = str(engine_smoke.get("engine_execution") or "not_run")
        export_manifest = {
            "engine": self.engine,
            "strategy": bundle.primary_strategy,
            "reference_mode": reference_mode,
            "engine_execution": engine_execution,
            "dependency": "nautilus_trader",
            "dependency_available": dependency_available,
            "nautilus_engine_smoke": engine_smoke,
            "inputs": {
                "result": "result.json",
                "prices": "price_series.csv",
                "signals": "signals.csv",
                "trades": "trades.csv",
                "fills": "fills.csv",
                "book_snapshots": "book_snapshots.csv",
                "trade_ticks": "trade_ticks.csv",
            },
            "outputs": {
                "signals": "reference_nautilus_signals.csv",
                "trades": "reference_nautilus_trades.csv",
                "equity_curve": "reference_nautilus_equity_curve.csv",
            },
            "limitations": [
                "Nautilus signal replay uses an advisory Strategy generated from exported/reference signals, not the project strategy source code.",
                "Signal-replay order/fill parity checks Nautilus market-order acceptance and fills; queue priority, L2/L3 fills, funding settlement, and exchange adapter behavior remain unvalidated.",
                "The output is suitable as advisory portability evidence only.",
            ],
        }
        return ReferenceResult(
            engine=self.engine,
            status="OK",
            reason=(
                "Nautilus-compatible artifact export/replay completed; "
                f"Nautilus advisory execution is {engine_execution}; full project strategy parity is not run in v1"
            ),
            reference_role="advisory",
            signals=signals,
            trades=trades,
            equity_curve=equity,
            metrics=metrics,
            metadata={
                "strategy": bundle.primary_strategy,
                "reference_mode": reference_mode,
                "engine_execution": engine_execution,
                "nautilus_engine_smoke": engine_smoke,
                "order_fill_parity_scope": "signal_replay_order_fill",
                "dependency": "nautilus_trader",
                "dependency_available": dependency_available,
                "price_input": price_input,
                "signal_position_source": _signal_position_source(bundle),
                "scope_limit": scope_limit,
                "required_full_adapter_data": "Nautilus catalog with L2/L3 order book, order/fill events, funding cashflows where applicable",
                "export_manifest": export_manifest,
            },
        )


def _nautilus_engine_smoke(
    bundle: ArtifactBundle,
    signals: pd.DataFrame | None = None,
    max_ticks: int = 500,
) -> dict[str, Any]:
    if importlib.util.find_spec("nautilus_trader") is None:
        return {
            "status": "SKIP",
            "engine_execution": "not_run",
            "reason": "nautilus_trader is not installed",
            "scope_limit": "dependency check only; no Nautilus BacktestEngine smoke run",
        }

    try:
        from nautilus_trader.backtest.config import BacktestEngineConfig
        from nautilus_trader.config import LoggingConfig
        from nautilus_trader.model.enums import OrderSide
        from nautilus_trader.model.enums import AggressorSide
        from nautilus_trader.test_kit.providers import TestInstrumentProvider
        from nautilus_trader.test_kit.stubs.component import TestComponentStubs
        from nautilus_trader.test_kit.stubs.data import TestDataStubs
        from nautilus_trader.trading.strategy import Strategy
    except Exception as exc:  # pragma: no cover - depends on optional package internals.
        return {
            "status": "FAIL",
            "engine_execution": "smoke_failed",
            "reason": f"failed to import Nautilus smoke helpers: {exc}",
            "scope_limit": "optional Nautilus dependency import only",
        }

    try:
        instruments, instrument_meta = _nautilus_smoke_instruments(bundle, TestInstrumentProvider, signals=signals)
        primary_instrument = next(iter(instruments.values()))
        replay_signals, replay_coverage = _nautilus_replay_signals(bundle, instruments=instruments, signals=signals)
        effective_max_ticks = max_ticks
        if replay_signals:
            effective_max_ticks = max(
                max_ticks,
                (
                    int(len(bundle.price_series))
                    + int(len(_book_snapshot_events(bundle)))
                    + int(len(_trade_tick_frame(bundle)))
                    + int(len(replay_signals))
                    + 1
                ),
            )
        ticks, input_rows = _nautilus_smoke_ticks(
            bundle,
            instruments,
            TestDataStubs,
            AggressorSide,
            max_ticks=effective_max_ticks,
            replay_signals=replay_signals,
        )
        if not ticks:
            return {
                "status": "SKIP",
                "engine_execution": "not_run",
                "reason": "no valid price_series/book/trade rows available for Nautilus smoke ticks",
                "instrument": instrument_meta,
                "input_rows": input_rows,
                "scope_limit": "artifact-to-Nautilus data conversion only",
            }

        result_meta: dict[str, Any] = {}
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            config = BacktestEngineConfig(
                logging=LoggingConfig(bypass_logging=True),
                run_analysis=False,
            )
            engine = TestComponentStubs.backtest_engine(
                config=config,
                instrument=primary_instrument,
                ticks=None,
                venue=primary_instrument.id.venue,
            )
            added_instrument_ids = {str(primary_instrument.id)}
            for instrument in list(instruments.values())[1:]:
                instrument_id = str(instrument.id)
                if instrument_id in added_instrument_ids:
                    continue
                engine.add_instrument(instrument)
                added_instrument_ids.add(instrument_id)
            engine.add_data(ticks)
            strategy = None
            if replay_signals:
                strategy = _nautilus_signal_replay_strategy(
                    Strategy,
                    OrderSide,
                    instruments,
                    replay_signals,
                )
                engine.add_strategy(strategy)
            try:
                engine.run()
                result = engine.get_result()
                for field in ("instance_id", "total_events", "total_orders", "total_positions"):
                    if hasattr(result, field):
                        result_meta[field] = getattr(result, field)
                if strategy is not None:
                    result_meta["strategy_order_attempts"] = int(getattr(strategy, "order_attempts", 0))
                    result_meta["strategy_fills"] = int(getattr(strategy, "fills", 0))
            finally:
                if hasattr(engine, "dispose"):
                    engine.dispose()
        orders = int(result_meta.get("total_orders") or 0)
        execution = "signal_replay_run" if replay_signals and orders > 0 else "smoke_run"
        reason = (
            "Nautilus BacktestEngine ran an advisory signal-replay Strategy and accepted generated orders"
            if execution == "signal_replay_run"
            else "Nautilus BacktestEngine accepted converted artifact ticks in a data smoke run"
        )
        return {
            "status": "OK",
            "engine_execution": execution,
            "reason": reason,
            "instrument": instrument_meta,
            "input_rows": input_rows,
            "ticks_submitted": len(ticks),
            "max_ticks_requested": int(max_ticks),
            "max_ticks_effective": int(effective_max_ticks),
            "data_types": sorted({type(tick).__name__ for tick in ticks}),
            "signals_available": int(replay_coverage["total_signal_rows"]),
            "signals_replayed": int(len(replay_signals)),
            "signal_replay_coverage": replay_coverage,
            "backtest_result": result_meta,
            "scope_limit": (
                "advisory signal replay with Nautilus order/fill parity; project strategy source logic, L2/L3 queue priority, funding settlement, and PnL are not validated"
                if execution == "signal_replay_run"
                else "engine data smoke only; no replayable buy/sell signals were executed"
            ),
        }
    except Exception as exc:  # pragma: no cover - depends on optional package internals.
        return {
            "status": "FAIL",
            "engine_execution": "smoke_failed",
            "reason": str(exc),
            "scope_limit": "engine smoke only; advisory export still available",
        }


def _nautilus_replay_signals(
    bundle: ArtifactBundle,
    instruments: dict[str, Any] | None = None,
    signals: pd.DataFrame | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    normalized = _normalize_signals(signals if signals is not None else bundle.signals)
    primary_symbol = str(bundle.symbols[0] if bundle.symbols else "").upper()
    mapped_symbols = set(instruments or ({primary_symbol: object()} if primary_symbol else {}))
    coverage = {
        "total_signal_rows": int(len(normalized)),
        "buy_sell_signal_rows": 0,
        "replayable_signal_rows": 0,
        "skipped_non_primary_symbol": 0,
        "skipped_unmapped_symbol": 0,
        "skipped_unsupported_side": 0,
        "skipped_invalid_timestamp": 0,
        "primary_symbol": primary_symbol,
        "mapped_symbols": sorted(symbol for symbol in mapped_symbols if symbol),
        "replayed_symbols": [],
        "skipped_symbols": [],
    }
    if normalized.empty:
        return [], coverage
    rows: list[dict[str, Any]] = []
    replayed_symbols: set[str] = set()
    skipped_symbols: set[str] = set()
    for _, row in normalized.iterrows():
        side = str(row.get("side") or "").lower()
        if side not in {"buy", "sell"}:
            coverage["skipped_unsupported_side"] += 1
            continue
        coverage["buy_sell_signal_rows"] += 1
        inst_id = str(row.get("inst_id") or "").upper()
        symbol_key = inst_id or primary_symbol
        if symbol_key not in mapped_symbols:
            coverage["skipped_non_primary_symbol"] += 1
            coverage["skipped_unmapped_symbol"] += 1
            skipped_symbols.add(inst_id)
            continue
        dt = _to_datetime(row.get("datetime", row.get("ts")))
        if pd.isna(dt):
            coverage["skipped_invalid_timestamp"] += 1
            continue
        fair_value = _safe_float(row.get("fair_value", row.get("price", row.get("close"))), float("nan"))
        replayed_symbols.add(symbol_key)
        rows.append({
            "ts_ns": _ts_ms(dt) * 1_000_000,
            "side": side,
            "source_inst_id": symbol_key,
            "instrument_key": symbol_key,
            "fair_value": fair_value if math.isfinite(fair_value) and fair_value > 0 else None,
        })
    rows.sort(key=lambda item: int(item["ts_ns"]))
    coverage["replayable_signal_rows"] = int(len(rows))
    coverage["replayed_symbols"] = sorted(symbol for symbol in replayed_symbols if symbol)
    coverage["skipped_symbols"] = sorted(symbol for symbol in skipped_symbols if symbol)
    return rows, coverage


def _nautilus_signal_replay_strategy(
    strategy_base: Any,
    order_side_enum: Any,
    instruments: dict[str, Any],
    signals: list[dict[str, Any]],
) -> Any:
    instrument_by_key = {str(key): instrument for key, instrument in instruments.items()}
    instrument_by_id: dict[str, Any] = {}
    pending_by_instrument_id: dict[str, deque[dict[str, Any]]] = {}
    for signal in sorted(signals, key=lambda item: int(item["ts_ns"])):
        instrument_key = str(signal.get("instrument_key") or "")
        instrument = instrument_by_key.get(instrument_key)
        if instrument is None:
            continue
        instrument_id = str(instrument.id)
        instrument_by_id[instrument_id] = instrument
        pending_by_instrument_id.setdefault(instrument_id, deque()).append(dict(signal))

    class ArtifactSignalReplayStrategy(strategy_base):
        def __init__(self) -> None:
            super().__init__()
            self.pending_by_instrument_id = {
                instrument_id: deque(rows)
                for instrument_id, rows in pending_by_instrument_id.items()
            }
            self.order_attempts = 0
            self.fills = 0
            self.replayed_signal_count = 0

        def on_start(self) -> None:
            seen: set[str] = set()
            for instrument in instrument_by_id.values():
                instrument_id = str(instrument.id)
                if instrument_id in seen:
                    continue
                self.subscribe_quote_ticks(instrument.id)
                seen.add(instrument_id)

        def on_quote_tick(self, tick: Any) -> None:
            instrument_id = str(tick.instrument_id)
            instrument = instrument_by_id.get(instrument_id)
            pending = self.pending_by_instrument_id.get(instrument_id)
            if instrument is None or pending is None:
                return
            while pending and int(pending[0]["ts_ns"]) <= int(tick.ts_event):
                signal = pending.popleft()
                side = signal["side"]
                order_side = order_side_enum.BUY if side == "buy" else order_side_enum.SELL
                order = self.order_factory.market(
                    instrument_id=instrument.id,
                    order_side=order_side,
                    quantity=instrument.make_qty(1),
                )
                self.order_attempts += 1
                self.replayed_signal_count += 1
                self.submit_order(order)

        def on_order_filled(self, event: Any) -> None:
            self.fills += 1

    return ArtifactSignalReplayStrategy()


def _nautilus_smoke_instruments(
    bundle: ArtifactBundle,
    provider: Any,
    signals: pd.DataFrame | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_symbols = _nautilus_source_symbols(bundle, signals=signals)
    instruments: dict[str, Any] = {}
    mapped_symbols: dict[str, str] = {}
    unsupported_symbols: list[str] = []
    for symbol in source_symbols:
        instrument = _nautilus_test_instrument_for_symbol(symbol, provider)
        if instrument is None:
            unsupported_symbols.append(symbol)
            continue
        instruments[symbol] = instrument
        mapped_symbols[symbol] = str(instrument.id)

    if not instruments:
        fallback_symbol = "BTC-USDT-SWAP"
        fallback = provider.btcusdt_perp_binance()
        instruments[fallback_symbol] = fallback
        mapped_symbols[fallback_symbol] = str(fallback.id)

    primary_symbol = next(iter(instruments))
    primary_instrument = instruments[primary_symbol]
    return instruments, {
        "source_symbols": source_symbols,
        "primary_symbol": primary_symbol,
        "smoke_instrument_id": str(primary_instrument.id),
        "mapped_symbols": mapped_symbols,
        "unsupported_symbols": unsupported_symbols,
        "mapping": "Nautilus test-kit perpetual instruments are currently available for BTC and ETH symbols only.",
    }


def _nautilus_source_symbols(bundle: ArtifactBundle, signals: pd.DataFrame | None = None) -> list[str]:
    symbols: list[str] = []

    def add_symbol(value: Any) -> None:
        symbol = str(value or "").upper()
        if symbol and symbol not in symbols:
            symbols.append(symbol)

    for symbol in bundle.symbols:
        add_symbol(symbol)
    if "inst_id" in bundle.price_series.columns:
        for symbol in bundle.price_series["inst_id"].dropna().astype(str).unique():
            add_symbol(symbol)
    normalized_signals = _normalize_signals(signals if signals is not None else bundle.signals)
    if "inst_id" in normalized_signals.columns:
        for symbol in normalized_signals["inst_id"].dropna().astype(str).unique():
            add_symbol(symbol)
    if not symbols:
        add_symbol("BTC-USDT-SWAP")
    return symbols


def _nautilus_test_instrument_for_symbol(symbol: str, provider: Any) -> Any | None:
    normalized = str(symbol or "").upper()
    if normalized.startswith("BTC"):
        return provider.btcusdt_perp_binance()
    if normalized.startswith("ETH"):
        return provider.ethusdt_perp_binance()
    return None


def _nautilus_smoke_ticks(
    bundle: ArtifactBundle,
    instruments: dict[str, Any],
    data_stubs: Any,
    aggressor_side: Any,
    *,
    max_ticks: int,
    replay_signals: list[dict[str, Any]] | None = None,
) -> tuple[list[Any], dict[str, Any]]:
    ticks: list[Any] = []
    input_rows = {
        "book_snapshots": 0,
        "trade_ticks": 0,
        "price_series": 0,
        "quote_ticks": 0,
        "trade_tick_ticks": 0,
        "terminal_replay_quote_ticks": 0,
        "mapped_symbols": sorted(instruments),
        "skipped_unmapped_book_snapshots": 0,
        "skipped_unmapped_price_rows": 0,
        "skipped_unmapped_trade_ticks": 0,
    }
    book_quote_symbols: set[str] = set()

    for event in _book_snapshot_events(bundle):
        if len(ticks) >= max_ticks:
            break
        symbol = str(event.get("inst_id") or "").upper()
        instrument = instruments.get(symbol)
        if instrument is None:
            input_rows["skipped_unmapped_book_snapshots"] += 1
            continue
        bid = _safe_float(event["bids"][0][0], float("nan"))
        ask = _safe_float(event["asks"][0][0], float("nan"))
        bid_size = _safe_float(event["bids"][0][1], float("nan"))
        ask_size = _safe_float(event["asks"][0][1], float("nan"))
        input_rows["book_snapshots"] += 1
        if not all(math.isfinite(value) and value > 0 for value in (bid, ask, bid_size, ask_size)):
            continue
        if bid >= ask:
            continue
        ts_ns = int(event["ts"]) * 1_000_000
        ticks.append(data_stubs.quote_tick(
            instrument=instrument,
            bid_price=bid,
            ask_price=ask,
            bid_size=bid_size,
            ask_size=ask_size,
            ts_event=ts_ns,
            ts_init=ts_ns,
        ))
        input_rows["quote_ticks"] += 1
        book_quote_symbols.add(symbol)

    price_frame = _nautilus_price_frame_for_smoke(bundle, instruments, book_quote_symbols)
    for _, row in price_frame.iterrows():
        if len(ticks) >= max_ticks:
            break
        input_rows["price_series"] += 1
        symbol = str(row.get("_inst_id") or "").upper()
        instrument = instruments.get(symbol)
        if instrument is None:
            input_rows["skipped_unmapped_price_rows"] += 1
            continue
        close = _safe_float(row.get("close"), float("nan"))
        dt = _to_datetime(row.get("datetime", row.get("ts")))
        if not math.isfinite(close) or close <= 0 or pd.isna(dt):
            continue
        spread = max(abs(close) * 0.0001, 0.1)
        bid = max(close - spread / 2.0, 0.000001)
        ask = close + spread / 2.0
        ts_ns = _ts_ms(dt) * 1_000_000
        ticks.append(data_stubs.quote_tick(
            instrument=instrument,
            bid_price=bid,
            ask_price=ask,
            bid_size=1.0,
            ask_size=1.0,
            ts_event=ts_ns,
            ts_init=ts_ns,
        ))
        input_rows["quote_ticks"] += 1

    trade_frame = _trade_tick_frame(bundle)
    input_rows["trade_ticks"] = int(len(trade_frame))
    for _, row in trade_frame.iterrows():
        if len(ticks) >= max_ticks:
            break
        symbol = str(row.get("inst_id") or "").upper()
        instrument = instruments.get(symbol)
        if instrument is None:
            input_rows["skipped_unmapped_trade_ticks"] += 1
            continue
        dt = _to_datetime(row.get("dt"))
        price = _safe_float(row.get("price"), float("nan"))
        size = _safe_float(row.get("size"), float("nan"))
        if pd.isna(dt) or not math.isfinite(price) or not math.isfinite(size) or price <= 0 or size <= 0:
            continue
        side = str(row.get("side") or "").lower()
        nautilus_side = aggressor_side.SELLER if side in {"sell", "ask"} else aggressor_side.BUYER
        trade_id = str(row.get("trade_id") or f"artifact-{input_rows['trade_tick_ticks'] + 1}")
        ts_ns = _ts_ms(dt) * 1_000_000
        ticks.append(data_stubs.trade_tick(
            instrument=instrument,
            price=price,
            size=size,
            aggressor_side=nautilus_side,
            trade_id=trade_id,
            ts_event=ts_ns,
            ts_init=ts_ns,
        ))
        input_rows["trade_tick_ticks"] += 1

    last_quote_ts_by_instrument: dict[str, int] = {}
    for tick in ticks:
        if type(tick).__name__ != "QuoteTick":
            continue
        instrument_id = str(getattr(tick, "instrument_id", ""))
        last_quote_ts_by_instrument[instrument_id] = max(
            last_quote_ts_by_instrument.get(instrument_id, -1),
            int(getattr(tick, "ts_event", 0)),
        )
    for signal in replay_signals or []:
        if len(ticks) >= max_ticks:
            break
        instrument = instruments.get(str(signal.get("instrument_key") or ""))
        if instrument is None:
            continue
        ts_ns = int(signal.get("ts_ns") or 0)
        instrument_id = str(instrument.id)
        if last_quote_ts_by_instrument.get(instrument_id, -1) >= ts_ns:
            continue
        price = _safe_float(signal.get("fair_value"), float("nan"))
        if not math.isfinite(price) or price <= 0:
            price = 1.0
        spread = max(abs(price) * 0.0001, 0.1)
        bid = max(price - spread / 2.0, 0.000001)
        ask = price + spread / 2.0
        ticks.append(data_stubs.quote_tick(
            instrument=instrument,
            bid_price=bid,
            ask_price=ask,
            bid_size=1.0,
            ask_size=1.0,
            ts_event=ts_ns,
            ts_init=ts_ns,
        ))
        input_rows["quote_ticks"] += 1
        input_rows["terminal_replay_quote_ticks"] += 1
        last_quote_ts_by_instrument[instrument_id] = ts_ns

    ticks.sort(key=lambda tick: int(getattr(tick, "ts_event", 0)))
    return ticks, input_rows


def _nautilus_price_frame_for_smoke(
    bundle: ArtifactBundle,
    instruments: dict[str, Any],
    book_quote_symbols: set[str],
) -> pd.DataFrame:
    if bundle.price_series.empty:
        return pd.DataFrame()
    frame = bundle.price_series.copy()
    if "inst_id" in frame.columns:
        frame["_inst_id"] = frame["inst_id"].astype(str).str.upper()
    else:
        primary = str(bundle.symbols[0] if bundle.symbols else "").upper()
        frame["_inst_id"] = primary
    frame["_dt"] = [_to_datetime(value) for value in _series_time(frame)]
    frame = frame.dropna(subset=["_dt"])
    if frame.empty:
        return frame
    target_symbols = set(instruments) - set(book_quote_symbols)
    if not target_symbols:
        return pd.DataFrame(columns=list(frame.columns))
    frame = frame[frame["_inst_id"].isin(target_symbols)]
    return frame.sort_values(["_dt", "_inst_id"]).reset_index(drop=True)


def _book_snapshot_events(bundle: ArtifactBundle) -> list[dict[str, Any]]:
    path = _resolve_artifact_path(bundle.run_dir, "book_snapshots")
    if path is None:
        return []
    df = _read_csv(path)
    if df.empty:
        return []
    required = {"inst_id", "side", "level", "px", "sz"}
    if not required.issubset(df.columns):
        return []
    work = df.copy()
    work["_dt"] = [_to_datetime(value) for value in _series_time(work)]
    work = work.dropna(subset=["_dt"])
    if work.empty:
        return []
    work["_ts_ms"] = [_ts_ms(ts) for ts in work["_dt"]]
    work["_seq_id"] = pd.to_numeric(work.get("seq_id", pd.Series(0, index=work.index)), errors="coerce").fillna(0)
    work["_level"] = pd.to_numeric(work["level"], errors="coerce")
    work["_px"] = pd.to_numeric(work["px"], errors="coerce")
    work["_sz"] = pd.to_numeric(work["sz"], errors="coerce")
    work["_side"] = work["side"].astype(str).str.lower()
    work = work.dropna(subset=["_level", "_px", "_sz"])
    work = work[(work["_px"] > 0) & (work["_sz"] > 0) & (work["_side"].isin(["bid", "ask"]))]
    events: list[dict[str, Any]] = []
    group_cols = ["inst_id", "_dt", "_ts_ms", "_seq_id"]
    for (inst_id, dt, ts_ms, seq_id), group in work.sort_values(group_cols + ["_side", "_level"]).groupby(group_cols, sort=True):
        bids_df = group[group["_side"] == "bid"].sort_values("_level")
        asks_df = group[group["_side"] == "ask"].sort_values("_level")
        if bids_df.empty or asks_df.empty:
            continue
        bids = bids_df[["_px", "_sz"]].to_numpy(dtype=float)
        asks = asks_df[["_px", "_sz"]].to_numpy(dtype=float)
        events.append({
            "inst_id": str(inst_id),
            "dt": _ensure_utc_timestamp(pd.Timestamp(dt)),
            "ts": int(ts_ms),
            "seq_id": int(seq_id),
            "bids": bids,
            "asks": asks,
        })
    events.sort(key=lambda item: (item["dt"], item["seq_id"], item["inst_id"]))
    return events


def _trade_tick_frame(bundle: ArtifactBundle) -> pd.DataFrame:
    path = _resolve_artifact_path(bundle.run_dir, "trade_ticks")
    if path is None:
        return pd.DataFrame(columns=["dt", "inst_id", "trade_id", "price", "size", "side"])
    df = _read_csv(path)
    if df.empty or not {"inst_id", "price", "size"}.issubset(df.columns):
        return pd.DataFrame(columns=["dt", "inst_id", "trade_id", "price", "size", "side"])
    work = df.copy()
    work["dt"] = [_to_datetime(value) for value in _series_time(work)]
    work["price"] = pd.to_numeric(work["price"], errors="coerce")
    work["size"] = pd.to_numeric(work["size"], errors="coerce")
    work["side"] = work["side"].astype(str).str.lower() if "side" in work.columns else ""
    work["trade_id"] = work["trade_id"].astype(str) if "trade_id" in work.columns else ""
    work = work.dropna(subset=["dt", "price", "size"])
    work = work[(work["price"] > 0) & (work["size"] > 0)]
    if work.empty:
        return pd.DataFrame(columns=["dt", "inst_id", "trade_id", "price", "size", "side"])
    return work[["dt", "inst_id", "trade_id", "price", "size", "side"]].sort_values("dt").reset_index(drop=True)


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
            "display_name": payload.get("display_name") or payload.get("validation_id", path.parent.name),
            "run_id": payload.get("run_id", Path(run_dir).name),
            "created_at": payload.get("created_at"),
            "status": payload.get("status"),
            "admissibility": payload.get("admissibility"),
            "promotion_gate_evidence": payload.get("promotion_gate_evidence"),
            "signal_logic_gate": payload.get("signal_logic_gate"),
            "portable_validation_gate": payload.get("portable_validation_gate"),
            "signal_point_correctness": payload.get("signal_point_correctness"),
            "nautilus_order_fill_parity": payload.get("nautilus_order_fill_parity"),
            "reference_validation_contract": payload.get("reference_validation_contract"),
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
                "display_name": payload.get("display_name") or payload.get("validation_id", path.parent.name),
                "validation_scope": payload.get("validation_scope", "strategy"),
                "strategy": payload.get("strategy", strategy_dir.name),
                "fixture_run_id": payload.get("fixture_run_id"),
                "fixture_display_name": payload.get("fixture_display_name") or payload.get("fixture_run_id"),
                "materialized_from_sweep_summary": bool(payload.get("materialized_from_sweep_summary")),
                "created_at": payload.get("created_at"),
                "status": payload.get("status"),
                "admissibility": payload.get("admissibility"),
                "promotion_gate_evidence": payload.get("promotion_gate_evidence"),
                "signal_logic_gate": payload.get("signal_logic_gate"),
                "portable_validation_gate": payload.get("portable_validation_gate"),
                "signal_point_correctness": payload.get("signal_point_correctness"),
                "nautilus_order_fill_parity": payload.get("nautilus_order_fill_parity"),
                "reference_validation_contract": payload.get("reference_validation_contract"),
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


def _daily_winner_reference_result(bundle: ArtifactBundle, engine: str) -> ReferenceResult:
    signals, trades, equity, price_input = _daily_winner_reference_components(bundle)
    metrics = neutral_metrics(equity, bundle.periods)
    return ReferenceResult(
        engine=engine,
        status="OK",
        reason=(
            "prior-day winner signal comparison is strict; synthetic fill costs, "
            "trade accounting, and PnL remain advisory in v1"
        ),
        reference_role="reference_signals_only",
        indicator_series=pd.DataFrame(columns=_indicator_columns()),
        signals=signals,
        trades=trades,
        equity_curve=equity,
        metrics=metrics,
        metadata={
            "strategy": bundle.primary_strategy,
            "reference_mode": "daily_winner_prior_day_recompute",
            "price_input": price_input,
            "scope_limit": "daily winner signal recompute only; synthetic fills and PnL are advisory",
        },
    )


def _daily_winner_reference_components(
    bundle: ArtifactBundle,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    frames, price_input = _daily_winner_reference_price_frames(bundle)
    if len(frames) < 2:
        raise ValueError("daily_winner reference validation needs at least two symbols with OHLCV rows")
    open_panel, close_panel = _daily_winner_open_close_panels(frames)
    if len(open_panel.index) < 2:
        raise ValueError("daily_winner reference validation needs at least two daily bars")

    signal_returns = close_panel / open_panel - 1.0
    cost_rate = _daily_winner_reference_cost_rate(bundle)
    equity = float(bundle.initial_equity)
    signal_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    equity_rows: list[dict[str, Any]] = [{
        "ts": _ts_ms(open_panel.index[0]),
        "datetime": _iso(open_panel.index[0]),
        "equity": equity,
    }]

    for idx in range(1, len(open_panel.index)):
        signal_date = open_panel.index[idx - 1]
        trade_date = open_panel.index[idx]
        signal_row = signal_returns.loc[signal_date].replace([np.inf, -np.inf], np.nan).dropna()
        if signal_row.empty:
            equity_rows.append({
                "ts": _ts_ms(trade_date),
                "datetime": _iso(trade_date),
                "equity": equity,
            })
            continue
        winner = str(signal_row.idxmax())
        entry_price = _safe_float(open_panel.loc[trade_date, winner], float("nan"))
        exit_price = _safe_float(close_panel.loc[trade_date, winner], float("nan"))
        if not math.isfinite(entry_price) or not math.isfinite(exit_price) or entry_price <= 0:
            equity_rows.append({
                "ts": _ts_ms(trade_date),
                "datetime": _iso(trade_date),
                "equity": equity,
            })
            continue

        exit_ts = trade_date + pd.Timedelta(days=1)
        qty = equity / entry_price if entry_price > 0 else 0.0
        gross_return = exit_price / entry_price - 1.0
        net_return = gross_return - cost_rate
        pnl = equity * net_return
        signal_rows.extend([
            {
                "ts": _ts_ms(trade_date),
                "datetime": _iso(trade_date),
                "strategy": "daily_winner",
                "inst_id": winner,
                "side": "buy",
                "fair_value": entry_price,
            },
            {
                "ts": _ts_ms(exit_ts),
                "datetime": _iso(exit_ts),
                "strategy": "daily_winner",
                "inst_id": winner,
                "side": "sell",
                "fair_value": exit_price,
            },
        ])
        trade_rows.extend([
            {
                "ts": _ts_ms(trade_date),
                "datetime": _iso(trade_date),
                "strategy": "daily_winner",
                "inst_id": winner,
                "side": "buy",
                "price": entry_price,
                "qty": qty,
                "pnl": float("nan"),
            },
            {
                "ts": _ts_ms(exit_ts),
                "datetime": _iso(exit_ts),
                "strategy": "daily_winner",
                "inst_id": winner,
                "side": "sell",
                "price": exit_price,
                "qty": qty,
                "pnl": pnl,
            },
        ])
        equity += pnl
        equity_rows.append({
            "ts": _ts_ms(trade_date),
            "datetime": _iso(trade_date),
            "equity": equity,
        })

    signals = pd.DataFrame(signal_rows, columns=["ts", "datetime", "strategy", "inst_id", "side", "fair_value"])
    trades = pd.DataFrame(trade_rows, columns=["ts", "datetime", "strategy", "inst_id", "side", "price", "qty", "pnl"])
    equity_curve = pd.DataFrame(equity_rows, columns=["ts", "datetime", "equity"])
    return signals, trades, equity_curve, price_input


def _daily_winner_reference_price_frames(bundle: ArtifactBundle) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    frames: dict[str, pd.DataFrame] = {}
    symbol_metadata: list[dict[str, Any]] = []
    symbols = bundle.symbols or _daily_winner_symbols_from_result(bundle.result)
    for symbol in symbols:
        frame, metadata = _reference_price_frame_for_symbol(bundle, symbol)
        symbol_metadata.append(metadata)
        if not frame.empty:
            frames[symbol] = frame
    sources = {str(row.get("source") or "unknown") for row in symbol_metadata}
    source = sources.pop() if len(sources) == 1 else "mixed_reference_price_frames"
    price_input = {
        "source": source,
        "symbols": symbol_metadata,
        "rows": int(sum(len(frame) for frame in frames.values())),
        "reason": "Daily winner reference uses per-symbol OHLCV frames for independent prior-day winner recompute.",
    }
    _set_reference_price_input_metadata(bundle, price_input)
    return frames, price_input


def _daily_winner_symbols_from_result(result: dict[str, Any]) -> list[str]:
    symbols: list[str] = []
    for row in (result.get("round_trips") or []) + (result.get("trades") or []):
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("inst_id") or row.get("symbol") or "")
        if symbol and symbol not in symbols:
            symbols.append(symbol)
    return symbols


def _daily_winner_open_close_panels(frames: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    opens: dict[str, pd.Series] = {}
    closes: dict[str, pd.Series] = {}
    for symbol, frame in frames.items():
        if frame.empty or "open" not in frame.columns or "close" not in frame.columns:
            continue
        data = frame.copy()
        data["_dt"] = pd.to_datetime(_series_time(data), utc=True, errors="coerce")
        data = data.dropna(subset=["_dt"]).sort_values("_dt")
        if data.empty:
            continue
        data["_day"] = data["_dt"].dt.normalize()
        grouped = data.groupby("_day", sort=True)
        opens[symbol] = grouped["open"].first()
        closes[symbol] = grouped["close"].last()
    if not opens:
        raise ValueError("daily_winner reference validation found no usable OHLCV rows")
    open_panel = pd.DataFrame(opens).sort_index()
    close_panel = pd.DataFrame(closes).sort_index()
    common_index = open_panel.index.intersection(close_panel.index)
    return open_panel.loc[common_index], close_panel.loc[common_index]


def _daily_winner_reference_cost_rate(bundle: ArtifactBundle) -> float:
    round_trips = [row for row in bundle.result.get("round_trips") or [] if isinstance(row, dict)]
    for row in round_trips:
        value = _safe_float(row.get("cost_rate"), float("nan"))
        if math.isfinite(value):
            return abs(value)
    params = bundle.strategy_params("daily_winner")
    fee_bps = _safe_float(params.get("fee_bps"), 2.0)
    slippage_bps = _safe_float(params.get("slippage_bps"), 2.0)
    return 2.0 * (fee_bps + slippage_bps) / 10_000.0


def _ohlcv_rotation_reference_result(bundle: ArtifactBundle, engine: str) -> ReferenceResult:
    signals, trades, equity, price_input = _ohlcv_rotation_reference_components(bundle)
    metrics = neutral_metrics(equity, bundle.periods)
    return ReferenceResult(
        engine=engine,
        status="OK",
        reason=(
            "cross-sectional rebalance signal comparison is strict; multi-asset "
            "fill sequencing, PnL, and metrics remain advisory in v1"
        ),
        reference_role="reference_signals_only",
        indicator_series=pd.DataFrame(columns=_indicator_columns()),
        signals=signals,
        trades=trades,
        equity_curve=equity,
        metrics=metrics,
        metadata={
            "strategy": bundle.primary_strategy,
            "reference_mode": "ohlcv_rotation_target_weight_recompute",
            "price_input": price_input,
            "scope_limit": "target-weight signal recompute only; multi-asset fills and PnL are advisory",
        },
    )


def _ohlcv_rotation_reference_components(
    bundle: ArtifactBundle,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    frames, price_input = _ohlcv_rotation_reference_price_frames(bundle)
    if len(frames) < 2:
        raise ValueError("ohlcv_rotation reference validation needs at least two symbols with OHLCV rows")
    close, high, low, vol = _ohlcv_rotation_wide_panels(frames)
    if close.empty:
        raise ValueError("ohlcv_rotation reference validation found no usable OHLCV rows")

    params = _ohlcv_rotation_params(bundle, list(close.columns))
    if params.benchmark_inst_id not in close.columns:
        raise ValueError(f"ohlcv_rotation benchmark {params.benchmark_inst_id} is missing from reference prices")

    from okx_quant.strategies.ohlcv_rotation import (
        apply_exit_rules,
        build_feature_panel,
        compute_benchmark_regime,
        compute_cross_sectional_scores,
        generate_target_weights,
    )

    features = build_feature_panel(close, high, low, vol, params)
    features["close"] = close
    scores = compute_cross_sectional_scores(features, params)
    regime = compute_benchmark_regime(close[params.benchmark_inst_id], params)
    rebalance_ts = _ohlcv_rotation_rebalance_timestamps(close.index, params.rebalance_minutes)
    raw_weights = generate_target_weights(scores, features, regime, params, rebalance_ts)
    target_weights = apply_exit_rules(raw_weights, features, scores, regime, params)

    signals = _ohlcv_rotation_weight_signals(target_weights, close)
    trades = _ohlcv_rotation_trades_from_signals(signals)
    equity = _ohlcv_rotation_reference_equity(bundle, close, target_weights, params)
    return signals, trades, equity, price_input


def _ohlcv_rotation_reference_price_frames(bundle: ArtifactBundle) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    frames: dict[str, pd.DataFrame] = {}
    symbol_metadata: list[dict[str, Any]] = []
    for symbol in bundle.symbols:
        frame, metadata = _reference_price_frame_for_symbol(bundle, symbol)
        symbol_metadata.append(metadata)
        prepared = _ohlcv_rotation_prepare_price_frame(frame)
        if not prepared.empty:
            frames[symbol] = prepared
    sources = {str(row.get("source") or "unknown") for row in symbol_metadata}
    source = sources.pop() if len(sources) == 1 else "mixed_reference_price_frames"
    price_input = {
        "source": source,
        "symbols": symbol_metadata,
        "rows": int(sum(len(frame) for frame in frames.values())),
        "reason": "OHLCV rotation reference uses per-symbol OHLCV frames for independent target-weight recompute.",
    }
    _set_reference_price_input_metadata(bundle, price_input)
    return frames, price_input


def _ohlcv_rotation_prepare_price_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "vol"])
    data = frame.copy()
    data["_dt"] = [_naive_utc_timestamp(value) for value in _series_time(data)]
    data = data.dropna(subset=["_dt"]).sort_values("_dt")
    data = data[~data["_dt"].duplicated(keep="last")]
    if data.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "vol"])
    for column in ["open", "high", "low", "close", "vol"]:
        if column not in data.columns:
            data[column] = float("nan")
        data[column] = pd.to_numeric(data[column], errors="coerce")
    out = data.set_index("_dt")[["open", "high", "low", "close", "vol"]]
    out.index = pd.DatetimeIndex(out.index)
    return out


def _ohlcv_rotation_wide_panels(
    frames: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    close = pd.DataFrame({symbol: frame["close"] for symbol, frame in frames.items()}).sort_index()
    high = pd.DataFrame({symbol: frame["high"] for symbol, frame in frames.items()}).reindex(close.index)
    low = pd.DataFrame({symbol: frame["low"] for symbol, frame in frames.items()}).reindex(close.index)
    vol = pd.DataFrame({symbol: frame["vol"] for symbol, frame in frames.items()}).reindex(close.index)
    return close, high, low, vol


def _ohlcv_rotation_params(bundle: ArtifactBundle, symbols: list[str]) -> Any:
    from okx_quant.strategies.ohlcv_rotation import OHLCVRotationParams

    raw: dict[str, Any] = {}
    config_params = bundle.strategy_params("ohlcv_rotation")
    raw.update(config_params)
    result_params = bundle.result.get("parameters") if isinstance(bundle.result.get("parameters"), dict) else {}
    strategies = result_params.get("strategies") if isinstance(result_params.get("strategies"), dict) else {}
    strategy_params = strategies.get("ohlcv_rotation") if isinstance(strategies.get("ohlcv_rotation"), dict) else {}
    raw.update(strategy_params)
    backtest_params = result_params.get("backtest") if isinstance(result_params.get("backtest"), dict) else {}
    if "fill_all_signals" in backtest_params and "fill_all_signals" not in raw:
        raw["fill_all_signals"] = bool(backtest_params.get("fill_all_signals"))

    benchmark = (
        raw.get("benchmark_inst_id")
        or raw.get("benchmark")
        or bundle.result.get("benchmark")
        or (symbols[0] if symbols else "BTC-USDT-SWAP")
    )
    params = OHLCVRotationParams(
        universe=list(symbols),
        benchmark_inst_id=str(benchmark),
        bar=str(raw.get("bar") or bundle.bar or "1m"),
    )
    for key, value in raw.items():
        if key in {"universe", "benchmark", "benchmark_inst_id", "bar"}:
            continue
        if not hasattr(params, key):
            continue
        current = getattr(params, key)
        try:
            if isinstance(current, bool):
                value = bool(value)
            elif isinstance(current, int) and not isinstance(current, bool):
                value = int(value)
            elif isinstance(current, float):
                value = float(value)
        except (TypeError, ValueError):
            continue
        setattr(params, key, value)
    params.universe = list(symbols)
    if params.benchmark_inst_id not in symbols and symbols:
        params.benchmark_inst_id = symbols[0]
    return params


def _ohlcv_rotation_rebalance_timestamps(index: pd.DatetimeIndex, rebalance_minutes: int) -> pd.DatetimeIndex:
    if len(index) == 0:
        return pd.DatetimeIndex([])
    minutes = max(int(rebalance_minutes or 1), 1)
    return pd.DatetimeIndex(index[index.minute % minutes == 0])


def _ohlcv_rotation_weight_signals(
    target_weights: pd.DataFrame,
    close_panel: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if target_weights.empty:
        return pd.DataFrame(columns=["ts", "datetime", "strategy", "inst_id", "side", "fair_value"])
    weights = target_weights.copy().sort_index()
    rows: list[dict[str, Any]] = []
    prev = pd.Series(0.0, index=weights.columns)
    aligned_close = close_panel.reindex(weights.index, method="ffill") if close_panel is not None and not close_panel.empty else None
    for ts, curr in weights.iterrows():
        dt = _to_datetime(ts)
        if pd.isna(dt):
            prev = curr
            continue
        for inst in weights.columns:
            before = _safe_float(prev.get(inst), 0.0)
            after = _safe_float(curr.get(inst), 0.0)
            side = ""
            if before <= 0.0 and after > 0.0:
                side = "buy"
            elif before > 0.0 and after <= 0.0:
                side = "sell"
            if not side:
                continue
            fair_value = float("nan")
            if aligned_close is not None and ts in aligned_close.index and inst in aligned_close.columns:
                fair_value = _safe_float(aligned_close.loc[ts, inst], float("nan"))
            rows.append({
                "ts": _ts_ms(dt),
                "datetime": _iso(dt),
                "strategy": "ohlcv_rotation",
                "inst_id": inst,
                "side": side,
                "fair_value": fair_value,
            })
        prev = curr
    return pd.DataFrame(rows, columns=["ts", "datetime", "strategy", "inst_id", "side", "fair_value"])


def _ohlcv_rotation_reference_equity(
    bundle: ArtifactBundle,
    close: pd.DataFrame,
    target_weights: pd.DataFrame,
    params: Any,
) -> pd.DataFrame:
    if close.empty:
        return pd.DataFrame(columns=["ts", "datetime", "equity"])
    if target_weights.empty:
        equity = pd.Series(float(bundle.initial_equity), index=close.index)
    else:
        target_upsampled = target_weights.reindex(close.index).ffill().fillna(0.0)
        actual_weights = target_upsampled.shift(1).fillna(0.0)
        returns = close.pct_change().fillna(0.0)
        gross = (actual_weights * returns).sum(axis=1)
        turnover = target_upsampled.diff().abs().sum(axis=1).fillna(0.0)
        costs = turnover * (
            _safe_float(getattr(params, "fee_bps", 0.0), 0.0)
            + _safe_float(getattr(params, "slippage_bps", 0.0), 0.0)
        ) / 10_000.0
        equity = (1.0 + gross - costs).cumprod() * float(bundle.initial_equity)
    return pd.DataFrame({
        "ts": [_ts_ms(_to_datetime(ts)) for ts in equity.index],
        "datetime": [_iso(_to_datetime(ts)) for ts in equity.index],
        "equity": equity.to_numpy(dtype=float),
    })


def _ohlcv_rotation_trades_from_signals(signals: pd.DataFrame) -> pd.DataFrame:
    if signals.empty:
        return pd.DataFrame(columns=["datetime", "side", "price", "qty", "pnl"])
    return pd.DataFrame({
        "datetime": signals["datetime"],
        "side": signals["side"],
        "price": pd.to_numeric(signals.get("fair_value", pd.Series(float("nan"), index=signals.index)), errors="coerce"),
        "qty": pd.Series(float("nan"), index=signals.index),
        "pnl": pd.Series(float("nan"), index=signals.index),
    })


@dataclass
class _PairsReferenceParams:
    symbol_y: str = "ETH-USDT-SWAP"
    symbol_x: str = "BTC-USDT-SWAP"
    kalman_delta: float = 1e-4
    entry_z: float = 2.0
    exit_z: float = 0.3
    stop_z: float = 4.0
    lookback_hours: int = 168
    bar_seconds: int = 3600
    max_half_life_hours: float = 48.0
    max_hedge_uncertainty: float = 10.0


def _pairs_trading_reference_result(bundle: ArtifactBundle, engine: str) -> ReferenceResult:
    signals, trades, equity, price_input = _pairs_trading_reference_components(bundle)
    metrics = neutral_metrics(equity, bundle.periods)
    return ReferenceResult(
        engine=engine,
        status="OK",
        reason=(
            "pairs Kalman/OU y-leg signal comparison is strict; hedge-leg execution, "
            "fill latency, spread accounting, and PnL remain advisory in v1"
        ),
        reference_role="reference_signals_only",
        indicator_series=pd.DataFrame(columns=_indicator_columns()),
        signals=signals,
        trades=trades,
        equity_curve=equity,
        metrics=metrics,
        metadata={
            "strategy": bundle.primary_strategy,
            "reference_mode": "pairs_trading_kalman_ou_signal_recompute",
            "price_input": price_input,
            "state_model": price_input.get("state_model"),
            "scope_limit": "y-leg Kalman/OU signal recompute only; hedge leg fills and PnL are advisory",
        },
    )


def _pairs_trading_reference_components(
    bundle: ArtifactBundle,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    params = _pairs_trading_params(bundle)
    frames, price_input = _pairs_trading_reference_price_frames(bundle, params)
    events = _pairs_trading_price_events(frames)
    if len(events) < 2:
        raise ValueError("pairs_trading reference validation needs paired price rows for symbol_y and symbol_x")

    signals, state_model = _pairs_trading_signal_rows(bundle, events, params)
    price_input["state_model"] = state_model
    trades = _pairs_trading_trades_from_signals(signals)
    equity = _pairs_trading_reference_equity(bundle, events)
    return signals, trades, equity, price_input


def _pairs_trading_params(bundle: ArtifactBundle) -> _PairsReferenceParams:
    raw: dict[str, Any] = {}
    raw.update(bundle.strategy_params("pairs_trading"))
    result_params = bundle.result.get("parameters") if isinstance(bundle.result.get("parameters"), dict) else {}
    strategies = result_params.get("strategies") if isinstance(result_params.get("strategies"), dict) else {}
    result_strategy = strategies.get("pairs_trading") if isinstance(strategies, dict) else {}
    if isinstance(result_strategy, dict):
        raw.update(result_strategy)

    symbols = [symbol for symbol in bundle.symbols if symbol]
    symbol_y = str(raw.get("symbol_y") or (symbols[0] if symbols else "ETH-USDT-SWAP"))
    symbol_x = str(raw.get("symbol_x") or next((symbol for symbol in symbols if symbol != symbol_y), "BTC-USDT-SWAP"))
    bar_seconds = raw.get("bar_seconds")
    if bar_seconds is None:
        delta = _bar_timedelta(bundle.bar)
        bar_seconds = int(delta.total_seconds()) if delta is not None else 3600
    max_half_life = raw.get("max_half_life_hours", raw.get("max_half_life", 48.0))
    return _PairsReferenceParams(
        symbol_y=symbol_y,
        symbol_x=symbol_x,
        kalman_delta=_safe_float(raw.get("kalman_delta"), 1e-4),
        entry_z=_safe_float(raw.get("entry_z"), 2.0),
        exit_z=_safe_float(raw.get("exit_z"), 0.3),
        stop_z=_safe_float(raw.get("stop_z"), 4.0),
        lookback_hours=max(int(_safe_float(raw.get("lookback_hours"), 168.0)), 1),
        bar_seconds=max(int(_safe_float(bar_seconds, 3600.0)), 1),
        max_half_life_hours=_safe_float(max_half_life, 48.0),
        max_hedge_uncertainty=_safe_float(raw.get("max_hedge_uncertainty"), 10.0),
    )


def _pairs_trading_reference_price_frames(
    bundle: ArtifactBundle,
    params: _PairsReferenceParams,
) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    frames: dict[str, pd.DataFrame] = {}
    symbol_metadata: list[dict[str, Any]] = []
    for symbol in [params.symbol_y, params.symbol_x]:
        frame, metadata = _reference_price_frame_for_symbol(bundle, symbol)
        symbol_metadata.append(metadata)
        prepared = _pairs_trading_prepare_price_frame(frame)
        if not prepared.empty:
            frames[symbol] = prepared
    sources = {str(row.get("source") or "unknown") for row in symbol_metadata}
    source = sources.pop() if len(sources) == 1 else "mixed_reference_price_frames"
    price_input = {
        "source": source,
        "symbols": symbol_metadata,
        "rows": int(sum(len(frame) for frame in frames.values())),
        "reason": "Pairs reference uses y/x price_series rows for independent Kalman/OU y-leg signal recompute.",
    }
    _set_reference_price_input_metadata(bundle, price_input)
    return frames, price_input


def _pairs_trading_prepare_price_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["_dt", "_ts", "_order", "inst_id", "_price"])
    data = frame.copy()
    data["_dt"] = [_to_datetime(value) for value in _series_time(data)]
    data = data.dropna(subset=["_dt"])
    if data.empty:
        return pd.DataFrame(columns=["_dt", "_ts", "_order", "inst_id", "_price"])
    orders: list[int] = []
    for pos, idx in enumerate(data.index):
        try:
            orders.append(int(idx))
        except (TypeError, ValueError):
            orders.append(pos)
    data["_order"] = orders
    price_source = "close" if "close" in data.columns else ("fair_value" if "fair_value" in data.columns else "")
    if not price_source:
        return pd.DataFrame(columns=["_dt", "_ts", "_order", "inst_id", "_price"])
    data["_price"] = pd.to_numeric(data[price_source], errors="coerce")
    data = data.dropna(subset=["_price"])
    data = data[data["_price"] > 0].copy()
    if data.empty:
        return pd.DataFrame(columns=["_dt", "_ts", "_order", "inst_id", "_price"])
    data["_ts"] = [_ts_ms(_ensure_utc_timestamp(ts)) for ts in data["_dt"]]
    return data.sort_values(["_ts", "_order"])[["_dt", "_ts", "_order", "inst_id", "_price"]]


def _pairs_trading_price_events(frames: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for symbol, frame in frames.items():
        for _, row in frame.iterrows():
            rows.append({
                "symbol": symbol,
                "dt": _ensure_utc_timestamp(row["_dt"]),
                "ts": int(row["_ts"]),
                "order": int(row["_order"]),
                "price": _safe_float(row["_price"], float("nan")),
            })
    rows.sort(key=lambda row: (row["ts"], row["order"], row["symbol"]))
    return rows


def _pairs_trading_signal_rows(
    bundle: ArtifactBundle,
    events: list[dict[str, Any]],
    params: _PairsReferenceParams,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    kd = min(max(float(params.kalman_delta), 1e-12), 0.999999)
    beta = 1.0
    p_value = 1.0
    r_value = 1.0
    ve_value = kd / (1.0 - kd)
    spread_history: list[float] = []
    max_spreads = max(int(params.lookback_hours) * 60, 1)
    ou_params = {"theta": 0.0, "mu": float("nan"), "sigma": float("nan"), "half_life": float("inf")}
    ou_calibrated = False
    in_position = False
    position_side = ""
    last_ou_update_ms = 0
    last_spread_ts_ms = 0
    latest_price: dict[str, float] = {}
    latest_ts: dict[str, int] = {}
    fill_events = _pairs_trading_fill_transitions(bundle, params)
    fill_idx = 0
    rows: list[dict[str, Any]] = []

    def apply_fills(up_to_ts: int) -> None:
        nonlocal fill_idx, in_position, position_side
        while fill_idx < len(fill_events) and fill_events[fill_idx]["ts"] <= up_to_ts:
            fill = fill_events[fill_idx]
            action = fill["action"]
            if action == "entry":
                in_position = True
                position_side = "short_y" if fill.get("side") == "sell" else "long_y"
            elif action in {"exit", "stop"}:
                in_position = False
                position_side = ""
            fill_idx += 1

    for event in events:
        current_ts_ms = int(event["ts"])
        if fill_events:
            apply_fills(current_ts_ms)
        symbol = str(event["symbol"])
        price = _safe_float(event["price"], float("nan"))
        if not math.isfinite(price) or price <= 0:
            continue
        latest_price[symbol] = price
        latest_ts[symbol] = current_ts_ms
        if params.symbol_y not in latest_price or params.symbol_x not in latest_price:
            continue

        pair_ts_ms = min(latest_ts[params.symbol_y], latest_ts[params.symbol_x])
        if pair_ts_ms <= last_spread_ts_ms:
            continue
        price_y = latest_price[params.symbol_y]
        price_x = latest_price[params.symbol_x]
        log_y = math.log(price_y)
        log_x = math.log(price_x)

        p_pred = p_value + ve_value
        innov = log_y - beta * log_x
        s_value = p_pred * log_x ** 2 + r_value
        if s_value != 0:
            kalman_gain = p_pred * log_x / s_value
            beta += kalman_gain * innov
            p_value = (1.0 - kalman_gain * log_x) * p_pred
        spread = innov
        spread_history.append(float(spread))
        if len(spread_history) > max_spreads:
            spread_history = spread_history[-max_spreads:]
        last_spread_ts_ms = pair_ts_ms

        if current_ts_ms - last_ou_update_ms > 3_600_000 and len(spread_history) > 100:
            ou_params = _pairs_estimate_ou(pd.Series(spread_history, dtype=float))
            ou_calibrated = True
            last_ou_update_ms = current_ts_ms

        mu = _safe_float(ou_params.get("mu"), float("nan"))
        sigma = _safe_float(ou_params.get("sigma"), float("nan"))
        if not math.isfinite(mu) or not math.isfinite(sigma) or sigma <= 0:
            continue
        z_score = (spread - mu) / sigma
        current_dt = _ensure_utc_timestamp(event["dt"])

        if abs(z_score) > params.stop_z and in_position:
            side = "buy" if position_side == "short_y" else "sell"
            rows.append(_pairs_signal_row(current_ts_ms, current_dt, params.symbol_y, side, price_y, "stop", z_score, beta))
            if not fill_events:
                in_position = False
                position_side = ""
            continue

        if in_position and abs(z_score) < params.exit_z:
            side = "buy" if position_side == "short_y" else "sell"
            rows.append(_pairs_signal_row(current_ts_ms, current_dt, params.symbol_y, side, price_y, "exit", z_score, beta))
            if not fill_events:
                in_position = False
                position_side = ""
            continue

        if not in_position and abs(z_score) > params.entry_z:
            gate_ok, _ = _pairs_quality_gate_passed(
                ou_params,
                p_value,
                params.bar_seconds,
                params.max_half_life_hours,
                params.max_hedge_uncertainty,
                ou_calibrated,
            )
            if not gate_ok:
                continue
            side = "sell" if z_score > 0 else "buy"
            position_side = "short_y" if side == "sell" else "long_y"
            rows.append(_pairs_signal_row(current_ts_ms, current_dt, params.symbol_y, side, price_y, "entry", z_score, beta))
            if not fill_events:
                in_position = True

    signals = pd.DataFrame(rows, columns=["ts", "datetime", "strategy", "inst_id", "side", "fair_value", "metadata"])
    state_model = {
        "source": "fills_metadata" if fill_events else "signal_immediate_assumption",
        "fill_events_used": len(fill_events),
        "limitation": (
            "Uses fills.csv action metadata to mirror strategy _in_position state."
            if fill_events
            else "No fill action metadata was available; reference assumes signal state changes immediately."
        ),
    }
    return signals, state_model


def _pairs_signal_row(
    ts_ms: int,
    dt: pd.Timestamp,
    inst_id: str,
    side: str,
    fair_value: float,
    action: str,
    z_score: float,
    beta: float,
) -> dict[str, Any]:
    return {
        "ts": int(ts_ms),
        "datetime": _iso(dt),
        "strategy": "pairs_trading",
        "inst_id": inst_id,
        "side": side,
        "fair_value": fair_value,
        "metadata": {
            "action": action,
            "z_score": float(z_score),
            "beta": float(beta),
        },
    }


def _pairs_quality_gate_passed(
    ou_params: dict[str, Any],
    p_value: float,
    bar_seconds: int,
    max_half_life_hours: float,
    max_hedge_uncertainty: float,
    ou_calibrated: bool,
) -> tuple[bool, str]:
    if not ou_calibrated:
        return False, "not_calibrated"
    half_life_bars = _safe_float(ou_params.get("half_life"), float("inf"))
    half_life_hours = half_life_bars * max(int(bar_seconds), 1) / 3600.0
    sigma = _safe_float(ou_params.get("sigma"), 0.0)
    if not math.isfinite(half_life_bars) or half_life_bars <= 0:
        return False, "invalid_half_life"
    if half_life_hours > max_half_life_hours:
        return False, "half_life_too_slow"
    if sigma <= 0 or not math.isfinite(sigma):
        return False, "invalid_spread_sigma"
    if p_value > max_hedge_uncertainty:
        return False, "hedge_ratio_uncertain"
    return True, "passed"


def _pairs_estimate_ou(spread: pd.Series) -> dict[str, float]:
    clean = pd.to_numeric(spread, errors="coerce").dropna()
    lag = clean.shift(1).dropna()
    dlt = clean.diff().dropna()
    idx = lag.index.intersection(dlt.index)
    lag = lag.loc[idx]
    dlt = dlt.loc[idx]
    if len(lag) < 10:
        return {
            "theta": 0.0,
            "mu": float(clean.mean()) if not clean.empty else float("nan"),
            "sigma": float(clean.std()) if len(clean) > 1 else float("nan"),
            "half_life": float("inf"),
        }
    x = lag.to_numpy(dtype=float)
    y = dlt.to_numpy(dtype=float)
    design = np.column_stack([np.ones_like(x), x])
    try:
        a_value, b_value = np.linalg.lstsq(design, y, rcond=None)[0]
    except np.linalg.LinAlgError:
        return {
            "theta": 0.0,
            "mu": float(clean.mean()),
            "sigma": float(clean.std()),
            "half_life": float("inf"),
        }
    if b_value >= 0:
        return {
            "theta": 0.0,
            "mu": float(clean.mean()),
            "sigma": float(clean.std()),
            "half_life": float("inf"),
        }
    residual = y - (a_value + b_value * x)
    denom = 1.0 - math.exp(2.0 * b_value)
    sigma_scale = -2.0 * b_value / denom if denom != 0 else float("nan")
    sigma = float(np.std(residual)) * math.sqrt(sigma_scale) if sigma_scale > 0 else float("nan")
    theta = -float(b_value)
    return {
        "theta": theta,
        "mu": float(-a_value / b_value),
        "sigma": sigma,
        "half_life": float(math.log(2.0) / theta),
    }


def _pairs_trading_fill_transitions(
    bundle: ArtifactBundle,
    params: _PairsReferenceParams,
) -> list[dict[str, Any]]:
    if bundle.fills.empty:
        return []
    fills = bundle.fills.copy()
    if "strategy" in fills.columns:
        fills = fills[fills["strategy"].astype(str) == "pairs_trading"]
    if "inst_id" in fills.columns:
        fills = fills[fills["inst_id"].astype(str) == params.symbol_y]
    if fills.empty:
        return []
    rows: list[dict[str, Any]] = []
    for _, row in fills.iterrows():
        state = str(row.get("state") or "filled").lower()
        if state not in {"filled", "partially_filled", "fill"}:
            continue
        fill_sz = _safe_float(row.get("fill_sz"), 0.0)
        if fill_sz <= 0:
            continue
        metadata = _metadata_dict(row.get("metadata"))
        action = str(metadata.get("action") or "").lower()
        if action not in {"entry", "exit", "stop"}:
            continue
        dt = _to_datetime(row.get("datetime", row.get("ts")))
        if pd.isna(dt):
            continue
        rows.append({
            "ts": _ts_ms(dt),
            "action": action,
            "side": str(row.get("side") or "").lower(),
        })
    rows.sort(key=lambda row: row["ts"])
    return rows


def _metadata_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            try:
                parsed = ast.literal_eval(value)
            except (SyntaxError, ValueError):
                return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _pairs_trading_trades_from_signals(signals: pd.DataFrame) -> pd.DataFrame:
    if signals.empty:
        return pd.DataFrame(columns=["datetime", "side", "price", "qty", "pnl"])
    return pd.DataFrame({
        "datetime": signals["datetime"],
        "side": signals["side"],
        "price": pd.to_numeric(signals.get("fair_value", pd.Series(float("nan"), index=signals.index)), errors="coerce"),
        "qty": pd.Series(float("nan"), index=signals.index),
        "pnl": pd.Series(float("nan"), index=signals.index),
    })


def _pairs_trading_reference_equity(bundle: ArtifactBundle, events: list[dict[str, Any]]) -> pd.DataFrame:
    if not events:
        return pd.DataFrame(columns=["ts", "datetime", "equity"])
    seen: set[int] = set()
    rows: list[dict[str, Any]] = []
    for event in events:
        ts_ms = int(event["ts"])
        if ts_ms in seen:
            continue
        seen.add(ts_ms)
        dt = _ensure_utc_timestamp(event["dt"])
        rows.append({
            "ts": ts_ms,
            "datetime": _iso(dt),
            "equity": float(bundle.initial_equity),
        })
    return pd.DataFrame(rows, columns=["ts", "datetime", "equity"])


@dataclass
class _FundingCarryReferenceParams:
    perp_symbol: str = "BTC-USDT-SWAP"
    spot_symbol: str = "BTC-USDT"
    min_apr_threshold: float = 0.12
    max_abs_basis_z: float = 2.5
    max_crowding: float = 0.85


def _funding_carry_reference_result(bundle: ArtifactBundle, engine: str) -> ReferenceResult:
    signals, trades, equity, price_input = _funding_carry_reference_components(bundle)
    metrics = neutral_metrics(equity, bundle.periods)
    return ReferenceResult(
        engine=engine,
        status="OK",
        reason=(
            "funding-rate signal comparison is strict; funding settlements, "
            "dual-leg execution, PnL, and metrics remain advisory in v1"
        ),
        reference_role="reference_signals_only",
        indicator_series=pd.DataFrame(columns=_indicator_columns()),
        signals=signals,
        trades=trades,
        equity_curve=equity,
        metrics=metrics,
        metadata={
            "strategy": bundle.primary_strategy,
            "reference_mode": "funding_carry_rate_signal_recompute",
            "price_input": price_input,
            "funding_input": price_input.get("funding_input"),
            "state_model": price_input.get("state_model"),
            "scope_limit": "funding entry/exit signal recompute only; cashflows, dual-leg fills, and PnL are advisory",
        },
    )


def _funding_carry_reference_components(
    bundle: ArtifactBundle,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    params = _funding_carry_reference_params(bundle)
    price_frame, price_input = _funding_carry_price_frame(bundle, params.perp_symbol)
    funding_frame, funding_input = _funding_rate_reference_frame(bundle, params.perp_symbol)
    signals, state_model = _funding_carry_reference_signals(bundle, funding_frame, params)
    price_input = dict(price_input)
    price_input["funding_input"] = funding_input
    price_input["state_model"] = state_model
    trades = _funding_carry_trades_from_signals(signals)
    equity = _funding_carry_reference_equity(bundle, price_frame, funding_frame)
    return signals, trades, equity, price_input


def _funding_carry_reference_params(bundle: ArtifactBundle) -> _FundingCarryReferenceParams:
    raw = _strategy_param_overlay(bundle, "funding_carry")
    symbols = bundle.symbols
    default_perp = next((symbol for symbol in symbols if symbol.endswith("-SWAP")), None)
    return _FundingCarryReferenceParams(
        perp_symbol=str(raw.get("perp_symbol") or default_perp or "BTC-USDT-SWAP"),
        spot_symbol=str(raw.get("spot_symbol") or "BTC-USDT"),
        min_apr_threshold=_safe_float(raw.get("min_apr_threshold"), 0.12),
        max_abs_basis_z=_safe_float(raw.get("max_abs_basis_z"), 2.5),
        max_crowding=_safe_float(raw.get("max_crowding"), 0.85),
    )


def _funding_carry_price_frame(
    bundle: ArtifactBundle,
    symbol: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    frame, metadata = _reference_price_frame_for_symbol(bundle, symbol)
    prepared = _external_feature_prepare_price_frame(frame)
    meta = dict(metadata)
    meta["rows"] = int(len(prepared))
    meta["reason"] = "Funding-carry reference uses per-symbol price rows for advisory equity timestamps."
    _set_reference_price_input_metadata(bundle, meta)
    if prepared.empty:
        raise ValueError(f"funding_carry reference validation found no usable price rows for {symbol}")
    return prepared, meta


def _funding_rate_reference_frame(
    bundle: ArtifactBundle,
    symbol: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    artifact = _funding_rate_artifact_frame(bundle)
    if not artifact.empty:
        prepared = _prepare_funding_rate_reference_frame(artifact, symbol)
        if not prepared.empty:
            return prepared, {
                "source": "funding_rates.csv" if (bundle.run_dir / "funding_rates.csv").exists() else "funding.csv",
                "symbol": symbol,
                "rows": int(len(prepared)),
                "reason": "Reference funding input loaded from funding-rate artifact.",
            }
    db_frame, db_meta = _funding_rate_reference_frame_from_db(bundle, symbol)
    if not db_frame.empty:
        return db_frame, db_meta
    raise ValueError(f"funding_carry reference validation needs funding rates for {symbol}")


def _funding_rate_reference_frame_from_db(
    bundle: ArtifactBundle,
    symbol: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if os.environ.get("DIFF_VALIDATION_ENABLE_DB_PARITY") != "1":
        return pd.DataFrame(), {
            "source": "unavailable",
            "symbol": symbol,
            "reason": "No funding_rates.csv and DB parity is not enabled.",
        }
    dsn = os.environ.get("DIFF_VALIDATION_DB_DSN") or os.environ.get("DATABASE_URL")
    if not dsn:
        return pd.DataFrame(), {
            "source": "unavailable",
            "symbol": symbol,
            "reason": "No funding_rates.csv and no DB DSN is configured.",
        }
    try:
        from backtesting.data_loader import _dsn_reachable, load_funding
    except Exception as exc:
        return pd.DataFrame(), {
            "source": "unavailable",
            "symbol": symbol,
            "reason": f"Funding DB loader unavailable: {type(exc).__name__}: {exc}",
        }
    if not _dsn_reachable(dsn):
        return pd.DataFrame(), {
            "source": "unavailable",
            "symbol": symbol,
            "reason": "No funding_rates.csv and DB is not reachable.",
        }
    start = _iso(_to_datetime(_series_time(bundle.price_series).min())) if not bundle.price_series.empty else None
    end = _iso(_to_datetime(_series_time(bundle.price_series).max())) if not bundle.price_series.empty else None
    try:
        db = load_funding(
            symbol,
            backend="postgres",
            dsn=dsn,
            start=start,
            end=end,
        )
    except Exception as exc:
        return pd.DataFrame(), {
            "source": "unavailable",
            "symbol": symbol,
            "reason": f"DB funding query failed: {type(exc).__name__}: {exc}",
        }
    prepared = _prepare_funding_rate_reference_frame(db, symbol)
    return prepared, {
        "source": "db_funding_rates",
        "symbol": symbol,
        "rows": int(len(prepared)),
        "reason": "Reference funding input loaded from DB funding_rates.",
    }


def _prepare_funding_rate_reference_frame(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    columns = [
        "_dt", "_ts", "inst_id", "funding_rate", "funding_interval_hours",
        "next_funding_time", "mark_price", "basis_z", "crowding",
    ]
    if df.empty:
        return pd.DataFrame(columns=columns)
    data = df.copy()
    if "datetime" not in data.columns and "ts" not in data.columns and not isinstance(data.index, pd.RangeIndex):
        data = data.reset_index().rename(columns={data.index.name or "index": "datetime"})
    if "funding_rate" not in data.columns and "rate" in data.columns:
        data["funding_rate"] = data["rate"]
    if "next_funding_time" not in data.columns and "nextFundingTime" in data.columns:
        data["next_funding_time"] = data["nextFundingTime"]
    if "inst_id" not in data.columns:
        data["inst_id"] = symbol
    if symbol:
        data = data[data["inst_id"].astype(str) == str(symbol)].copy()
    if data.empty:
        return pd.DataFrame(columns=columns)
    data["_dt"] = [_to_datetime(value) for value in _series_time(data)]
    data = data.dropna(subset=["_dt"]).copy()
    if data.empty:
        return pd.DataFrame(columns=columns)
    data["_ts"] = [_ts_ms(_ensure_utc_timestamp(ts)) for ts in data["_dt"]]
    data["funding_rate"] = pd.to_numeric(data.get("funding_rate", pd.Series(np.nan, index=data.index)), errors="coerce")
    data = data.dropna(subset=["funding_rate"]).copy()
    if data.empty:
        return pd.DataFrame(columns=columns)
    if "funding_interval_hours" not in data.columns:
        data["funding_interval_hours"] = 8.0
    data["funding_interval_hours"] = pd.to_numeric(data["funding_interval_hours"], errors="coerce").fillna(8.0)
    data.loc[data["funding_interval_hours"] <= 0, "funding_interval_hours"] = 8.0
    for col in ["next_funding_time", "mark_price", "basis_z", "crowding"]:
        if col not in data.columns:
            data[col] = np.nan
    return data.sort_values(["_ts"]).reset_index(drop=True)[columns]


def _funding_carry_reference_signals(
    bundle: ArtifactBundle,
    funding_frame: pd.DataFrame,
    params: _FundingCarryReferenceParams,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    in_position = False
    fill_events = _funding_carry_fill_transitions(bundle, params.perp_symbol)
    fill_idx = 0
    rows: list[dict[str, Any]] = []

    def apply_fills(up_to_ts: int) -> None:
        nonlocal fill_idx, in_position
        while fill_idx < len(fill_events) and fill_events[fill_idx]["ts"] <= up_to_ts:
            fill = fill_events[fill_idx]
            action = fill.get("action")
            side = fill.get("side")
            if action == "entry" or side == "sell":
                in_position = True
            elif action == "exit" or side == "buy":
                in_position = False
            fill_idx += 1

    for _, row in funding_frame.iterrows():
        current_ts = int(row["_ts"])
        if fill_events:
            apply_fills(current_ts)
        rate = _safe_float(row.get("funding_rate"), float("nan"))
        interval_hours = _safe_float(row.get("funding_interval_hours"), 8.0)
        if not math.isfinite(rate):
            continue
        if not math.isfinite(interval_hours) or interval_hours <= 0:
            interval_hours = 8.0
        apr = rate * (365 * 24 / interval_hours)
        basis_z = _optional_reference_float(row.get("basis_z"))
        crowding = _optional_reference_float(row.get("crowding"))
        current_dt = _ensure_utc_timestamp(row["_dt"])
        if not in_position:
            allowed, reason = _funding_carry_entry_gate(
                apr=apr,
                min_apr=params.min_apr_threshold,
                basis_z=basis_z,
                max_abs_basis_z=params.max_abs_basis_z,
                crowding=crowding,
                max_crowding=params.max_crowding,
            )
            if not allowed:
                continue
            rows.append(_funding_carry_signal_row(
                ts_ms=current_ts,
                dt=current_dt,
                params=params,
                side="sell",
                action="entry",
                apr=apr,
                funding_rate=rate,
                interval_hours=interval_hours,
                basis_z=basis_z,
                crowding=crowding,
                reason=reason,
            ))
            if not fill_events:
                in_position = True
        elif apr < 0:
            rows.append(_funding_carry_signal_row(
                ts_ms=current_ts,
                dt=current_dt,
                params=params,
                side="buy",
                action="exit",
                apr=apr,
                funding_rate=rate,
                interval_hours=interval_hours,
                basis_z=basis_z,
                crowding=crowding,
                reason="apr_negative",
            ))
            if not fill_events:
                in_position = False

    state_model = {
        "source": "fills_metadata" if fill_events else "signal_immediate_assumption",
        "fill_events_used": len(fill_events),
        "limitation": (
            "Uses fills.csv side/action metadata to mirror funding_carry _in_position state."
            if fill_events
            else "No fill metadata was available; reference assumes funding signals change state immediately."
        ),
    }
    signals = pd.DataFrame(rows, columns=[
        "ts", "datetime", "strategy", "inst_id", "side", "strength", "fair_value", "metadata",
    ])
    return signals, state_model


def _funding_carry_entry_gate(
    *,
    apr: float,
    min_apr: float,
    basis_z: float | None,
    max_abs_basis_z: float,
    crowding: float | None,
    max_crowding: float,
) -> tuple[bool, str]:
    if apr <= min_apr:
        return False, "apr_below_threshold"
    if basis_z is not None and abs(basis_z) > max_abs_basis_z:
        return False, "basis_too_extreme"
    if crowding is not None and crowding > max_crowding:
        return False, "crowding_too_high"
    return True, "allowed"


def _funding_carry_signal_row(
    *,
    ts_ms: int,
    dt: pd.Timestamp,
    params: _FundingCarryReferenceParams,
    side: str,
    action: str,
    apr: float,
    funding_rate: float,
    interval_hours: float,
    basis_z: float | None,
    crowding: float | None,
    reason: str,
) -> dict[str, Any]:
    strength = min(apr / params.min_apr_threshold, 1.0) if action == "entry" and params.min_apr_threshold > 0 else 1.0
    metadata = {
        "action": action,
        "apr_pct": apr * 100.0,
        "funding_rate": funding_rate,
        "funding_interval_hours": interval_hours,
        "basis_z": basis_z,
        "crowding": crowding,
        "spot_symbol": params.spot_symbol,
        "leg": "dual",
        "reason": reason,
    }
    return {
        "ts": int(ts_ms),
        "datetime": _iso(dt),
        "strategy": "funding_carry",
        "inst_id": params.perp_symbol,
        "side": side,
        "strength": float(strength),
        "fair_value": 0.0,
        "metadata": metadata,
    }


def _funding_carry_fill_transitions(bundle: ArtifactBundle, symbol: str) -> list[dict[str, Any]]:
    if bundle.fills.empty:
        return []
    fills = bundle.fills.copy()
    if "strategy" in fills.columns:
        fills = fills[fills["strategy"].astype(str) == "funding_carry"]
    if "inst_id" in fills.columns:
        fills = fills[fills["inst_id"].astype(str) == symbol]
    if fills.empty:
        return []
    rows: list[dict[str, Any]] = []
    for _, row in fills.iterrows():
        state = str(row.get("state") or "filled").lower()
        if state not in {"filled", "partially_filled", "fill"}:
            continue
        fill_sz = _safe_float(row.get("fill_sz"), 0.0)
        if fill_sz <= 0:
            continue
        dt = _to_datetime(row.get("datetime", row.get("ts")))
        if pd.isna(dt):
            continue
        metadata = _metadata_dict(row.get("metadata"))
        action = str(metadata.get("action") or "").lower()
        rows.append({
            "ts": _ts_ms(dt),
            "side": str(row.get("side") or "").lower(),
            "action": action,
        })
    rows.sort(key=lambda row: row["ts"])
    return rows


def _funding_carry_trades_from_signals(signals: pd.DataFrame) -> pd.DataFrame:
    if signals.empty:
        return pd.DataFrame(columns=["datetime", "side", "price", "qty", "pnl"])
    return pd.DataFrame({
        "datetime": signals["datetime"],
        "side": signals["side"],
        "price": pd.to_numeric(signals.get("fair_value", pd.Series(float("nan"), index=signals.index)), errors="coerce"),
        "qty": pd.Series(float("nan"), index=signals.index),
        "pnl": pd.Series(float("nan"), index=signals.index),
    })


def _funding_carry_reference_equity(
    bundle: ArtifactBundle,
    price_frame: pd.DataFrame,
    funding_frame: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    seen: set[int] = set()
    for frame in (price_frame, funding_frame):
        if frame.empty:
            continue
        ts_col = "_ts" if "_ts" in frame.columns else "ts"
        dt_col = "_dt" if "_dt" in frame.columns else "datetime"
        for _, row in frame.iterrows():
            ts_ms = int(row[ts_col])
            if ts_ms in seen:
                continue
            seen.add(ts_ms)
            rows.append({
                "ts": ts_ms,
                "datetime": _iso(_ensure_utc_timestamp(_to_datetime(row[dt_col]))),
                "equity": float(bundle.initial_equity),
            })
    rows.sort(key=lambda row: row["ts"])
    return pd.DataFrame(rows, columns=["ts", "datetime", "equity"])


_FNG_REFERENCE_LABELS = {
    "extreme fear": "Extreme Fear",
    "fear": "Fear",
    "neutral": "Neutral",
    "greed": "Greed",
    "extreme greed": "Extreme Greed",
}


@dataclass
class _FearGreedReferenceParams:
    symbol: str = "BTC-USDT-SWAP"
    dataset_id: str = "fear_greed_btc"
    max_age_seconds: int = 172800
    extreme_fear_label: str = "Extreme Fear"
    exit_labels: set[str] = field(default_factory=lambda: {"Greed", "Extreme Greed"})
    extreme_fear_threshold: float = 25.0
    exit_value_threshold: float = 51.0


@dataclass
class _CMEGapReferenceParams:
    symbol: str = "BTC-USDT-SWAP"
    dataset_id: str = "cme_btc1_continuous"
    max_age_seconds: int = 604800
    min_gap_bps: float = 25.0
    max_hold_days: float = 2.0
    stop_loss_bps_mult: float = 1.5
    max_gap_bps: float = 0.0
    allow_direction: str = "long_only"
    roll_dates: set[str] = field(default_factory=set)


@dataclass
class _CMEReferenceGap:
    direction: str
    cme_target_price: float
    cme_gap_open_price: float
    gap_bps: float
    detected_ts: int
    expires_at: int
    entered: bool = False
    entry_side: str = ""
    okx_entry_anchor_price: float | None = None
    okx_target_price: float | None = None
    exit_requested: bool = False


def _external_feature_reference_result(bundle: ArtifactBundle, engine: str) -> ReferenceResult:
    signals, trades, equity, price_input = _external_feature_reference_components(bundle)
    metrics = neutral_metrics(equity, bundle.periods)
    strategy = bundle.primary_strategy
    return ReferenceResult(
        engine=engine,
        status="OK",
        reason=(
            "external-feature signal comparison is strict; feature-source parity, "
            "fills, PnL, and metrics remain advisory in v1"
        ),
        reference_role="reference_signals_only",
        indicator_series=pd.DataFrame(columns=_indicator_columns()),
        signals=signals,
        trades=trades,
        equity_curve=equity,
        metrics=metrics,
        metadata={
            "strategy": strategy,
            "reference_mode": f"{strategy}_external_feature_signal_recompute",
            "price_input": price_input,
            "feature_input": price_input.get("feature_input"),
            "state_model": price_input.get("state_model"),
            "scope_limit": "external feature signal recompute only; fills and PnL are advisory",
        },
    )


def _external_feature_reference_components(
    bundle: ArtifactBundle,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    strategy = bundle.primary_strategy
    if strategy == "fear_greed_sentiment":
        params = _fear_greed_reference_params(bundle)
        price_frame, price_input = _external_feature_price_frame(bundle, params.symbol)
        observations, feature_input = _external_reference_observations(bundle, params.dataset_id)
        events = _external_feature_events(price_frame, observations, symbol=params.symbol)
        signals, state_model = _fear_greed_reference_signals(bundle, events, params)
    elif strategy == "cme_gap_fill":
        params = _cme_gap_reference_params(bundle)
        price_frame, price_input = _external_feature_price_frame(bundle, params.symbol)
        observations, feature_input = _external_reference_observations(bundle, params.dataset_id)
        events = _external_feature_events(price_frame, observations, symbol=params.symbol)
        signals, state_model = _cme_gap_reference_signals(bundle, events, params)
    else:
        raise ValueError(f"unsupported external feature reference strategy: {strategy}")
    price_input = dict(price_input)
    price_input["feature_input"] = feature_input
    price_input["state_model"] = state_model
    trades = _external_feature_trades_from_signals(signals)
    equity = _external_feature_reference_equity(bundle, price_frame)
    return signals, trades, equity, price_input


def _fear_greed_reference_params(bundle: ArtifactBundle) -> _FearGreedReferenceParams:
    raw = _strategy_param_overlay(bundle, "fear_greed_sentiment")
    symbol = str(raw.get("symbol") or (bundle.symbols[0] if bundle.symbols else "BTC-USDT-SWAP"))
    exit_labels = raw.get("exit_labels") or ["Greed", "Extreme Greed"]
    return _FearGreedReferenceParams(
        symbol=symbol,
        dataset_id=str(raw.get("dataset_id") or "fear_greed_btc"),
        max_age_seconds=max(int(_safe_float(raw.get("max_age_seconds"), 172800.0)), 1),
        extreme_fear_label=_canonical_fng_reference_label(raw.get("extreme_fear_label") or "Extreme Fear"),
        exit_labels={_canonical_fng_reference_label(label) for label in exit_labels},
        extreme_fear_threshold=_safe_float(raw.get("extreme_fear_threshold"), 25.0),
        exit_value_threshold=_safe_float(raw.get("exit_value_threshold"), 51.0),
    )


def _cme_gap_reference_params(bundle: ArtifactBundle) -> _CMEGapReferenceParams:
    raw = _strategy_param_overlay(bundle, "cme_gap_fill")
    symbol = str(raw.get("symbol") or (bundle.symbols[0] if bundle.symbols else "BTC-USDT-SWAP"))
    roll_dates = set()
    for value in raw.get("roll_dates") or []:
        try:
            roll_dates.add(pd.Timestamp(value).date().isoformat())
        except Exception:
            continue
    return _CMEGapReferenceParams(
        symbol=symbol,
        dataset_id=str(raw.get("dataset_id") or "cme_btc1_continuous"),
        max_age_seconds=max(int(_safe_float(raw.get("max_age_seconds"), 604800.0)), 1),
        min_gap_bps=_safe_float(raw.get("min_gap_bps"), 25.0),
        max_hold_days=_safe_float(raw.get("max_hold_days"), 2.0),
        stop_loss_bps_mult=_safe_float(raw.get("stop_loss_bps_mult"), 1.5),
        max_gap_bps=_safe_float(raw.get("max_gap_bps"), 0.0),
        allow_direction=str(raw.get("allow_direction") or "long_only"),
        roll_dates=roll_dates,
    )


def _strategy_param_overlay(bundle: ArtifactBundle, strategy: str) -> dict[str, Any]:
    raw: dict[str, Any] = {}
    raw.update(bundle.strategy_params(strategy))
    result_params = bundle.result.get("parameters") if isinstance(bundle.result.get("parameters"), dict) else {}
    strategies = result_params.get("strategies") if isinstance(result_params.get("strategies"), dict) else {}
    result_strategy = strategies.get(strategy) if isinstance(strategies, dict) else {}
    if isinstance(result_strategy, dict):
        raw.update(result_strategy)
    return raw


def _external_feature_price_frame(
    bundle: ArtifactBundle,
    symbol: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    frame, metadata = _reference_price_frame_for_symbol(bundle, symbol)
    prepared = _external_feature_prepare_price_frame(frame)
    meta = dict(metadata)
    meta["rows"] = int(len(prepared))
    meta["reason"] = "External-feature reference uses per-symbol price rows for independent signal recompute."
    _set_reference_price_input_metadata(bundle, meta)
    if prepared.empty:
        raise ValueError(f"external-feature reference validation found no usable price rows for {symbol}")
    return prepared, meta


def _external_feature_prepare_price_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["_dt", "_ts", "_order", "inst_id", "_price"])
    data = frame.copy()
    data["_dt"] = [_to_datetime(value) for value in _series_time(data)]
    data = data.dropna(subset=["_dt"])
    if data.empty:
        return pd.DataFrame(columns=["_dt", "_ts", "_order", "inst_id", "_price"])
    orders: list[int] = []
    for pos, idx in enumerate(data.index):
        try:
            orders.append(int(idx))
        except (TypeError, ValueError):
            orders.append(pos)
    data["_order"] = orders
    price_source = "close" if "close" in data.columns else ("fair_value" if "fair_value" in data.columns else "")
    if not price_source:
        return pd.DataFrame(columns=["_dt", "_ts", "_order", "inst_id", "_price"])
    data["_price"] = pd.to_numeric(data[price_source], errors="coerce")
    data = data.dropna(subset=["_price"])
    data = data[data["_price"] > 0].copy()
    data["_ts"] = [_ts_ms(_ensure_utc_timestamp(ts)) for ts in data["_dt"]]
    return data.sort_values(["_ts", "_order"])[["_dt", "_ts", "_order", "inst_id", "_price"]]


def _external_reference_observations(
    bundle: ArtifactBundle,
    dataset_id: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    artifact = _external_observations_artifact_frame(bundle)
    if not artifact.empty:
        prepared = _prepare_external_observation_frame(artifact, dataset_id)
        if not prepared.empty:
            return prepared, {
                "source": "external_observations.csv",
                "dataset_id": dataset_id,
                "rows": int(len(prepared)),
                "reason": "Reference feature input loaded from external_observations.csv.",
            }
    db_frame, db_meta = _external_reference_observations_from_db(bundle, dataset_id)
    if not db_frame.empty:
        return db_frame, db_meta
    raise ValueError(f"external-feature reference validation needs observations for dataset {dataset_id}")


def _external_reference_observations_from_db(
    bundle: ArtifactBundle,
    dataset_id: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if os.environ.get("DIFF_VALIDATION_ENABLE_DB_PARITY") != "1":
        return pd.DataFrame(), {
            "source": "unavailable",
            "dataset_id": dataset_id,
            "reason": "No external_observations.csv and DB parity is not enabled.",
        }
    dsn = os.environ.get("DIFF_VALIDATION_DB_DSN") or os.environ.get("DATABASE_URL")
    if not dsn:
        return pd.DataFrame(), {
            "source": "unavailable",
            "dataset_id": dataset_id,
            "reason": "No external_observations.csv and no DB DSN is configured.",
        }
    try:
        from backtesting.data_loader import _dsn_reachable, load_external_observations
    except Exception as exc:
        return pd.DataFrame(), {
            "source": "unavailable",
            "dataset_id": dataset_id,
            "reason": f"External observation DB loader unavailable: {type(exc).__name__}: {exc}",
        }
    if not _dsn_reachable(dsn):
        return pd.DataFrame(), {
            "source": "unavailable",
            "dataset_id": dataset_id,
            "reason": "No external_observations.csv and DB is not reachable.",
        }
    start = _iso(_to_datetime(_series_time(bundle.price_series).min())) if not bundle.price_series.empty else None
    end = _iso(_to_datetime(_series_time(bundle.price_series).max())) if not bundle.price_series.empty else None
    try:
        db = load_external_observations(
            dataset_id,
            backend="postgres",
            dsn=dsn,
            start=start,
            end=end,
            lookback_seconds=0,
        )
    except Exception as exc:
        return pd.DataFrame(), {
            "source": "unavailable",
            "dataset_id": dataset_id,
            "reason": f"DB external_observations query failed: {type(exc).__name__}: {exc}",
        }
    prepared = _prepare_external_observation_frame(db, dataset_id)
    return prepared, {
        "source": "db_external_observations",
        "dataset_id": dataset_id,
        "rows": int(len(prepared)),
        "reason": "Reference feature input loaded from DB external_observations.",
    }


def _prepare_external_observation_frame(df: pd.DataFrame, dataset_id: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=[
            "_event_dt", "_event_ts", "_observed_ts", "_published_ts",
            "dataset_id", "value_num", "value_text", "fields", "quality_status",
        ])
    data = df.copy()
    if "dataset_id" not in data.columns:
        data["dataset_id"] = dataset_id
    data = data[data["dataset_id"].astype(str) == str(dataset_id)].copy()
    if data.empty:
        return pd.DataFrame(columns=[
            "_event_dt", "_event_ts", "_observed_ts", "_published_ts",
            "dataset_id", "value_num", "value_text", "fields", "quality_status",
        ])
    if "observed_at" not in data.columns:
        if "datetime" in data.columns:
            data["observed_at"] = data["datetime"]
        elif "ts" in data.columns:
            data["observed_at"] = data["ts"]
    if "published_at" not in data.columns:
        data["published_at"] = pd.NaT
    data["_observed_dt"] = [_to_datetime(value) for value in data["observed_at"]]
    data["_published_dt"] = [_to_datetime(value) for value in data["published_at"]]
    data["_event_dt"] = [
        published if not pd.isna(published) else observed
        for published, observed in zip(data["_published_dt"], data["_observed_dt"])
    ]
    data = data.dropna(subset=["_event_dt", "_observed_dt"]).copy()
    if data.empty:
        return pd.DataFrame(columns=[
            "_event_dt", "_event_ts", "_observed_ts", "_published_ts",
            "dataset_id", "value_num", "value_text", "fields", "quality_status",
        ])
    data["_event_ts"] = [_ts_ms(_ensure_utc_timestamp(ts)) for ts in data["_event_dt"]]
    data["_observed_ts"] = [_ts_ms(_ensure_utc_timestamp(ts)) for ts in data["_observed_dt"]]
    data["_published_ts"] = [
        _ts_ms(_ensure_utc_timestamp(ts)) if not pd.isna(ts) else None
        for ts in data["_published_dt"]
    ]
    if "fields" not in data.columns:
        data["fields"] = [{} for _ in range(len(data))]
    data["fields"] = data["fields"].apply(_metadata_dict)
    if "value_num" not in data.columns:
        data["value_num"] = None
    if "value_text" not in data.columns:
        data["value_text"] = None
    if "quality_status" not in data.columns:
        data["quality_status"] = "raw"
    return data.sort_values(["_event_ts", "_observed_ts"]).reset_index(drop=True)[[
        "_event_dt", "_event_ts", "_observed_ts", "_published_ts",
        "dataset_id", "value_num", "value_text", "fields", "quality_status",
    ]]


def _external_feature_events(
    price_frame: pd.DataFrame,
    observations: pd.DataFrame,
    *,
    symbol: str,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for _, row in observations.iterrows():
        events.append({
            "kind": "feature",
            "ts": int(row["_event_ts"]),
            "priority": 0,
            "dt": _ensure_utc_timestamp(row["_event_dt"]),
            "observed_ts": int(row["_observed_ts"]),
            "published_ts": int(row["_published_ts"]) if row.get("_published_ts") is not None and not pd.isna(row.get("_published_ts")) else None,
            "dataset_id": str(row.get("dataset_id") or ""),
            "value_num": _optional_reference_float(row.get("value_num")),
            "value_text": None if pd.isna(row.get("value_text")) else str(row.get("value_text") or ""),
            "fields": _metadata_dict(row.get("fields")),
        })
    for _, row in price_frame.iterrows():
        events.append({
            "kind": "market",
            "ts": int(row["_ts"]),
            "priority": 1,
            "dt": _ensure_utc_timestamp(row["_dt"]),
            "symbol": symbol,
            "price": _safe_float(row["_price"], float("nan")),
        })
    events.sort(key=lambda row: (row["ts"], row["priority"]))
    return events


def _fear_greed_reference_signals(
    bundle: ArtifactBundle,
    events: list[dict[str, Any]],
    params: _FearGreedReferenceParams,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    latest_feature: dict[str, Any] | None = None
    in_position = False
    fill_events = _external_feature_fill_transitions(bundle, strategy="fear_greed_sentiment", symbol=params.symbol)
    fill_idx = 0
    rows: list[dict[str, Any]] = []

    def apply_fills(up_to_ts: int) -> None:
        nonlocal fill_idx, in_position
        while fill_idx < len(fill_events) and fill_events[fill_idx]["ts"] <= up_to_ts:
            fill = fill_events[fill_idx]
            if fill.get("side") == "buy":
                in_position = True
            elif fill.get("side") == "sell":
                in_position = False
            fill_idx += 1

    for event in events:
        current_ts = int(event["ts"])
        if fill_events:
            apply_fills(current_ts)
        if event["kind"] == "feature":
            latest_feature = event
            latest_feature["value_text"] = _canonical_fng_reference_label(event.get("value_text") or "")
            continue
        price = _safe_float(event.get("price"), float("nan"))
        if latest_feature is None or not math.isfinite(price) or price <= 0:
            continue
        if _feature_age_seconds_from_event(latest_feature, current_ts) > params.max_age_seconds:
            continue
        label = _canonical_fng_reference_label(latest_feature.get("value_text") or "")
        value_num = _optional_reference_float(latest_feature.get("value_num"))
        is_extreme_fear = label == params.extreme_fear_label or (
            value_num is not None and value_num <= params.extreme_fear_threshold
        )
        is_exit = label in params.exit_labels or (
            value_num is not None and value_num >= params.exit_value_threshold
        )
        if is_extreme_fear and not in_position:
            rows.append(_external_signal_row(
                strategy="fear_greed_sentiment",
                ts_ms=current_ts,
                dt=event["dt"],
                inst_id=params.symbol,
                side="buy",
                fair_value=price,
                metadata={
                    "action": "entry",
                    "dataset_id": params.dataset_id,
                    "feature_value_num": value_num,
                    "feature_value_text": label,
                },
            ))
            if not fill_events:
                in_position = True
        elif is_exit and in_position:
            rows.append(_external_signal_row(
                strategy="fear_greed_sentiment",
                ts_ms=current_ts,
                dt=event["dt"],
                inst_id=params.symbol,
                side="sell",
                fair_value=price,
                metadata={
                    "action": "exit",
                    "dataset_id": params.dataset_id,
                    "feature_value_num": value_num,
                    "feature_value_text": label,
                },
            ))
            if not fill_events:
                in_position = False

    state_model = _external_feature_state_model(fill_events)
    signals = pd.DataFrame(rows, columns=["ts", "datetime", "strategy", "inst_id", "side", "fair_value", "metadata"])
    return signals, state_model


def _cme_gap_reference_signals(
    bundle: ArtifactBundle,
    events: list[dict[str, Any]],
    params: _CMEGapReferenceParams,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    previous_feature: dict[str, Any] | None = None
    active_gap: _CMEReferenceGap | None = None
    in_position = False
    fill_events = _external_feature_fill_transitions(bundle, strategy="cme_gap_fill", symbol=params.symbol)
    fill_idx = 0
    rows: list[dict[str, Any]] = []

    def apply_fills(up_to_ts: int) -> None:
        nonlocal fill_idx, in_position, active_gap
        while fill_idx < len(fill_events) and fill_events[fill_idx]["ts"] <= up_to_ts:
            fill = fill_events[fill_idx]
            action = fill.get("action")
            if action == "entry":
                in_position = True
            elif action == "exit":
                in_position = False
                active_gap = None
            fill_idx += 1

    for event in events:
        current_ts = int(event["ts"])
        if fill_events:
            apply_fills(current_ts)
        if event["kind"] == "feature":
            active_gap = _cme_handle_feature_reference(event, previous_feature, active_gap, params)
            previous_feature = event
            continue
        price = _safe_float(event.get("price"), float("nan"))
        if not math.isfinite(price) or price <= 0:
            continue
        if previous_feature is None and active_gap is None:
            continue
        if (
            previous_feature is not None
            and not in_position
            and _feature_age_seconds_from_event(previous_feature, current_ts) > params.max_age_seconds
        ):
            continue
        gap = active_gap
        if gap is None:
            continue
        if in_position:
            if gap.exit_requested:
                continue
            reason = ""
            if gap.okx_target_price is not None and _cme_target_touched(gap.direction, price, gap.okx_target_price):
                reason = "target_fill"
            elif _cme_stop_loss_touched(gap, price, params.stop_loss_bps_mult):
                reason = "stop_loss"
            elif current_ts >= gap.expires_at:
                reason = "timeout"
            if reason:
                rows.append(_cme_gap_signal_row(params, gap, current_ts, event["dt"], price, "exit", reason))
                gap.exit_requested = True
                if not fill_events:
                    in_position = False
                    active_gap = None
            continue
        if not gap.entered:
            gap.entered = True
            gap.okx_entry_anchor_price = price
            gap.okx_target_price = _cme_okx_target_from_anchor(gap.direction, price, gap.gap_bps)
            rows.append(_cme_gap_signal_row(params, gap, current_ts, event["dt"], price, "entry", "gap_open"))
            if not fill_events:
                in_position = True

    state_model = _external_feature_state_model(fill_events)
    signals = pd.DataFrame(rows, columns=["ts", "datetime", "strategy", "inst_id", "side", "fair_value", "metadata"])
    return signals, state_model


def _cme_handle_feature_reference(
    current: dict[str, Any],
    previous: dict[str, Any] | None,
    active_gap: _CMEReferenceGap | None,
    params: _CMEGapReferenceParams,
) -> _CMEReferenceGap | None:
    if previous is None:
        return active_gap
    current_open = _field_float_reference(current.get("fields") or {}, "open")
    current_observed = _timestamp_from_ms(current.get("observed_ts"))
    prev_close = _field_float_reference(previous.get("fields") or {}, "close")
    prev_observed = _timestamp_from_ms(previous.get("observed_ts"))
    if current_open is None or prev_close is None or prev_close <= 0 or current_observed is None or prev_observed is None:
        return active_gap
    if _cme_is_roll_day(previous, params.roll_dates) or _cme_is_roll_day(current, params.roll_dates):
        return active_gap
    if not _cme_is_weekend_reopen(prev_observed, current_observed):
        return active_gap
    gap_bps = abs(current_open - prev_close) / prev_close * 10_000.0
    if gap_bps < params.min_gap_bps:
        return active_gap
    direction = "short" if current_open > prev_close else "long"
    if params.max_gap_bps > 0 and gap_bps > params.max_gap_bps:
        return active_gap
    if not _cme_trade_direction_allowed(direction, params.allow_direction):
        return active_gap
    return _CMEReferenceGap(
        direction=direction,
        cme_target_price=float(prev_close),
        cme_gap_open_price=float(current_open),
        gap_bps=float(gap_bps),
        detected_ts=int(current["ts"]),
        expires_at=int(current["ts"] + params.max_hold_days * 86400 * 1000),
    )


def _external_signal_row(
    *,
    strategy: str,
    ts_ms: int,
    dt: pd.Timestamp,
    inst_id: str,
    side: str,
    fair_value: float,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    return {
        "ts": int(ts_ms),
        "datetime": _iso(dt),
        "strategy": strategy,
        "inst_id": inst_id,
        "side": side,
        "fair_value": fair_value,
        "metadata": metadata,
    }


def _cme_gap_signal_row(
    params: _CMEGapReferenceParams,
    gap: _CMEReferenceGap,
    ts_ms: int,
    dt: pd.Timestamp,
    price: float,
    action: str,
    reason: str,
) -> dict[str, Any]:
    if action == "entry":
        side = "sell" if gap.direction == "short" else "buy"
        gap.entry_side = side
    else:
        side = "buy" if gap.direction == "short" else "sell"
    return _external_signal_row(
        strategy="cme_gap_fill",
        ts_ms=ts_ms,
        dt=dt,
        inst_id=params.symbol,
        side=side,
        fair_value=price,
        metadata={
            "action": action,
            "reason": reason,
            "dataset_id": params.dataset_id,
            "gap_direction": gap.direction,
            "gap_target_price": gap.okx_target_price,
            "okx_target_price": gap.okx_target_price,
            "okx_entry_anchor_price": gap.okx_entry_anchor_price,
            "cme_target_price": gap.cme_target_price,
            "cme_gap_open_price": gap.cme_gap_open_price,
            "gap_bps": gap.gap_bps,
            "detected_ts": gap.detected_ts,
            "expires_at": gap.expires_at,
        },
    )


def _external_feature_fill_transitions(
    bundle: ArtifactBundle,
    *,
    strategy: str,
    symbol: str,
) -> list[dict[str, Any]]:
    if bundle.fills.empty:
        return []
    fills = bundle.fills.copy()
    if "strategy" in fills.columns:
        fills = fills[fills["strategy"].astype(str) == strategy]
    if "inst_id" in fills.columns:
        fills = fills[fills["inst_id"].astype(str) == symbol]
    if fills.empty:
        return []
    rows: list[dict[str, Any]] = []
    for _, row in fills.iterrows():
        state = str(row.get("state") or "filled").lower()
        if state not in {"filled", "partially_filled", "fill"}:
            continue
        fill_sz = _safe_float(row.get("fill_sz"), 0.0)
        if fill_sz <= 0:
            continue
        dt = _to_datetime(row.get("datetime", row.get("ts")))
        if pd.isna(dt):
            continue
        metadata = _metadata_dict(row.get("metadata"))
        rows.append({
            "ts": _ts_ms(dt),
            "side": str(row.get("side") or "").lower(),
            "action": str(metadata.get("action") or "").lower(),
        })
    rows.sort(key=lambda row: row["ts"])
    return rows


def _external_feature_state_model(fill_events: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "source": "fills_metadata" if fill_events else "signal_immediate_assumption",
        "fill_events_used": len(fill_events),
        "limitation": (
            "Uses fills.csv metadata to mirror strategy position state."
            if fill_events
            else "No fill metadata was available; reference assumes signal state changes immediately."
        ),
    }


def _external_feature_trades_from_signals(signals: pd.DataFrame) -> pd.DataFrame:
    if signals.empty:
        return pd.DataFrame(columns=["datetime", "side", "price", "qty", "pnl"])
    return pd.DataFrame({
        "datetime": signals["datetime"],
        "side": signals["side"],
        "price": pd.to_numeric(signals.get("fair_value", pd.Series(float("nan"), index=signals.index)), errors="coerce"),
        "qty": pd.Series(float("nan"), index=signals.index),
        "pnl": pd.Series(float("nan"), index=signals.index),
    })


def _external_feature_reference_equity(bundle: ArtifactBundle, price_frame: pd.DataFrame) -> pd.DataFrame:
    if price_frame.empty:
        return pd.DataFrame(columns=["ts", "datetime", "equity"])
    return pd.DataFrame({
        "ts": price_frame["_ts"].astype(int).to_list(),
        "datetime": [_iso(_ensure_utc_timestamp(ts)) for ts in price_frame["_dt"]],
        "equity": [float(bundle.initial_equity)] * len(price_frame),
    })


def _canonical_fng_reference_label(value: object) -> str:
    text = str(value or "").strip()
    return _FNG_REFERENCE_LABELS.get(text.casefold(), text)


def _optional_reference_float(value: object) -> float | None:
    if value in (None, "", "."):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def _feature_age_seconds_from_event(feature: dict[str, Any], ts_ms: int) -> float:
    feature_ts = feature.get("published_ts") or feature.get("observed_ts") or feature.get("ts") or 0
    return max(0.0, (int(ts_ms) - int(feature_ts)) / 1000.0)


def _field_float_reference(fields: dict[str, Any], key: str) -> float | None:
    value = fields.get(key)
    if value in (None, "", "."):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def _timestamp_from_ms(value: Any) -> pd.Timestamp | None:
    numeric = _safe_float(value, float("nan"))
    if not math.isfinite(numeric):
        return None
    return pd.Timestamp(int(numeric), unit="ms", tz="UTC")


def _cme_target_touched(direction: str, price: float, target: float) -> bool:
    if direction == "short":
        return price <= target
    return price >= target


def _cme_stop_loss_touched(gap: _CMEReferenceGap, price: float, stop_loss_bps_mult: float) -> bool:
    stop_price = _cme_stop_loss_price(gap, stop_loss_bps_mult)
    if stop_price is None:
        return False
    if gap.direction == "short":
        return price >= stop_price
    return price <= stop_price


def _cme_stop_loss_price(gap: _CMEReferenceGap, stop_loss_bps_mult: float) -> float | None:
    if stop_loss_bps_mult <= 0 or gap.okx_entry_anchor_price is None:
        return None
    stop_pct = stop_loss_bps_mult * float(gap.gap_bps) / 10_000.0
    if gap.direction == "short":
        return gap.okx_entry_anchor_price * (1.0 + stop_pct)
    return gap.okx_entry_anchor_price * (1.0 - stop_pct)


def _cme_okx_target_from_anchor(direction: str, anchor_price: float, gap_bps: float) -> float:
    gap_pct = float(gap_bps) / 10_000.0
    if direction == "short":
        return anchor_price * (1.0 - gap_pct)
    return anchor_price * (1.0 + gap_pct)


def _cme_is_weekend_reopen(prev_observed: pd.Timestamp, current_observed: pd.Timestamp) -> bool:
    gap_days = (current_observed.date() - prev_observed.date()).days
    if prev_observed.weekday() != 4 or gap_days < 2:
        return False
    return current_observed.weekday() in {6, 0, 1, 2}


def _cme_is_roll_day(event: dict[str, Any], configured_roll_dates: set[str]) -> bool:
    observed = _timestamp_from_ms(event.get("observed_ts"))
    observed_date = observed.date().isoformat() if observed is not None else None
    raw = event.get("fields") or {}
    field_flag = raw.get("is_roll_day", raw.get("roll_day", raw.get("is_roll", False)))
    if isinstance(field_flag, str):
        field_flag = field_flag.strip().casefold() in {"1", "true", "yes", "y"}
    return bool(field_flag) or (observed_date in configured_roll_dates if observed_date else False)


def _cme_trade_direction_allowed(trade_direction: str, allow_direction: str) -> bool:
    if allow_direction == "long_only":
        return trade_direction == "long"
    if allow_direction == "short_only":
        return trade_direction == "short"
    return True


def _artifact_reference_signals(bundle: ArtifactBundle) -> pd.DataFrame:
    normalized = _normalize_signals(bundle.signals)
    if normalized.empty:
        return pd.DataFrame(columns=["ts", "datetime", "strategy", "inst_id", "side", "fair_value"])
    rows = []
    for _, row in normalized.iterrows():
        dt = _to_datetime(row.get("datetime"))
        rows.append({
            "ts": _ts_ms(dt) if not pd.isna(dt) else "",
            "datetime": _iso(dt) if not pd.isna(dt) else "",
            "strategy": bundle.primary_strategy,
            "inst_id": row.get("inst_id", ""),
            "side": row.get("side", ""),
            "fair_value": "",
        })
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


def _run_backtrader_signal_replay_reference(
    bt: Any,
    bundle: ArtifactBundle,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    prices = _price_frame_for_primary_symbol(bundle)
    data = prices.copy()
    data["datetime"] = pd.to_datetime(data["datetime"], utc=True)
    data = data.set_index("datetime")
    data = data.rename(columns={"vol": "volume"})
    reference_signals = _artifact_reference_signals(bundle)
    inst_id = prices["inst_id"].iloc[0] if "inst_id" in prices.columns and not prices.empty else ""
    primary_signals = reference_signals
    if inst_id and "inst_id" in primary_signals.columns:
        primary_signals = primary_signals[primary_signals["inst_id"].astype(str) == str(inst_id)].copy()
    signals_by_dt: dict[str, list[str]] = {}
    for _, row in primary_signals.iterrows():
        dt = _to_datetime(row.get("datetime", row.get("ts")))
        if pd.isna(dt):
            continue
        signals_by_dt.setdefault(_iso(dt), []).append(str(row.get("side", "")).lower())

    trade_rows: list[dict[str, Any]] = []
    equity_rows: list[dict[str, Any]] = []

    class SignalReplayStrategy(bt.Strategy):
        def __init__(self):
            self.pending_order = None

        def next(self):
            dt = _ensure_utc_timestamp(pd.Timestamp(bt.num2date(self.datas[0].datetime[0])))
            dt_key = _iso(dt)
            close_value = float(self.datas[0].close[0])
            equity_rows.append({
                "ts": _ts_ms(dt),
                "datetime": dt_key,
                "equity": float(self.broker.getvalue()),
            })
            if self.pending_order is not None:
                return
            sides = signals_by_dt.get(dt_key, [])
            if "buy" in sides and not self.position and close_value > 0:
                size = float(self.broker.getcash()) / close_value
                if size > 0:
                    self.pending_order = self.buy(size=size)
            elif "sell" in sides and self.position:
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
                    "strategy": bundle.primary_strategy,
                    "inst_id": inst_id,
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
    cerebro.addstrategy(SignalReplayStrategy)
    cerebro.run()
    return reference_signals, pd.DataFrame(trade_rows), pd.DataFrame(equity_rows)


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
    compare_quotes = _has_quote_signal_fields(project) or _has_quote_signal_fields(reference)
    project_quotes = _normalize_signal_quotes(project) if compare_quotes else pd.DataFrame()
    reference_quotes = _normalize_signal_quotes(reference) if compare_quotes else pd.DataFrame()
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
        if compare_quotes and i < len(project_quotes) and i < len(reference_quotes):
            pq = project_quotes.iloc[i]
            rq = reference_quotes.iloc[i]
            for field in ("fair_value", "target_bid", "target_ask"):
                pv = _safe_float(pq.get(field), float("nan"))
                rv = _safe_float(rq.get(field), float("nan"))
                if not _within_tol(pv, rv, 1e-6, 1e-8):
                    rows.append(_mismatch(
                        engine,
                        "strategy_logic_mismatch",
                        field,
                        i,
                        pv,
                        rv,
                        "quote_value_mismatch",
                        abs_diff=_abs_diff(pv, rv),
                        tolerance=_tol_label(1e-6, 1e-8),
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


def _has_quote_signal_fields(signals: pd.DataFrame) -> bool:
    if signals.empty:
        return False
    for field in ("target_bid", "target_ask"):
        if field in signals.columns and pd.to_numeric(signals[field], errors="coerce").notna().any():
            return True
    return False


def _normalize_signal_quotes(signals: pd.DataFrame) -> pd.DataFrame:
    columns = ["datetime", "inst_id", "side", "fair_value", "target_bid", "target_ask"]
    if signals.empty:
        return pd.DataFrame(columns=columns)
    out = signals.copy()
    normalized = pd.DataFrame({
        "datetime": [_iso(_to_datetime(row)) for row in _series_time(out)],
        "inst_id": out.get("inst_id", pd.Series("", index=out.index)).astype(str),
        "side": out.get("side", pd.Series("", index=out.index)).astype(str).str.lower(),
        "fair_value": _numeric(out.get("fair_value", pd.Series(float("nan"), index=out.index))),
        "target_bid": _numeric(out.get("target_bid", pd.Series(float("nan"), index=out.index))),
        "target_ask": _numeric(out.get("target_ask", pd.Series(float("nan"), index=out.index))),
    })
    return normalized.sort_values(["datetime", "inst_id", "side"]).reset_index(drop=True)


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
    symbol = bundle.symbols[0] if bundle.symbols else None
    prices, metadata = _reference_price_frame_for_symbol(bundle, symbol or "")
    _set_reference_price_input_metadata(bundle, metadata)
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
    export_manifest = ref.metadata.get("export_manifest") if isinstance(ref.metadata, dict) else None
    if isinstance(export_manifest, dict):
        (out_dir / f"reference_{ref.engine}_export_manifest.json").write_text(
            json.dumps(_json_safe(export_manifest), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


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


def _load_signals(root: Path, result: dict[str, Any]) -> pd.DataFrame:
    path = root / "signals.csv"
    signals = _read_csv(path)
    if not signals.empty:
        return signals
    strategies = [str(s) for s in result.get("strategies", []) if s]
    if not strategies and result.get("strategy"):
        strategies = [str(result.get("strategy"))]
    if "daily_winner" in strategies:
        return _daily_winner_project_signals(result)
    if "ohlcv_rotation" in strategies:
        return _ohlcv_rotation_project_signals(root, result)
    return signals


def _ohlcv_rotation_project_signals(root: Path, result: dict[str, Any]) -> pd.DataFrame:
    target_weights = _load_target_weights(root / "target_weights.csv")
    if not target_weights.empty:
        close_panel = _ohlcv_rotation_project_close_panel(root)
        return _ohlcv_rotation_weight_signals(target_weights, close_panel)
    trades = _read_csv(root / "trades.csv")
    if trades.empty:
        trades = pd.DataFrame(result.get("trades") if isinstance(result.get("trades"), list) else [])
    return _ohlcv_rotation_signals_from_trades(trades)


def _load_target_weights(path: Path) -> pd.DataFrame:
    df = _read_csv(path)
    if df.empty:
        return pd.DataFrame()
    data = df.copy()
    time_col = "ts" if "ts" in data.columns else ("datetime" if "datetime" in data.columns else data.columns[0])
    data["_dt"] = [_naive_utc_timestamp(value) for value in data[time_col]]
    data = data.dropna(subset=["_dt"]).sort_values("_dt")
    value_cols = [
        column for column in data.columns
        if column not in {time_col, "datetime", "ts", "_dt"} and not str(column).startswith("Unnamed")
    ]
    if not value_cols:
        return pd.DataFrame()
    weights = data.set_index("_dt")[value_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    weights.index = pd.DatetimeIndex(weights.index)
    return weights


def _ohlcv_rotation_project_close_panel(root: Path) -> pd.DataFrame:
    prices = _read_csv(root / "price_series.csv")
    if prices.empty or "inst_id" not in prices.columns or "close" not in prices.columns:
        return pd.DataFrame()
    frames: dict[str, pd.Series] = {}
    for symbol, group in prices.groupby(prices["inst_id"].astype(str)):
        prepared = _ohlcv_rotation_prepare_price_frame(group)
        if not prepared.empty:
            frames[symbol] = prepared["close"]
    if not frames:
        return pd.DataFrame()
    return pd.DataFrame(frames).sort_index()


def _ohlcv_rotation_signals_from_trades(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=["ts", "datetime", "strategy", "inst_id", "side", "fair_value"])
    rows: list[dict[str, Any]] = []
    for _, row in trades.iterrows():
        inst_id = str(row.get("inst_id") or row.get("symbol") or "")
        entry = _daily_winner_signal_from_values(
            strategy="ohlcv_rotation",
            inst_id=inst_id,
            side="buy",
            ts_value=row.get("entry_ts") or row.get("datetime") or row.get("ts"),
            fair_value=row.get("entry_price", row.get("price")),
        )
        if entry:
            rows.append(entry)
        exit_row = _daily_winner_signal_from_values(
            strategy="ohlcv_rotation",
            inst_id=inst_id,
            side="sell",
            ts_value=row.get("exit_ts") or row.get("close_ts"),
            fair_value=row.get("exit_price", row.get("close_price")),
        )
        if exit_row:
            rows.append(exit_row)
    if not rows:
        return pd.DataFrame(columns=["ts", "datetime", "strategy", "inst_id", "side", "fair_value"])
    return pd.DataFrame(rows, columns=["ts", "datetime", "strategy", "inst_id", "side", "fair_value"])


def _daily_winner_project_signals(result: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    strategy = "daily_winner"
    round_trips = [row for row in result.get("round_trips") or [] if isinstance(row, dict)]
    trades = [row for row in result.get("trades") or [] if isinstance(row, dict)]
    source_rows = round_trips or trades
    for row in source_rows:
        if _daily_winner_execution_signal_row(row):
            side = str(row.get("side") or "").lower()
            if side in {"buy", "sell"}:
                signal = _daily_winner_signal_from_values(
                    strategy=strategy,
                    inst_id=str(row.get("inst_id") or row.get("symbol") or ""),
                    side=side,
                    ts_value=row.get("datetime") or row.get("ts"),
                    fair_value=row.get("price", row.get("fill_px")),
                )
                if signal:
                    rows.append(signal)
            continue
        inst_id = str(row.get("inst_id") or row.get("symbol") or "")
        entry = _daily_winner_signal_from_values(
            strategy=strategy,
            inst_id=inst_id,
            side="buy",
            ts_value=row.get("entry_ts") or row.get("datetime") or row.get("ts"),
            fair_value=row.get("entry_price", row.get("price")),
        )
        if entry:
            rows.append(entry)
        exit_row = _daily_winner_signal_from_values(
            strategy=strategy,
            inst_id=inst_id,
            side="sell",
            ts_value=row.get("exit_ts") or row.get("close_ts"),
            fair_value=row.get("exit_price", row.get("close_price")),
        )
        if exit_row:
            rows.append(exit_row)
    if not rows:
        return pd.DataFrame(columns=["ts", "datetime", "strategy", "inst_id", "side", "fair_value"])
    return pd.DataFrame(rows, columns=["ts", "datetime", "strategy", "inst_id", "side", "fair_value"])


def _daily_winner_execution_signal_row(row: dict[str, Any]) -> bool:
    phase = str(row.get("execution_phase") or "").lower()
    if phase in {"entry", "exit"}:
        return True
    if str(row.get("type") or "") == "validation_synthetic_fill":
        return True
    return bool(row.get("side") and (row.get("datetime") or row.get("ts")))


def _daily_winner_signal_from_values(
    *,
    strategy: str,
    inst_id: str,
    side: str,
    ts_value: Any,
    fair_value: Any,
) -> dict[str, Any] | None:
    if not inst_id or side not in {"buy", "sell"} or ts_value in {None, ""}:
        return None
    dt = _to_datetime(ts_value)
    if pd.isna(dt):
        return None
    return {
        "ts": _ts_ms(dt),
        "datetime": _iso(dt),
        "strategy": strategy,
        "inst_id": inst_id,
        "side": side,
        "fair_value": _safe_float(fair_value, float("nan")),
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
        result = _normalize_embedded_daily_winner(_read_json(run_dir / "result.json"))
    except Exception:
        return None
    strategies = [str(s) for s in result.get("strategies", []) if s]
    if not strategies and result.get("strategy"):
        strategies = [str(result.get("strategy"))]
    primary = strategies[0] if strategies else ""
    if clean_strategy and primary != clean_strategy:
        return None
    if primary in TECHNICAL_STRATEGIES and not _csv_has_data_rows(run_dir / "price_series.csv"):
        return None
    config = {}
    if not result.get("bar") and (run_dir / "config.json").exists():
        try:
            config = _read_json(run_dir / "config.json")
        except Exception:
            config = {}
    symbols = result.get("symbols") or []
    symbols = [str(s) for s in symbols if s]
    validation = result.get("validation") if isinstance(result.get("validation"), dict) else {}
    materialized = _materialized_from_sweep_summary(result)
    row = {
        "run_id": result.get("run_id") or run_dir.name,
        "strategy": primary,
        "strategies": strategies,
        "symbols": symbols,
        "bar": str(result.get("bar") or config.get("cli_args", {}).get("bar") or "1H"),
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
    row["display_name"] = result.get("display_name") or _fixture_display_name(row, str(row["run_id"]))
    return row


def _csv_has_data_rows(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            next(handle, None)
            return any(line.strip() for line in handle)
    except OSError:
        return False


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
            row = {
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
            }
            row["display_name"] = _fixture_display_name(row, run_id)
            rows.append(row)
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


def _naive_utc_timestamp(value: Any) -> pd.Timestamp:
    ts = _to_datetime(value)
    if pd.isna(ts):
        return pd.NaT
    return _ensure_utc_timestamp(ts).tz_localize(None)


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


def _build_validation_id(bundle: ArtifactBundle | None = None, created_at: datetime | None = None) -> str:
    ts = created_at or datetime.now(timezone.utc)
    stamp = ts.strftime("%Y%m%d")
    if bundle is None:
        return f"diff_{stamp}_{uuid.uuid4().hex[:8]}"
    strategy = _slug_part(bundle.primary_strategy or "strategy")
    symbols = bundle.symbols
    symbol = _slug_part("_".join(symbols[:2]) if symbols else "multi_symbol")
    if len(symbols) > 2:
        symbol = f"{symbol}_plus{len(symbols) - 2}"
    return f"{stamp}_{strategy}_{symbol}_{uuid.uuid4().hex[:8]}"


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
    "REFERENCE_VALIDATION_CONTRACTS",
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
    "strategy_reference_validation_contract",
]
