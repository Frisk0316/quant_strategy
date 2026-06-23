from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

import okx_quant.api.routes_data as routes_data


def test_coverage_exchange_label_and_mixed_flag():
    # Single source -> that exchange, not mixed.
    assert routes_data._coverage_exchange(["binance"]) == ("binance", False)
    # Multiple sources -> joined + mixed (Binance-preferred fill with OKX gaps).
    assert routes_data._coverage_exchange(["okx", "binance"]) == ("binance+okx", True)
    # Empty / null -> no label.
    assert routes_data._coverage_exchange(None) == (None, False)
    assert routes_data._coverage_exchange([None]) == (None, False)


def test_pair_delete_statements_order_and_keys():
    stmts = routes_data._pair_delete_statements("MATIC-USDT-SWAP")
    tables = [sql.split("FROM")[1].split()[0] for sql, _ in stmts]

    assert tables.index("market_klines") < tables.index("market_instruments")
    assert tables.index("market_funding_rates") < tables.index("market_instruments")
    for table in (
        "canonical_candles",
        "raw_candles",
        "funding_rates",
        "instrument_bars",
        "instruments",
        "market_instruments",
    ):
        assert table in tables
    for _sql, params in stmts:
        assert params == ["MATIC-USDT-SWAP"]


def test_active_job_for_symbol_detects_running_job():
    routes_data._jobs.clear()
    routes_data._jobs["j1"] = {
        "job_id": "j1",
        "status": "running",
        "symbols": ["MATIC-USDT-SWAP"],
    }

    assert routes_data._active_job_for_symbol("MATIC-USDT-SWAP") is True
    assert routes_data._active_job_for_symbol("BTC-USDT-SWAP") is False
    routes_data._jobs["j1"]["status"] = "done"
    assert routes_data._active_job_for_symbol("MATIC-USDT-SWAP") is False


def test_delete_pair_route_rejects_active_fetch_job():
    routes_data._jobs.clear()
    routes_data._jobs["j1"] = {
        "job_id": "j1",
        "status": "queued",
        "symbols": ["MATIC-USDT-SWAP"],
    }
    app = FastAPI()
    app.include_router(routes_data.make_data_router("postgresql://unused"), prefix="/api/data")

    response = TestClient(app).delete("/api/data/pairs/MATIC-USDT-SWAP")

    assert response.status_code == 409
    assert "active fetch job" in response.json()["detail"]


def test_delete_pair_route_returns_db_and_parquet_counts(monkeypatch, tmp_path):
    import asyncpg

    routes_data._jobs.clear()
    calls = []

    class FakeTransaction:
        async def __aenter__(self):
            return None

        async def __aexit__(self, *_args):
            return None

    class FakeConn:
        def transaction(self):
            return FakeTransaction()

        async def execute(self, sql, *params):
            calls.append((sql, params))
            return "DELETE 2"

        async def close(self):
            return None

    async def fake_connect(dsn):
        assert dsn == "postgresql://unused"
        return FakeConn()

    parquet_dir = tmp_path / "data" / "ticks" / "MATIC_USDT_SWAP"
    parquet_dir.mkdir(parents=True)
    (parquet_dir / "candles_1m.parquet").write_bytes(b"x")
    monkeypatch.setattr(asyncpg, "connect", fake_connect)
    monkeypatch.setattr(routes_data, "_project_root_path", lambda: tmp_path)
    app = FastAPI()
    app.include_router(routes_data.make_data_router("postgresql://unused"), prefix="/api/data")

    response = TestClient(app).delete("/api/data/pairs/MATIC-USDT-SWAP")

    assert response.status_code == 200
    payload = response.json()
    assert payload["deleted"]["market_klines"] == 2
    assert payload["deleted"]["instruments"] == 2
    assert payload["parquet_removed"] is True
    assert payload["parquet_error"] is None
    assert len(calls) == len(routes_data._pair_delete_statements("MATIC-USDT-SWAP"))


def test_remove_pair_parquet_deletes_inst_directory(tmp_path):
    inst_dir = tmp_path / "MATIC_USDT_SWAP"
    inst_dir.mkdir()
    (inst_dir / "candles_1m.parquet").write_bytes(b"x")

    removed, error = routes_data._remove_pair_parquet("MATIC-USDT-SWAP", tmp_path)

    assert removed is True
    assert error is None
    assert not inst_dir.exists()


def test_remove_pair_parquet_missing_dir_is_non_fatal(tmp_path):
    removed, error = routes_data._remove_pair_parquet("GHOST-USDT-SWAP", tmp_path)

    assert removed is False
    assert error is None
