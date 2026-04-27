"""Shared models for minute-bar stock backtesting and order routing."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import pandas as pd


class StockMarket(str, Enum):
    TW = "TW"
    US = "US"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


@dataclass(frozen=True)
class TargetSignal:
    """Target portfolio weight generated from data available at one bar close."""

    symbol: str
    target_percent: float
    strategy: str = "stock_strategy"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StockOrder:
    symbol: str
    market: StockMarket
    side: OrderSide
    quantity: float
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = None
    strategy: str = "manual"
    client_order_id: str = field(default_factory=lambda: uuid.uuid4().hex[:32])
    time_in_force: str = "day"
    ts: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StockFill:
    symbol: str
    market: StockMarket
    side: OrderSide
    quantity: float
    price: float
    fee: float
    tax: float
    ts: pd.Timestamp
    order_id: str
    client_order_id: str
    strategy: str
    state: str = "filled"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def gross_amount(self) -> float:
        return self.quantity * self.price

    @property
    def total_cost(self) -> float:
        return self.fee + self.tax

    @property
    def cash_flow(self) -> float:
        if self.side == OrderSide.BUY:
            return -(self.gross_amount + self.total_cost)
        return self.gross_amount - self.total_cost


@dataclass
class StockPosition:
    symbol: str
    quantity: float = 0.0
    avg_price: float = 0.0

    def apply_fill(self, fill: StockFill) -> None:
        signed_qty = fill.quantity if fill.side == OrderSide.BUY else -fill.quantity
        new_qty = self.quantity + signed_qty

        if self.quantity >= 0 and signed_qty > 0:
            total_cost = self.avg_price * self.quantity + fill.price * signed_qty
            self.avg_price = total_cost / new_qty if new_qty else 0.0
        elif new_qty == 0:
            self.avg_price = 0.0
        elif self.quantity == 0:
            self.avg_price = fill.price

        self.quantity = new_qty


@dataclass
class StockBacktestResult:
    equity_curve: pd.Series
    returns: pd.Series
    metrics: dict
    orders: pd.DataFrame
    fills: pd.DataFrame
    positions: pd.DataFrame
