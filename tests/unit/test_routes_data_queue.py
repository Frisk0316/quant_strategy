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
