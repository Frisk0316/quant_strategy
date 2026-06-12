from scripts.market_data.ingest import (
    _dedupe_sort,
    _infer_funding_intervals,
    _normalize_symbol,
    _resume_cursor,
)
from okx_quant.data.exchange_clients.binance_public import BinancePublicClient
from okx_quant.data.exchange_clients.bybit_public import BybitPublicClient
from okx_quant.data.exchange_clients.okx_public import OKXPublicClient


def test_binance_kline_row_normalization(monkeypatch):
    client = BinancePublicClient()
    raw = [[
        1_700_000_000_000, "100.1", "101.2", "99.9", "100.5", "12.3",
        1_700_000_059_999, "1234.5", 42, "6.1", "612.0", "0",
    ]]
    monkeypatch.setattr(client, "_get", lambda *_args, **_kwargs: raw)

    rows = client.get_klines("BTCUSDT", "1m")

    assert rows[0]["ts_ms"] == 1_700_000_000_000
    assert rows[0]["open"] == 100.1
    assert rows[0]["vol_base"] == 12.3
    assert rows[0]["vol_quote"] == 1234.5
    assert rows[0]["trade_count"] == 42
    client.close()


def test_binance_funding_row_normalization(monkeypatch):
    client = BinancePublicClient()
    raw = [{
        "symbol": "BTCUSDT",
        "fundingTime": 1_700_000_000_000,
        "fundingRate": "0.0001",
        "markPrice": "50000.5",
    }]
    monkeypatch.setattr(client, "_get", lambda *_args, **_kwargs: raw)

    rows = client.get_funding_rates("BTCUSDT")

    assert rows[0]["ts_ms"] == 1_700_000_000_000
    assert rows[0]["funding_rate"] == 0.0001
    assert rows[0]["mark_price"] == 50000.5
    client.close()


def test_binance_kline_range_honors_cancel_before_fetch(monkeypatch):
    client = BinancePublicClient()
    monkeypatch.setattr(client, "get_klines", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("fetch called")))

    rows = client.get_klines_range(
        "BTCUSDT",
        "1m",
        1_700_000_000_000,
        1_700_000_060_000,
        should_cancel=lambda: True,
    )

    assert rows == []
    client.close()


def test_okx_paginate_history_honors_cancel_before_fetch(monkeypatch):
    client = OKXPublicClient()
    monkeypatch.setattr(client, "get_history_candles", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("fetch called")))

    rows = client.paginate_history(
        "BTC-USDT-SWAP",
        "1m",
        1_700_000_000_000,
        1_700_000_060_000,
        should_cancel=lambda: True,
    )

    assert rows == []
    client.close()


def test_bybit_kline_reverse_order_sorting(monkeypatch):
    client = BybitPublicClient()
    raw = [
        ["1700000060000", "101", "102", "100", "101.5", "2", "203"],
        ["1700000000000", "100", "101", "99", "100.5", "1", "100"],
    ]
    monkeypatch.setattr(client, "_get", lambda *_args, **_kwargs: raw)

    rows = client.get_kline("BTCUSDT", "1m")

    assert [row["ts_ms"] for row in rows] == [1_700_000_000_000, 1_700_000_060_000]
    client.close()


def test_okx_symbol_normalization():
    assert _normalize_symbol("okx", "BTC-USDT-SWAP") == "BTCUSDT"


def test_duplicate_rows_deduped_by_timestamp():
    rows = [
        {"ts_ms": 2, "close": 2},
        {"ts_ms": 1, "close": 1},
        {"ts_ms": 2, "close": 3},
    ]

    assert _dedupe_sort(rows) == [{"ts_ms": 1, "close": 1}, {"ts_ms": 2, "close": 3}]


def test_resume_cursor_uses_checkpoint():
    assert _resume_cursor(
        direction="forward",
        start_ms=100,
        end_ms=1_000,
        checkpoint_cursor_ms=500,
    ) == 500
    assert _resume_cursor(
        direction="backward",
        start_ms=100,
        end_ms=1_000,
        checkpoint_cursor_ms=700,
    ) == 700


def test_funding_interval_inferred_from_adjacent_timestamps():
    rows = [
        {"ts_ms": 0, "funding_rate": 0.1},
        {"ts_ms": 4 * 60 * 60 * 1000, "funding_rate": 0.2},
        {"ts_ms": 12 * 60 * 60 * 1000, "funding_rate": 0.3},
    ]

    inferred = _infer_funding_intervals(rows)

    assert inferred[0]["funding_interval_hours"] == 4.0
    assert inferred[1]["funding_interval_hours"] == 8.0
    assert "funding_interval_hours" not in inferred[2]
