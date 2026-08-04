from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from okx_quant.data.external_clients.xvenue_options_iv import (
    CrossVenueOptionsIVClient,
    aggregate_options_iv,
)
from scripts.market_data import snapshot_xvenue_options


SNAPSHOT = datetime(2026, 1, 1, 8, tzinfo=timezone.utc)
SNAPSHOT_MS = int(SNAPSHOT.timestamp() * 1000)


def _leg(
    instrument: str,
    expiry: datetime,
    option_type: str,
    strike: float,
    delta: float,
    mark_iv: float,
) -> dict:
    return {
        "instrument": instrument,
        "expiry": expiry,
        "option_type": option_type,
        "strike": strike,
        "delta": delta,
        "mark_iv": mark_iv,
        "bid_iv": mark_iv - 0.01,
        "ask_iv": mark_iv + 0.01,
        "open_interest": 1.0,
        "underlying_price": 100.0,
        "source": {"instrument": instrument},
    }


def _expiry_chain(expiry: datetime, atm_iv: float, call25_iv: float, put25_iv: float):
    suffix = expiry.strftime("%d%b%y").upper()
    return [
        _leg(f"BTC-{suffix}-100-C", expiry, "call", 100, 0.50, atm_iv),
        _leg(f"BTC-{suffix}-100-P", expiry, "put", 100, -0.50, atm_iv),
        _leg(f"BTC-{suffix}-110-C", expiry, "call", 110, 0.25, call25_iv),
        _leg(f"BTC-{suffix}-90-P", expiry, "put", 90, -0.25, put25_iv),
    ]


def test_total_variance_interpolation_rr_sign_and_full_chain():
    lower = SNAPSHOT + timedelta(days=20)
    upper = SNAPSHOT + timedelta(days=40)
    options = [
        *_expiry_chain(lower, 0.40, 0.50, 0.40),
        *_expiry_chain(upper, 0.60, 0.70, 0.50),
    ]

    row = aggregate_options_iv(
        "test",
        "BTC",
        options,
        SNAPSHOT,
        oi_unit="contracts",
    )

    expected_atm = ((0.40**2 * 20 + 0.60**2 * 40) / 2 / 30) ** 0.5
    expected_call = ((0.50**2 * 20 + 0.70**2 * 40) / 2 / 30) ** 0.5
    expected_put = ((0.40**2 * 20 + 0.50**2 * 40) / 2 / 30) ** 0.5
    assert row["value_num"] == pytest.approx(expected_atm)
    assert row["fields"]["atm_iv_30d"] == pytest.approx(expected_atm)
    assert row["fields"]["rr_25d"] == pytest.approx(expected_call - expected_put)
    assert row["fields"]["rr_25d"] > 0
    assert row["fields"]["interp"] == "total_variance"
    assert row["published_at"] == SNAPSHOT + timedelta(hours=1)
    assert row["raw_payload"]["scope"] == "full_current_chain"
    assert len(row["raw_payload"]["instruments"]) == len(options)


def test_nearest_expiry_fallback():
    expiry = SNAPSHOT + timedelta(days=45)

    row = aggregate_options_iv(
        "test",
        "ETH",
        _expiry_chain(expiry, 0.50, 0.55, 0.60),
        SNAPSHOT,
        oi_unit="contracts",
    )

    assert row["value_num"] == pytest.approx(0.50)
    assert row["fields"]["rr_25d"] == pytest.approx(-0.05)
    assert row["fields"]["interp"] == "nearest"
    assert row["fields"]["expiry_lower"] == row["fields"]["expiry_upper"]


def test_okx_fetch_merges_open_interest_and_keeps_full_chain(monkeypatch):
    client = CrossVenueOptionsIVClient(now=lambda: SNAPSHOT)
    expiry = "260131"
    summary = [
        (f"BTC-USD-{expiry}-110-C", "0.25", "0.55", "100"),
        (f"BTC-USD-{expiry}-90-P", "-0.25", "0.60", "100"),
        (f"BTC-USD-{expiry}-100-C", "0.50", "0.50", "100"),
        (f"BTC-USD-{expiry}-100-P", "-0.50", "0.52", "100"),
    ]

    def fake_get(url, params):
        if url == client.OKX_SUMMARY:
            return {
                "code": "0",
                "data": [
                    {
                        "instId": instrument,
                        "deltaBS": delta,
                        "markVol": iv,
                        "bidVol": str(float(iv) - 0.01),
                        "askVol": str(float(iv) + 0.01),
                        "fwdPx": forward,
                        "ts": str(SNAPSHOT_MS),
                    }
                    for instrument, delta, iv, forward in summary
                ],
            }
        return {
            "code": "0",
            "data": [
                {
                    "instId": instrument,
                    "oi": "2",
                    "oiUsd": "100",
                    "ts": str(SNAPSHOT_MS),
                }
                for instrument, _, _, _ in summary
            ],
        }

    monkeypatch.setattr(client, "_get", fake_get)
    [row] = client.fetch(venue="okx", currency="BTC")

    assert row["fields"]["oi_total"] == 8
    assert row["fields"]["oi_total_usd"] == 400
    assert len(row["raw_payload"]["instruments"]) == 4


