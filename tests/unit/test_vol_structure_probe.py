import numpy as np
import pandas as pd
import pytest

from backtesting.vol_structure_probe import (
    build_positive_jump_book,
    build_vov_signals,
    membership_frame,
    positive_jump_variance,
    probe_vol_of_vol,
)


def test_vov_first_cell_uses_hourly_dvol_and_emits_daily_signal():
    index = pd.date_range("2024-01-01", periods=240, freq="h", tz="UTC")
    dvol = pd.DataFrame(
        {
            "BTC-USDT-SWAP": 50 + np.sin(np.arange(240) / 5),
            "ETH-USDT-SWAP": 60 + np.cos(np.arange(240) / 7),
        },
        index=index,
    )

    signals, valid = build_vov_signals(dvol, window_days=2, z_cut=1.0)

    assert set(signals.columns) == {"BTC-USDT-SWAP", "ETH-USDT-SWAP"}
    assert all(signals.index.hour == 8)
    assert valid.any()


def test_positive_jump_feature_and_weekly_low_minus_high_book():
    assert positive_jump_variance(pd.Series([-0.01, -0.01, 0.03])) > 0.0
    dates = pd.date_range("2024-01-01", periods=45, freq="D", tz="UTC")
    symbols = ["A-USDT-SWAP", "B-USDT-SWAP", "C-USDT-SWAP", "D-USDT-SWAP"]
    jumps = pd.DataFrame(
        {symbol: np.linspace(i, i + 1, len(dates)) for i, symbol in enumerate(symbols)},
        index=dates,
    )
    closes = pd.DataFrame(
        {symbol: np.linspace(100 + i, 110 + i, len(dates)) for i, symbol in enumerate(symbols)},
        index=dates,
    )
    membership = {day.date().isoformat(): symbols for day in dates}

    result = build_positive_jump_book(jumps, closes, membership, lookback_days=2, quantile=0.25)

    assert {"gross", "net", "cost", "weights"} == set(result)
    assert result["weights"].abs().sum(axis=1).max() > 0.0
    assert (result["cost"] >= 0.0).all()
    assert str(membership_frame(membership)["date"].dt.tz) == "UTC"


@pytest.mark.asyncio
async def test_vol_probe_refuses_db_without_whole_slate_i49():
    class ForbiddenConnection:
        async def fetch(self, *_args):
            raise AssertionError("DB accessed")

    with pytest.raises(ValueError, match="I49"):
        await probe_vol_of_vol(ForbiddenConnection(), {})
