from __future__ import annotations

from okx_quant.risk.circuit_breaker import CircuitBreaker


def test_ws_reconnect_exact_threshold_does_not_trip(monkeypatch):
    now = 1_000.0
    monkeypatch.setattr("okx_quant.risk.circuit_breaker.time.time", lambda: now)
    breaker = CircuitBreaker(ws_reconnect_threshold=3, ws_window_secs=60)

    for _ in range(3):
        breaker.record_ws_reconnect()

    assert breaker.tripped is False


def test_ws_reconnect_over_threshold_trips(monkeypatch):
    now = 1_000.0
    monkeypatch.setattr("okx_quant.risk.circuit_breaker.time.time", lambda: now)
    breaker = CircuitBreaker(ws_reconnect_threshold=3, ws_window_secs=60)

    for _ in range(4):
        breaker.record_ws_reconnect()

    assert breaker.tripped is True
    assert "WS reconnect" in breaker.trip_reason


def test_ws_reconnect_outside_window_does_not_trip(monkeypatch):
    times = iter([1_000.0, 1_001.0, 1_002.0, 1_100.0])
    monkeypatch.setattr("okx_quant.risk.circuit_breaker.time.time", lambda: next(times))
    breaker = CircuitBreaker(ws_reconnect_threshold=3, ws_window_secs=60)

    for _ in range(4):
        breaker.record_ws_reconnect()

    assert breaker.tripped is False
