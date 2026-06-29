import pandas as pd
import pytest

from backtesting import replay
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


def test_venue_tagged_candle_load_uses_postgres_not_parquet(monkeypatch):
    monkeypatch.setattr(data_loader, "_dsn_reachable", lambda dsn: True)

    def fake_parquet_loader(*_args, **_kwargs):
        return pd.DataFrame(
            {"open": [1.0], "high": [1.0], "low": [1.0], "close": [63258.8], "vol": [1.0]},
            index=pd.DatetimeIndex(["2024-04-29T00:00:00"]),
        )

    def fake_pg_loader(_inst_id, _bar, _dsn, _start, _end, _include_suspect, exchange):
        assert exchange == "binance"
        return pd.DataFrame(
            {"open": [1.0], "high": [1.0], "low": [1.0], "close": [63229.2], "vol": [1.0]},
            index=pd.DatetimeIndex(["2024-04-29T00:00:00"]),
        )

    monkeypatch.setattr(data_loader, "_load_candles_parquet", fake_parquet_loader)
    monkeypatch.setattr(data_loader, "_load_candles_pg", fake_pg_loader)

    loaded = data_loader.load_candles(
        "BTC-USDT-SWAP",
        bar="1H",
        backend="parquet",
        dsn="postgresql://unit",
        exchange="binance",
    )

    assert loaded.iloc[0]["close"] == 63229.2


def test_venue_tagged_candle_load_requires_reachable_postgres(monkeypatch):
    monkeypatch.setattr(data_loader, "_dsn_reachable", lambda dsn: False)

    def fail_if_parquet_is_used(*_args, **_kwargs):
        raise AssertionError("venue-scoped loads must not fall back to parquet")

    monkeypatch.setattr(data_loader, "_load_candles_parquet", fail_if_parquet_is_used)

    with pytest.raises(ValueError, match="Venue-scoped candle load"):
        data_loader.load_candles(
            "BTC-USDT-SWAP",
            bar="1H",
            backend="postgres",
            dsn="postgresql://unit",
            exchange="binance",
        )


def test_venue_scoped_gap_raises_explicit_error():
    one_binance_bar = pd.DataFrame(
        {"open": [1.0], "high": [1.0], "low": [1.0], "close": [63229.2], "vol": [1.0]},
        index=pd.DatetimeIndex(["2024-04-29T00:00:00"]),
    )

    with pytest.raises(ValueError, match="expected 2 bars, found 1"):
        data_loader._raise_on_venue_gap(
            one_binance_bar,
            inst_id="BTC-USDT-SWAP",
            bar="1H",
            start_dt=pd.Timestamp("2024-04-29T00:00:00Z").to_pydatetime(),
            end_dt=pd.Timestamp("2024-04-29T02:00:00Z").to_pydatetime(),
            exchange="binance",
        )


def test_venue_scoped_gap_allows_late_listing_symbol():
    # Symbol lists at 02:00 (no bars before that) but is fully covered through the
    # window end — a multi-symbol backtest must not crash on its later start date.
    late_listed = pd.DataFrame(
        {"open": [1.0, 1.0], "high": [1.0, 1.0], "low": [1.0, 1.0],
         "close": [10.0, 11.0], "vol": [1.0, 1.0]},
        index=pd.DatetimeIndex(["2024-04-29T02:00:00", "2024-04-29T03:00:00"]),
    )

    data_loader._raise_on_venue_gap(
        late_listed,
        inst_id="CC-USDT-SWAP",
        bar="1H",
        start_dt=pd.Timestamp("2024-04-29T00:00:00Z").to_pydatetime(),
        end_dt=pd.Timestamp("2024-04-29T04:00:00Z").to_pydatetime(),
        exchange="binance",
    )


def test_venue_scoped_gap_raises_on_sparse_internal_holes():
    # Listed at 00:00 but only 1 of 10 expected bars present -> genuine data gap.
    sparse = pd.DataFrame(
        {"open": [1.0], "high": [1.0], "low": [1.0], "close": [10.0], "vol": [1.0]},
        index=pd.DatetimeIndex(["2024-04-29T00:00:00"]),
    )

    with pytest.raises(ValueError, match="No cross-venue fallback is allowed"):
        data_loader._raise_on_venue_gap(
            sparse,
            inst_id="CC-USDT-SWAP",
            bar="1H",
            start_dt=pd.Timestamp("2024-04-29T00:00:00Z").to_pydatetime(),
            end_dt=pd.Timestamp("2024-04-29T10:00:00Z").to_pydatetime(),
            exchange="binance",
        )


def test_replay_l1_loader_passes_exchange_to_candle_loader(monkeypatch):
    calls = []

    def fake_load_candles(
        inst_id,
        *,
        bar,
        data_dir,
        start,
        end,
        backend,
        dsn,
        exchange,
    ):
        calls.append((inst_id, backend, dsn, exchange))
        return pd.DataFrame(
            {"open": [1.0], "high": [1.0], "low": [1.0], "close": [10_000.0], "vol": [1.0]},
            index=pd.DatetimeIndex(["2024-01-01T00:00:00"]),
        )

    monkeypatch.setattr(replay, "load_ohlcv_candles", fake_load_candles)

    loaded = replay.load_l1_books(
        "BTC-USDT-SWAP",
        backend="postgres",
        dsn="postgresql://unit",
        exchange="binance",
    )

    assert not loaded.empty
    assert calls == [("BTC-USDT-SWAP", "postgres", "postgresql://unit", "binance")]


def test_replay_l1_loader_uses_same_venue_fallback_after_primary_venue_gap(monkeypatch):
    calls = []

    def fake_load_candles(
        inst_id,
        *,
        bar,
        data_dir,
        start,
        end,
        backend,
        dsn,
        exchange,
    ):
        calls.append((inst_id, backend, dsn, exchange))
        if inst_id == "BTC-USDT":
            raise ValueError(
                "Venue-scoped candle gap for BTC-USDT 1H exchange='binance': "
                "expected 2 bars, found 0. No cross-venue fallback is allowed."
            )
        return pd.DataFrame(
            {"open": [1.0], "high": [1.0], "low": [1.0], "close": [10_000.0], "vol": [1.0]},
            index=pd.DatetimeIndex(["2024-01-01T00:00:00"]),
        )

    monkeypatch.setattr(replay, "load_ohlcv_candles", fake_load_candles)

    loaded = replay.load_l1_books(
        "BTC-USDT",
        fallback_inst_id="BTC-USDT-SWAP",
        backend="postgres",
        dsn="postgresql://unit",
        exchange="binance",
    )

    assert not loaded.empty
    assert loaded.iloc[0]["inst_id"] == "BTC-USDT"
    assert calls == [
        ("BTC-USDT", "postgres", "postgresql://unit", "binance"),
        ("BTC-USDT-SWAP", "postgres", "postgresql://unit", "binance"),
    ]


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
