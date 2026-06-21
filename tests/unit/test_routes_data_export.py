from __future__ import annotations

from datetime import datetime, timezone

import pytest

import okx_quant.api.routes_data as routes_data
from okx_quant.api.routes_data import (
    FetchRequest,
    _external_export_row,
    _existing_update_ranges,
    _funding_export_row,
    _instrument_sort_key,
    _next_existing_update_start,
    _refresh_external_datasets,
    _request_symbols,
)


def test_funding_export_row_includes_apr_and_settlement_fields():
    row = {
        "ts": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "source": "okx",
        "inst_id": "BTC-USDT-SWAP",
        "funding_rate": 0.0001,
        "realized_rate": 0.00009,
        "mark_price": 43000.0,
        "funding_interval_hours": 8.0,
        "next_funding_ts": datetime(2024, 1, 1, 8, tzinfo=timezone.utc),
        "apr": 0.1095,
    }

    exported = _funding_export_row(row)

    assert exported[0] == "2024-01-01T00:00:00+00:00"
    assert exported[2] == "BTC-USDT-SWAP"
    assert exported[-1] == 0.1095


def test_external_export_row_flattens_yfinance_ohlcv_fields():
    row = {
        "dataset_id": "cme_btc_yfinance",
        "observed_at": datetime(2024, 1, 5, tzinfo=timezone.utc),
        "published_at": datetime(2024, 1, 6, tzinfo=timezone.utc),
        "value_num": 43500.0,
        "value_text": None,
        "fields": {
            "open": 43000.0,
            "high": 44000.0,
            "low": 42000.0,
            "close": 43500.0,
            "volume": 1000.0,
            "ticker": "BTC=F",
            "interval": "1d",
            "source_caveat": "Yahoo/yfinance is not an official CME source",
        },
        "quality_status": "raw",
        "provider": "yahoo_finance",
        "attribution": "Research-only proxy",
        "research_only": True,
    }

    exported = _external_export_row(row)

    assert exported[0] == "cme_btc_yfinance"
    assert exported[5:10] == [43000.0, 44000.0, 42000.0, 43500.0, 1000.0]
    assert exported[15] is True


def test_request_symbols_normalizes_binance_native_pair():
    req = FetchRequest(
        exchange="binance",
        symbol="BTCUSDT",
        symbols=["ETHUSDT", "BTC-USDT-SWAP"],
        bar="1m",
        start="2024-01-01",
        end="2024-01-02",
    )

    assert _request_symbols(req) == ["ETH-USDT-SWAP", "BTC-USDT-SWAP"]


def test_instrument_sort_key_prioritizes_exact_base_match():
    rows = [
        {"inst_id": "BRETT-USDT-SWAP", "native_symbol": "BRETTUSDT", "base_ccy": "BRETT", "quote_ccy": "USDT"},
        {"inst_id": "BTC-USDT-SWAP", "native_symbol": "BTCUSDT", "base_ccy": "BTC", "quote_ccy": "USDT"},
        {"inst_id": "PUMPBTC-USDT-SWAP", "native_symbol": "PUMPBTCUSDT", "base_ccy": "PUMPBTC", "quote_ccy": "USDT"},
    ]

    sorted_rows = sorted(rows, key=lambda row: _instrument_sort_key(row, "BTC"))

    assert sorted_rows[0]["inst_id"] == "BTC-USDT-SWAP"


def test_binance_filter_value_reads_precision_filters():
    item = {
        "filters": [
            {"filterType": "PRICE_FILTER", "tickSize": "0.0000010"},
            {"filterType": "LOT_SIZE", "stepSize": "1", "minQty": "1"},
        ]
    }

    assert routes_data._binance_filter_value(item, "PRICE_FILTER", "tickSize") == 0.000001
    assert routes_data._binance_filter_value(item, "LOT_SIZE", "stepSize") == 1.0
    assert routes_data._binance_filter_value(item, "LOT_SIZE", "minQty") == 1.0


def test_binance_venue_spec_payload_handles_multiplier_contract():
    spec = routes_data._binance_venue_spec_from_meta({
        "tick_size": 0.000001,
        "lot_size": 1.0,
        "min_size": 1.0,
    })

    assert spec == {
        "ct_val": 1.0,
        "lot_size": 1.0,
        "tick_size": 0.000001,
        "min_size": 1.0,
        "source": "binance_exchange_info",
    }


