"""Smoke tests for frontend ES module MIME types."""

import pytest
from fastapi.testclient import TestClient

from okx_quant.api.server import create_app
from okx_quant.api.state import EngineState
from okx_quant.execution.order_manager import OrderManager
from okx_quant.execution.rate_limiter import RateLimiter
from okx_quant.portfolio.positions import PositionLedger
from okx_quant.risk.circuit_breaker import CircuitBreaker
from okx_quant.risk.drawdown_tracker import DrawdownTracker
from okx_quant.risk.risk_guard import RiskGuard


JAVASCRIPT_CONTENT_TYPES = ("application/javascript", "text/javascript")
INVALID_MODULE_CONTENT_TYPES = ("application/octet-stream", "text/plain", "text/html")


@pytest.fixture
def static_client(tmp_path, filled_broker):
    frontend_dir = tmp_path / "frontend"
    frontend_dir.mkdir()
    (frontend_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    (frontend_dir / "app.js").write_text("export const app = true;\n", encoding="utf-8")
    (frontend_dir / "app.jsx").write_text("export const legacy = true;\n", encoding="utf-8")

    results_dir = tmp_path / "results"
    results_dir.mkdir()

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
    app = create_app(state=state, results_dir=results_dir, frontend_dir=frontend_dir)
    return TestClient(app)


def _assert_javascript_mime(response):
    content_type = response.headers.get("content-type", "").split(";")[0].lower()

    assert response.status_code == 200
    assert content_type in JAVASCRIPT_CONTENT_TYPES
    assert content_type not in INVALID_MODULE_CONTENT_TYPES


def test_app_js_is_served_as_javascript_mime(static_client):
    response = static_client.get("/app.js")

    _assert_javascript_mime(response)


def test_legacy_jsx_is_served_as_javascript_mime_if_present(static_client):
    response = static_client.get("/app.jsx")

    _assert_javascript_mime(response)
