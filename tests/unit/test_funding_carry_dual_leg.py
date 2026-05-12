"""Regression tests for funding carry dual-leg order alignment."""

from __future__ import annotations

import asyncio
import time

import pytest

from okx_quant.core.bus import EventBus
from okx_quant.core.events import Event, EvtType, MarketPayload, SignalPayload
from okx_quant.portfolio.portfolio_manager import PortfolioManager
from okx_quant.portfolio.positions import PositionLedger
from okx_quant.strategies.funding_carry import FundingCarryStrategy


PERP_SYMBOL = "BTC-USDT-SWAP"
SPOT_SYMBOL = "BTC-USDT"
BTC_PRICE = 40_000.0


class DummyRisk:
    max_order_notional = 1_000_000.0

    def get_size_multiplier(self, strategy: str) -> float:
        return 1.0

    def check(self, *args, **kwargs) -> bool:
        return True


def _market(inst_id: str, price: float) -> MarketPayload:
    return MarketPayload(
        inst_id=inst_id,
        ts=1_704_067_200_000,
        bids=[[str(price - 1.0), "10"]],
        asks=[[str(price + 1.0), "10"]],
        seq_id=0,
        channel="books",
    )


def _funding(rate: float) -> MarketPayload:
    return MarketPayload(
        inst_id=PERP_SYMBOL,
        ts=1_704_067_200_000,
        bids=[],
        asks=[],
        seq_id=0,
        channel="funding-rate",
        funding_rate=rate,
        funding_interval_hours=8.0,
    )


def _portfolio_with_markets(initial_equity: float = 10_000.0):
    bus = EventBus()
    ledger = PositionLedger(initial_equity=initial_equity)
    pm = PortfolioManager(
        bus=bus,
        positions=ledger,
        risk_guard=DummyRisk(),
        instrument_specs={
            PERP_SYMBOL: {"ctVal": 0.01, "minSz": 0.01, "lotSz": 0.01, "tickSz": 0.1},
            SPOT_SYMBOL: {"minSz": 0.0001, "lotSz": 0.0001, "tickSz": 0.1, "tdMode": "cash"},
        },
    )
    pm.on_market(_market(PERP_SYMBOL, BTC_PRICE))
    pm.on_market(_market(SPOT_SYMBOL, BTC_PRICE))
    return bus, pm


async def _orders_from_signal(bus: EventBus, pm: PortfolioManager, signal: SignalPayload):
    await pm.on_signal(Event(EvtType.SIGNAL, payload=signal))
    orders = []
    while not bus._queue.empty():
        event = await asyncio.wait_for(bus._queue.get(), timeout=0.1)
        orders.append(event.payload)
        bus._queue.task_done()
    return orders


def _entry_signal() -> SignalPayload:
    return SignalPayload(
        strategy="funding_carry",
        inst_id=PERP_SYMBOL,
        side="sell",
        strength=1.0,
        fair_value=0.0,
        metadata={
            "action": "entry",
            "spot_symbol": SPOT_SYMBOL,
            "leg": "dual",
        },
    )


def _exit_signal() -> SignalPayload:
    return SignalPayload(
        strategy="funding_carry",
        inst_id=PERP_SYMBOL,
        side="buy",
        strength=1.0,
        fair_value=0.0,
        metadata={
            "action": "exit",
            "spot_symbol": SPOT_SYMBOL,
            "leg": "dual",
        },
    )


@pytest.mark.asyncio
async def test_funding_carry_entry_signal_declares_dual_leg_metadata():
    strategy = FundingCarryStrategy(
        {
            "perp_symbol": PERP_SYMBOL,
            "spot_symbol": SPOT_SYMBOL,
            "min_apr_threshold": 0.12,
        }
    )

    signal = await strategy.on_market(Event(EvtType.FUNDING, payload=_funding(0.001)))

    assert signal is not None
    assert signal.inst_id == PERP_SYMBOL
    assert signal.side == "sell"
    assert signal.metadata["action"] == "entry"
    assert signal.metadata["spot_symbol"] == SPOT_SYMBOL
    assert signal.metadata["leg"] == "dual"


@pytest.mark.asyncio
async def test_funding_carry_exit_signal_declares_dual_leg_metadata():
    strategy = FundingCarryStrategy(
        {
            "perp_symbol": PERP_SYMBOL,
            "spot_symbol": SPOT_SYMBOL,
            "min_apr_threshold": 0.12,
        }
    )
    strategy._in_position = True
    strategy._last_rebalance_ts = time.time()

    signal = await strategy.on_market(Event(EvtType.FUNDING, payload=_funding(-0.001)))

    assert signal is not None
    assert signal.inst_id == PERP_SYMBOL
    assert signal.side == "buy"
    assert signal.metadata["action"] == "exit"
    assert signal.metadata["spot_symbol"] == SPOT_SYMBOL
    assert signal.metadata["leg"] == "dual"


@pytest.mark.asyncio
async def test_funding_carry_entry_places_short_perp_and_long_spot_with_aligned_notional():
    bus, pm = _portfolio_with_markets()

    orders = await _orders_from_signal(bus, pm, _entry_signal())

    assert {(order.inst_id, order.side) for order in orders} == {
        (PERP_SYMBOL, "sell"),
        (SPOT_SYMBOL, "buy"),
    }
    perp_order = next(order for order in orders if order.inst_id == PERP_SYMBOL)
    spot_order = next(order for order in orders if order.inst_id == SPOT_SYMBOL)
    assert perp_order.notional_usd == pytest.approx(spot_order.notional_usd)
    assert perp_order.metadata["leg"] == "dual"
    assert spot_order.metadata["leg"] == "dual"
    assert spot_order.metadata["spot_symbol"] == SPOT_SYMBOL


@pytest.mark.asyncio
async def test_funding_carry_exit_places_long_perp_and_short_spot_with_aligned_notional():
    bus, pm = _portfolio_with_markets()

    orders = await _orders_from_signal(bus, pm, _exit_signal())

    assert {(order.inst_id, order.side) for order in orders} == {
        (PERP_SYMBOL, "buy"),
        (SPOT_SYMBOL, "sell"),
    }
    perp_order = next(order for order in orders if order.inst_id == PERP_SYMBOL)
    spot_order = next(order for order in orders if order.inst_id == SPOT_SYMBOL)
    assert perp_order.notional_usd == pytest.approx(spot_order.notional_usd)
    assert perp_order.metadata["action"] == "exit"
    assert spot_order.metadata["action"] == "exit"
