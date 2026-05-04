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
    SimBroker,
    ShadowBroker,
    is_shadow_mirror_cl_ord_id,
    to_shadow_mirror_cl_ord_id,
)
from okx_quant.execution.execution_handler import ExecutionHandler
from okx_quant.execution.order_manager import OrderManager
from okx_quant.execution.rate_limiter import RateLimiter
from okx_quant.execution.replay_execution import ReplayExecutionModel
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


def test_position_ledger_applies_non_trade_cashflow():
    ledger = PositionLedger(initial_equity=1_000.0)

    ledger.apply_cashflow(12.5, inst_id="BTC-USDT-SWAP", reason="funding", strategy="carry")

    assert ledger.get_equity() == pytest.approx(1_012.5)
    assert ledger.get_trade_log()[-1]["cashflow"] == pytest.approx(12.5)
    assert ledger.get_trade_log()[-1]["side"] == "funding"


def make_market_payload(
    ts: int = 1,
    bid_px: float = 99.0,
    bid_sz: float = 5.0,
    ask_px: float = 101.0,
    ask_sz: float = 5.0,
):
    from okx_quant.core.events import MarketPayload

    return MarketPayload(
        inst_id="BTC-USDT-SWAP",
        ts=ts,
        bids=[[str(bid_px), str(bid_sz)]],
        asks=[[str(ask_px), str(ask_sz)]],
        seq_id=0,
        channel="books",
    )


def test_replay_execution_model_rejects_post_only_crossing_order():
    model = ReplayExecutionModel(instrument_specs={"BTC-USDT-SWAP": {"ctVal": 0.01}})
    model.on_market(make_market_payload(ask_px=101.0))

    accepted = model.submit({
        "cl_ord_id": "cross",
        "inst_id": "BTC-USDT-SWAP",
        "side": "buy",
        "sz": "1",
        "px": "101.0",
        "strategy": "test",
        "metadata": {},
    })

    assert accepted is None
    assert model.rejected_log[-1]["reason"] == "post_only_cross"


def test_replay_execution_model_partially_fills_resting_order():
    model = ReplayExecutionModel(
        instrument_specs={"BTC-USDT-SWAP": {"ctVal": 0.01}},
        queue_fill_fraction=0.5,
    )
    model.on_market(make_market_payload(ts=1, bid_px=99.0, ask_px=101.0))
    pending = model.submit({
        "cl_ord_id": "partial",
        "inst_id": "BTC-USDT-SWAP",
        "side": "buy",
        "sz": "10",
        "px": "100.0",
        "strategy": "test",
        "metadata": {},
    })

    fills = model.on_market(make_market_payload(ts=2, ask_px=99.5, ask_sz=4.0))

    assert pending is not None
    assert pending.state == "pending"
    assert len(fills) == 1
    assert fills[0].state == "partially_filled"
    assert fills[0].fill_sz == pytest.approx(2.0)
    assert model.resting_orders["partial"].remaining_sz == pytest.approx(8.0)


def test_replay_execution_model_queue_fraction_bounds_fill_quantity():
    order = {
        "cl_ord_id": "queue-test",
        "inst_id": "BTC-USDT-SWAP",
        "side": "buy",
        "sz": "5",
        "px": "100.0",
        "strategy": "test",
        "metadata": {},
    }

    zero_model = ReplayExecutionModel(
        instrument_specs={"BTC-USDT-SWAP": {"ctVal": 0.01}},
        queue_fill_fraction=0.0,
    )
    zero_model.on_market(make_market_payload(ts=1, bid_px=99.0, ask_px=101.0))
    zero_model.submit(order)

    full_model = ReplayExecutionModel(
        instrument_specs={"BTC-USDT-SWAP": {"ctVal": 0.01}},
        queue_fill_fraction=1.0,
    )
    full_model.on_market(make_market_payload(ts=1, bid_px=99.0, ask_px=101.0))
    full_model.submit(order)

    assert zero_model.on_market(make_market_payload(ts=2, ask_px=99.5, ask_sz=5.0)) == []

    fills = full_model.on_market(make_market_payload(ts=2, ask_px=99.5, ask_sz=5.0))
    assert len(fills) == 1
    assert fills[0].state == "filled"
    assert fills[0].fill_sz == pytest.approx(5.0)


def test_replay_execution_model_respects_cancel_latency():
    model = ReplayExecutionModel(
        instrument_specs={"BTC-USDT-SWAP": {"ctVal": 0.01}},
        cancel_latency_ms=10,
    )
    model.on_market(make_market_payload(ts=100, bid_px=99.0, ask_px=101.0))
    model.submit({
        "cl_ord_id": "cancel-me",
        "inst_id": "BTC-USDT-SWAP",
        "side": "buy",
        "sz": "1",
        "px": "100.0",
        "strategy": "test",
        "metadata": {},
    })

    assert model.cancel("BTC-USDT-SWAP", "cancel-me") is True
    assert "cancel-me" in model.resting_orders
    model.on_market(make_market_payload(ts=109, bid_px=99.0, ask_px=101.0))
    assert "cancel-me" in model.resting_orders
    model.on_market(make_market_payload(ts=110, bid_px=99.0, ask_px=101.0))
    assert "cancel-me" not in model.resting_orders


@pytest.mark.asyncio
async def test_sim_broker_uses_contract_value_for_fee_and_notional_metadata():
    broker = SimBroker(
        slippage_bps=0.0,
        fill_probability=1.0,
        instrument_specs={"BTC-USDT-SWAP": {"ctVal": 0.01}},
        maker_fee_rate=0.0002,
    )
    fill = await broker.submit({
        "cl_ord_id": "sim-1",
        "inst_id": "BTC-USDT-SWAP",
        "side": "buy",
        "sz": "2",
        "px": "100.0",
        "strategy": "test",
        "metadata": {},
    })

    assert fill is not None
    assert fill.metadata["notional_usd"] == pytest.approx(2.0)
    assert fill.fee == pytest.approx(0.0004)


def test_portfolio_manager_refuses_unknown_swap_ct_val_fallback():
    pm = PortfolioManager(
        bus=EventBus(),
        positions=PositionLedger(initial_equity=10_000.0),
        risk_guard=DummyRisk(),
        instrument_specs={},
    )

    with pytest.raises(ValueError, match="Missing ctVal"):
        pm._compute_order_quantity("SOL-USDT-SWAP", price=100.0, size_usd=1_000.0)


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
