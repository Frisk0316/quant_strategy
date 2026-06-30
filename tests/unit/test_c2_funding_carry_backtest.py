import numpy as np
import pandas as pd


def _panels():
    idx = pd.date_range("2024-01-01", periods=4 * 24, freq="h")
    spot = pd.Series(100.0, index=idx)
    perp = pd.Series(100.0, index=idx)
    perp.loc["2024-01-03"] = np.linspace(100.0, 101.0, 24)
    perp.loc["2024-01-04"] = 101.0
    perp_close = pd.DataFrame({"BTC-USDT-SWAP": perp.ffill()})
    spot_close = pd.DataFrame({"BTC-USDT": spot})
    funding = pd.DataFrame(0.0, index=idx, columns=perp_close.columns)
    funding.loc["2024-01-03":] = 0.001
    return perp_close, spot_close, funding


def test_c2_funding_carry_trades_next_day_not_same_day_funding_signal():
    from backtesting.c2_funding_carry_backtest import C2FundingCarryParams, run_c2_funding_carry_backtest

    perp_close, spot_close, funding = _panels()
    params = C2FundingCarryParams(
        pairs={"BTC-USDT-SWAP": "BTC-USDT"},
        funding_enter_apr=0.05,
        exit_funding_apr=0.0,
        basis_z_max=5.0,
        fee_bps=0.0,
        slippage_bps=0.0,
        rebalance="daily",
    )

    result = run_c2_funding_carry_backtest(perp_close, spot_close, funding, params)

    assert result.positions.loc["2024-01-03"].abs().sum(axis=1).max() == 0.0
    jan4 = result.positions.loc["2024-01-04"].iloc[1]
    assert jan4["BTC-USDT-SWAP"] < 0.0
    assert jan4["BTC-USDT"] > 0.0


def test_scan_c2_records_family_cumulative_n_trials():
    from backtesting.c2_funding_carry_backtest import C2FundingCarryParams, scan_c2_funding_carry

    perp_close, spot_close, funding = _panels()
    result = scan_c2_funding_carry(
        perp_close,
        spot_close,
        funding,
        C2FundingCarryParams(pairs={"BTC-USDT-SWAP": "BTC-USDT"}),
        grid={"funding_enter_apr": [0.05, 0.10], "rebalance": ["daily"]},
        prior_family_n_trials=22,
    )

    assert result.attrs["n_trials"] == 24
    assert set(result["n_trials"]) == {24}


def test_c2_realistic_costs_are_applied_to_two_leg_turnover_and_vol():
    from backtesting.c2_funding_carry_backtest import C2FundingCarryParams, run_c2_funding_carry_backtest

    perp_close, spot_close, funding = _panels()
    base = C2FundingCarryParams(
        pairs={"BTC-USDT-SWAP": "BTC-USDT"},
        bar="1H",
        funding_enter_apr=0.05,
        basis_z_max=5.0,
        fee_bps=0.0,
        slippage_bps=0.0,
    )
    idealized = run_c2_funding_carry_backtest(perp_close, spot_close, funding, base)
    realistic = run_c2_funding_carry_backtest(
        perp_close,
        spot_close,
        funding,
        C2FundingCarryParams(
            pairs={"BTC-USDT-SWAP": "BTC-USDT"},
            bar="1H",
            funding_enter_apr=0.05,
            basis_z_max=5.0,
            fee_bps=2.0,
            slippage_bps=3.0,
            basis_execution_slippage_bps=2.0,
            carry_cost_bps=1.0,
        ),
    )

    assert realistic.metrics["total_return"] < idealized.metrics["total_return"]
    assert realistic.metrics["two_leg_rebalance_slippage_cost"] > 0.0
    assert realistic.metrics["basis_execution_slippage_cost"] > 0.0
    assert realistic.metrics["carry_cost"] > 0.0
    assert realistic.metrics["realized_annualized_volatility"] > 0.0027


def test_c2_short_perp_pays_when_funding_flips_negative_while_held():
    from backtesting.c2_funding_carry_backtest import C2FundingCarryParams, run_c2_funding_carry_backtest

    perp_close, spot_close, funding = _panels()
    funding.loc["2024-01-04":] = -0.01
    result = run_c2_funding_carry_backtest(
        perp_close,
        spot_close,
        funding,
        C2FundingCarryParams(
            pairs={"BTC-USDT-SWAP": "BTC-USDT"},
            bar="1H",
            funding_enter_apr=0.05,
            exit_funding_apr=-1.0,
            basis_z_max=5.0,
            fee_bps=0.0,
            slippage_bps=0.0,
        ),
    )

    assert result.positions.loc["2024-01-04", "BTC-USDT-SWAP"].min() < 0.0
    assert result.metrics["funding_cashflow"] < 0.0
    assert result.metrics["stress_evaluation"]["stress_day_count"] > 0
    assert result.metrics["stress_evaluation"]["mid_flip_active_days"] > 0
