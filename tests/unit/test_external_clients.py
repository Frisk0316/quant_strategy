from __future__ import annotations

from datetime import datetime, timezone

import click
import pytest

from okx_quant.data.external_clients import BinanceOIClient, DeribitDVOLClient
from scripts.market_data import ingest_external


def test_binance_oi_client_normalizes_notional_and_filters_window(monkeypatch):
    client = BinanceOIClient()
    seen = {}

    def fake_get(params):
        seen.update(params)
        return [
            {
                "symbol": "BTCUSDT",
                "sumOpenInterest": "100.5",
                "sumOpenInterestValue": "1234567.89",
                "timestamp": 1704070800000,
            },
            {
                "symbol": "BTCUSDT",
                "sumOpenInterest": "101.5",
                "sumOpenInterestValue": "2234567.89",
                "timestamp": 1704078000000,
            },
        ]

    monkeypatch.setattr(client, "_get", fake_get)

    rows = client.fetch(
        symbol="BTCUSDT",
        interval="1h",
        start=datetime(2024, 1, 1, 1, tzinfo=timezone.utc),
        end=datetime(2024, 1, 1, 2, tzinfo=timezone.utc),
    )

    assert seen["symbol"] == "BTCUSDT"
    assert seen["period"] == "1h"
    assert seen["startTime"] == 1704070800000
    assert seen["endTime"] == 1704074400000
    assert len(rows) == 1
    assert rows[0]["observed_at"] == datetime(2024, 1, 1, 1, tzinfo=timezone.utc)
    assert rows[0]["value_num"] == 1234567.89
    assert rows[0]["fields"]["unit"] == "USDT_notional"
    assert rows[0]["fields"]["source_value_field"] == "sumOpenInterestValue"
    assert rows[0]["fields"]["open_interest_contracts"] == 100.5


def test_deribit_dvol_client_normalizes_ohlc_and_filters_history_window(monkeypatch):
    client = DeribitDVOLClient()
    seen = {}

    def fake_get(params):
        seen.update(params)
        return {
            "result": {
                "data": [
                    [1704067200000, 50.0, 51.0, 49.0, 50.5],
                    [1704153600000, 52.0, 53.0, 51.0, 52.5],
                ]
            }
        }

    monkeypatch.setattr(client, "_get", fake_get)

    rows = client.fetch(
        currency="BTC",
        resolution="1D",
        start=datetime(2024, 1, 2, tzinfo=timezone.utc),
        end=datetime(2024, 1, 3, tzinfo=timezone.utc),
    )

    assert seen["currency"] == "BTC"
    assert seen["resolution"] == "1D"
    assert seen["start_timestamp"] == 1704153600000
    assert seen["end_timestamp"] == 1704240000000
    assert len(rows) == 1
    assert rows[0]["observed_at"] == datetime(2024, 1, 2, tzinfo=timezone.utc)
    assert rows[0]["value_num"] == 52.5
    assert rows[0]["fields"]["unit"] == "dvol_index_points"
    assert rows[0]["fields"]["open"] == 52.0
    assert rows[0]["fields"]["close"] == 52.5


def test_fetch_rows_dispatches_new_external_adapters(monkeypatch):
    calls = []

    class FakeClient:
        def fetch(self, **kwargs):
            calls.append(kwargs)
            return [{"observed_at": datetime(2024, 1, 1, tzinfo=timezone.utc), "value_num": 1.0}]

    monkeypatch.setattr(ingest_external, "_build_client", lambda dataset_id, cfg: FakeClient())

    ingest_external._fetch_rows(
        "oi_binance_btc",
        {"adapter": "binance_oi", "symbol": "BTCUSDT", "interval": "1h"},
        None,
        None,
    )
    ingest_external._fetch_rows(
        "dvol_deribit_btc",
        {"adapter": "deribit_dvol", "currency": "BTC", "resolution": "1D"},
        None,
        None,
    )

    assert calls == [
        {"symbol": "BTCUSDT", "start": None, "end": None, "interval": "1h"},
        {"currency": "BTC", "start": None, "end": None, "resolution": "1D"},
    ]


@pytest.mark.asyncio
async def test_empty_fetch_with_fail_on_empty_does_not_update_checkpoint(monkeypatch):
    class FakeStore:
        def __init__(self):
            self.finished = []
            self.checkpoints = []
            self.observations = []

        async def upsert_dataset(self, dataset_id, cfg):
            pass

        async def start_fetch_job(self, dataset_id, provider, start, end):
            return "job-1"

        async def finish_fetch_job(self, job_id, **kwargs):
            self.finished.append(kwargs)

        async def upsert_observations(self, dataset_id, rows):
            self.observations.append(rows)
            return {"inserted": 0, "updated": 0}

        async def update_checkpoint(self, dataset_id, **kwargs):
            self.checkpoints.append(kwargs)

    monkeypatch.setattr(ingest_external, "_fetch_rows", lambda *args: [])
    store = FakeStore()

    with pytest.raises(click.ClickException, match="empty fetch"):
        await ingest_external._ingest_one(
            store,
            "oi_binance_btc",
            {"provider": "binance", "adapter": "binance_oi", "fail_on_empty_fetch": True},
            None,
            None,
            dry_run=False,
        )

    assert store.finished[-1]["status"] == "failed"
    assert store.observations == []
    assert store.checkpoints == []


@pytest.mark.asyncio
async def test_dry_run_builds_client_without_db_or_fetch(monkeypatch):
    built = []

    def fake_build_client(dataset_id, cfg):
        built.append(dataset_id)
        return object()

    monkeypatch.setattr(ingest_external, "load_config", lambda *args, **kwargs: pytest.fail("dry-run should not load DB config"))
    monkeypatch.setattr(ingest_external, "_build_client", fake_build_client)

    await ingest_external._main(
        {"oi_binance_btc": {"provider": "binance", "adapter": "binance_oi"}},
        ["oi_binance_btc"],
        "config/settings.yaml",
        None,
        None,
        dry_run=True,
    )

    assert built == ["oi_binance_btc"]
