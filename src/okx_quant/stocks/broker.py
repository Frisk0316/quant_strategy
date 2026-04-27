"""Unified stock order routing for paper, TW, and US broker adapters."""
from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx
import pandas as pd

from okx_quant.stocks.fees import DEFAULT_FEE_MODELS, StockFeeModel
from okx_quant.stocks.models import OrderSide, StockFill, StockMarket, StockOrder


class StockBroker(ABC):
    @abstractmethod
    async def submit(self, order: StockOrder) -> Optional[StockFill]:
        ...

    @abstractmethod
    async def cancel(self, client_order_id: str) -> bool:
        ...

    @abstractmethod
    async def positions(self) -> dict[str, float]:
        ...

    @abstractmethod
    async def close_all(self) -> None:
        ...


class PaperStockBroker(StockBroker):
    """Immediate-fill paper broker for live-like dry runs."""

    def __init__(
        self,
        market: StockMarket,
        fee_model: StockFeeModel | None = None,
        default_price: float = 1.0,
    ) -> None:
        self.market = market
        self.fee_model = fee_model or DEFAULT_FEE_MODELS[market]
        self.default_price = default_price
        self._positions: dict[str, float] = {}

    async def submit(self, order: StockOrder) -> Optional[StockFill]:
        price = float(order.limit_price or order.metadata.get("reference_price", self.default_price))
        fee, tax = self.fee_model.estimate(order.side, price, order.quantity)
        fill = StockFill(
            symbol=order.symbol,
            market=order.market,
            side=order.side,
            quantity=order.quantity,
            price=price,
            fee=fee,
            tax=tax,
            ts=pd.Timestamp.now(tz="UTC"),
            order_id=f"paper-{uuid.uuid4().hex[:12]}",
            client_order_id=order.client_order_id,
            strategy=order.strategy,
            metadata=dict(order.metadata),
        )
        signed_qty = fill.quantity if fill.side == OrderSide.BUY else -fill.quantity
        self._positions[fill.symbol] = self._positions.get(fill.symbol, 0.0) + signed_qty
        return fill

    async def cancel(self, client_order_id: str) -> bool:
        return True

    async def positions(self) -> dict[str, float]:
        return dict(self._positions)

    async def close_all(self) -> None:
        self._positions.clear()


@dataclass
class RestBrokerConfig:
    base_url: str
    api_key: str
    account_id: str | None = None
    submit_path: str = "/orders"
    cancel_path_template: str = "/orders/{client_order_id}"
    timeout_secs: float = 10.0
    extra_headers: dict[str, str] = field(default_factory=dict)


class RestStockBroker(StockBroker):
    """Small REST adapter for broker APIs wrapped by an internal service.

    This intentionally speaks a simple JSON contract so TW and US broker-specific
    signing/auth details can live in a thin gateway service rather than inside
    the strategy engine.
    """

    def __init__(self, market: StockMarket, config: RestBrokerConfig) -> None:
        self.market = market
        self.config = config

    async def submit(self, order: StockOrder) -> Optional[StockFill]:
        async with httpx.AsyncClient(timeout=self.config.timeout_secs) as client:
            response = await client.post(
                f"{self.config.base_url.rstrip('/')}{self.config.submit_path}",
                headers=self._headers(),
                json=self._order_payload(order),
            )
            response.raise_for_status()
            data = response.json()
        if data.get("state", "accepted") not in {"accepted", "filled", "partially_filled"}:
            return None
        if data.get("state") != "filled":
            return None
        return _fill_from_response(order, data)

    async def cancel(self, client_order_id: str) -> bool:
        path = self.config.cancel_path_template.format(client_order_id=client_order_id)
        async with httpx.AsyncClient(timeout=self.config.timeout_secs) as client:
            response = await client.delete(
                f"{self.config.base_url.rstrip('/')}{path}",
                headers=self._headers(),
            )
            return response.status_code < 400

    async def positions(self) -> dict[str, float]:
        return {}

    async def close_all(self) -> None:
        return None

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            **self.config.extra_headers,
        }

    def _order_payload(self, order: StockOrder) -> dict[str, Any]:
        payload = {
            "account_id": self.config.account_id,
            "client_order_id": order.client_order_id,
            "market": order.market.value,
            "symbol": order.symbol,
            "side": order.side.value,
            "quantity": order.quantity,
            "order_type": order.order_type.value,
            "limit_price": order.limit_price,
            "time_in_force": order.time_in_force,
            "strategy": order.strategy,
            "metadata": order.metadata,
        }
        return {key: value for key, value in payload.items() if value is not None}


class StockOrderRouter:
    """Risk-aware order entry point shared by live and paper trading."""

    def __init__(
        self,
        broker: StockBroker,
        market: StockMarket,
        max_order_notional: float,
        dry_run: bool = True,
    ) -> None:
        self.broker = broker
        self.market = market
        self.max_order_notional = max_order_notional
        self.dry_run = dry_run

    async def submit(self, order: StockOrder) -> Optional[StockFill]:
        self._validate(order)
        if self.dry_run:
            paper = PaperStockBroker(order.market, default_price=order.limit_price or 1.0)
            return await paper.submit(order)
        return await self.broker.submit(order)

    def _validate(self, order: StockOrder) -> None:
        if order.market != self.market:
            raise ValueError(f"Router market {self.market.value} cannot submit {order.market.value} order")
        if order.quantity <= 0:
            raise ValueError("Order quantity must be positive")
        reference_price = order.limit_price or order.metadata.get("reference_price")
        if reference_price is not None and reference_price * order.quantity > self.max_order_notional:
            raise ValueError("Order exceeds max_order_notional")


def _fill_from_response(order: StockOrder, data: dict[str, Any]) -> StockFill:
    return StockFill(
        symbol=order.symbol,
        market=order.market,
        side=order.side,
        quantity=float(data.get("filled_quantity", order.quantity)),
        price=float(data.get("filled_price", order.limit_price or 0.0)),
        fee=float(data.get("fee", 0.0)),
        tax=float(data.get("tax", 0.0)),
        ts=pd.Timestamp(data.get("ts", int(time.time() * 1000)), unit="ms", tz="UTC"),
        order_id=str(data.get("order_id", "")),
        client_order_id=order.client_order_id,
        strategy=order.strategy,
        state=str(data.get("state", "filled")),
        metadata=dict(order.metadata),
    )
