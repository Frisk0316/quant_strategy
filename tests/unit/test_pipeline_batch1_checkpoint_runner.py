from __future__ import annotations

import pandas as pd

from scripts.run_pipeline_batch1_checkpoint import _best_combo_record, _refit_validation


def test_best_combo_record_scores_only_train_index():
    index = pd.date_range("2024-01-01", periods=10, freq="D")
    train_index = index[:5]
    fast = pd.Series([-0.10] * 10, index=index)
    slow = pd.Series([0.0] * 10, index=index)
    fast.loc[train_index] = [0.01, -0.01, 0.02, -0.01, 0.03]
    slow.loc[train_index] = [0.0, 0.0, 0.001, 0.0, 0.0]

    selected = _best_combo_record([
        {"combo": {"name": "fast"}, "daily_returns": fast},
        {"combo": {"name": "slow"}, "daily_returns": slow},
    ], train_index)

    assert selected["combo"] == {"name": "fast"}


def test_refit_validation_reports_fold_selected_params():
    index = pd.date_range("2024-01-01", periods=550, freq="D")
    early = index[:365]
    fast = pd.Series(-0.05, index=index)
    slow = pd.Series(0.01, index=index)
    fast.loc[early] = [0.01, -0.01, 0.02, -0.01, 0.03] * 73
    slow.loc[early] = [0.0, 0.0, 0.001, 0.0, 0.0] * 73

    summary = _refit_validation(
        [
            {"combo": {"name": "fast"}, "daily_returns": fast},
            {"combo": {"name": "slow"}, "daily_returns": slow},
        ],
        n_trials=2,
        cpcv_n_splits=3,
        cpcv_k_test=1,
        embargo_pct=0.0,
        purge_size=0,
    )

    assert summary["wf_selected_param_counts"]["name=fast"] > 0
    assert summary["cpcv_selected_param_counts"]
    assert summary["validation_mode"] == "fold_refit_param_selection"
