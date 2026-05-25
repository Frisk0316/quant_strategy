from __future__ import annotations

import httpx
import pytest

from okx_quant.api.server import create_app
from okx_quant.api.state import EngineState
from okx_quant.execution.order_manager import OrderManager
from okx_quant.execution.rate_limiter import RateLimiter
from okx_quant.portfolio.positions import PositionLedger
from okx_quant.risk.circuit_breaker import CircuitBreaker
from okx_quant.risk.drawdown_tracker import DrawdownTracker
from okx_quant.risk.risk_guard import RiskGuard


@pytest.fixture
def api_app(tmp_path, filled_broker):
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "index.html").write_text("<html></html>", encoding="utf-8")
    results = tmp_path / "results"
    results.mkdir()
    ledger = PositionLedger(initial_equity=1_000.0)
    tracker = DrawdownTracker()
    tracker.set_initial_equity(1_000.0)
    risk = RiskGuard(lambda: ledger.get_equity(), tracker)
    state = EngineState(
        positions=ledger,
        dd_tracker=tracker,
        risk_guard=risk,
        order_manager=OrderManager(filled_broker, RateLimiter()),
        circuit_breaker=CircuitBreaker(),
        mode="demo",
        strategy_count=1,
    )
    return create_app(state=state, results_dir=results, frontend_dir=frontend)


@pytest.fixture
async def client(api_app):
    transport = httpx.ASGITransport(app=api_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_live_status_endpoint(client):
    response = await client.get("/api/live/status")
    assert response.status_code == 200
    assert response.json()["mode"] == "demo"


@pytest.mark.asyncio
async def test_live_risk_endpoint(client):
    response = await client.get("/api/live/risk")
    assert response.status_code == 200
    assert response.json()["equity_usd"] == 1_000.0


@pytest.mark.asyncio
async def test_config_risk_endpoint(client):
    response = await client.get("/api/config/risk")
    assert response.status_code == 200
    assert "risk" in response.json()


@pytest.mark.asyncio
async def test_backtest_runs_endpoint(client):
    response = await client.get("/api/backtest/runs")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_parameter_sweep_endpoint_marks_job_done(client, monkeypatch):
    from okx_quant.api import routes_backtest

    seen_kwargs = {}

    def fake_run_parameter_sweep(**kwargs):
        seen_kwargs.update(kwargs)
        progress_callback = kwargs.get("progress_callback")
        if progress_callback:
            progress_callback({
                "progress": 55,
                "message": "Screened parameter set 1/1",
                "completed_trials": 1,
                "total_trials": 1,
                "elapsed_seconds": 0.1,
                "estimated_remaining_seconds": 0.0,
            })
        return {
            "sweep_id": kwargs["sweep_id"],
            "artifacts": {"summary_json": "results/parameter_sweeps/fake.json"},
            "top_results": [{"rank": 1, "trial": 1, "params": {"fast_window": 7, "slow_window": 21}}],
            "completed_count": 1,
            "failed_count": 0,
            "skipped_count": 0,
            "finalist_results": [],
            "elapsed_seconds": 0.1,
        }

    monkeypatch.setattr(routes_backtest, "run_parameter_sweep", fake_run_parameter_sweep)

    response = await client.post(
        "/api/backtest/sweep",
        json={
            "strategy": "ma_crossover",
            "symbols": ["BTC-USDT-SWAP"],
            "bar": "1H",
            "start": "2024-01-01",
            "end": "2024-01-02",
            "parameter_grid": {"fast_window": [7], "slow_window": [21]},
            "fill_all_signals": True,
            "run_finalists": False,
        },
    )

    assert response.status_code == 200
    job_id = response.json()["job_id"]
    status = await client.get(f"/api/backtest/sweep/status/{job_id}")
    payload = status.json()
    assert payload["status"] == "done"
    assert payload["progress"] == 100
    assert payload["completed_count"] == 1
    assert payload["finished_at"]
    assert seen_kwargs["fill_all_signals"] is True
    assert "idealized_fill" in payload["warnings"]
