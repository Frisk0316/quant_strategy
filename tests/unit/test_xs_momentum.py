import asyncio

import numpy as np
import pandas as pd

from okx_quant.portfolio.allocation import dollar_neutral_long_short_weights


def test_weights_are_dollar_neutral_and_gross_normalized():
    scores = pd.Series({"a": 5, "b": 4, "c": 0, "d": -4, "e": -5})

    weights = dollar_neutral_long_short_weights(scores, q=0.4, inverse_vol=None, gross=1.0)

    assert abs(weights.sum()) < 1e-9
    assert abs(weights.abs().sum() - 1.0) < 1e-9
    assert (weights[["a", "b"]] > 0).all()
    assert (weights[["d", "e"]] < 0).all()
    assert weights.get("c", 0.0) == 0.0


def test_higher_steady_trend_scores_above_noisier_trend():
    from okx_quant.strategies.xs_momentum import vol_normalized_momentum

    idx = pd.date_range("2024-01-01", periods=40, freq="D")
    steady = pd.Series(np.linspace(100, 140, 40), index=idx)
    noisy = pd.Series(np.linspace(100, 140, 40) + np.tile([5, -5], 20), index=idx)
    close = pd.DataFrame({"STEADY": steady, "NOISY": noisy})

    score = vol_normalized_momentum(close, lookback=28, skip=0, vol_window=28)

    last = score.iloc[-1]
    assert last["STEADY"] > last["NOISY"]


def test_target_weights_respect_membership_neutrality_and_caps():
    from okx_quant.strategies.xs_momentum import XSMomentumParams, target_weights

    idx = pd.date_range("2024-01-01", periods=10, freq="D")
    scores = pd.DataFrame(
        {"A": 4.0, "B": 1.0, "C": 10.0, "D": -5.0},
        index=idx,
    )
    membership = pd.DataFrame(
        [
            {"date": date, "symbol": symbol, "eligible": symbol != "C", "adv_usd": 1.0, "listing_ts": idx[0]}
            for date in idx
            for symbol in ["A", "B", "C", "D"]
        ]
    )
    realized_vol = pd.DataFrame(0.2, index=idx, columns=scores.columns)
    params = XSMomentumParams(
        universe=list(scores.columns),
        quantile=0.34,
        max_name_weight=0.2,
    )

    weights = target_weights(scores, membership, params, realized_vol)

    assert (weights["C"] == 0.0).all()
    assert (weights.sum(axis=1).abs() < 1e-9).all()
    assert weights.abs().max().max() <= params.max_name_weight


def test_crash_regime_reduces_gross_exposure():
    from okx_quant.strategies.xs_momentum import XSMomentumParams, target_weights

    idx = pd.date_range("2024-01-01", periods=14, freq="D")
    scores = pd.DataFrame({"A": 4.0, "B": 1.0, "C": -1.0, "D": -5.0}, index=idx)
    membership = pd.DataFrame(
        [
            {"date": date, "symbol": symbol, "eligible": True, "adv_usd": 1.0, "listing_ts": idx[0]}
            for date in idx
            for symbol in scores.columns
        ]
    )
    realized_vol = pd.DataFrame(0.1, index=idx, columns=scores.columns)
    market_close = pd.Series(
        [100, 101, 102, 103, 104, 105, 80, 79, 78, 77, 76, 75, 74, 73],
        index=idx,
    )
    params = XSMomentumParams(
        universe=list(scores.columns),
        quantile=0.25,
        max_name_weight=1.0,
        vol_target_annual=1.0,
    )

    weights = target_weights(scores, membership, params, realized_vol, market_close=market_close)

    assert weights.loc[pd.Timestamp("2024-01-08")].abs().sum() < weights.loc[pd.Timestamp("2024-01-01")].abs().sum()


def test_vol_target_uses_portfolio_book_vol_and_cap():
    from okx_quant.strategies.xs_momentum import XSMomentumParams, target_weights

    idx = pd.date_range("2024-01-01", periods=2, freq="D")
    scores = pd.DataFrame({"A": 1.0, "B": -1.0}, index=idx)
    membership = pd.DataFrame(
        [
            {"date": date, "symbol": symbol, "eligible": True, "adv_usd": 1.0, "listing_ts": idx[0]}
            for date in idx
            for symbol in scores.columns
        ]
    )
    daily_vol = 0.01
    realized_vol = pd.DataFrame(daily_vol, index=idx, columns=scores.columns)
    unit_book_annual_vol = np.sqrt((0.5 * daily_vol) ** 2 + (0.5 * daily_vol) ** 2) * np.sqrt(365.0)
    params = XSMomentumParams(
        universe=list(scores.columns),
        rebalance="daily",
        quantile=0.5,
        max_name_weight=10.0,
        vol_target_annual=unit_book_annual_vol * 0.5,
    )

    weights = target_weights(scores, membership, params, realized_vol)

    assert abs(weights.iloc[0].abs().sum() - 0.5) < 1e-9

    capped = target_weights(
        scores,
        membership,
        XSMomentumParams(
            universe=list(scores.columns),
            rebalance="daily",
            quantile=0.5,
            max_name_weight=10.0,
            vol_target_annual=unit_book_annual_vol * 100.0,
        ),
        realized_vol,
    )

    assert abs(capped.iloc[0].abs().sum() - 2.0) < 1e-9


def test_xs_momentum_strategy_stub_is_noop():
    from okx_quant.strategies.xs_momentum import XSMomentumStrategy

    strategy = XSMomentumStrategy({})

    assert asyncio.run(strategy.on_market(None)) is None


def test_config_loads_xs_momentum_disabled():
    from okx_quant.core.config import load_config

    cfg = load_config(require_secrets=False)

    assert cfg.strategies.xs_momentum.enabled is False


def test_replay_registry_can_load_xs_momentum_stub():
    from backtesting.replay import ReplayBacktestEngine
    from okx_quant.core.config import load_config

    cfg = load_config(require_secrets=False)
    engine = ReplayBacktestEngine(cfg, strategy_names=["xs_momentum"])

    strategies = engine._build_strategies()

    assert [strategy.name for strategy in strategies] == ["xs_momentum"]
