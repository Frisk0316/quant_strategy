"""Regression tests for pairs trading hedge-close behavior."""

from __future__ import annotations

import asyncio
from collections import deque
from types import MethodType

import pytest

from okx_quant.core.bus import EventBus
from okx_quant.core.events import Event, EvtType, MarketPayload, SignalPayload
from okx_quant.data.okx_book import OkxBook
from okx_quant.portfolio.portfolio_manager import PortfolioManager
from okx_quant.portfolio.positions import PositionLedger
from okx_quant.strategies.pairs_trading import PairsTradingStrategy


SYMBOL_Y = "ETH-USDT-SWAP"
SYMBOL_X = "BTC-USDT-SWAP"
PRICE_Y = 2_000.0
PRICE_X = 40_000.0


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


def _book(payload: MarketPayload) -> OkxBook:
    book = OkxBook(payload.inst_id)
    for px, sz, *_ in payload.bids:
        book.bids[float(px)] = (px, sz)
    for px, sz, *_ in payload.asks:
        book.asks[float(px)] = (px, sz)
    return book


def _portfolio_with_markets(initial_equity: float = 10_000.0):
    bus = EventBus()
    ledger = PositionLedger(initial_equity=initial_equity)
    pm = PortfolioManager(
        bus=bus,
        positions=ledger,
        risk_guard=DummyRisk(),
        instrument_specs={
            SYMBOL_Y: {"ctVal": 0.01, "minSz": 0.01, "lotSz": 0.01, "tickSz": 0.1},
            SYMBOL_X: {"ctVal": 0.01, "minSz": 0.01, "lotSz": 0.01, "tickSz": 0.1},
        },
    )
    pm.on_market(_market(SYMBOL_Y, PRICE_Y))
    pm.on_market(_market(SYMBOL_X, PRICE_X))
    return bus, ledger, pm


def _open_pair_position(ledger: PositionLedger, *, y_size: float, x_size: float) -> None:
    ledger.on_fill(
        SYMBOL_Y,
        "sell",
        fill_px=PRICE_Y,
        fill_sz=y_size,
        fee=0.0,
        strategy="pairs_trading",
        metadata={"ct_val": 0.01},
    )
    ledger.on_fill(
        SYMBOL_X,
        "buy",
        fill_px=PRICE_X,
        fill_sz=x_size,
        fee=0.0,
        strategy="pairs_trading",
        metadata={"ct_val": 0.01},
    )


def _exit_signal(*, strength: float = 0.01, beta: float = 0.5) -> SignalPayload:
    return SignalPayload(
        strategy="pairs_trading",
        inst_id=SYMBOL_Y,
        side="buy",
        strength=strength,
        fair_value=PRICE_Y,
        metadata={
            "action": "exit",
            "beta": beta,
            "size_multiplier": strength,
            "hedge_inst_id": SYMBOL_X,
            "hedge_side": "sell",
        },
    )


async def _orders_from_signal(bus: EventBus, pm: PortfolioManager, signal: SignalPayload):
    await pm.on_signal(Event(EvtType.SIGNAL, payload=signal))
    orders = []
    while not bus._queue.empty():
        event = await asyncio.wait_for(bus._queue.get(), timeout=0.1)
        orders.append(event.payload)
        bus._queue.task_done()
    return orders


def _apply_orders_as_fills(ledger: PositionLedger, orders) -> None:
    for order in orders:
        ledger.on_fill(
            order.inst_id,
            order.side,
            fill_px=float(order.px),
            fill_sz=float(order.sz),
            fee=0.0,
            strategy=order.strategy,
            metadata=dict(order.metadata),
        )


@pytest.mark.asyncio
async def test_pairs_exit_signal_with_hedge_metadata_closes_both_legs():
    bus, ledger, pm = _portfolio_with_markets()
    _open_pair_position(ledger, y_size=2.5, x_size=0.06)

    orders = await _orders_from_signal(bus, pm, _exit_signal())
    _apply_orders_as_fills(ledger, orders)

    assert {(order.inst_id, order.side) for order in orders} == {
        (SYMBOL_Y, "buy"),
        (SYMBOL_X, "sell"),
    }
    assert ledger.get_all_positions() == {}


@pytest.mark.asyncio
async def test_pairs_partial_exit_scales_main_and_hedge_reductions():
    bus, ledger, pm = _portfolio_with_markets()
    _open_pair_position(ledger, y_size=5.0, x_size=0.12)

    orders = await _orders_from_signal(bus, pm, _exit_signal())
    _apply_orders_as_fills(ledger, orders)

    y_pos = ledger.get_position(SYMBOL_Y)
    x_pos = ledger.get_position(SYMBOL_X)

    assert y_pos.size == pytest.approx(-2.5)
    assert x_pos.size == pytest.approx(0.06)


@pytest.mark.asyncio
async def test_pairs_strategy_exit_signal_includes_hedge_close_metadata():
    strategy = PairsTradingStrategy(
        {
            "symbol_y": SYMBOL_Y,
            "symbol_x": SYMBOL_X,
            "exit_z": 0.3,
        }
    )
    strategy._in_position = True
    strategy._position_side = "short_y"
    strategy._prices[SYMBOL_Y] = deque([PRICE_Y, PRICE_Y], maxlen=10)
    strategy._prices[SYMBOL_X] = deque([PRICE_X, PRICE_X], maxlen=10)
    strategy._price_ts_ms[SYMBOL_X] = 1_704_067_200_000
    strategy._ou_params = {"theta": 0.1, "mu": 0.0, "sigma": 0.01, "half_life": 6.0}
    strategy._ou_calibrated = True

    def fake_kalman_update(self, y: float, x: float) -> float:
        return 0.001

    strategy._kalman_update = MethodType(fake_kalman_update, strategy)
    payload = _market(SYMBOL_Y, PRICE_Y)

    signal = await strategy.on_market(Event(EvtType.MARKET, payload=payload), _book(payload))

    assert signal is not None
    assert signal.metadata["action"] == "exit"
    assert signal.metadata["hedge_inst_id"] == SYMBOL_X
    assert signal.metadata["hedge_side"] == "sell"


@pytest.mark.asyncio
async def test_pairs_strategy_stop_signal_includes_hedge_close_metadata():
    strategy = PairsTradingStrategy(
        {
            "symbol_y": SYMBOL_Y,
            "symbol_x": SYMBOL_X,
            "exit_z": 10.0,
            "stop_z": 4.0,
        }
    )
    strategy._in_position = True
    strategy._position_side = "long_y"
    strategy._prices[SYMBOL_Y] = deque([PRICE_Y, PRICE_Y], maxlen=10)
    strategy._prices[SYMBOL_X] = deque([PRICE_X, PRICE_X], maxlen=10)
    strategy._price_ts_ms[SYMBOL_X] = 1_704_067_200_000
    strategy._ou_params = {"theta": 0.1, "mu": 0.0, "sigma": 0.01, "half_life": 6.0}
    strategy._ou_calibrated = True

    def fake_kalman_update(self, y: float, x: float) -> float:
        return 0.05

    strategy._kalman_update = MethodType(fake_kalman_update, strategy)
    payload = _market(SYMBOL_Y, PRICE_Y)

    signal = await strategy.on_market(Event(EvtType.MARKET, payload=payload), _book(payload))

    assert signal is not None
    assert signal.metadata["action"] == "stop"
    assert signal.metadata["hedge_inst_id"] == SYMBOL_X
    assert signal.metadata["hedge_side"] == "buy"
