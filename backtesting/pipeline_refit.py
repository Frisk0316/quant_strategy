"""Small helpers for fold-refit pipeline validation."""
from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np
import pandas as pd

from backtesting.cpcv import CPCV
from backtesting.walk_forward import WalkForward
from okx_quant.analytics.performance import sharpe


def _finite(value: object) -> object:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return value
    return out if np.isfinite(out) else None


def combo_key(combo: dict[str, Any]) -> str:
    if not combo:
        return "default"
    return "|".join(f"{key}={combo[key]}" for key in sorted(combo))


def score_returns_on(window_index: pd.Index, daily_returns: pd.Series) -> float:
    returns = daily_returns.reindex(window_index).dropna().astype(float)
    return float(_finite(sharpe(returns, periods=365)) or 0.0)


def select_combo_on(window_index: pd.Index, combo_returns: dict[str, pd.Series]) -> str:
    if not combo_returns:
        raise ValueError("at least one combo return series is required")
    best_key = sorted(combo_returns)[0]
    best_score = float("-inf")
    for key in sorted(combo_returns):
        score = score_returns_on(window_index, combo_returns[key])
        if score > best_score:
            best_key = key
            best_score = score
    return best_key


def validation_frame(combo_returns: dict[str, pd.Series]) -> pd.DataFrame:
    indexes = [
        pd.DatetimeIndex(series.dropna().index)
        for series in combo_returns.values()
        if not series.dropna().empty
    ]
    if not indexes:
        raise ValueError("combo return series are empty")
    index = indexes[0]
    for next_index in indexes[1:]:
        index = index.union(next_index)
    return pd.DataFrame({"fold_marker": 0.0}, index=index.sort_values())


def refit_validation(
    combo_returns: dict[str, pd.Series],
    n_trials: int,
    *,
    is_days: int = 365,
    oos_days: int = 90,
    cpcv_n_splits: int = 6,
    cpcv_k_test: int = 2,
    embargo_pct: float = 0.02,
    purge_size: int = 1,
) -> dict[str, Any]:
    frame = validation_frame(combo_returns)
    wf_counts: Counter[str] = Counter()
    cpcv_counts: Counter[str] = Counter()

    def wf_returns(train: pd.DataFrame, test: pd.DataFrame) -> pd.Series:
        selected = select_combo_on(train.index, combo_returns)
        wf_counts[selected] += 1
        return combo_returns[selected].reindex(test.index).fillna(0.0)

    def cpcv_returns(train: pd.DataFrame, test: pd.DataFrame) -> pd.Series:
        selected = select_combo_on(train.index, combo_returns)
        cpcv_counts[selected] += 1
        return combo_returns[selected].reindex(test.index).fillna(0.0)

    wf = WalkForward(is_days=is_days, oos_days=oos_days).evaluate(frame, wf_returns, periods=365)
    cpcv = CPCV(
        n_splits=cpcv_n_splits,
        k_test=cpcv_k_test,
        embargo_pct=embargo_pct,
        purge_size=purge_size,
    ).evaluate(frame, cpcv_returns, periods=365, n_trials=n_trials)
    wf_sharpe = wf["oos_sharpe"].mean() if not wf.empty else 0.0

    return {
        "validation_mode": "fold_refit_param_selection",
        "wf_oos_sharpe": float(_finite(wf_sharpe) or 0.0),
        "cpcv_oos_sharpe": _finite(cpcv["overall_oos_sharpe"]),
        "dsr": _finite(cpcv["dsr"]),
        "psr": _finite(cpcv["psr"]),
        "wf_selected_param_counts": dict(sorted(wf_counts.items())),
        "cpcv_selected_param_counts": dict(sorted(cpcv_counts.items())),
        "cpcv": {
            "n_splits": cpcv_n_splits,
            "k_test": cpcv_k_test,
            "embargo_pct": embargo_pct,
            "purge_size": purge_size,
            "n_combinations": cpcv.get("n_combinations"),
            "n_paths": cpcv.get("n_paths"),
            "path_sharpes": [_finite(x) for x in cpcv.get("path_sharpes", [])],
        },
    }
