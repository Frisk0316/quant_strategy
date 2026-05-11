from __future__ import annotations

import asyncio

import pytest

from okx_quant.core.bus import EventBus
from okx_quant.core.events import Event, EvtType, FillPayload, MarketPayload, SignalPayload
from okx_quant.execution.broker import (
    Broker,
    ShadowBroker,
    SimBroker,
    to_shadow_mirror_cl_ord_id,
)
from okx_quant.execution.execution_handler import ExecutionHandler
from okx_quant.execution.order_manager import OrderManager
from okx_quant.execution.rate_limiter import RateLimiter
from okx_quant.execution.replay_execution import ReplayExecutionModel
from okx_quant.portfolio.portfolio_manager import PortfolioManager
from okx_quant.portfolio.positions import PositionLedger


class RaisingBroker(Broker):
    async def submit(self, order: dict):
        raise RuntimeError("mirror down")

    async def cancel(self, inst_id: str, cl_ord_id: str) -> bool:
        raise RuntimeError("mirror down")

    async def close_all(self) -> None:
        raise RuntimeError("mirror down")


class DummyRisk:
    max_order_notional = 1_000_000.0

    def get_size_multiplier(self, strategy: str) -> float:
        return 1.0

    def check(self, *args, **kwargs) -> bool:
        return True


def _order(cl_ord_id: str = "order-1"):
    return {
        "cl_ord_id": cl_ord_id,
        "inst_id": "BTC-USDT-SWAP",
        "side": "buy",
        "ord_type": "post_only",
        "sz": "1",
        "px": "100.0",
        "td_mode": "cross",
        "strategy": "test",
        "metadata": {},
    }


def _market(ts: int, bid: float, ask: float):
    return MarketPayload(
        inst_id="BTC-USDT-SWAP",
        ts=ts,
        bids=[[str(bid), "5"]],
        asks=[[str(ask), "5"]],
        seq_id=0,
        channel="books",
    )


def test_shadow_mirror_cl_ord_id_always_32_chars():
    for raw in ["a", "b" * 32, "c" * 100]:
        assert len(to_shadow_mirror_cl_ord_id(raw)) <= 32


@pytest.mark.asyncio
async def test_shadow_mirror_failure_does_not_affect_primary(filled_broker):
    broker = ShadowBroker(primary=filled_broker, mirror=RaisingBroker())

    fill = await broker.submit(_order("a" * 32))
    await asyncio.sleep(0)

    assert fill is not None
    assert fill.state == "filled"
    assert filled_broker.orders


@pytest.mark.asyncio
async def test_sim_broker_zero_latency_fills_immediately():
    broker = SimBroker(
        slippage_bps=0.0,
        fill_probability=1.0,
        instrument_specs={"BTC-USDT-SWAP": {"ctVal": 0.01}},
    )

    fill = await broker.submit(_order())

    assert fill is not None
    assert fill.state == "filled"
    assert fill.fill_px == pytest.approx(100.0)


def test_replay_execution_model_latency_delays_fill():
    model = ReplayExecutionModel(
        instrument_specs={"BTC-USDT-SWAP": {"ctVal": 0.01}},
        order_latency_ms=50,
        queue_fill_fraction=1.0,
    )
    model.on_market(_market(1_000, 99.0, 101.0))
    model.submit(_order())

    assert model.on_market(_market(1_040, 99.0, 99.5)) == []
    assert len(model.on_market(_market(1_051, 99.0, 99.5))) == 1


@pytest.mark.asyncio
async def test_portfolio_manager_signal_to_fill_ledger():
    bus = EventBus()
    ledger = PositionLedger(initial_equity=1_000.0)
    pm = PortfolioManager(
        bus=bus,
        positions=ledger,
        risk_guard=DummyRisk(),
        instrument_specs={"BTC-USDT-SWAP": {"ctVal": 1.0, "minSz": 0.01, "lotSz": 0.01, "tickSz": 0.1}},
    )
    handler = ExecutionHandler(
        bus=bus,
        order_manager=OrderManager(
            SimBroker(slippage_bps=0.0, fill_probability=1.0, instrument_specs={"BTC-USDT-SWAP": {"ctVal": 1.0}}),
            RateLimiter(),
        ),
    )

    pm.on_market(_market(1, 99.0, 101.0))
    buy = SignalPayload("test", "BTC-USDT-SWAP", "buy", 1.0, 100.0)
    await pm.on_signal(Event(EvtType.SIGNAL, payload=buy))
    order_event = await asyncio.wait_for(bus._queue.get(), timeout=0.1)
    bus._queue.task_done()
    await handler.on_order(order_event)
    fill_event = await asyncio.wait_for(bus._queue.get(), timeout=0.1)
    bus._queue.task_done()
    await pm.on_fill(fill_event)

    sell = SignalPayload("test", "BTC-USDT-SWAP", "sell", 1.0, 110.0)
    await pm.on_signal(Event(EvtType.SIGNAL, payload=sell))
    order_event = await asyncio.wait_for(bus._queue.get(), timeout=0.1)
    bus._queue.task_done()
    await handler.on_order(order_event)
    fill_event = await asyncio.wait_for(bus._queue.get(), timeout=0.1)
    bus._queue.task_done()
    sell_fill: FillPayload = fill_event.payload
    await pm.on_fill(fill_event)

    assert sell_fill.fill_px == pytest.approx(110.0)
    assert ledger.get_equity() > 1_000.0
