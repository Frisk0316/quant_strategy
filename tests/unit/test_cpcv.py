import numpy as np
import pandas as pd

from backtesting.cpcv import CPCV


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
    )

    assert result["n_trials"] == 0
    assert result["dsr"] == 0.0
    assert result["validation"]["n_trials_missing"] is True
