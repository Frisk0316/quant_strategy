from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from okx_quant.api import routes_backtest
from okx_quant.api.server import create_app, run_api_server
from scripts import backtest_ohlcv_rotation
from scripts import run_server


def _engine_client(tmp_path: Path, *, host: str = "127.0.0.1") -> TestClient:
    frontend = tmp_path / "frontend"
    frontend.mkdir(exist_ok=True)
    (frontend / "index.html").write_text("<html></html>", encoding="utf-8")
    results = tmp_path / "results"
    results.mkdir(exist_ok=True)
    return TestClient(create_app(MagicMock(), results, frontend, host=host))


@pytest.mark.asyncio
async def test_engine_server_rejects_remote_bind_without_api_key(tmp_path, monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="API_KEY is required"):
        await run_api_server(None, tmp_path, tmp_path, host="0.0.0.0")  # type: ignore[arg-type]


def test_engine_manual_and_progress_routes_require_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("API_KEY", "unit-key")
    client = _engine_client(tmp_path)

    assert client.get("/api/manual").status_code == 401
    assert client.get("/api/progress").status_code == 401


def test_non_ascii_auth_header_returns_401(tmp_path, monkeypatch):
    monkeypatch.setenv("API_KEY", "unit-key")
    client = _engine_client(tmp_path)

    response = client.get("/api/manual", headers=[(b"x-api-key", b"\xff")])

    assert response.status_code == 401


def test_websocket_uses_protocol_header_not_query_string(tmp_path, monkeypatch):
    monkeypatch.setenv("API_KEY", "unit-key")
    client = _engine_client(tmp_path)

    with client.websocket_connect("/api/ws?api_key=unit-key") as websocket:
        with pytest.raises(WebSocketDisconnect) as rejected:
            websocket.receive_text()
    assert rejected.value.code == 4001

    with client.websocket_connect(
        "/api/ws",
        headers={"Sec-WebSocket-Protocol": "unit-key"},
    ):
        pass


def test_remote_websocket_without_api_key_closes_4001(tmp_path, monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    client = _engine_client(tmp_path, host="0.0.0.0")

    with client.websocket_connect("/api/ws") as websocket:
        with pytest.raises(WebSocketDisconnect) as rejected:
            websocket.receive_text()

    assert rejected.value.code == 4001


@pytest.mark.parametrize("origins", ["*", "dashboard.example.com"])
def test_credentialed_cors_rejects_wildcard_or_missing_scheme(tmp_path, monkeypatch, origins):
    monkeypatch.setenv("ALLOWED_ORIGINS", origins)

    with pytest.raises(RuntimeError, match="credentialed CORS origins"):
        _engine_client(tmp_path)


def test_cors_allows_only_dashboard_methods_and_headers(tmp_path, monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://dashboard.example.com")
    client = _engine_client(tmp_path)
    headers = {
        "Origin": "https://dashboard.example.com",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type, X-API-Key, X-Research-Action",
    }

    assert client.options("/api/live/status", headers=headers).status_code == 200
    assert client.options(
        "/api/live/status",
        headers={**headers, "Access-Control-Request-Method": "PATCH"},
    ).status_code == 400


def test_standalone_sensitive_routes_use_api_key(tmp_path, monkeypatch):
    monkeypatch.setenv("API_KEY", "unit-key")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(run_server, "_db_dsn", lambda: None)
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
