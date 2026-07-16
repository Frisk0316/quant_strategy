import pytest

from okx_quant.data.exchange_clients.deribit_public import DeribitPublicClient
from scripts.market_data.ingest import (
    BAR_MS,
    DERIBIT_PAGE_ROWS,
    IngestState,
    _fetch_page,
    _flush,
)


def test_deribit_chart_data_normalizes_1m_rows(monkeypatch):
    client = DeribitPublicClient(rate_sleep=0)
    monkeypatch.setattr(
        client,
        "_get",
        lambda params: {
            "status": "ok",
            "ticks": [1_700_000_000_000],
            "open": [100.0],
            "high": [102.0],
            "low": [99.0],
            "close": [101.0],
            "volume": [2.5],
            "cost": [252.5],
        },
    )

    rows = client.get_tradingview_chart_data(
        "BTC-PERPETUAL",
        start_ms=1_700_000_000_000,
        end_ms=1_700_000_060_000,
        resolution=1,
    )

    assert rows == [
        {
            "ts_ms": 1_700_000_000_000,
            "open": 100.0,
            "high": 102.0,
            "low": 99.0,
            "close": 101.0,
            "vol_contract": None,
            "vol_base": 2.5,
            "vol_quote": 252.5,
            "is_closed": True,
            "raw_payload": {
                "exchange": "deribit",
                "instrument_name": "BTC-PERPETUAL",
                "resolution": "1",
            },
        }
    ]
    client.close()


def test_deribit_chart_data_rejects_mismatched_columns(monkeypatch):
    client = DeribitPublicClient(rate_sleep=0)
    monkeypatch.setattr(
        client,
        "_get",
        lambda params: {
            "status": "ok",
            "ticks": [1],
            "open": [],
            "high": [1],
            "low": [1],
            "close": [1],
            "volume": [1],
            "cost": [1],
        },
    )

    with pytest.raises(RuntimeError, match="mismatched column lengths"):
        client.get_tradingview_chart_data("BTC-PERPETUAL", start_ms=0, end_ms=1)
    client.close()


def test_deribit_ingest_page_is_bounded_to_api_cap():
    class FakeClient:
        def get_tradingview_chart_data(self, symbol, *, start_ms, end_ms, resolution):
            assert symbol == "ETH-PERPETUAL"
            assert end_ms - start_ms == (DERIBIT_PAGE_ROWS - 1) * BAR_MS
            assert resolution == 1
            return [{"ts_ms": end_ms, "is_closed": True}]

    rows, next_cursor, done = _fetch_page(
        client=FakeClient(),
        exchange="deribit",
        dataset="klines_1m",
        symbol="ETH-PERPETUAL",
        cursor_ms=0,
        start_ms=0,
        end_ms=2 * DERIBIT_PAGE_ROWS * BAR_MS,
        direction="forward",
    )

    assert rows == [{"ts_ms": (DERIBIT_PAGE_ROWS - 1) * BAR_MS, "is_closed": True}]
    assert next_cursor == DERIBIT_PAGE_ROWS * BAR_MS
    assert done is False


@pytest.mark.asyncio
async def test_deribit_flush_writes_native_venue_scoped_canonical_rows():
    class FakeStore:
        def __init__(self):
            self.canonical = None

        async def register_instrument(self, **kwargs):
            assert kwargs["inst_id"] == "BTC-PERPETUAL"
            assert kwargs["exchange"] == "other"
            assert kwargs["quote_ccy"] == "USD"
            assert kwargs["settle_ccy"] == "BTC"

        async def register_instrument_bar(self, inst_id, bar):
            assert (inst_id, bar) == ("BTC-PERPETUAL", "1m")

        async def upsert_canonical_candles(self, rows, **kwargs):
            self.canonical = (rows, kwargs)
            return {"inserted": len(rows)}

        async def update_instrument_bar_bounds(self, inst_id, bar):
            assert (inst_id, bar) == ("BTC-PERPETUAL", "1m")

        async def update_checkpoint(self, *args, **kwargs):
            return None

    store = FakeStore()
    rows = [{"ts_ms": 1, "open": 1, "high": 1, "low": 1, "close": 1}]
    inserted = await _flush(
        store=store,
        exchange="deribit",
        dataset="klines_1m",
        symbol="BTC-PERPETUAL",
        direction="forward",
        buffer=rows,
        state=IngestState(cursor_ms=BAR_MS, requests_since_flush=1),
        checkpoint_status="running",
    )

    assert inserted == 1
    assert store.canonical == (
        rows,
        {
            "inst_id": "BTC-PERPETUAL",
            "bar": "1m",
            "source_primary": "deribit",
            "quality_status": "raw",
        },
    )
