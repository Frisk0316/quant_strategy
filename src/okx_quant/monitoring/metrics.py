"""
Prometheus metrics for Grafana dashboard.
Tracks: orders_sent, fills, api_errors, ws_reconnects, rolling_sharpe, equity, drawdown.
"""
from __future__ import annotations

try:
    from prometheus_client import Counter, Gauge, Histogram, start_http_server

    ORDERS_SENT = Counter("okx_orders_sent_total", "Total orders submitted", ["strategy", "side"])
    FILLS = Counter("okx_fills_total", "Total fills", ["strategy", "side"])
    API_ERRORS = Counter("okx_api_errors_total", "REST API errors", ["endpoint"])
    WS_RECONNECTS = Counter("okx_ws_reconnects_total", "WebSocket reconnects", ["channel"])
    EQUITY = Gauge("okx_equity_usd", "Current account equity in USD")
    DRAWDOWN = Gauge("okx_drawdown_pct", "Current drawdown percentage")
    DAILY_PNL = Gauge("okx_daily_pnl_usd", "Daily PnL in USD")
    LATENCY = Histogram(
        "okx_order_latency_ms",
        "Order submission latency in ms",
        buckets=[1, 5, 10, 25, 50, 100, 200, 500, 1000],
    )
    VPIN = Gauge("okx_vpin_cdf", "Current VPIN CDF value", ["inst_id"])
    INVENTORY = Gauge("okx_inventory_contracts", "Current inventory in contracts", ["strategy", "inst_id"])

    def start_metrics_server(port: int = 8000) -> None:
        start_http_server(port)

    PROMETHEUS_AVAILABLE = True

except ImportError:
    PROMETHEUS_AVAILABLE = False

    # Stub implementations — no-ops when prometheus_client not installed
    class _Stub:
        def inc(self, *a, **k): pass
        def dec(self, *a, **k): pass
        def set(self, *a, **k): pass
        def observe(self, *a, **k): pass
        def labels(self, *a, **k): return self

    ORDERS_SENT = _Stub()
    FILLS = _Stub()
    API_ERRORS = _Stub()
    WS_RECONNECTS = _Stub()
    EQUITY = _Stub()
    DRAWDOWN = _Stub()
    DAILY_PNL = _Stub()
    LATENCY = _Stub()
    VPIN = _Stub()
    INVENTORY = _Stub()

    def start_metrics_server(port: int = 8000) -> None:
        pass
