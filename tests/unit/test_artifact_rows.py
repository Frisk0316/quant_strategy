from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from backtesting.artifact_rows import (
    build_artifact_row_records,
    normalized_records_hash,
    row_payloads_hash,
    select_downsample_indices,
    upsert_artifact_rows,
)


def test_build_artifact_row_records_extracts_symbol_timestamp_and_preserves_payload():
    payload = [
        {
            "symbol": "BTC-USDT-SWAP",
            "ts": 1_704_067_200_000,
            "datetime": "2024-01-01T00:00:00+00:00",
            "close": 42000.0,
        },
        {
            "inst_id": "ETH-USDT-SWAP",
            "datetime": "2024-01-02T00:00:00Z",
            "close": 2300.0,
        },
    ]

    rows = build_artifact_row_records("run1", "price_series", payload)

    assert [row.ordinal for row in rows] == [0, 1]
    assert rows[0].inst_id == "BTC-USDT-SWAP"
    assert rows[0].ts_ms == 1_704_067_200_000
    assert rows[0].datetime_text == "2024-01-01T00:00:00+00:00"
    assert rows[0].payload == payload[0]
    assert rows[1].inst_id == "ETH-USDT-SWAP"
    assert rows[1].ts_ms == 1_704_153_600_000
    assert rows[1].payload == payload[1]


def test_build_artifact_row_records_uses_stable_ordinals_and_ignores_non_list_payloads():
    assert build_artifact_row_records("run1", "metrics", {"sharpe": 1.2}) == []
    assert build_artifact_row_records("run1", "price_series", []) == []
    assert build_artifact_row_records("run1", "price_series", [1, "x", {"ts": 1}])[0].ordinal == 0


def test_normalized_hash_parity_uses_row_payloads_without_key_order_sensitivity():
    original = [{"b": 2, "a": 1}, {"symbol": "BTC-USDT-SWAP", "ts": 1}]
    reordered = [{"a": 1, "b": 2}, {"ts": 1, "symbol": "BTC-USDT-SWAP"}]
    rows = build_artifact_row_records("run1", "fills", reordered)

    assert normalized_records_hash(original) == normalized_records_hash(reordered)
    assert row_payloads_hash(rows) == normalized_records_hash(original)


def test_select_downsample_indices_matches_existing_even_spacing_semantics():
    assert select_downsample_indices(0, 1200) == []
    assert select_downsample_indices(3, 1200) == [0, 1, 2]
    assert select_downsample_indices(10, 3) == [0, 3, 6, 9]


@pytest.mark.asyncio
async def test_upsert_artifact_rows_uses_bulk_copy(monkeypatch):
    class FakeTx:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeConn:
        def __init__(self):
            self.copy_calls = []
            self.executemany_called = False

        async def execute(self, *args):
            return None

        async def executemany(self, *args):
            self.executemany_called = True

        async def copy_records_to_table(self, table, *, records, columns):
            self.copy_calls.append((table, list(records), tuple(columns)))

        def transaction(self):
            return FakeTx()

        async def close(self):
            return None

    fake_conn = FakeConn()

    async def fake_connect(_dsn):
        return fake_conn

    monkeypatch.setitem(sys.modules, "asyncpg", SimpleNamespace(connect=fake_connect))

    counts = await upsert_artifact_rows(
        dsn="postgresql://unit/db",
        run_id="run1",
        artifacts={"fills": [{"ts": 1}, {"ts": 2}]},
        artifact_types={"fills"},
    )

    assert counts == {"fills": 2}
    assert fake_conn.copy_calls
    assert not fake_conn.executemany_called
