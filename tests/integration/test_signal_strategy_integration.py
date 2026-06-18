from __future__ import annotations

from collections import deque
from types import MethodType

import pytest

from okx_quant.core.events import Event, EvtType, MarketPayload
from okx_quant.data.okx_book import OkxBook
from okx_quant.strategies.funding_carry import FundingCarryStrategy
from okx_quant.strategies.pairs_trading import PairsTradingStrategy
import okx_quant.strategies.pairs_trading as pairs_module


def _payload(
    inst_id: str = "BTC-USDT-SWAP",
    ts: int = 1,
    bid: float = 99.0,
    ask: float = 101.0,
    bid_sz: float = 5.0,
    ask_sz: float = 5.0,
) -> MarketPayload:
    return MarketPayload(
        inst_id=inst_id,
        ts=ts,
        bids=[[str(bid), str(bid_sz)]],
        asks=[[str(ask), str(ask_sz)]],
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


@pytest.mark.asyncio
async def test_funding_carry_no_exit_when_basis_spikes_in_position():
    strategy = FundingCarryStrategy({"perp_symbol": "BTC-USDT-SWAP", "spot_symbol": "BTC-USDT"})
    strategy._in_position = True
    payload = MarketPayload(
        inst_id="BTC-USDT-SWAP",
        ts=1,
        bids=[],
        asks=[],
        seq_id=0,
        channel="funding-rate",
        funding_rate=0.001,
        funding_interval_hours=8.0,
    )
    payload.basis_z = 5.0

    signal = await strategy.on_market(Event(EvtType.FUNDING, payload=payload))

    assert signal is None


@pytest.mark.asyncio
async def test_pairs_stop_loss_overrides_exit_z():
    strategy = PairsTradingStrategy(
        {
            "symbol_y": "ETH-USDT-SWAP",
            "symbol_x": "BTC-USDT-SWAP",
            "exit_z": 10.0,
            "stop_z": 4.0,
        }
    )
    strategy._in_position = True
    strategy._position_side = "short_y"
    strategy._prices["ETH-USDT-SWAP"] = deque([100.0, 100.0], maxlen=10)
    strategy._prices["BTC-USDT-SWAP"] = deque([100.0, 100.0], maxlen=10)
    strategy._price_ts_ms["BTC-USDT-SWAP"] = 1_000
    strategy._ou_params = {"theta": 0.1, "mu": 0.0, "sigma": 0.01, "half_life": 6.0}
    strategy._ou_calibrated = True

    def fake_kalman_update(self, y: float, x: float) -> float:
        return 0.05

    strategy._kalman_update = MethodType(fake_kalman_update, strategy)
    payload = _payload(inst_id="ETH-USDT-SWAP", bid=99.0, ask=101.0)

    signal = await strategy.on_market(Event(EvtType.MARKET, payload=payload), _book(payload))

    assert signal is not None
    assert signal.metadata["action"] == "stop"


def test_pairs_quality_gate_blocks_until_ou_calibrated():
    strategy = PairsTradingStrategy(
        {
            "symbol_y": "ETH-USDT-SWAP",
            "symbol_x": "BTC-USDT-SWAP",
        }
    )

    gate_ok, gate_reason = strategy._quality_gate_passed()

    assert gate_ok is False
    assert gate_reason == "not_calibrated"
    assert not strategy._ou_calibrated
    assert not strategy._ou_params["sigma"] > 0


@pytest.mark.asyncio
async def test_pairs_ou_recalibration_uses_simulated_event_time(monkeypatch):
    strategy = PairsTradingStrategy(
        {
            "symbol_y": "ETH-USDT-SWAP",
            "symbol_x": "BTC-USDT-SWAP",
        }
    )
    base_ts = 1_704_067_200_000
    strategy._prices["ETH-USDT-SWAP"] = deque([100.0], maxlen=10)
    strategy._prices["BTC-USDT-SWAP"] = deque([100.0], maxlen=10)
    strategy._price_ts_ms["ETH-USDT-SWAP"] = base_ts
    strategy._price_ts_ms["BTC-USDT-SWAP"] = base_ts
    strategy._last_spread_ts_ms = base_ts
    strategy._spread_history = deque([0.001] * 101, maxlen=200)
    strategy._spread_interval_ms = deque([60_000] * 100, maxlen=200)
    calls: list[int] = []

    def fake_estimate_ou(spread):
        calls.append(len(spread))
        return {"theta": 0.1, "mu": 0.0, "sigma": 1.0, "half_life": 1.0}

    monkeypatch.setattr(pairs_module, "estimate_ou", fake_estimate_ou)

    next_ts = base_ts + 3_600_001
    y_payload = _payload(inst_id="ETH-USDT-SWAP", ts=next_ts, bid=100.0, ask=102.0)
    x_payload = _payload(inst_id="BTC-USDT-SWAP", ts=next_ts, bid=100.0, ask=102.0)

    assert await strategy.on_market(Event(EvtType.MARKET, payload=y_payload), _book(y_payload)) is None
    await strategy.on_market(Event(EvtType.MARKET, payload=x_payload), _book(x_payload))

    assert calls == [102]
    assert strategy._ou_calibrated is True
    assert strategy._last_ou_update_ms == next_ts

    later_ts = next_ts + 60_000
    y_payload = _payload(inst_id="ETH-USDT-SWAP", ts=later_ts, bid=101.0, ask=103.0)
    x_payload = _payload(inst_id="BTC-USDT-SWAP", ts=later_ts, bid=101.0, ask=103.0)

    await strategy.on_market(Event(EvtType.MARKET, payload=y_payload), _book(y_payload))
    await strategy.on_market(Event(EvtType.MARKET, payload=x_payload), _book(x_payload))

    assert len(calls) == 1

