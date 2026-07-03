import numpy as np
import pandas as pd

from backtesting.funding_xs_dispersion_backtest import (
    FundingXSDispersionParams,
    run_funding_xs_dispersion_backtest,
    scan_funding_xs_dispersion,
)


def _membership(index, symbols):
    days = pd.DatetimeIndex(index).normalize().unique()
    return pd.DataFrame(
        [
            {"date": day, "symbol": symbol, "eligible": True, "adv_usd": 1.0, "listing_ts": days[0]}
            for day in days
            for symbol in symbols
        ]
    )


def test_low_funding_leg_is_long_and_high_funding_leg_is_short():
    idx = pd.date_range("2024-01-01", periods=5, freq="D")
    close = pd.DataFrame({"LOW": 100.0, "HIGH": 100.0}, index=idx)
    funding = pd.DataFrame({"LOW": 0.0, "HIGH": 0.001}, index=idx)
    params = FundingXSDispersionParams(
        universe=list(close.columns),
        rebalance="daily",
        lookback_days=1,
        quantile=0.5,
        inverse_vol=False,
        max_name_weight=1.0,
    )

    result = run_funding_xs_dispersion_backtest(close, close, close, close, funding, _membership(idx, close.columns), params)

    assert result.target_weights["LOW"].iloc[-1] > 0
    assert result.target_weights["HIGH"].iloc[-1] < 0


def test_funding_signal_target_is_not_traded_on_same_day():
    idx = pd.date_range("2024-01-01", periods=4 * 24, freq="h")
    close = pd.DataFrame(index=idx, columns=["LOW", "HIGH"], dtype=float)
    close.loc[:, "LOW"] = 100.0
    close.loc[:, "HIGH"] = 100.0
    close.loc["2024-01-03", "LOW"] = np.linspace(100.0, 150.0, 24)
    close = close.ffill()
    funding = pd.DataFrame(np.nan, index=idx, columns=close.columns)
    funding.loc["2024-01-03", "LOW"] = 0.0
    funding.loc["2024-01-03", "HIGH"] = 0.001
    params = FundingXSDispersionParams(
        universe=list(close.columns),
        rebalance="daily",
        lookback_days=1,
        quantile=0.5,
        inverse_vol=False,
        max_name_weight=1.0,
        fee_bps=0.0,
        slippage_bps=0.0,
    )

    result = run_funding_xs_dispersion_backtest(close, close, close, close, funding, _membership(idx, close.columns), params)

    assert result.positions.loc["2024-01-03"].abs().sum(axis=1).max() == 0.0
    assert result.positions.loc["2024-01-04"].abs().sum(axis=1).max() > 0.0


def test_scan_accepts_caller_declared_researched_n_trials():
    idx = pd.date_range("2024-01-01", periods=5, freq="D")
    close = pd.DataFrame({"LOW": 100.0, "HIGH": 100.0}, index=idx)
    funding = pd.DataFrame({"LOW": 0.0, "HIGH": 0.001}, index=idx)
    params = FundingXSDispersionParams(universe=list(close.columns), rebalance="daily")

    result = scan_funding_xs_dispersion(
        close,
        close,
        close,
        close,
        funding,
        _membership(idx, close.columns),
        params,
        grid={"lookback_days": [7, 14], "quantile": [0.2, 0.3]},
        researched_n_trials=4,
    )

    assert result.attrs["n_trials"] == 4
    assert set(result["n_trials"]) == {4}
    assert set(result["n_trials_provenance"]) == {"caller_declared"}
