import numpy as np
import pandas as pd

from backtesting.cpcv import CPCV
from okx_quant.analytics.dsr import deflated_sharpe, psr
from okx_quant.analytics.performance import sharpe


def test_cpcv_dsr_does_not_exceed_psr_with_honest_trials():
    rng = np.random.default_rng(11)
    idx = pd.date_range("2024-01-01", periods=240, freq="h")
    df = pd.DataFrame({"ret": rng.normal(0.00005, 0.01, len(idx))}, index=idx)

    result = CPCV(n_splits=6, k_test=2, embargo_pct=0.0, purge_size=0).evaluate(
        df,
        lambda _train, test: test["ret"],
        periods=365 * 24,
        n_trials=20,
    )

    assert result["dsr"] <= result["psr"]


def test_cpcv_missing_n_trials_does_not_emit_fake_dsr():
    idx = pd.date_range("2024-01-01", periods=12, freq="D")
    df = pd.DataFrame({"ret": np.linspace(-0.01, 0.02, len(idx))}, index=idx)

    result = CPCV(n_splits=4, k_test=2, embargo_pct=0.0, purge_size=0).evaluate(
        df,
        lambda _train, test: test["ret"],
        periods=365,
        n_trials=0,
    )

    assert result["n_trials"] == 0
    assert result["dsr"] == 0.0
    assert result["validation"]["n_trials_missing"] is True


def test_cpcv_emits_path_returns_that_recompute_dsr():
    rng = np.random.default_rng(22)
    idx = pd.date_range("2024-01-01", periods=240, freq="h")
    df = pd.DataFrame({"ret": rng.normal(0.0001, 0.008, len(idx))}, index=idx)
    periods = 365 * 24

    result = CPCV(n_splits=6, k_test=2, embargo_pct=0.0, purge_size=0).evaluate(
        df,
        lambda _train, test: test["ret"],
        periods=periods,
        n_trials=12,
    )

    path_returns = [np.asarray(values, dtype=float) for values in result["path_returns"]]
    path_sharpes = [sharpe(values, periods=periods) for values in path_returns]
    recomputed_dsr = float(np.mean([
        deflated_sharpe(values, sr, path_sharpes, N=result["n_trials"])
        for values, sr in zip(path_returns, path_sharpes)
    ]))
    recomputed_psr = float(np.mean([psr(values) for values in path_returns]))

    assert result["path_return_periods"] == periods
    assert result["path_return_lengths"] == [len(values) for values in path_returns]
    assert recomputed_dsr == result["dsr"]
    assert recomputed_psr == result["psr"]


def test_recheck_dsr_recomputes_retained_path_returns():
    from scripts.recheck_dsr import _recompute_retained_cpcv

    rng = np.random.default_rng(33)
    idx = pd.date_range("2024-01-01", periods=240, freq="h")
    df = pd.DataFrame({"ret": rng.normal(0.0001, 0.008, len(idx))}, index=idx)

    result = CPCV(n_splits=6, k_test=2, embargo_pct=0.0, purge_size=0).evaluate(
        df,
        lambda _train, test: test["ret"],
        periods=365 * 24,
        n_trials=12,
    )

    recomputed = _recompute_retained_cpcv(result)

    assert recomputed is not None
    assert recomputed[0] == result["dsr"]
    assert recomputed[1] == result["psr"]
    assert "path returns" in recomputed[2]


def test_cpcv_emits_combined_returns_when_paths_are_unavailable():
    rng = np.random.default_rng(44)
    idx = pd.date_range("2024-01-01", periods=125, freq="D")
    df = pd.DataFrame({"ret": rng.normal(0.0002, 0.01, len(idx))}, index=idx)

    result = CPCV(n_splits=5, k_test=2, embargo_pct=0.0, purge_size=0).evaluate(
        df,
        lambda _train, test: test["ret"],
        periods=365,
        n_trials=10,
    )

    combined = np.asarray(result["combined_returns"], dtype=float)
    overall_sr = sharpe(combined, periods=365)
    recomputed_dsr = deflated_sharpe(combined, overall_sr, result["sharpe_list"], N=result["n_trials"])

    assert result["path_returns"] == []
    assert result["combined_return_periods"] == 365
    assert result["combined_return_length"] == len(combined)
    assert recomputed_dsr == result["dsr"]


def test_cpcv_absent_n_trials_is_tagged_as_grid_size_floor():
    idx = pd.date_range("2024-01-01", periods=60, freq="D")
    df = pd.DataFrame({"ret": np.linspace(-0.01, 0.02, len(idx))}, index=idx)

    result = CPCV(n_splits=4, k_test=2, embargo_pct=0.0, purge_size=0).evaluate(
        df,
        lambda _train, test: test["ret"],
        periods=365,
    )

    assert result["n_trials"] == result["n_combinations"]
    assert result["n_trials_provenance"] == "grid_size_floor"
    assert result["n_trials_is_floor"] is True
    assert result["validation"]["n_trials_provenance"] == "grid_size_floor"
    assert result["validation"]["n_trials_is_floor"] is True