def test_bybit_settlement_suffix_is_parsed(monkeypatch):
    client = CrossVenueOptionsIVClient(now=lambda: SNAPSHOT)
    rows = [
        ("BTC-31JAN26-110-C-USDT", "0.25", "0.55"),
        ("BTC-31JAN26-90-P-USDT", "-0.25", "0.60"),
        ("BTC-31JAN26-100-C-USDT", "0.50", "0.50"),
        ("BTC-31JAN26-100-P-USDT", "-0.50", "0.52"),
    ]
    monkeypatch.setattr(
        client,
        "_get",
        lambda url, params: {
            "retCode": 0,
            "time": SNAPSHOT_MS,
            "result": {
                "list": [
                    {
                        "symbol": instrument,
                        "delta": delta,
                        "markIv": iv,
                        "bid1Iv": str(float(iv) - 0.01),
                        "ask1Iv": str(float(iv) + 0.01),
                        "openInterest": "3",
                        "underlyingPrice": "100",
                    }
                    for instrument, delta, iv in rows
                ]
            },
        },
    )

    [row] = client.fetch(venue="bybit", currency="BTC")

    assert row["fields"]["atm_iv_30d"] == pytest.approx(0.51)
    assert row["fields"]["oi_total"] == 12


def test_deribit_percent_iv_is_normalized(monkeypatch):
    client = CrossVenueOptionsIVClient(now=lambda: SNAPSHOT)
    summary = [
        ("BTC-31JAN26-110-C", 55),
        ("BTC-31JAN26-90-P", 60),
        ("BTC-31JAN26-100-C", 50),
        ("BTC-31JAN26-100-P", 52),
    ]
    exact = {
        "BTC-31JAN26-110-C": (0.25, 55),
        "BTC-31JAN26-90-P": (-0.25, 60),
        "BTC-31JAN26-100-C": (0.50, 50),
        "BTC-31JAN26-100-P": (-0.50, 52),
    }

    def fake_get(url, params):
        if url == client.DERIBIT_SUMMARY:
            return {
                "result": [
                    {
                        "instrument_name": instrument,
                        "mark_iv": iv,
                        "underlying_price": 100,
                        "interest_rate": 0,
                        "open_interest": 1,
                        "creation_timestamp": SNAPSHOT_MS,
                    }
                    for instrument, iv in summary
                ]
            }
        delta, iv = exact[params["instrument_name"]]
        return {
            "result": {
                "instrument_name": params["instrument_name"],
                "timestamp": SNAPSHOT_MS,
                "mark_iv": iv,
                "bid_iv": iv - 1,
                "ask_iv": iv + 1,
                "open_interest": 1,
                "greeks": {"delta": delta},
            }
        }

    monkeypatch.setattr(client, "_get", fake_get)
    [row] = client.fetch(venue="deribit", currency="BTC")

    assert row["fields"]["atm_iv_30d"] == pytest.approx(0.51)
    assert row["fields"]["rr_25d"] == pytest.approx(-0.05)
    assert row["fields"]["atm_top_of_book_iv_spread"] == pytest.approx(0.02)


def test_snapshot_continues_after_one_venue_failure(monkeypatch):
    attempted = []

    class FakeStore:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def summarize_observations(self, dataset_id):
            return {"last_observed_at": None}

    async def fake_from_dsn(*args, **kwargs):
        return FakeStore()

    async def fake_ingest(store, dataset_id, cfg, start, end, dry_run):
        attempted.append(dataset_id)
        if dataset_id == "bad":
            raise RuntimeError("venue down")

    monkeypatch.setattr(
        snapshot_xvenue_options,
        "_load_external_config",
        lambda path: {"bad": {}, "good": {}},
    )
    monkeypatch.setattr(
        snapshot_xvenue_options,
        "load_config",
        lambda **kwargs: SimpleNamespace(
            storage=SimpleNamespace(timescale_dsn="postgresql://unused")
        ),
    )
    monkeypatch.setattr(
        snapshot_xvenue_options.ExternalDataStore,
        "from_dsn",
        fake_from_dsn,
    )
    monkeypatch.setattr(snapshot_xvenue_options, "_ingest_one", fake_ingest)
    args = argparse.Namespace(
        dataset=["bad", "good"],
        config="unused",
        settings="unused",
        max_gap_hours=1.5,
    )

    with pytest.raises(SystemExit, match="snapshot failures"):
        asyncio.run(snapshot_xvenue_options._snapshot(args))

    assert attempted == ["bad", "good"]
