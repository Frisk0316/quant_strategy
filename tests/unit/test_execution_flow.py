"""Unit tests for simulated execution flow and position accounting."""
import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from okx_quant.core.bus import EventBus
from okx_quant.core.events import Event, EvtType, FillPayload, OrderPayload
from okx_quant.engine import _should_use_demo_environment
from okx_quant.execution.broker import (
    Broker,
    ShadowBroker,
    is_shadow_mirror_cl_ord_id,
    to_shadow_mirror_cl_ord_id,
)
from okx_quant.execution.execution_handler import ExecutionHandler
from okx_quant.execution.order_manager import OrderManager
from okx_quant.execution.rate_limiter import RateLimiter
from okx_quant.portfolio.portfolio_manager import PortfolioManager
from okx_quant.portfolio.positions import PositionLedger


class FilledBroker(Broker):
    def __init__(self) -> None:
        self.orders: list[dict] = []

    async def submit(self, order: dict):
        self.orders.append(order)
        return FillPayload(
            cl_ord_id=order["cl_ord_id"],
            ord_id="ord-1",
            inst_id=order["inst_id"],
            fill_px=float(order["px"]),
            fill_sz=float(order["sz"]),
            fee=0.0,
            fee_ccy="USDT",
            side=order["side"],
            ts=1,
            strategy=order["strategy"],
            state="filled",
        )

    async def cancel(self, inst_id: str, cl_ord_id: str) -> bool:
        return True

    async def close_all(self) -> None:
        return None


class PendingBroker(Broker):
    def __init__(self) -> None:
        self.orders: list[dict] = []

    async def submit(self, order: dict):
        self.orders.append(order)
        return FillPayload(
            cl_ord_id=order["cl_ord_id"],
            ord_id="ord-pending",
            inst_id=order["inst_id"],
            fill_px=0.0,
            fill_sz=0.0,
            fee=0.0,
            fee_ccy="USDT",
            side=order["side"],
            ts=1,
            strategy=order["strategy"],
            state="pending",
        )

    async def cancel(self, inst_id: str, cl_ord_id: str) -> bool:
        return True

    async def close_all(self) -> None:
        return None


class DummyRisk:
    def get_size_multiplier(self, strategy: str) -> float:
        return 1.0


class DummyCfg:
    def __init__(self, mode: str) -> None:
        self.system = type("System", (), {"mode": mode})()

    def is_demo(self) -> bool:
        return self.system.mode == "demo"


@pytest.mark.asyncio
async def test_execution_handler_emits_immediate_fill_event_for_simulated_fills():
    bus = EventBus()
    order_manager = OrderManager(FilledBroker(), RateLimiter())
    handler = ExecutionHandler(bus=bus, order_manager=order_manager)
    order = OrderPayload(
        cl_ord_id="a" * 32,
        inst_id="BTC-USDT-SWAP",
        side="buy",
        ord_type="post_only",
        sz="2",
        px="100.0",
        td_mode="cross",
        strategy="as_market_maker",
    )

    await handler.on_order(Event(EvtType.ORDER, payload=order))
    queued = await asyncio.wait_for(bus._queue.get(), timeout=0.1)

    assert queued.type == EvtType.FILL
    assert queued.payload.strategy == "as_market_maker"
    assert queued.payload.fill_px == 100.0


@pytest.mark.asyncio
async def test_execution_handler_ignores_shadow_mirror_ws_fills():
    bus = EventBus()
    order_manager = OrderManager(PendingBroker(), RateLimiter())
    handler = ExecutionHandler(bus=bus, order_manager=order_manager)

    await handler.on_fill_ws({
        "data": [{
            "clOrdId": to_shadow_mirror_cl_ord_id("a" * 32),
            "ordId": "mirror-1",
            "instId": "BTC-USDT-SWAP",
            "fillPx": "100",
            "fillSz": "1",
            "fee": "0.1",
            "feeCcy": "USDT",
            "side": "buy",
            "uTime": "1",
            "state": "filled",
        }]
    })

    assert bus._queue.empty()


@pytest.mark.asyncio
async def test_shadow_broker_mirrors_orders_with_prefixed_client_id():
    primary = FilledBroker()
    mirror = PendingBroker()
    broker = ShadowBroker(primary=primary, mirror=mirror)
    order = {
        "cl_ord_id": "b" * 32,
        "inst_id": "BTC-USDT-SWAP",
        "side": "sell",
        "ord_type": "post_only",
        "sz": "1",
        "px": "101.0",
        "td_mode": "cross",
        "strategy": "pairs_trading",
    }

    fill = await broker.submit(order)
    await asyncio.sleep(0)

    assert fill is not None
    assert fill.strategy == "pairs_trading"
    assert mirror.orders
    assert is_shadow_mirror_cl_ord_id(mirror.orders[0]["cl_ord_id"])


def test_position_ledger_resets_avg_entry_on_reversal():
    ledger = PositionLedger(initial_equity=1_000.0)

    ledger.on_fill("BTC-USDT-SWAP", "buy", fill_px=100.0, fill_sz=2.0, fee=1.0, strategy="test")
    ledger.on_fill("BTC-USDT-SWAP", "sell", fill_px=110.0, fill_sz=3.0, fee=2.0, strategy="test")

    pos = ledger.get_position("BTC-USDT-SWAP")
    assert pos.size == -1.0
    assert pos.avg_entry == 110.0
    assert ledger.get_equity() == pytest.approx(1_017.0)


@pytest.mark.asyncio
async def test_portfolio_manager_tracks_non_zero_returns_from_fill_history():
    ledger = PositionLedger(initial_equity=10_000.0)
    pm = PortfolioManager(bus=EventBus(), positions=ledger, risk_guard=DummyRisk())

    first = FillPayload(
        cl_ord_id="1",
        ord_id="1",
        inst_id="BTC-USDT-SWAP",
        fill_px=100.0,
        fill_sz=1.0,
        fee=0.0,
        fee_ccy="USDT",
        side="buy",
        ts=1,
        strategy="test",
        state="filled",
    )
    second = FillPayload(
        cl_ord_id="2",
        ord_id="2",
        inst_id="BTC-USDT-SWAP",
        fill_px=110.0,
        fill_sz=1.0,
        fee=0.0,
        fee_ccy="USDT",
        side="buy",
        ts=2,
        strategy="test",
        state="filled",
    )

    await pm.on_fill(Event(EvtType.FILL, payload=first))
    await pm.on_fill(Event(EvtType.FILL, payload=second))

    assert pm._returns["BTC-USDT-SWAP"][-1] == pytest.approx(0.10)


def test_shadow_mode_uses_demo_environment():
    assert _should_use_demo_environment(DummyCfg("shadow")) is True
    assert _should_use_demo_environment(DummyCfg("demo")) is True
    assert _should_use_demo_environment(DummyCfg("live")) is False
