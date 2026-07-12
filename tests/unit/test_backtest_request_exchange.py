from types import SimpleNamespace
from urllib.parse import quote

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from okx_quant.api.routes_backtest import (
    ParameterSweepRequest,
    RunBacktestRequest,
    _validate_parameter_sweep_request,
    _normalize_backtest_request,
    _normalize_exchange,
    _validate_backtest_request,
    make_backtest_router,
)


def test_run_backtest_request_uses_configured_exchange_when_omitted():
    req = RunBacktestRequest(strategy="funding_carry")
    assert req.exchange is None
    assert _normalize_exchange(req.exchange) == "binance"


@pytest.mark.parametrize("exchange", [None, "", "   "])
def test_omitted_or_blank_exchange_uses_non_binance_config_primary(monkeypatch, exchange):
    config = SimpleNamespace(storage=SimpleNamespace(primary_exchange="okx"))
    monkeypatch.setattr("okx_quant.core.config.load_config", lambda **_: config)

    assert _normalize_exchange(exchange) == "okx"


@pytest.mark.parametrize("exchange", ["binance", "okx", "bybit", "coinbase", "kraken"])
def test_run_backtest_request_accepts_supported_exchange(exchange):
    req = RunBacktestRequest(strategy="funding_carry", exchange=exchange.upper())
    assert _normalize_exchange(req.exchange) == exchange


def test_unknown_exchange_fails_closed():
    with pytest.raises(HTTPException) as exc:
        _normalize_exchange("typo-venue")

    assert exc.value.status_code == 400


def test_request_validators_store_the_normalized_exchange():
    run = RunBacktestRequest(strategy="funding_carry", exchange=" OKX ")
    sweep = ParameterSweepRequest(strategy="ma_crossover", symbols=["BTC-USDT-SWAP"], exchange="BYBIT")

    _validate_backtest_request(run)
    _validate_parameter_sweep_request(sweep)

    assert run.exchange == "okx"
    assert sweep.exchange == "bybit"


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/api/backtest/run", {"strategy": "ma_crossover", "symbols": ["BTC-USDT-SWAP"]}),
        ("/api/backtest/sweep", {"strategy": "ma_crossover", "symbols": ["BTC-USDT-SWAP"]}),
    ],
)
def test_backtest_api_rejects_unknown_exchange_before_queueing(tmp_path, path, payload):
    app = FastAPI()
    app.include_router(make_backtest_router(tmp_path), prefix="/api/backtest")
    client = TestClient(app)
    before = client.get(f"{path}/jobs").json()

    response = client.post(path, json={**payload, "exchange": "typo-venue"})

    assert response.status_code == 400
    assert "exchange must be one of" in response.json()["detail"]
    assert client.get(f"{path}/jobs").json() == before


@pytest.mark.parametrize(
    ("path", "id_field"),
    [
        ("/api/backtest/run", "run_id"),
        ("/api/backtest/sweep", "sweep_id"),
    ],
)
@pytest.mark.parametrize(
    "unsafe_id",
    ["", ".", "..", "../outside", "..\\outside", "/tmp/outside", "C:outside", "x" * 129, "..∕outside"],
)
def test_backtest_api_rejects_unsafe_write_id_before_io(tmp_path, path, id_field, unsafe_id):
    app = FastAPI()
    app.include_router(make_backtest_router(tmp_path), prefix="/api/backtest")
    client = TestClient(app)
    before = client.get(f"{path}/jobs").json()

    write = client.post(
        path,
        json={
            "strategy": "ma_crossover",
            "symbols": ["BTC-USDT-SWAP"],
            id_field: unsafe_id,
        },
    )

    assert write.status_code == 400
    assert client.get(f"{path}/jobs").json() == before
    assert not (tmp_path.parent / "outside").exists()


@pytest.mark.parametrize(
    "unsafe_id",
    ["", ".", "..", "../outside", "..\\outside", "/tmp/outside", "C:outside", "x" * 129, "..∕outside"],
)
def test_backtest_api_read_does_not_serve_unsafe_id(tmp_path, unsafe_id):
    app = FastAPI()
    app.include_router(make_backtest_router(tmp_path), prefix="/api/backtest")

    response = TestClient(app).get(f"/api/backtest/{quote(unsafe_id, safe='')}")

    assert response.status_code in {400, 404}


def test_backtest_request_defaults_execution_profile_to_strategy_fill():
    req = RunBacktestRequest(strategy="ma_crossover", symbols=["BTC-USDT-SWAP"])

    normalized = _normalize_backtest_request(req)
    _validate_backtest_request(normalized)

    assert normalized.execution_profile == "strategy_fill"


def test_backtest_request_accepts_public_dual_output_profile():
    req = RunBacktestRequest(
        strategy="ma_crossover",
        symbols=["BTC-USDT-SWAP"],
        execution_profile="dual_output",
    )

    normalized = _normalize_backtest_request(req)
    _validate_backtest_request(normalized)

    assert normalized.execution_profile == "dual_output"


def test_backtest_request_rejects_public_realistic_execution_profile():
    req = RunBacktestRequest(
        strategy="ma_crossover",
        symbols=["BTC-USDT-SWAP"],
        execution_profile="realistic_execution",
    )

    with pytest.raises(HTTPException) as exc:
        _validate_backtest_request(req)

    assert exc.value.status_code == 400
    assert "execution profile" in str(exc.value.detail)
