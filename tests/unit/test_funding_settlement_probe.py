from __future__ import annotations

import pandas as pd
import pytest

from backtesting.funding_settlement_probe import ROUNDTRIP_COST, construct_event_returns


def test_event_construction_uses_next_minute_exit_hold_cost_and_z_eligibility():
    start = pd.Timestamp("2024-01-01T00:00:00Z")
    funding = [
        {"inst_id": "BTC-USDT-SWAP", "ts": start + pd.Timedelta(hours=8 * i), "rate": (-1) ** i * 0.001}
        for i in range(4)
    ]
    event_ts = start + pd.Timedelta(hours=32, milliseconds=2)
    settlement_minute = event_ts.floor("min")
    funding.append({"inst_id": "BTC-USDT-SWAP", "ts": event_ts, "rate": 0.02})
    bars = {
        ("BTC-USDT-SWAP", settlement_minute + pd.Timedelta(minutes=1)): 100.0,
        ("BTC-USDT-SWAP", settlement_minute + pd.Timedelta(minutes=121)): 99.0,
        # A settlement-time bar must not be used as entry.
        ("BTC-USDT-SWAP", settlement_minute): 50.0,
    }

    result = construct_event_returns(funding, bars, lookback=4, z_cut=1.5, hold_hours=2)

    assert list(result.index) == [settlement_minute]
    assert result.iloc[0]["gross"] == pytest.approx(0.01)
    assert result.iloc[0]["cost"] == pytest.approx(ROUNDTRIP_COST)
    assert result.iloc[0]["net"] == pytest.approx(0.01 - ROUNDTRIP_COST)
    assert result.iloc[0]["active_symbols"] == 1
