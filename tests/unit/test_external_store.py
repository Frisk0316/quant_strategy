from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from okx_quant.data.external_store import ExternalDataStore


class _Connection:
    def __init__(self, records):
        self.records = records

    async def fetch(self, _sql, dataset_id, observed_at):
        return [
            {"observed_at": ts}
            for ts in observed_at
            if (dataset_id, ts) in self.records
        ]

    async def executemany(self, sql, payload):
        payload_only = "published_at = EXCLUDED.published_at" not in sql
        for dataset_id, observed_at, published_at, value_num, value_text, fields, quality, raw in payload:
            key = (dataset_id, observed_at)
            if key not in self.records:
                self.records[key] = {
                    "published_at": published_at,
                    "value_num": value_num,
                    "value_text": value_text,
                    "fields": json.loads(fields),
                    "quality_status": quality,
                    "ingested_at": 0,
                }
            elif not payload_only:
                self.records[key].update(
                    published_at=published_at,
                    value_num=value_num,
                    value_text=value_text,
                    fields=json.loads(fields),
                    quality_status=quality,
                )
            self.records[key]["raw_payload"] = json.loads(raw)
            self.records[key]["ingested_at"] += 1


class _Acquire:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, *_args):
        return None


class _Pool:
    def __init__(self, records):
        self.connection = _Connection(records)

    def acquire(self):
        return _Acquire(self.connection)


def _row(observed_at, *, value_num, raw_payload):
    return {
        "observed_at": observed_at,
        "published_at": observed_at + timedelta(hours=1),
        "value_num": value_num,
        "value_text": f"value-{value_num}",
        "fields": {"trade_count": int(value_num)},
        "quality_status": "validated",
        "raw_payload": raw_payload,
    }


@pytest.mark.asyncio
async def test_payload_only_preserves_frozen_columns_and_fully_inserts_new_rows():
    observed_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    frozen = {
        "published_at": observed_at,
        "value_num": 1.0,
        "value_text": "frozen",
        "fields": {"trade_count": 1},
        "quality_status": "raw",
        "raw_payload": {"sample": []},
        "ingested_at": 1,
    }
    records = {("optflow_deribit_btc", observed_at): frozen}
    store = ExternalDataStore(_Pool(records))

    stats = await store.upsert_observations(
        "optflow_deribit_btc",
        [_row(observed_at, value_num=9.0, raw_payload={"sample": [{"trade_id": "new"}]})],
        payload_only=True,
    )

    assert stats == {"rows": 1, "inserted": 0, "updated": 1}
    assert frozen == {
        "published_at": observed_at,
        "value_num": 1.0,
        "value_text": "frozen",
        "fields": {"trade_count": 1},
        "quality_status": "raw",
        "raw_payload": {"sample": [{"trade_id": "new"}]},
        "ingested_at": 2,
    }

    new_at = observed_at + timedelta(hours=1)
    stats = await store.upsert_observations(
        "optflow_deribit_btc",
        [_row(new_at, value_num=3.0, raw_payload={"sample": [{"trade_id": "inserted"}]})],
        payload_only=True,
    )

    assert stats == {"rows": 1, "inserted": 1, "updated": 0}
    assert records[("optflow_deribit_btc", new_at)]["value_num"] == 3.0
    assert records[("optflow_deribit_btc", new_at)]["fields"] == {"trade_count": 3}


@pytest.mark.asyncio
async def test_default_upsert_still_updates_all_columns():
    observed_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    record = {
        "published_at": observed_at,
        "value_num": 1.0,
        "value_text": "old",
        "fields": {"trade_count": 1},
        "quality_status": "raw",
        "raw_payload": {},
        "ingested_at": 1,
    }
    store = ExternalDataStore(_Pool({("other_dataset", observed_at): record}))

    await store.upsert_observations(
        "other_dataset",
        [_row(observed_at, value_num=4.0, raw_payload={"changed": True})],
    )

    assert record["published_at"] == observed_at + timedelta(hours=1)
    assert record["value_num"] == 4.0
    assert record["value_text"] == "value-4.0"
    assert record["fields"] == {"trade_count": 4}
    assert record["quality_status"] == "validated"
    assert record["raw_payload"] == {"changed": True}
