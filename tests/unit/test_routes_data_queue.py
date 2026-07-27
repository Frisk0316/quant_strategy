from __future__ import annotations

import asyncio

import pytest

import okx_quant.api.routes_data as routes_data
from okx_quant.api.routes_data import FetchRequest

_REQ = FetchRequest(
    exchange="binance",
    symbols=["BTC-USDT-SWAP"],
    bar="1m",
    start="2024-01-01",
    end="2024-01-02",
)


@pytest.fixture(autouse=True)
def _reset_fetch_state():
    routes_data._jobs.clear()
    routes_data._fetch_lock = asyncio.Lock()
    yield
    routes_data._jobs.clear()
    routes_data._fetch_lock = asyncio.Lock()


def _seed_job(job_id: str) -> None:
    routes_data._jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "symbols": ["BTC-USDT-SWAP"],
        "progress": 0,
    }


def test_deribit_dataset_ids_include_native_and_derived_volatility():
    assert routes_data._deribit_dataset_ids(["BTC"]) == [
        "dvol_deribit_btc",
        "dvol_deribit_btc_1h",
        "hv_deribit_btc_1h",
        "rv30_deribit_btc_1h",
        "optsurf_deribit_btc",
    ]


@pytest.mark.asyncio
async def test_deribit_fetch_reuses_external_refresh(monkeypatch):
    req = FetchRequest(
        exchange="deribit",
        symbols=["BTC"],
        bar="1H",
        start="2021-01-01",
        end="2021-01-02",
    )
    _seed_job("deribit")

    async def fake_refresh(db_dsn, dataset_ids, start, end):
        assert db_dsn == "postgresql://unused"
        assert dataset_ids == routes_data._deribit_dataset_ids(["BTC"])
        return {
            "status": "done",
            "datasets": [
                {"dataset_id": dataset_id, "status": "success", "rows_fetched": 1}
                for dataset_id in dataset_ids
            ],
        }

    monkeypatch.setattr(routes_data, "_refresh_external_datasets", fake_refresh)

    await routes_data._run_fetch_body("deribit", req, "postgresql://unused")

    assert routes_data._jobs["deribit"]["status"] == "done"
    assert len(routes_data._jobs["deribit"]["results"]) == 5


@pytest.mark.asyncio
async def test_second_fetch_waits_as_queued_until_first_releases(monkeypatch):
    gate = asyncio.Event()
    started: list[str] = []

    async def fake_body(job_id, req, db_dsn):
        started.append(job_id)
        await gate.wait()

    monkeypatch.setattr(routes_data, "_run_fetch_body", fake_body)
    _seed_job("job_a")
    _seed_job("job_b")

    ta = asyncio.create_task(routes_data._run_fetch("job_a", _REQ, "postgresql://unused"))
    tb = asyncio.create_task(routes_data._run_fetch("job_b", _REQ, "postgresql://unused"))
    await asyncio.sleep(0.05)

    assert routes_data._jobs["job_a"]["status"] == "running"
    assert routes_data._jobs["job_b"]["status"] == "queued"
    assert started == ["job_a"]

    gate.set()
    await asyncio.gather(ta, tb)
    assert started == ["job_a", "job_b"]


@pytest.mark.asyncio
async def test_cancel_while_queued_skips_execution(monkeypatch):
    gate = asyncio.Event()
    started: list[str] = []

    async def fake_body(job_id, req, db_dsn):
        started.append(job_id)
        await gate.wait()

    monkeypatch.setattr(routes_data, "_run_fetch_body", fake_body)
    _seed_job("job_a")
    _seed_job("job_b")

    ta = asyncio.create_task(routes_data._run_fetch("job_a", _REQ, "x"))
    tb = asyncio.create_task(routes_data._run_fetch("job_b", _REQ, "x"))
    await asyncio.sleep(0.05)

    routes_data._jobs["job_b"]["cancel_requested"] = True
    gate.set()
    await asyncio.gather(ta, tb)

    assert "job_b" not in started
    assert routes_data._jobs["job_b"]["status"] == "cancelled"
