import pandas as pd
import pytest

from backtesting.macro_state_probe import (
    build_fomc_event_returns,
    build_macro_state_book,
    load_fomc_dates,
    probe_macro_event_drift,
)


def test_fomc_fixture_and_first_cell_construct_two_costed_legs():
    dates = pd.date_range("2024-01-01", periods=8, freq="D", tz="UTC")
    btc = pd.Series([100, 101, 102, 104, 103, 106, 107, 108], index=dates)
    yields = pd.Series([4.0, 4.0, 4.0, 4.1, 4.1, 4.1, 4.1, 4.1], index=dates)

    result = build_fomc_event_returns(btc, yields, ["2024-01-04"])

    assert list(result["leg"]) == ["pre", "post"]
    assert result["cost"].tolist() == [0.0008, 0.0008]
    assert result.loc[1, "gross"] == pytest.approx(-(106 / 104 - 1))
    assert len(load_fomc_dates()) == 55


def test_macro_state_first_cell_is_lagged_and_costs_position_changes():
    dates = pd.date_range("2024-01-01", periods=70, freq="D", tz="UTC")
    closes = pd.DataFrame(
        {"BTC-USDT-SWAP": range(100, 170), "ETH-USDT-SWAP": range(200, 270)},
        index=dates,
    )
    vix = pd.Series(range(70), index=dates)
    dollar = pd.Series(range(70), index=dates)

    result = build_macro_state_book(closes, vix, dollar, window_days=5, z_cut=1.0)

    assert result["position"].iloc[0] == 0.0
    assert (result["cost"] >= 0.0).all()
    assert set(result["position"].unique()).issubset({0.0, 1.0})


@pytest.mark.asyncio
async def test_macro_probe_refuses_db_without_whole_slate_i49():
    class ForbiddenConnection:
        async def fetch(self, *_args):
            raise AssertionError("DB accessed")

    with pytest.raises(ValueError, match="I49"):
        await probe_macro_event_drift(ForbiddenConnection(), {})
