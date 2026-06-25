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


def test_scan_adds_prior_family_trials_to_n_trials():
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
        prior_family_n_trials=10,
    )

    assert result.attrs["n_trials"] == 26
    assert set(result["n_trials"]) == {26}


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


def test_daily_close_target_is_not_traded_on_same_day():
    from backtesting.ohlcv_rotation_backtest import compute_turnover
    from backtesting.xs_momentum_backtest import (
        _daily_close,
        _funding_returns,
        run_xs_momentum_backtest,
    )
    from okx_quant.strategies.xs_momentum import target_weights, vol_normalized_momentum

    idx = pd.date_range("2024-01-01", periods=4 * 24, freq="h")
    close = pd.DataFrame(index=idx, columns=["A", "B"], dtype=float)
    close.loc["2024-01-01", ["A", "B"]] = [100.0, 100.0]
    close.loc["2024-01-02", ["A", "B"]] = [101.0, 99.0]
    close.loc["2024-01-03", "A"] = np.linspace(101.0, 202.0, 24)
    close.loc["2024-01-03", "B"] = np.linspace(99.0, 98.0, 24)
    close.loc["2024-01-04", ["A", "B"]] = [202.0, 98.0]
    close = close.ffill()
    vol = pd.DataFrame(1_000.0, index=idx, columns=close.columns)
    funding = pd.DataFrame(0.0, index=idx, columns=close.columns)
    daily_index = pd.date_range("2024-01-01", periods=4, freq="D")
    membership = pd.DataFrame(
        [
            {"date": date, "symbol": symbol, "eligible": True, "adv_usd": 1.0, "listing_ts": daily_index[0]}
            for date in daily_index
            for symbol in close.columns
        ]
    )
    params = XSMomentumParams(
        universe=list(close.columns),
        rebalance="daily",
        lookback_days=1,
        vol_window_days=2,
        quantile=0.5,
        inverse_vol=False,
        vol_target_annual=10.0,
        max_name_weight=10.0,
        fee_bps=0.0,
        slippage_bps=0.0,
    )

    close_daily = _daily_close(close)
    scores = vol_normalized_momentum(close_daily, params.lookback_days, params.skip_days, params.vol_window_days)
    realized_vol = close_daily.pct_change().rolling(params.vol_window_days, min_periods=2).std()
    buggy_target = target_weights(scores, membership, params, realized_vol).reindex(close.index).ffill().fillna(0.0)
    buggy_positions = buggy_target.shift(1).fillna(0.0)
    buggy_returns = (
        (buggy_positions * close.pct_change().fillna(0.0)).sum(axis=1)
        + _funding_returns(buggy_positions, funding).sum(axis=1)
        - compute_turnover(buggy_target) * (params.fee_bps + params.slippage_bps) / 10_000
    )
    assert float((1.0 + buggy_returns).prod() - 1.0) > 0.1

    result = run_xs_momentum_backtest(close, close, close, vol, funding, membership, params)

    assert result.positions.loc["2024-01-03"].abs().sum(axis=1).max() == 0.0
    assert result.positions.loc["2024-01-04"].abs().sum(axis=1).max() > 0.0
    assert abs(result.metrics["total_return"]) < 1e-12
