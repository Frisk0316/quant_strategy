"""Regression tests for the authorized WS-C C5/C3/C10 trade-safety fixes."""
from unittest.mock import Mock

import pytest

from okx_quant.core.bus import EventBus
from okx_quant.core.config import AppConfig, OKXSecrets, SystemConfig
from okx_quant.engine import main
from okx_quant.portfolio.portfolio_manager import PortfolioManager
from okx_quant.portfolio.positions import PositionLedger


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
