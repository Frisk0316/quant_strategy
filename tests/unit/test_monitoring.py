from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from okx_quant.monitoring import metrics
from okx_quant.monitoring.calibration_log import CalibrationLogger
from okx_quant.monitoring.telegram_alert import TelegramMonitor


class FakeTelegramClient:
    def __init__(self) -> None:
        self.posts: list[dict] = []

    async def post(self, url: str, json: dict) -> SimpleNamespace:
        self.posts.append({"url": url, "json": json})
        return SimpleNamespace(status_code=200)


@pytest.mark.asyncio
async def test_telegram_monitor_send_alert_posts_prefixed_message():
    monitor = TelegramMonitor(token="unit-token", chat_id="unit-chat")
    await monitor._client.aclose()
    fake_client = FakeTelegramClient()
    monitor._client = fake_client  # type: ignore[assignment]

    await monitor.send_alert("Risk threshold crossed", level="warning")

    assert len(fake_client.posts) == 1
    post = fake_client.posts[0]
    assert post["url"] == "https://api.telegram.org/botunit-token/sendMessage"
    assert post["json"]["chat_id"] == "unit-chat"
    assert "Risk threshold crossed" in post["json"]["text"]


class FakeDrawdownTracker:
    def current_drawdown(self) -> float:
        return 0.1234

    def daily_pnl(self) -> float:
        return -42.5


class FakeRiskGuard:
    def __init__(self) -> None:
        self.kill = False
        self.reset_called = False
        self.hard_stop_reason = None
        self._dd_tracker = FakeDrawdownTracker()

    def trigger_hard_stop(self, reason: str) -> None:
        self.kill = True
        self.hard_stop_reason = reason

    def reset(self) -> None:
        self.kill = False
        self.reset_called = True


class FakePositions:
    def get_equity(self) -> float:
        return 12345.67


@pytest.mark.asyncio
async def test_telegram_monitor_commands_use_risk_guard_and_positions():
    monitor = TelegramMonitor(token="unit-token", chat_id="unit-chat")
    await monitor._client.aclose()
    risk_guard = FakeRiskGuard()
    positions = FakePositions()
    alerts: list[tuple[str, str]] = []

    async def record_alert(message: str, level: str = "info") -> None:
        alerts.append((level, message))

    monitor.send_alert = record_alert  # type: ignore[method-assign]

    await monitor._handle_command("/kill", risk_guard, positions)
    await monitor._handle_command("/status", risk_guard, positions)
    await monitor._handle_command("/reset", risk_guard, positions)
    await monitor._handle_command("/help", risk_guard, positions)

    assert risk_guard.hard_stop_reason == "Telegram /kill command"
    assert risk_guard.reset_called is True
    assert [level for level, _message in alerts] == ["critical", "info", "warning", "info"]
    status = alerts[1][1]
    assert "Equity: $12345.67" in status
    assert "Drawdown: 12.34%" in status
    assert "Daily PnL: $-42.50" in status
    assert "Kill: True" in status
    assert "/kill" in alerts[3][1]


def test_metrics_handles_are_callable_without_starting_server():
    assert isinstance(metrics.PROMETHEUS_AVAILABLE, bool)

    metrics.ORDERS_SENT.labels(strategy="unit", side="buy").inc()
    metrics.FILLS.labels(strategy="unit", side="sell").inc()
    metrics.API_ERRORS.labels(endpoint="/unit").inc()
    metrics.WS_RECONNECTS.labels(channel="books").inc()
    metrics.EQUITY.set(1000.0)
    metrics.DRAWDOWN.set(0.05)
    metrics.DAILY_PNL.set(-12.5)
    metrics.LATENCY.observe(25.0)
    metrics.VPIN.labels(inst_id="BTC-USDT-SWAP").set(0.5)
    metrics.INVENTORY.labels(strategy="unit", inst_id="BTC-USDT-SWAP").set(2.0)


def test_calibration_logger_writes_jsonl_and_summary(tmp_path):
    logger = CalibrationLogger(tmp_path)

    logger.record_submit(
        cl_ord_id="mirror-1",
        inst_id="BTC-USDT-SWAP",
        side="buy",
        order_px=100.0,
        order_sz=2.0,
        submit_ts=1_000,
    )
    logger.record_fill(
        cl_ord_id="mirror-1",
        inst_id="BTC-USDT-SWAP",
        fill_px=100.5,
        fill_sz=2.0,
        fill_ts=1_250,
        state="filled",
    )
    logger.record_cancel_request("mirror-1", ts=1_300)
    logger.record_cancel_ack("mirror-1", ack_ts=1_360)

    summary = logger.flush_summary()

    assert summary["n_submitted"] == 1
    assert summary["n_filled"] == 1
    assert summary["fill_rate"] == 1.0
    assert summary["mean_order_latency_ms"] == 250.0
    assert summary["mean_cancel_latency_ms"] == 60.0
    assert summary["mean_slippage_bps"] == 50.0

    jsonl_path = next(tmp_path.glob("calib_*.jsonl"))
    rows = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines()]
    assert [row["type"] for row in rows] == ["submit", "fill", "cancel_request", "cancel_ack"]
    assert rows[1]["latency_ms"] == 250.0
    assert rows[3]["cancel_latency_ms"] == 60.0

    summary_path = next(tmp_path.glob("summary_*.json"))
    persisted = json.loads(summary_path.read_text(encoding="utf-8"))
    assert persisted == summary
