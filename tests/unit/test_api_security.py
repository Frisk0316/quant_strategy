from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from okx_quant.api import routes_backtest
from okx_quant.api.server import run_api_server
from scripts import backtest_ohlcv_rotation
from scripts import run_server


@pytest.mark.asyncio
async def test_engine_server_rejects_remote_bind_without_api_key(tmp_path, monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="API_KEY is required"):
        await run_api_server(None, tmp_path, tmp_path, host="0.0.0.0")  # type: ignore[arg-type]


def test_standalone_sensitive_routes_use_api_key(tmp_path, monkeypatch):
    monkeypatch.setenv("API_KEY", "unit-key")
    app = run_server.create_app(tmp_path, Path("frontend"))
    client = TestClient(app)

    assert client.get("/api/backtest/runs").status_code == 401
    assert client.get("/api/backtest/runs", headers={"X-API-Key": "unit-key"}).status_code == 200


def test_standalone_remote_mode_disables_api_docs(tmp_path):
    app = run_server.create_app(tmp_path, Path("frontend"), docs_enabled=False)
    client = TestClient(app)

    assert client.get("/api/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_standalone_remote_bind_requires_flag_and_api_key(monkeypatch):
    monkeypatch.setattr("sys.argv", ["run_server.py", "--host", "0.0.0.0"])
    with pytest.raises(SystemExit):
        run_server.main()

    monkeypatch.setattr(
        "sys.argv",
        ["run_server.py", "--host", "0.0.0.0", "--allow-remote"],
    )
    monkeypatch.delenv("API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="API_KEY is required"):
        run_server.main()


def test_rotation_job_keeps_dsn_out_of_command(tmp_path, monkeypatch):
    dsn = "postgresql://quant:top-secret@db:5432/quant"
    captured: dict = {}

    class FakeProcess:
        returncode = 1

        def __init__(self, cmd, **kwargs):
            captured["cmd"] = cmd
            captured["env"] = kwargs["env"]

        def communicate(self):
            return "", "stopped"

    monkeypatch.setattr(routes_backtest, "_resolve_candle_backend", lambda _exchange: ("postgres", dsn))
    monkeypatch.setattr(routes_backtest.subprocess, "Popen", FakeProcess)
    routes_backtest._run_jobs["job"] = {}
    req = routes_backtest.RunBacktestRequest(
        strategy="ohlcv_rotation",
        exchange="okx",
        universe=[],
    )

    routes_backtest._run_ohlcv_rotation_job("job", req, "run", tmp_path)

    assert "--dsn" not in captured["cmd"]
    assert "top-secret" not in routes_backtest._run_jobs["job"]["command"]
    assert captured["env"]["DATABASE_URL"] == dsn


@pytest.mark.parametrize(("exchange_args", "expected_backend"), [([], "postgres"), (["--exchange", "okx"], "market")])
def test_rotation_runner_reads_database_url(monkeypatch, exchange_args, expected_backend):
    dsn = "postgresql://quant:top-secret@db:5432/quant"
    captured: dict = {}

    monkeypatch.setenv("DATABASE_URL", dsn)
    monkeypatch.setattr(
        "sys.argv",
        [
            "backtest_ohlcv_rotation.py",
            "--backend",
            "postgres",
            "--universe",
            "BTC-USDT-SWAP",
            *exchange_args,
        ],
    )

    def fake_load_candles(**kwargs):
        captured.update(kwargs)
        return backtest_ohlcv_rotation.pd.DataFrame()

    monkeypatch.setattr(backtest_ohlcv_rotation, "load_candles", fake_load_candles)

    with pytest.raises(SystemExit, match="benchmark .* could not be loaded"):
        backtest_ohlcv_rotation.main()

    assert captured["backend"] == expected_backend
    assert captured["dsn"] == dsn


def test_compose_requires_secrets_and_binds_app_to_loopback():
    compose = Path("docker/docker-compose.yml").read_text(encoding="utf-8")

    assert '"127.0.0.1:8080:8080"' in compose
    assert "${API_KEY:?" in compose
    assert "${TIMESCALE_PASSWORD:?" in compose
    assert "${GRAFANA_PASSWORD:?" in compose
