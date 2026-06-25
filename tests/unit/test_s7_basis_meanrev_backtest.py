import asyncio

import numpy as np
import pandas as pd


def _panels():
    idx = pd.date_range("2024-01-01", periods=4 * 24, freq="h")
    spot = pd.Series(100.0, index=idx)
    perp = pd.Series(100.0, index=idx)
    perp.loc["2024-01-03"] = np.linspace(100.0, 120.0, 24)
    perp.loc["2024-01-04"] = 120.0
    perp_close = pd.DataFrame({"BTC-USDT-SWAP": perp.ffill()})
    spot_close = pd.DataFrame({"BTC-USDT": spot})
    funding = pd.DataFrame(0.0, index=idx, columns=perp_close.columns)
    return perp_close, spot_close, funding


def test_s7_basis_meanrev_strategy_stub_is_noop():
    from okx_quant.strategies.s7_basis_meanrev import S7BasisMeanReversionStrategy

    assert asyncio.run(S7BasisMeanReversionStrategy({}).on_market(None)) is None


def test_s7_rich_basis_shorts_perp_longs_spot_next_day():
    from backtesting.s7_basis_meanrev_backtest import run_s7_basis_meanrev_backtest
    from okx_quant.strategies.s7_basis_meanrev import S7BasisMeanReversionParams

    perp_close, spot_close, funding = _panels()
    params = S7BasisMeanReversionParams(
        pairs={"BTC-USDT-SWAP": "BTC-USDT"},
        lookback_days=1,
        z_enter=0.5,
        z_exit=0.0,
        max_half_life_days=float("inf"),
        max_hold_days=7,
        fee_bps=0.0,
        slippage_bps=0.0,
    )

    result = run_s7_basis_meanrev_backtest(perp_close, spot_close, funding, params)

    assert result.positions.loc["2024-01-03"].abs().sum(axis=1).max() == 0.0
    jan4 = result.positions.loc["2024-01-04"].iloc[1]
    assert jan4["BTC-USDT-SWAP"] < 0.0
    assert jan4["BTC-USDT"] > 0.0


def test_scan_s7_records_family_cumulative_n_trials():
    from backtesting.s7_basis_meanrev_backtest import scan_s7_basis_meanrev
    from okx_quant.strategies.s7_basis_meanrev import S7BasisMeanReversionParams

    perp_close, spot_close, funding = _panels()
    result = scan_s7_basis_meanrev(
        perp_close,
        spot_close,
        funding,
        S7BasisMeanReversionParams(pairs={"BTC-USDT-SWAP": "BTC-USDT"}, lookback_days=1),
        grid={"z_enter": [1.5, 2.0], "max_hold_days": [7]},
        prior_family_n_trials=70,
    )

    assert result.attrs["n_trials"] == 72
    assert set(result["n_trials"]) == {72}
