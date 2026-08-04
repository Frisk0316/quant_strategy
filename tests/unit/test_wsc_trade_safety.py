"""Regression tests for the authorized WS-C C5/C3/C10 trade-safety fixes."""
from unittest.mock import Mock

import pytest

from okx_quant.core.bus import EventBus
from okx_quant.core.config import AppConfig, OKXSecrets, SystemConfig
from okx_quant.core.events import OrderPayload
from okx_quant.engine import main
from okx_quant.execution.broker import OKXBroker
from okx_quant.execution.order_manager import OrderManager
from okx_quant.execution.rate_limiter import RateLimiter
from okx_quant.portfolio.portfolio_manager import PortfolioManager
from okx_quant.portfolio.positions import PositionLedger
from okx_quant.risk.drawdown_tracker import DrawdownTracker
from okx_quant.risk.risk_guard import RiskGuard


class _Risk:
    def get_size_multiplier(self, _strategy: str) -> float:
        return 1.0

    def check(self, *_args, **_kwargs) -> bool:
        return True


def _engine_config() -> AppConfig:
    return AppConfig(
        system=SystemConfig(
            mode="live",
            symbols=["ETH-USDT-SWAP"],
            spot_symbols=[],
            equity_usd=10_000.0,
        ),
        secrets=OKXSecrets(
            OKX_API_KEY="test-key",
            OKX_SECRET="test-secret",
            OKX_PASSPHRASE="test-passphrase",
        ),
    )


def _instrument(ct_val: str) -> dict[str, str]:
    return {
        "instId": "ETH-USDT-SWAP",
        "ctVal": ct_val,
        "minSz": "1",
        "lotSz": "1",
        "tickSz": "0.01",
    }


@pytest.mark.asyncio
async def test_engine_instrument_fetch_failure_stops_before_broker(monkeypatch):
    rest = Mock()
    rest.get_instruments.side_effect = ConnectionError("instrument endpoint unavailable")
    broker_factory = Mock()
    monkeypatch.setattr("okx_quant.engine.setup_logging", Mock())
    monkeypatch.setattr("okx_quant.engine.OKXRestClient", Mock(return_value=rest))
    monkeypatch.setattr("okx_quant.engine._build_broker", broker_factory)

    with pytest.raises(RuntimeError, match="Could not fetch complete instrument specs"):
        await main(_engine_config())

    broker_factory.assert_not_called()


@pytest.mark.parametrize(
    "response",
    [{"code": "0", "data": []}, {"code": "0", "data": [_instrument("")]}],
    ids=["configured-symbol-missing", "empty-ct-val"],
)
@pytest.mark.asyncio
async def test_engine_incomplete_instrument_specs_stop_before_broker(monkeypatch, response):
    rest = Mock()
    rest.get_instruments.return_value = response
    broker_factory = Mock()
    monkeypatch.setattr("okx_quant.engine.setup_logging", Mock())
    monkeypatch.setattr("okx_quant.engine.OKXRestClient", Mock(return_value=rest))
    monkeypatch.setattr("okx_quant.engine._build_broker", broker_factory)

    with pytest.raises(RuntimeError, match="Could not fetch complete instrument specs"):
        await main(_engine_config())

    broker_factory.assert_not_called()


@pytest.mark.asyncio
async def test_engine_nonzero_instrument_response_stops_before_broker(monkeypatch):
    rest = Mock()
    rest.get_instruments.return_value = {
        "code": "51000",
        "msg": "instrument request rejected",
        "data": [_instrument("0.1")],
    }
    broker_factory = Mock()
    monkeypatch.setattr("okx_quant.engine.setup_logging", Mock())
    monkeypatch.setattr("okx_quant.engine.OKXRestClient", Mock(return_value=rest))
    monkeypatch.setattr("okx_quant.engine._build_broker", broker_factory)

    with pytest.raises(RuntimeError, match="Could not fetch complete instrument specs"):
        await main(_engine_config())

    broker_factory.assert_not_called()


