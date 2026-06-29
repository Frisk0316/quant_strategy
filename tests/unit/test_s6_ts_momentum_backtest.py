import asyncio

import numpy as np
import pandas as pd


def _panels():
    idx = pd.date_range("2024-01-01", periods=4 * 24, freq="h")
    btc = pd.Series(100.0, index=idx)
    eth = pd.Series(100.0, index=idx)
    btc.loc["2024-01-03"] = np.linspace(100.0, 130.0, 24)
    eth.loc["2024-01-03"] = np.linspace(100.0, 80.0, 24)
    btc.loc["2024-01-04"] = 130.0
    eth.loc["2024-01-04"] = 80.0
    close = pd.DataFrame({"BTC-USDT-SWAP": btc.ffill(), "ETH-USDT-SWAP": eth.ffill()})
    funding = pd.DataFrame(0.0, index=idx, columns=close.columns)
    return close, funding


def test_s6_ts_momentum_strategy_stub_is_noop():
    from okx_quant.strategies.s6_ts_momentum import S6TSMomentumStrategy

    assert asyncio.run(S6TSMomentumStrategy({}).on_market(None)) is None


def test_s6_trend_signal_trades_next_day_not_same_day_close():
    from backtesting.s6_ts_momentum_backtest import run_s6_ts_momentum_backtest
    from okx_quant.strategies.s6_ts_momentum import S6TSMomentumParams

    close, funding = _panels()
    params = S6TSMomentumParams(
        symbols=list(close.columns),
        lookback_days=1,
        vol_window_days=2,
        vol_target_annual=1.0,
        crash_filter=False,
        rebalance="daily",
        fee_bps=0.0,
        slippage_bps=0.0,
    )

    result = run_s6_ts_momentum_backtest(close, funding, params)

    assert result.positions.loc["2024-01-03"].abs().sum(axis=1).max() == 0.0
    jan4 = result.positions.loc["2024-01-04"].iloc[1]
    assert jan4["BTC-USDT-SWAP"] > 0.0
    assert jan4["ETH-USDT-SWAP"] < 0.0


def test_scan_s6_records_family_cumulative_n_trials():
    from backtesting.s6_ts_momentum_backtest import scan_s6_ts_momentum
    from okx_quant.strategies.s6_ts_momentum import S6TSMomentumParams

    close, funding = _panels()
    result = scan_s6_ts_momentum(
        close,
        funding,
        S6TSMomentumParams(symbols=list(close.columns), lookback_days=1),
        grid={"lookback_days": [1, 2], "crash_filter": [False]},
        prior_family_n_trials=46,
    )

    assert result.attrs["n_trials"] == 48
    assert set(result["n_trials"]) == {48}
