from __future__ import annotations

import json

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


@pytest.mark.asyncio
async def test_backtest_run_passes_execution_profile_to_subprocess(client, monkeypatch, tmp_path):
    from okx_quant.api import routes_backtest

    seen_cmd = {}

    class FakeProc:
        returncode = 0
        stdout = iter(["PROGRESS:50:unit\n"])
        stderr = iter([])

        def wait(self):
            return 0

    def fake_popen(cmd, **kwargs):
        seen_cmd["cmd"] = cmd
        run_id = cmd[cmd.index("--run-id") + 1]
        out_dir = tmp_path / "results" / f"{run_id}_strategy_fill"
        out_dir.mkdir(parents=True, exist_ok=True)
        (tmp_path / "results" / f"{run_id}_execution_comparison.json").write_text(
            json.dumps({
                "strategy_fill_run_id": f"{run_id}_strategy_fill",
                "realistic_execution_run_id": f"{run_id}_realistic_execution",
            }),
            encoding="utf-8",
        )
        (out_dir / "result.json").write_text(
            json.dumps({
                "run_id": f"{run_id}_strategy_fill",
                "metrics": {},
                "validation": {"execution_profile": "strategy_fill"},
            }),
            encoding="utf-8",
        )
        return FakeProc()

    monkeypatch.setattr(routes_backtest.subprocess, "Popen", fake_popen)

    response = await client.post(
        "/api/backtest/run",
        json={
            "strategy": "ma_crossover",
            "symbols": ["BTC-USDT-SWAP"],
            "bar": "1H",
            "start": "2024-01-01",
            "end": "2024-01-02",
            "execution_profile": "dual_output",
        },
    )

    assert response.status_code == 200
    job_id = response.json()["job_id"]
    status = await client.get(f"/api/backtest/run/status/{job_id}")
    payload = status.json()
    assert payload["status"] == "done"
    assert payload["execution_profile"] == "dual_output"
    assert payload["run_id"].endswith("_strategy_fill")
    assert "--execution-profile" in seen_cmd["cmd"]
    assert seen_cmd["cmd"][seen_cmd["cmd"].index("--execution-profile") + 1] == "dual_output"
