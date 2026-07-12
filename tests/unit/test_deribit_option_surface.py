from __future__ import annotations

from datetime import datetime, timezone

import pytest

from okx_quant.data.external_clients.deribit_option_surface import (
    DeribitOptionSurfaceClient,
    aggregate_option_surface,
)


def _option(name: str, oi: float, mark_iv: float, ts_ms: int = 1704067200000) -> dict:
    return {
        "instrument_name": name,
        "open_interest": oi,
        "mark_iv": mark_iv,
        "estimated_delivery_price": 105.0,
        "creation_timestamp": ts_ms,
    }


def test_option_surface_aggregate_math_and_snapshot_shape():
    row = aggregate_option_surface(
        "BTC",
        [
            _option("BTC-26JAN24-100-C", 10.0, 50.0),
            _option("BTC-26JAN24-100-P", 2.0, 60.0),
            _option("BTC-26JAN24-110-C", 1.0, 40.0),
            _option("BTC-26JAN24-110-P", 5.0, 70.0),
        ],
    )

    assert row["observed_at"] == datetime(2024, 1, 1, tzinfo=timezone.utc)
    assert row["published_at"] == datetime(2024, 1, 1, tzinfo=timezone.utc)
    assert row["value_num"] == 18.0
    assert row["fields"]["put_oi"] == 7.0
    assert row["fields"]["call_oi"] == 11.0
    assert row["fields"]["pc_oi_ratio"] == pytest.approx(7 / 11)
    assert row["fields"]["max_pain_strike"] == 100.0
    assert row["fields"]["oi_weighted_mark_iv"] == pytest.approx(1010 / 18)
    assert row["fields"]["spot_index"] == 105.0
    assert row["fields"]["n_instruments"] == 4
    assert row["fields"]["unit"] == "base_contracts"


def test_option_surface_raw_payload_is_top_20_by_open_interest(monkeypatch):
    client = DeribitOptionSurfaceClient()
    rows = [
        _option(f"BTC-26JAN24-{100 + i}-C", float(i), 50.0 + i)
        for i in range(25)
    ]
    monkeypatch.setattr(client, "_get", lambda params: {"result": rows})

    [snapshot] = client.fetch(currency="BTC")

    assert len(snapshot["raw_payload"]) == 20
    assert [item["open_interest"] for item in snapshot["raw_payload"][:3]] == [24.0, 23.0, 22.0]


def test_option_surface_all_missing_creation_timestamps_returns_none():
    row = aggregate_option_surface(
        "BTC",
        [
            _option("BTC-26JAN24-100-C", 10.0, 50.0, ts_ms=None),
            _option("BTC-26JAN24-100-P", 2.0, 60.0, ts_ms=None),
        ],
    )

    assert row is None
