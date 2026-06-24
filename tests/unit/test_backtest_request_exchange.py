import pytest
from fastapi import HTTPException

from okx_quant.api.routes_backtest import (
    RunBacktestRequest,
    _normalize_backtest_request,
    _normalize_exchange,
    _validate_backtest_request,
)


def test_run_backtest_request_defaults_exchange_to_binance():
    req = RunBacktestRequest(strategy="funding_carry")
    assert req.exchange == "binance"
    assert _normalize_exchange(req.exchange) == "binance"


def test_run_backtest_request_accepts_okx_exchange():
    req = RunBacktestRequest(strategy="funding_carry", exchange="okx")
    assert _normalize_exchange(req.exchange) == "okx"


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
