from __future__ import annotations

import numpy as np
import pandas as pd

from backtesting.pipeline_refit import refit_validation, select_combo_on


def test_select_combo_on_uses_only_supplied_window():
    index = pd.date_range("2024-01-01", periods=12, freq="D")
    first = index[:6]
    second = index[6:]
    combo_returns = {
        "a": pd.Series([0.02, -0.01, 0.03, -0.01, 0.02, -0.01] + [-0.02] * 6, index=index),
        "b": pd.Series([-0.02] * 6 + [0.02, -0.01, 0.03, -0.01, 0.02, -0.01], index=index),
    }

    assert select_combo_on(first, combo_returns) == "a"
    assert select_combo_on(second, combo_returns) == "b"


def test_refit_validation_cpcv_paths_are_not_degenerate():
    index = pd.date_range("2024-01-01", periods=180, freq="D")
    first_half = index[:90]
    a = pd.Series(-0.01, index=index)
    b = pd.Series(0.01, index=index)
    a.loc[first_half] = [0.02, -0.01, 0.03, -0.01, 0.02] * 18
    b.loc[first_half] = [-0.02, 0.01, -0.03, 0.01, -0.02] * 18

    summary = refit_validation(
        {"a": a, "b": b},
        n_trials=2,
        is_days=60,
        oos_days=30,
        cpcv_n_splits=6,
        cpcv_k_test=2,
        embargo_pct=0.0,
        purge_size=0,
    )

    path_sharpes = np.asarray(summary["cpcv"]["path_sharpes"], dtype=float)
    assert len(path_sharpes) > 1
    assert float(path_sharpes.std()) > 0.0
