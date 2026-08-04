from __future__ import annotations

import json
import pandas as pd
import pytest

from backtesting.intrabar_periodicity_probe import (
    ROUNDTRIP_COST,
    construct_boundary_events,
    preflight_slate_references,
)


def _row(ts: pd.Timestamp, imbalance: float, entry: float = 100.0, exit_price: float = 101.0) -> dict:
    volume = 10.0
    taker_buy = volume * (imbalance + 1.0) / 2.0
    raw = [0] * 11
    raw[9], raw[10] = str(taker_buy), "0"
    return {
        "ts": ts,
        "inst_id": "BTC-USDT-SWAP",
        "volume": volume,
        "raw_payload": {"raw": raw},
        "entry_open": entry,
        "exit_open": exit_price,
    }


def test_construct_boundary_events_uses_lagged_z_next_minute_price_and_event_cost():
    start = pd.Timestamp("2024-04-01T00:00:00Z")
    rows = [
        _row(
            start + pd.Timedelta(minutes=15 * i),
            (-1.0) ** i * 0.1,
            exit_price=100.0 + i,
        )
        for i in range(4)
    ]
    rows.append(_row(start + pd.Timedelta(minutes=60), 0.9))
    rows[-1]["raw_payload"] = json.dumps(rows[-1]["raw_payload"])

    events, coverage = construct_boundary_events(
        rows,
        lookback_boundaries=4,
        vol_window_boundaries=4,
        z_cut=1.5,
    )

    assert len(events) == 1
    assert 0.0 < events.iloc[0]["leverage"] <= 3.0
    assert events.iloc[0]["net"] == pytest.approx(events.iloc[0]["gross"] - ROUNDTRIP_COST)
    assert coverage["parseable_rows"] == 5
    assert coverage["formal_parseable_rows"] == 5


def test_i49_whole_slate_preflight_refuses_any_structural_shortfall():
    windows = {
        "H-030": ("2024-01-01", "2024-12-31"),
    }
    references = {
        "H-030": {"E-059/F-TAKER-FLOW": ("2024-12-01", "2024-12-31")},
    }

    with pytest.raises(ValueError, match="I49 whole-slate pre-flight contract stop"):
        preflight_slate_references(windows, references)


def test_default_whole_slate_preflight_passes_before_db_access():
    result = preflight_slate_references()

    assert result["status"] == "PASS"
    assert set(result["candidates"]) == {"H-030", "H-031", "H-032", "H-034", "H-035", "H-037"}
