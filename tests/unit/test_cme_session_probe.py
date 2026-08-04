import pandas as pd
import pytest

from backtesting.cme_session_probe import (
    DAILY_LIMITATION,
    build_cme_session_events,
    probe_cme_leadership,
)


def test_cme_daily_first_cell_is_lag_safe_and_costed():
    dates = pd.date_range("2024-01-01", periods=40, freq="D", tz="UTC")
    cme = pd.Series([100 + i + (3 if i % 5 == 0 else 0) for i in range(40)], index=dates)
    btc = pd.Series([200 + 2 * i for i in range(40)], index=dates)

    result = build_cme_session_events(cme, btc, x_cut_sigma=0.5)

    assert not result.empty
    assert (result["cost"] == 0.0008).all()
    assert "daily-only" in DAILY_LIMITATION


@pytest.mark.asyncio
async def test_cme_probe_refuses_db_without_whole_slate_i49():
    class ForbiddenConnection:
        async def fetch(self, *_args):
            raise AssertionError("DB accessed")

    with pytest.raises(ValueError, match="I49"):
        await probe_cme_leadership(ForbiddenConnection(), {})
