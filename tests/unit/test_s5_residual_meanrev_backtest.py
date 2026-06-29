import asyncio

import numpy as np
import pandas as pd


def _panels():
    idx = pd.date_range("2024-01-01", periods=4 * 24, freq="h")
    btc = pd.Series(100.0, index=idx)
    eth = pd.Series(100.0, index=idx)
    rich = pd.Series(100.0, index=idx)
    cheap = pd.Series(100.0, index=idx)
    rich.loc["2024-01-03"] = np.linspace(100.0, 130.0, 24)
    cheap.loc["2024-01-03"] = np.linspace(100.0, 80.0, 24)
    rich.loc["2024-01-04"] = 130.0
    cheap.loc["2024-01-04"] = 80.0
    close = pd.DataFrame(
        {
            "BTC-USDT-SWAP": btc,
            "ETH-USDT-SWAP": eth,
            "RICH-USDT-SWAP": rich.ffill(),
            "CHEAP-USDT-SWAP": cheap.ffill(),
        }
    )
    funding = pd.DataFrame(0.0, index=idx, columns=close.columns)
    membership_dates = pd.date_range("2024-01-01", periods=4, freq="D")
    membership = pd.DataFrame(
        [
            {"date": date, "symbol": symbol, "eligible": True, "adv_usd": 1.0, "listing_ts": membership_dates[0]}
            for date in membership_dates
            for symbol in close.columns
        ]
    )
    return close, funding, membership


def test_s5_residual_meanrev_strategy_stub_is_noop():
    from okx_quant.strategies.s5_residual_meanrev import S5ResidualMeanReversionStrategy

    assert asyncio.run(S5ResidualMeanReversionStrategy({}).on_market(None)) is None


def test_s5_residual_signal_is_reversion_and_not_same_day_close_leak():
    from backtesting.s5_residual_meanrev_backtest import run_s5_residual_meanrev_backtest
    from okx_quant.strategies.s5_residual_meanrev import S5ResidualMeanReversionParams

    close, funding, membership = _panels()
    params = S5ResidualMeanReversionParams(
        universe=list(close.columns),
        lookback_days=1,
        z_enter=0.5,
        z_exit=0.0,
        factors="BTC",
        top_n=4,
        rebalance="daily",
        fee_bps=0.0,
        slippage_bps=0.0,
    )

    result = run_s5_residual_meanrev_backtest(close, funding, membership, params)

    assert result.positions.loc["2024-01-03"].abs().sum(axis=1).max() == 0.0
    jan4 = result.positions.loc["2024-01-04"].iloc[1]
    assert jan4["RICH-USDT-SWAP"] < 0.0
    assert jan4["CHEAP-USDT-SWAP"] > 0.0


def test_scan_s5_records_family_cumulative_n_trials():
    from backtesting.s5_residual_meanrev_backtest import scan_s5_residual_meanrev
    from okx_quant.strategies.s5_residual_meanrev import S5ResidualMeanReversionParams

    close, funding, membership = _panels()
    result = scan_s5_residual_meanrev(
        close,
        funding,
        membership,
        S5ResidualMeanReversionParams(universe=list(close.columns), lookback_days=1),
        grid={"z_enter": [1.5, 2.0], "factors": ["BTC"]},
        prior_family_n_trials=70,
    )

    assert result.attrs["n_trials"] == 72
    assert set(result["n_trials"]) == {72}
