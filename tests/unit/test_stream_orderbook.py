from __future__ import annotations

import pyarrow.parquet as pq
from types import SimpleNamespace

from scripts import stream_orderbook


def test_trade_and_funding_rows_flush_to_separate_parquet(tmp_path, monkeypatch):
    monkeypatch.setattr(stream_orderbook, "DATA_DIR", tmp_path)

    trade = stream_orderbook._trade_rows({
        "data": [{"ts": "1", "tradeId": "t1", "px": "100", "sz": "2", "side": "buy"}]
    })
    funding = stream_orderbook._funding_rows({
        "data": [{"fundingTime": "2", "nextFundingTime": "3", "fundingRate": "0.0001"}]
    })

    cases = [
        ("trades", stream_orderbook.TRADE_SCHEMA, trade),
        ("funding", stream_orderbook.FUNDING_SCHEMA, funding),
    ]
    for prefix, schema, rows in cases:
        buffer = stream_orderbook.TickBuffer(
            "BTC-USDT-SWAP", "session", prefix=prefix, schema=schema, flush_every=1
        )
        buffer.append(rows[0])
        buffer.flush()
        table = pq.read_table(tmp_path / "BTC_USDT_SWAP" / f"{prefix}_session_0000.parquet")
        assert table.num_rows == 1
        assert table.schema.names == schema.names


def test_disk_guard_reserves_ten_gib(monkeypatch, tmp_path):
    monkeypatch.setattr(
        stream_orderbook.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(free=stream_orderbook.MIN_FREE_BYTES - 1),
    )

    assert stream_orderbook._has_disk_capacity(tmp_path) is False
