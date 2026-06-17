from okx_quant.api.routes_backtest import RunBacktestRequest, _normalize_exchange


def test_run_backtest_request_defaults_exchange_to_binance():
    req = RunBacktestRequest(strategy="funding_carry")
    assert req.exchange == "binance"
    assert _normalize_exchange(req.exchange) == "binance"


def test_run_backtest_request_accepts_okx_exchange():
    req = RunBacktestRequest(strategy="funding_carry", exchange="okx")
    assert _normalize_exchange(req.exchange) == "okx"
