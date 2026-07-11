import numpy as np
import pandas as pd

from backtesting.oi_positioning_backtest import (
    OIPositioningParams,
    build_oi_positioning_target_weights,
    daily_contract_open_interest,
    run_oi_positioning_backtest,
    scan_oi_positioning,
    zero_oi_integrity_report,
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


def test_daily_contract_oi_uses_fields_contracts_and_filters_suspect_rows():
    idx = pd.date_range("2024-01-01", periods=2, freq="D")
    observations = pd.DataFrame(
        [
            {
                "dataset_id": "oi_binance_hist_btc",
                "observed_at": "2024-01-01T12:00:00Z",
                "value_num": 1_000_000.0,
                "fields": {"open_interest_contracts": 10.0},
                "quality_status": "ok",
            },
            {
                "dataset_id": "oi_binance_hist_btc",
                "observed_at": "2024-01-01T23:55:00Z",
                "value_num": 2_000_000.0,
                "fields": {"open_interest_contracts": 11.0},
                "quality_status": "ok",
            },
            {
                "dataset_id": "oi_binance_hist_btc",
                "observed_at": "2024-01-01T23:59:00Z",
                "value_num": 3_000_000.0,
                "fields": {"open_interest_contracts": 999.0},
                "quality_status": "suspect",
            },
            {
                "dataset_id": "oi_binance_hist_btc",
                "observed_at": "2024-01-02T23:55:00Z",
                "value_num": 4_000_000.0,
                "fields": {"open_interest_contracts": 8.0},
                "quality_status": "ok",
            },
        ]
    )

    oi = daily_contract_open_interest(observations, idx, ["BTC-USDT-SWAP"])

    assert oi.loc[idx[0], "BTC-USDT-SWAP"] == 11.0
    assert oi.loc[idx[1], "BTC-USDT-SWAP"] == 8.0


def test_missing_oi_day_carries_previous_target_without_forward_filling_oi_value():
    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    close = pd.DataFrame({"BTC-USDT-SWAP": [100.0, 100.0, 110.0, 111.0]}, index=idx)
    oi = pd.DataFrame({"BTC-USDT-SWAP": [100.0, 110.0, 80.0, np.nan]}, index=idx)
    params = OIPositioningParams(
        universe=["BTC-USDT-SWAP"],
        lookback_days=1,
        oi_norm_window_days=2,
        max_name_weight=1.0,
        vol_target_annual=1.0,
        fee_bps=0.0,
        slippage_bps=0.0,
    )

    target = build_oi_positioning_target_weights(close, oi, _membership(idx, close.columns), params)

    assert oi.loc[idx[3], "BTC-USDT-SWAP"] != oi.loc[idx[2], "BTC-USDT-SWAP"]
    assert target.loc[idx[2], "BTC-USDT-SWAP"] < 0.0
    assert target.loc[idx[3], "BTC-USDT-SWAP"] == target.loc[idx[2], "BTC-USDT-SWAP"]


def test_oi_signal_target_is_not_traded_on_same_day():
    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    close = pd.DataFrame({"BTC-USDT-SWAP": [100.0, 100.0, 110.0, 111.0]}, index=idx)
    funding = pd.DataFrame(0.0, index=idx, columns=close.columns)
    oi = pd.DataFrame({"BTC-USDT-SWAP": [100.0, 110.0, 80.0, 80.0]}, index=idx)
    params = OIPositioningParams(
        universe=["BTC-USDT-SWAP"],
        lookback_days=1,
        oi_norm_window_days=2,
        max_name_weight=1.0,
        vol_target_annual=1.0,
        fee_bps=0.0,
        slippage_bps=0.0,
    )

    result = run_oi_positioning_backtest(close, close, close, close, funding, oi, _membership(idx, close.columns), params)

    assert result.target_weights.loc[idx[2], "BTC-USDT-SWAP"] < 0.0
    assert result.positions.loc[idx[2], "BTC-USDT-SWAP"] == 0.0
    assert result.positions.loc[idx[3], "BTC-USDT-SWAP"] < 0.0


def test_zero_oi_integrity_report_flags_symbols_over_threshold():
    idx = pd.date_range("2024-01-01", periods=10, freq="D")
    oi = pd.DataFrame(
        {
            "GOOD-USDT-SWAP": [10.0] * 10,
            "BAD-USDT-SWAP": [0.0] + [10.0] * 9,
        },
        index=idx,
    )

    report = zero_oi_integrity_report(oi, _membership(idx, oi.columns), max_zero_ratio=0.05)

    assert report["excluded_symbols"] == ["BAD-USDT-SWAP"]
    assert report["symbols"]["BAD-USDT-SWAP"]["zero_ratio"] == 0.1


def test_scan_oi_positioning_accepts_caller_declared_researched_n_trials():
    idx = pd.date_range("2024-01-01", periods=6, freq="D")
    close = pd.DataFrame({"BTC-USDT-SWAP": [100.0, 100.0, 110.0, 111.0, 109.0, 108.0]}, index=idx)
    funding = pd.DataFrame(0.0, index=idx, columns=close.columns)
    oi = pd.DataFrame({"BTC-USDT-SWAP": [100.0, 110.0, 80.0, 79.0, 82.0, 81.0]}, index=idx)
    params = OIPositioningParams(
        universe=["BTC-USDT-SWAP"],
        oi_norm_window_days=2,
        max_name_weight=1.0,
    )

    result = scan_oi_positioning(
        close,
        close,
        close,
        close,
        funding,
        oi,
        _membership(idx, close.columns),
        params,
        grid={"lookback_days": [1, 2], "z_min": [0.0, 0.5]},
        researched_n_trials=4,
    )

    assert result.attrs["n_trials"] == 4
    assert set(result["n_trials"]) == {4}
    assert set(result["n_trials_provenance"]) == {"caller_declared"}
