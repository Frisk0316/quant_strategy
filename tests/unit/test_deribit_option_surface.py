from __future__ import annotations

from datetime import datetime, timezone

import pytest

from okx_quant.data.external_clients.deribit_option_surface import (
    DeribitOptionSurfaceClient,
    aggregate_option_surface,
)
from okx_quant.data.external_clients.deribit_option_surface import moneyness_bucket


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


def test_option_surface_raw_payload_preserves_full_sorted_chain(monkeypatch):
    client = DeribitOptionSurfaceClient()
    rows = [
        _option(f"BTC-26JAN24-{100 + i}-C", float(i), 50.0 + i)
        for i in range(25)
    ]
    monkeypatch.setattr(client, "_get", lambda params: {"result": rows})

    [snapshot] = client.fetch(currency="BTC")

    assert len(snapshot["raw_payload"]) == 25
    assert [item["strike"] for item in snapshot["raw_payload"][:3]] == [100.0, 101.0, 102.0]
    assert snapshot["raw_payload"][0]["expiry"] == "2024-01-26"
    assert snapshot["raw_payload"][0]["option_type"] == "call"
    assert snapshot["fields"]["raw_payload_scope"] == "full_current_chain"


def test_option_surface_all_missing_creation_timestamps_returns_none():
    row = aggregate_option_surface(
        "BTC",
        [
            _option("BTC-26JAN24-100-C", 10.0, 50.0, ts_ms=None),
            _option("BTC-26JAN24-100-P", 2.0, 60.0, ts_ms=None),
        ],
    )

    assert row is None


def test_moneyness_bucket_classification():
    spot = 100_000.0
    # ATM band is +/-2.5% of spot
    assert moneyness_bucket("C", 100_000.0, spot) == "atm"
    assert moneyness_bucket("P", 102_500.0, spot) == "atm"   # exactly on band edge
    assert moneyness_bucket("C", 97_500.0, spot) == "atm"
    # Calls: strike below spot is ITM, above is OTM
    assert moneyness_bucket("C", 90_000.0, spot) == "itm"
    assert moneyness_bucket("C", 120_000.0, spot) == "otm"
    # Puts: mirrored
    assert moneyness_bucket("P", 120_000.0, spot) == "itm"
    assert moneyness_bucket("P", 90_000.0, spot) == "otm"


def test_moneyness_bucket_unclassifiable_inputs():
    assert moneyness_bucket("C", None, 100.0) is None
    assert moneyness_bucket("C", 100.0, None) is None
    assert moneyness_bucket("C", 100.0, 0.0) is None
    assert moneyness_bucket("X", 100.0, 100.0) is None


def test_option_surface_moneyness_bucket_fields(monkeypatch):
    client = DeribitOptionSurfaceClient()
    spot = 100_000.0
    chain = [
        # name, oi, iv  -> bucket for spot 100k
        ("BTC-26DEC26-100000-C", 10.0, 50.0),  # atm call
        ("BTC-26DEC26-80000-C", 5.0, 60.0),    # itm call
        ("BTC-26DEC26-120000-C", 2.0, 70.0),   # otm call
        ("BTC-26DEC26-120000-P", 4.0, 55.0),   # itm put
        ("BTC-26DEC26-80000-P", 8.0, 80.0),    # otm put
    ]
    rows = [
        {
            "instrument_name": name,
            "open_interest": oi,
            "mark_iv": iv,
            "estimated_delivery_price": spot,
            "creation_timestamp": 1_700_000_000_000,
        }
        for name, oi, iv in chain
    ]
    monkeypatch.setattr(client, "_get", lambda params: {"result": rows})
    fields = client.fetch(currency="BTC")[0]["fields"]

    assert fields["moneyness_atm_band"] == 0.025
    assert fields["atm_call_oi"] == 10.0
    assert fields["itm_call_oi"] == 5.0
    assert fields["otm_call_oi"] == 2.0
    assert fields["atm_put_oi"] == 0.0
    assert fields["itm_put_oi"] == 4.0
    assert fields["otm_put_oi"] == 8.0
    assert fields["atm_mark_iv"] == 50.0            # single atm instrument
    assert fields["otm_put_mark_iv"] == 80.0
    assert fields["otm_call_mark_iv"] == 70.0
    assert fields["otm_skew_mark_iv"] == 80.0 - 70.0
