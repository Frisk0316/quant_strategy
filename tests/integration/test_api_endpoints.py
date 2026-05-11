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
