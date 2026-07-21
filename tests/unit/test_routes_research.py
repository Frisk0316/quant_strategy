from __future__ import annotations

import shutil
import threading
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from okx_quant.api import routes_research


ACTION_HEADERS = {"X-Research-Action": "1"}


def _app(project_root: Path, *, actions_enabled: bool) -> FastAPI:
    app = FastAPI()
    app.include_router(
        routes_research.make_research_router(project_root, actions_enabled=actions_enabled),
        prefix="/api/research",
    )
    return app


@pytest.fixture
def project_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    config = tmp_path / "config"
    config.mkdir()
    shutil.copy(Path("config/h014_shadow.yaml"), config / "h014_shadow.yaml")
    (config / "settings.yaml").write_text(
        "storage:\n  timescale_dsn: postgresql://unused\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.mark.asyncio
async def test_h014_status_is_shadow_only_and_reports_empty_journal(project_root: Path):
    transport = httpx.ASGITransport(app=_app(project_root, actions_enabled=True))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/research/h014")

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "shadow_only"
    assert payload["actions_enabled"] is True
    assert payload["report"]["exit_criteria"]["live_trading_approved"] is False


@pytest.mark.asyncio
async def test_research_mutations_are_loopback_gated(project_root: Path):
    transport = httpx.ASGITransport(app=_app(project_root, actions_enabled=False))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        h014 = await client.post("/api/research/h014/run")
        h009 = await client.post(
            "/api/research/h009/sweep",
            json={"lookback_days": [7], "quantiles": [0.2]},
        )

    assert h014.status_code == 403
    assert h009.status_code == 403


@pytest.mark.asyncio
async def test_h014_run_reuses_public_shadow_runner(project_root: Path, monkeypatch: pytest.MonkeyPatch):
    request_thread = threading.get_ident()
    worker_threads = []

    async def fake_run(config, dsn):
        worker_threads.append(threading.get_ident())
        assert config["journal_path"].startswith(str(project_root))
        assert dsn == "postgresql://test"
        return {"order_capability": False, "credentials_used": False, "intents": []}

    monkeypatch.setattr(routes_research, "run_h014_cycle", fake_run)
    monkeypatch.setattr(routes_research, "resolve_dsn", lambda _path: "postgresql://test")
    transport = httpx.ASGITransport(app=_app(project_root, actions_enabled=True))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/research/h014/run", headers=ACTION_HEADERS)

    assert response.status_code == 200
    assert response.json()["order_capability"] is False
    assert response.json()["report"]["exit_criteria"]["live_trading_approved"] is False
    assert worker_threads and worker_threads[0] != request_thread


@pytest.mark.asyncio
async def test_research_mutations_require_local_action_header(project_root: Path):
    transport = httpx.ASGITransport(app=_app(project_root, actions_enabled=True))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        h014 = await client.post("/api/research/h014/run")
        h009 = await client.post(
            "/api/research/h009/sweep",
            json={"lookback_days": [7], "quantiles": [0.2]},
        )

    assert h014.status_code == 403
    assert h009.status_code == 403


@pytest.mark.asyncio
async def test_h009_sweep_records_trials_and_writes_new_artifact(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from scripts import run_funding_xs_dispersion_checkpoint as runner

    seen = []

    def fake_screen(ctx):
        seen.append(ctx)
        return {
            "grid_size_this_run": 1,
            "known_family_n_trials_lower_bound": ctx["prior_family_n_trials"] + 1,
            "results": [{"rank": 1, "lookback_days": 7, "quantile": 0.2, "sharpe": 1.0}],
            "warnings": ["research only"],
        }

    monkeypatch.setattr(runner, "run_funding_xs_dispersion_screen", fake_screen)
    transport = httpx.ASGITransport(app=_app(project_root, actions_enabled=True))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        queued = await client.post(
            "/api/research/h009/sweep",
            json={"lookback_days": [7], "quantiles": [0.2]},
            headers=ACTION_HEADERS,
        )
        job_id = queued.json()["job_id"]
        status = await client.get(f"/api/research/h009/sweep/{job_id}")
        queued_again = await client.post(
            "/api/research/h009/sweep",
            json={"lookback_days": [14], "quantiles": [0.3]},
            headers=ACTION_HEADERS,
        )
        second_status = await client.get(
            f"/api/research/h009/sweep/{queued_again.json()['job_id']}"
        )

    payload = status.json()
    assert payload["status"] == "done"
    assert payload["known_family_n_trials_lower_bound"] == 5
    assert second_status.json()["known_family_n_trials_lower_bound"] == 6
    assert [ctx["prior_family_n_trials"] for ctx in seen] == [4, 5]
    assert all(ctx["dsn"] == "postgresql://unused" for ctx in seen)
    assert seen[0]["grid"] == {"lookback_days": [7], "quantile": [0.2]}
    assert Path(payload["artifact"]).exists()


@pytest.mark.asyncio
async def test_h009_sweep_rejects_more_than_25_combinations(project_root: Path):
    transport = httpx.ASGITransport(app=_app(project_root, actions_enabled=True))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/research/h009/sweep",
            json={
                "lookback_days": [1, 2, 3, 4, 5, 6],
                "quantiles": [0.1, 0.2, 0.3, 0.4, 0.45],
            },
            headers=ACTION_HEADERS,
        )

    assert response.status_code == 422
