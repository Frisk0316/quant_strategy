import numpy as np
import pandas as pd

from okx_quant.strategies.xs_momentum import XSMomentumParams


def _panels():
    idx = pd.date_range("2024-01-01", periods=8, freq="D")
    close = pd.DataFrame(
        {
            "A": np.linspace(100, 130, len(idx)),
            "B": np.linspace(100, 70, len(idx)),
        },
        index=idx,
    )
    vol = pd.DataFrame(1_000.0, index=idx, columns=close.columns)
    membership = pd.DataFrame(
        [
            {"date": date, "symbol": symbol, "eligible": True, "adv_usd": 1.0, "listing_ts": idx[0]}
            for date in idx
            for symbol in close.columns
        ]
    )
    funding = pd.DataFrame(0.0, index=idx, columns=close.columns)
    return close, close, close, vol, funding, membership


def test_short_receives_positive_funding():
    from backtesting.xs_momentum_backtest import _funding_returns

    idx = pd.DatetimeIndex([pd.Timestamp("2024-01-01")])
    positions = pd.DataFrame({"LONG": [1.0], "SHORT": [-1.0]}, index=idx)
    funding = pd.DataFrame({"LONG": [0.01], "SHORT": [0.01]}, index=idx)

    returns = _funding_returns(positions, funding)

    assert returns["LONG"].iloc[0] == -0.01
    assert returns["SHORT"].iloc[0] == 0.01


def test_scan_xs_momentum_records_honest_n_trials():
    from backtesting.xs_momentum_backtest import scan_xs_momentum

    close, high, low, vol, funding, membership = _panels()
    params = XSMomentumParams(
        universe=list(close.columns),
        rebalance="daily",
        lookback_days=1,
        vol_window_days=2,
        quantile=0.5,
        max_name_weight=1.0,
        vol_target_annual=10.0,
    )

    result = scan_xs_momentum(
        close,
        high,
        low,
        vol,
        funding,
        membership,
        params,
        grid={
            "lookback_days": [1, 2],
            "skip_days": [0],
            "quantile": [0.25, 0.5],
            "vol_target_annual": [0.1, 0.2],
            "top_n": [2, 3],
        },
    )

    assert result.attrs["n_trials"] == 16
    assert set(result["n_trials"]) == {16}


def test_backtest_passes_market_close_to_crash_filter():
    from backtesting.xs_momentum_backtest import run_xs_momentum_backtest

    close, high, low, vol, funding, membership = _panels()
    params = XSMomentumParams(
        universe=list(close.columns),
        rebalance="daily",
        lookback_days=1,
        vol_window_days=2,
        quantile=0.5,
        max_name_weight=1.0,
        vol_target_annual=10.0,
    )
    calm = run_xs_momentum_backtest(close, high, low, vol, funding, membership, params)
    crash = run_xs_momentum_backtest(
        close,
        high,
        low,
        vol,
        funding,
        membership,
        params,
        market_close=pd.Series([100, 101, 102, 103, 70, 69, 68, 67], index=close.index),
    )

    post_crash = close.index[4:]
    assert crash.target_weights.loc[post_crash].abs().sum(axis=1).max() < calm.target_weights.loc[post_crash].abs().sum(axis=1).max()