@pytest.mark.asyncio
async def test_engine_preserves_exchange_eth_ct_val(monkeypatch):
    rest = Mock()
    rest.get_instruments.return_value = {"code": "0", "data": [_instrument("0.1")]}
    rest.get_balance.return_value = {"data": [{"details": []}]}
    captured = {}

    def capture_specs(*_args, **kwargs):
        captured.update(kwargs["instrument_specs"])
        raise LookupError("specs captured")

    monkeypatch.setattr("okx_quant.engine.setup_logging", Mock())
    monkeypatch.setattr("okx_quant.engine.OKXRestClient", Mock(return_value=rest))
    monkeypatch.setattr("okx_quant.engine._build_broker", capture_specs)

    with pytest.raises(LookupError, match="specs captured"):
        await main(_engine_config())

    assert captured["ETH-USDT-SWAP"]["ctVal"] == pytest.approx(0.1)


def test_portfolio_manager_never_falls_back_to_eth_ct_val():
    bus = EventBus()
    manager = PortfolioManager(
        bus=bus,
        positions=PositionLedger(initial_equity=10_000.0),
        risk_guard=_Risk(),
        instrument_specs={},
    )

    with pytest.raises(ValueError, match="Missing ctVal for swap: ETH-USDT-SWAP"):
        manager._compute_order_quantity("ETH-USDT-SWAP", price=3_000.0, size_usd=1_000.0)

    assert bus._queue.empty()


@pytest.mark.asyncio
async def test_okx_broker_sends_reduce_only_kwargs():
    trade = Mock()
    trade.place_order.return_value = {
        "code": "0",
        "data": [{"sCode": "0", "ordId": "reduce-direct"}],
    }
    broker = OKXBroker.__new__(OKXBroker)
    broker._trade = trade
    broker._strategy = ""
    broker._demo = True

    await broker.submit(
        {
            "cl_ord_id": "reduce-direct",
            "inst_id": "BTC-USDT-SWAP",
            "side": "buy",
            "ord_type": "post_only",
            "sz": "1",
            "px": "100",
            "td_mode": "cross",
            "strategy": "test",
            "reduce_only": True,
            "pos_side": "short",
        }
    )

    assert trade.place_order.call_args.kwargs["reduceOnly"] == "true"
    assert trade.place_order.call_args.kwargs["posSide"] == "short"


@pytest.mark.asyncio
async def test_reduce_only_risk_bypass_reaches_okx_payload():
    class Trade:
        def __init__(self) -> None:
            self.kwargs = {}

        def place_order(self, **kwargs):
            self.kwargs = kwargs
            return {"code": "0", "data": [{"sCode": "0", "ordId": "reduce-1"}]}

    tracker = DrawdownTracker()
    tracker.set_initial_equity(10_000.0)
    risk = RiskGuard(
        equity_fn=lambda: 10_000.0,
        drawdown_tracker=tracker,
        max_order_notional_usd=50.0,
    )
    risk.trigger_hard_stop("kill_switch")
    order = OrderPayload(
        cl_ord_id="reduce-only-1",
        inst_id="BTC-USDT-SWAP",
        side="sell",
        ord_type="post_only",
        sz="1",
        px="100",
        td_mode="cross",
        strategy="ma_crossover",
        reduce_only=True,
        pos_side="short",
        notional_usd=100.0,
    )
    assert risk.check(order, current_pos_notional=100.0, current_mid=100.0) is True

    trade = Trade()
    broker = OKXBroker.__new__(OKXBroker)
    broker._trade = trade
    broker._strategy = ""
    broker._demo = True
    fill = await OrderManager(broker, RateLimiter()).submit(order)

    assert fill is not None
    assert trade.kwargs["reduceOnly"] == "true"
    assert trade.kwargs["posSide"] == "short"