@pytest.mark.asyncio
async def test_upsert_venue_instrument_spec_writes_binance_1000_pair():
    calls = []

    class FakePool:
        async def execute(self, sql, *params):
            calls.append((sql, params))

    await routes_data._upsert_venue_instrument_spec(
        FakePool(),
        exchange="binance",
        symbol="1000SHIB-USDT-SWAP",
        ct_val=1.0,
        lot_size=1.0,
        tick_size=0.000001,
        min_size=1.0,
        source="binance_exchange_info",
    )

    assert len(calls) == 1
    sql, params = calls[0]
    assert "venue_instrument_specs" in sql
    assert params == (
        "binance",
        "1000SHIB-USDT-SWAP",
        1.0,
        1.0,
        0.000001,
        1.0,
        "binance_exchange_info",
    )


@pytest.mark.asyncio
async def test_run_fetch_body_syncs_binance_venue_spec_before_skip(monkeypatch):
    import asyncpg
    import okx_quant.data.candle_store as candle_store
    from okx_quant.data.exchange_clients.binance_public import BinancePublicClient

    calls = []

    class FakePool:
        async def execute(self, sql, *params):
            calls.append((sql, params))

        async def close(self):
            return None

    class FakeStore:
        def __init__(self, pool):
            assert isinstance(pool, FakePool)

    async def fake_create_pool(*_args, **_kwargs):
        return FakePool()

    def fake_exchange_info(self):
        return {
            "symbols": [{
                "symbol": "1000SHIBUSDT",
                "baseAsset": "1000SHIB",
                "quoteAsset": "USDT",
                "marginAsset": "USDT",
                "contractType": "PERPETUAL",
                "status": "TRADING",
                "onboardDate": "1706745600000",
                "filters": [
                    {"filterType": "PRICE_FILTER", "tickSize": "0.0000010"},
                    {"filterType": "LOT_SIZE", "stepSize": "1", "minQty": "1"},
                ],
            }]
        }

    monkeypatch.setattr(asyncpg, "create_pool", fake_create_pool)
    monkeypatch.setattr(candle_store, "CandleStore", FakeStore)
    monkeypatch.setattr(BinancePublicClient, "get_futures_exchange_info", fake_exchange_info)
    monkeypatch.setattr(BinancePublicClient, "close", lambda self: None)
    routes_data._jobs.clear()
    routes_data._jobs["job_spec"] = {"job_id": "job_spec", "status": "queued"}
    req = FetchRequest(
        exchange="binance",
        symbols=["1000SHIB-USDT-SWAP"],
        bar="1m",
        start="2024-01-01",
        end="2024-01-02",
    )

    await routes_data._run_fetch_body("job_spec", req, "postgresql://unused")

    assert len(calls) == 1
    sql, params = calls[0]
    assert "venue_instrument_specs" in sql
    assert params[:2] == ("binance", "1000SHIB-USDT-SWAP")
    assert routes_data._jobs["job_spec"]["results"][0]["status"] == "skipped"


@pytest.mark.asyncio
async def test_binance_instruments_preserves_precision_filters(monkeypatch):
    from okx_quant.data.exchange_clients.binance_public import BinancePublicClient

    def fake_exchange_info(self):
        return {
            "symbols": [{
                "symbol": "1000SHIBUSDT",
                "baseAsset": "1000SHIB",
                "quoteAsset": "USDT",
                "marginAsset": "USDT",
                "contractType": "PERPETUAL",
                "status": "TRADING",
                "onboardDate": "1704067200000",
                "filters": [
                    {"filterType": "PRICE_FILTER", "tickSize": "0.0000010"},
                    {"filterType": "LOT_SIZE", "stepSize": "1", "minQty": "1"},
                ],
            }]
        }

    monkeypatch.setattr(BinancePublicClient, "get_futures_exchange_info", fake_exchange_info)
    monkeypatch.setattr(BinancePublicClient, "close", lambda self: None)

    rows = await routes_data._binance_instruments(keyword="1000SHIB")

    assert rows == [{
        "exchange": "binance",
        "inst_id": "1000SHIB-USDT-SWAP",
        "native_symbol": "1000SHIBUSDT",
        "normalized_symbol": "1000SHIB-USDT-SWAP",
        "inst_type": "SWAP",
        "base_ccy": "1000SHIB",
        "quote_ccy": "USDT",
        "settle_ccy": "USDT",
        "state": "TRADING",
        "list_time_ms": 1704067200000,
        "list_date": "2024-01-01",
        "tick_size": 0.000001,
        "lot_size": 1.0,
        "min_size": 1.0,
    }]


def test_next_existing_update_start_resumes_after_last_db_candle():
    requested_start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    last_ts = datetime(2024, 6, 1, 0, 0, tzinfo=timezone.utc)

    assert _next_existing_update_start(requested_start, last_ts, "1m") == datetime(
        2024, 6, 1, 0, 1, tzinfo=timezone.utc
    )


