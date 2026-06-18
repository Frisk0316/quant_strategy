import pandas as pd
import pytest

from backtesting import data_loader
from okx_quant.data.candle_store import CandleStore


def test_postgres_candle_loader_receives_exchange(monkeypatch):
    monkeypatch.setattr(data_loader, "_dsn_reachable", lambda dsn: True)

    def fake_pg_loader(inst_id, bar, dsn, start, end, include_suspect, exchange):
        assert exchange == "binance"
        return pd.DataFrame(columns=["open", "high", "low", "close", "vol"])

    monkeypatch.setattr(data_loader, "_load_candles_pg", fake_pg_loader)

    data_loader.load_candles(
        "BTC-USDT-SWAP",
        bar="1H",
        backend="postgres",
        dsn="postgresql://unit",
        exchange="binance",
    )


@pytest.mark.asyncio
async def test_canonical_candles_can_filter_source_primary():
    class _Pool:
        sql = ""
        params = ()

        async def fetch(self, sql, *params):
            self.sql = sql
            self.params = params
            return []

    pool = _Pool()
    store = CandleStore(pool)

    await store.get_canonical_candles(
        inst_id="BTC-USDT-SWAP",
        bar="1H",
        source_primary="binance",
    )

    assert "source_primary=$3" in pool.sql
    assert pool.params == ("BTC-USDT-SWAP", "1H", "binance")


@pytest.mark.asyncio
async def test_canonical_candles_source_primary_changes_result_set():
    class _Pool:
        async def fetch(self, sql, *params):
            assert "source_primary=$3" in sql
            source = params[2]
            if source != "binance":
                return []
            return [
                {
                    "ts": pd.Timestamp("2026-01-01T00:00:00Z"),
                    "open": 1.0,
                    "high": 2.0,
                    "low": 0.5,
                    "close": 1.5,
                    "vol_contract": 10.0,
                    "vol_base": 10.0,
                    "vol_quote": 15.0,
                }
            ]

    store = CandleStore(_Pool())

    binance = await store.get_canonical_candles(
        inst_id="BTC-USDT-SWAP",
        bar="1H",
        source_primary="binance",
    )
    okx = await store.get_canonical_candles(
        inst_id="BTC-USDT-SWAP",
        bar="1H",
        source_primary="okx",
    )

    assert len(binance) == 1
    assert okx.empty
