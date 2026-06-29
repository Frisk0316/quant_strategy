import numpy as np
import pandas as pd


def _panels():
    idx = pd.date_range("2024-01-01", periods=4 * 24, freq="h")
    btc = pd.Series(100.0, index=idx)
    eth = pd.Series(100.0, index=idx)
    eth.loc["2024-01-03"] = np.linspace(100.0, 130.0, 24)
    eth.loc["2024-01-04"] = 130.0
    close = pd.DataFrame({"BTC-USDT-SWAP": btc, "ETH-USDT-SWAP": eth.ffill()})
    funding = pd.DataFrame(0.0, index=idx, columns=close.columns)
    return close, funding


def test_c1_pairs_ou_trades_next_day_not_same_day_close():
    from backtesting.c1_pairs_ou_backtest import C1PairsOUParams, run_c1_pairs_ou_backtest

    close, funding = _panels()
    params = C1PairsOUParams(
        lookback_days=1,
        z_enter=0.5,
        z_exit=0.0,
        max_half_life_days=float("inf"),
        fee_bps=0.0,
        slippage_bps=0.0,
    )

    result = run_c1_pairs_ou_backtest(close, funding, params)

    assert result.positions.loc["2024-01-03"].abs().sum(axis=1).max() == 0.0
    jan4 = result.positions.loc["2024-01-04"].iloc[1]
    assert jan4["ETH-USDT-SWAP"] < 0.0
    assert jan4["BTC-USDT-SWAP"] > 0.0


def test_scan_c1_records_family_cumulative_n_trials():
    from backtesting.c1_pairs_ou_backtest import C1PairsOUParams, scan_c1_pairs_ou

    close, funding = _panels()
    result = scan_c1_pairs_ou(
        close,
        funding,
        C1PairsOUParams(lookback_days=1),
        grid={"z_enter": [1.5, 2.0], "z_exit": [0.0]},
        prior_family_n_trials=22,
    )

    assert result.attrs["n_trials"] == 24
    assert set(result["n_trials"]) == {24}