def test_existing_update_ranges_backfills_before_first_db_candle():
    requested_start = datetime(2023, 1, 1, tzinfo=timezone.utc)
    requested_end = datetime(2024, 2, 1, tzinfo=timezone.utc)
    bounds = {
        "first_ts": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "last_ts": datetime(2024, 6, 1, tzinfo=timezone.utc),
    }

    assert _existing_update_ranges(requested_start, requested_end, bounds, "1m") == [
        (datetime(2023, 1, 1, tzinfo=timezone.utc), datetime(2024, 1, 1, tzinfo=timezone.utc))
    ]


def test_existing_update_ranges_can_backfill_and_append():
    requested_start = datetime(2023, 1, 1, tzinfo=timezone.utc)
    requested_end = datetime(2024, 6, 2, tzinfo=timezone.utc)
    bounds = {
        "first_ts": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "last_ts": datetime(2024, 6, 1, tzinfo=timezone.utc),
    }

    assert _existing_update_ranges(requested_start, requested_end, bounds, "1m") == [
        (datetime(2023, 1, 1, tzinfo=timezone.utc), datetime(2024, 1, 1, tzinfo=timezone.utc)),
        (datetime(2024, 6, 1, 0, 1, tzinfo=timezone.utc), datetime(2024, 6, 2, tzinfo=timezone.utc)),
    ]


def test_existing_update_ranges_skips_fully_covered_window():
    requested_start = datetime(2024, 2, 1, tzinfo=timezone.utc)
    requested_end = datetime(2024, 3, 1, tzinfo=timezone.utc)
    bounds = {
        "first_ts": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "last_ts": datetime(2024, 6, 1, tzinfo=timezone.utc),
    }

    assert _existing_update_ranges(requested_start, requested_end, bounds, "1m") == []


@pytest.mark.asyncio
async def test_resolve_fetch_symbols_can_use_existing_db_pairs(monkeypatch):
    async def fake_existing_db_symbols(db_dsn: str, bar: str) -> list[str]:
        assert db_dsn == "postgresql://unused"
        assert bar == "1m"
        return ["BTC-USDT-SWAP", "SOL-USDT-SWAP"]

    monkeypatch.setattr(routes_data, "_existing_db_symbols", fake_existing_db_symbols)
    req = FetchRequest(
        exchange="binance",
        symbols=["ETHUSDT"],
        existing_only=True,
        bar="1m",
        start="2024-01-01",
        end="2024-01-02",
    )

    resolved = await routes_data._resolve_fetch_symbols(req, "postgresql://unused")

    assert resolved == ["BTC-USDT-SWAP", "SOL-USDT-SWAP"]


@pytest.mark.asyncio
async def test_refresh_external_datasets_fetches_yfinance_and_upserts(monkeypatch):
    from okx_quant.data.external_clients.yfinance_client import YFinanceClient
    from okx_quant.data.external_store import ExternalDataStore

    calls: dict[str, object] = {}

    def fake_fetch(self, *, ticker, start, end, interval):
        calls["fetch"] = (ticker, start, end, interval)
        return [{
            "observed_at": datetime(2024, 1, 5, tzinfo=timezone.utc),
            "published_at": datetime(2024, 1, 6, tzinfo=timezone.utc),
            "value_num": 43500.0,
            "value_text": None,
            "fields": {"close": 43500.0},
            "quality_status": "raw",
            "raw_payload": {},
        }]

    class FakeStore:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def upsert_dataset(self, dataset_id, cfg):
            calls["dataset"] = (dataset_id, cfg["adapter"])

        async def start_fetch_job(self, dataset_id, provider, start, end):
            calls["job"] = (dataset_id, provider, start, end)
            return "00000000-0000-0000-0000-000000000001"

        async def finish_fetch_job(self, job_id, **kwargs):
            calls["finish"] = (job_id, kwargs)

        async def upsert_observations(self, dataset_id, rows):
            calls["rows"] = (dataset_id, rows)
            return {"rows": len(rows), "inserted": len(rows), "updated": 0}

        async def update_checkpoint(self, dataset_id, **kwargs):
            calls["checkpoint"] = (dataset_id, kwargs)

    async def fake_from_dsn(*_args, **_kwargs):
        return FakeStore()

    monkeypatch.setattr(YFinanceClient, "fetch", fake_fetch)
    monkeypatch.setattr(ExternalDataStore, "from_dsn", fake_from_dsn)

    result = await _refresh_external_datasets(
        "postgresql://unused",
        ["cme_btc_yfinance"],
        datetime(2024, 1, 1, tzinfo=timezone.utc),
        datetime(2024, 1, 10, tzinfo=timezone.utc),
    )

    assert result["status"] == "done"
    assert result["datasets"][0]["rows_fetched"] == 1
    assert calls["fetch"][0] == "BTC=F"
    assert calls["dataset"] == ("cme_btc_yfinance", "yfinance")
