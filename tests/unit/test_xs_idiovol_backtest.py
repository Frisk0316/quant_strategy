import numpy as np
import pandas as pd

from backtesting.xs_idiovol_backtest import (
    XSIdioVolParams,
    _xs_params,
    residual_volatility,
    run_xs_idiovol_backtest,
    scan_xs_idiovol,
)


def _panels():
    days = pd.date_range("2024-01-01", periods=15, freq="D")
    btc_returns = np.array(
        [0.0, 0.01, -0.015, 0.02, -0.005, 0.012, -0.018, 0.008, 0.015, -0.01, 0.006, -0.012, 0.018, -0.007, 0.011]
    )
    patterns = np.array([0.0, 1.0, -1.0, 0.5, -0.5, 1.5, -1.5, 0.75, -0.75, 1.25, -1.25, 0.25, -0.25, 1.0, -1.0])
    daily = pd.DataFrame(
        {
            "BTC-USDT-SWAP": 100.0 * np.cumprod(1.0 + btc_returns),
            "EXCLUDED": 100.0 * np.cumprod(1.0 + btc_returns),
            "LOW1": 100.0 * np.cumprod(1.0 + 0.8 * btc_returns + 0.001 * patterns),
            "LOW2": 100.0 * np.cumprod(1.0 + 1.2 * btc_returns + 0.003 * patterns[::-1]),
            "HIGH1": 100.0 * np.cumprod(1.0 + 0.5 * btc_returns + 0.02 * patterns),
            "HIGH2": 100.0 * np.cumprod(1.0 + 1.5 * btc_returns + 0.04 * patterns[::-1]),
        },
        index=days,
    )
    hours = pd.date_range(days[0], periods=len(days) * 24, freq="h")
    close = daily.reindex(hours.normalize()).set_axis(hours)
    funding = pd.DataFrame(0.0, index=hours, columns=close.columns)
    membership = pd.DataFrame(
        [
            {
                "date": day,
                "symbol": symbol,
                "eligible": symbol != "EXCLUDED",
                "adv_usd": 1.0,
                "listing_ts": days[0],
            }
            for day in days
            for symbol in close.columns
        ]
    )
    return daily, close, funding, membership


def test_low_idiovol_book_uses_same_day_btc_pit_and_t_plus_one_execution():
    daily, close, funding, membership = _panels()
    params = XSIdioVolParams(
        universe=list(close.columns),
        bar="1H",
        lookback_days=5,
        quantile=0.5,
        vol_window_days=5,
    )

    scores = residual_volatility(
        daily,
        params.lookback_days,
        market_close=daily["BTC-USDT-SWAP"],
    )
    result = run_xs_idiovol_backtest(
        close,
        funding,
        membership,
        params,
        market_close=close["BTC-USDT-SWAP"],
    )

    assert "BTC-USDT-SWAP" not in scores
    assert scores.loc["2024-01-08", "EXCLUDED"] < 1e-12
    assert scores.loc["2024-01-08", "LOW1"] < scores.loc["2024-01-08", "HIGH1"]
    assert pd.isna(
        residual_volatility(
            daily.assign(**{"BTC-USDT-SWAP": 100.0}),
            params.lookback_days,
        ).loc["2024-01-08", "LOW1"]
    )
    assert _xs_params(params).inverse_vol is False

    # Monday's closed-bar score is executable Tuesday, then held from the next bar.
    assert result.target_weights.loc["2024-01-08"].abs().sum() == 0.0
    target = result.target_weights.loc["2024-01-09"]
    assert target["LOW1"] > 0.0
    assert target["LOW2"] > 0.0
    assert target["HIGH1"] < 0.0
    assert target["HIGH2"] < 0.0
    assert target["BTC-USDT-SWAP"] == 0.0
    assert target["EXCLUDED"] == 0.0
    assert abs(target.sum()) < 1e-12
    assert result.positions.loc["2024-01-09 00:00"].abs().sum() == 0.0
    assert result.positions.loc["2024-01-09 01:00"].abs().sum() > 0.0


def test_scan_xs_idiovol_records_the_four_cell_trial_floor():
    _, close, funding, membership = _panels()

    result = scan_xs_idiovol(
        close,
        funding,
        membership,
        XSIdioVolParams(universe=list(close.columns), bar="1H", vol_window_days=5),
        grid={"lookback_days": [14, 28], "quantile": [0.2, 0.3]},
    )

    assert len(result) == 4
    assert result.attrs["n_trials"] == 4
    assert set(result["n_trials"]) == {4}
