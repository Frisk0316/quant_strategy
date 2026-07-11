from __future__ import annotations

from datetime import datetime, timezone

import pytest

from okx_quant.data.external_clients.deribit_funding import DeribitFundingClient
from scripts.market_data import ingest_external


def _funding_row(ts_ms: int, value: float) -> dict:
    return {
        "timestamp": ts_ms,
        "interest_1h": value,
        "interest_8h": value * 8,
        "index_price": 42000.0,
        "prev_index_price": 41900.0,
    }


def test_deribit_funding_client_pages_backward_filters_window_and_sets_fields(monkeypatch):
    client = DeribitFundingClient()
    calls = []
    pages = [
        [
            _funding_row(1704070800000, 0.0001),
            _funding_row(1704074400000, 0.0002),
            _funding_row(1704078000000, 0.0003),
        ],
        [
            _funding_row(1704067200000, 0.0000),
            _funding_row(1704070800000, 0.0001),
        ],
    ]

    def fake_get(params):
        calls.append(dict(params))
        return {"result": pages.pop(0)}

    monkeypatch.setattr(client, "_get", fake_get)

    rows = client.fetch(
        instrument_name="BTC-PERPETUAL",
        start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end=datetime(2024, 1, 1, 3, tzinfo=timezone.utc),
    )

    assert [row["observed_at"] for row in rows] == [
        datetime(2024, 1, 1, 0, tzinfo=timezone.utc),
        datetime(2024, 1, 1, 1, tzinfo=timezone.utc),
        datetime(2024, 1, 1, 2, tzinfo=timezone.utc),
    ]
    assert [row["value_num"] for row in rows] == [0.0, 0.0001, 0.0002]
    assert rows[1]["fields"] == {
        "instrument": "BTC-PERPETUAL",
        "interest_8h": 0.0008,
        "index_price": 42000.0,
        "prev_index_price": 41900.0,
        "unit": "rate_1h_decimal",
    }
    assert calls[0]["instrument_name"] == "BTC-PERPETUAL"
    assert calls[0]["start_timestamp"] == 1704067200000
    assert calls[0]["end_timestamp"] == 1704078000000
    assert calls[1]["end_timestamp"] == 1704070800000


def test_deribit_funding_client_handles_empty_window(monkeypatch):
    client = DeribitFundingClient()
    monkeypatch.setattr(client, "_get", lambda params: {"result": []})

    rows = client.fetch(
        instrument_name="ETH-PERPETUAL",
        start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end=datetime(2024, 1, 2, tzinfo=timezone.utc),
    )

    assert rows == []


def test_fetch_rows_dispatches_deribit_funding(monkeypatch):
    calls = []

    class FakeClient:
        def fetch(self, **kwargs):
            calls.append(kwargs)
            return []

    monkeypatch.setattr(ingest_external, "_build_client", lambda dataset_id, cfg: FakeClient())

    ingest_external._fetch_rows(
        "funding_deribit_btc",
        {"adapter": "deribit_funding", "instrument_name": "BTC-PERPETUAL"},
        None,
        None,
    )

    assert calls == [{
        "instrument_name": "BTC-PERPETUAL",
        "start": None,
        "end": None,
    }]


@pytest.mark.asyncio
async def test_deribit_funding_ingest_checkpoint_cursor_advances(monkeypatch):
    class FakeStore:
        def __init__(self):
            self.checkpoints = []

        async def upsert_dataset(self, dataset_id, cfg):
            pass

        async def start_fetch_job(self, dataset_id, provider, start, end):
            return "job-1"

        async def upsert_observations(self, dataset_id, rows):
            return {"inserted": len(rows), "updated": 0}

        async def finish_fetch_job(self, job_id, **kwargs):
            pass

        async def update_checkpoint(self, dataset_id, **kwargs):
            self.checkpoints.append((dataset_id, kwargs))

    rows = [
        {"observed_at": datetime(2024, 1, 1, 1, tzinfo=timezone.utc)},
        {"observed_at": datetime(2024, 1, 1, 2, tzinfo=timezone.utc)},
    ]
    monkeypatch.setattr(ingest_external, "_fetch_rows", lambda *args: rows)
    store = FakeStore()

    await ingest_external._ingest_one(
        store,
        "funding_deribit_btc",
        {"provider": "deribit", "adapter": "deribit_funding"},
        datetime(2024, 1, 1, tzinfo=timezone.utc),
        datetime(2024, 1, 2, tzinfo=timezone.utc),
        dry_run=False,
    )

    assert store.checkpoints == [(
        "funding_deribit_btc",
        {
            "direction": "backfill",
            "cursor_time": datetime(2024, 1, 1, 2, tzinfo=timezone.utc),
            "request_count": 1,
            "row_count": 2,
            "status": "success",
        },
    )]
