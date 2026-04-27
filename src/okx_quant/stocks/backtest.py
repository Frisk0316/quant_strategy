"""Minute-bar stock backtesting engine."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np
import pandas as pd

from okx_quant.analytics.performance import summary
from okx_quant.stocks.data import annualization_periods
from okx_quant.stocks.fees import DEFAULT_FEE_MODELS, StockFeeModel
from okx_quant.stocks.models import (
    OrderSide,
    OrderType,
    StockBacktestResult,
    StockFill,
    StockMarket,
    StockOrder,
    StockPosition,
    TargetSignal,
)


class StockStrategy(ABC):
    name: str = "stock_strategy"

    @abstractmethod
    def on_bar(
        self,
        ts: pd.Timestamp,
        history: dict[str, pd.DataFrame],
        portfolio: dict,
    ) -> list[TargetSignal]:
        """Return target weights using only bars up to ``ts``."""


class MovingAverageCrossStrategy(StockStrategy):
    def __init__(
        self,
        symbol: str,
        fast_window: int = 20,
        slow_window: int = 60,
        long_percent: float = 1.0,
        flat_percent: float = 0.0,
        name: str = "ma_cross",
    ) -> None:
        if fast_window <= 0 or slow_window <= 0 or fast_window >= slow_window:
            raise ValueError("Require 0 < fast_window < slow_window")
        self.symbol = symbol
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.long_percent = long_percent
        self.flat_percent = flat_percent
        self.name = name

    def on_bar(
        self,
        ts: pd.Timestamp,
        history: dict[str, pd.DataFrame],
        portfolio: dict,
    ) -> list[TargetSignal]:
        bars = history.get(self.symbol)
        if bars is None or len(bars) < self.slow_window:
            return []

        closes = bars["close"]
        fast = float(closes.iloc[-self.fast_window :].mean())
        slow = float(closes.iloc[-self.slow_window :].mean())
        target = self.long_percent if fast > slow else self.flat_percent
        return [TargetSignal(symbol=self.symbol, target_percent=target, strategy=self.name)]


@dataclass
class MinuteBacktestConfig:
    market: StockMarket
    initial_cash: float = 1_000_000.0
    fee_model: StockFeeModel | None = None
    slippage_bps: float = 0.0
    lot_size: float | None = None
    max_position_pct: float = 1.0
    allow_short: bool = False
    periods: int | None = None

    def resolved_fee_model(self) -> StockFeeModel:
        return self.fee_model or DEFAULT_FEE_MODELS[self.market]

    def resolved_lot_size(self) -> float:
        if self.lot_size is not None:
            return self.lot_size
        return 1000.0 if self.market == StockMarket.TW else 1.0

    def resolved_periods(self) -> int:
        return self.periods or annualization_periods(self.market)


class MinuteBarBacktester:
    """Executes target-weight signals on the next bar open."""

    def __init__(
        self,
        bars: pd.DataFrame | dict[str, pd.DataFrame],
        strategy: StockStrategy,
        config: MinuteBacktestConfig,
    ) -> None:
        self.bars = _normalize_bar_input(bars)
        self.strategy = strategy
        self.config = config
        self.fee_model = config.resolved_fee_model()
        self.cash = float(config.initial_cash)
        self.positions = {symbol: StockPosition(symbol=symbol) for symbol in self.bars}
        self.orders: list[dict] = []
        self.fills: list[dict] = []
        self.position_samples: list[dict] = []
        self.equity_samples: list[dict] = []

    def run(self) -> StockBacktestResult:
        pending_targets: list[TargetSignal] = []
        history = {symbol: pd.DataFrame(columns=df.columns) for symbol, df in self.bars.items()}
        all_index = sorted(set().union(*(df.index for df in self.bars.values())))

        for ts in all_index:
            self._execute_targets(ts, pending_targets)
            pending_targets = []

            for symbol, df in self.bars.items():
                if ts in df.index:
                    history[symbol] = df.loc[:ts]

            equity = self._equity_at(ts)
            self._record_equity(ts, equity)
            self._record_positions(ts)
            pending_targets = self.strategy.on_bar(
                ts=ts,
                history=history,
                portfolio=self._portfolio_snapshot(ts),
            )

        equity_curve = pd.Series(
            [row["equity"] for row in self.equity_samples],
            index=pd.DatetimeIndex([row["ts"] for row in self.equity_samples]),
            name="equity",
        )
        returns = equity_curve.pct_change().fillna(0.0)
        return StockBacktestResult(
            equity_curve=equity_curve,
            returns=returns,
            metrics=summary(returns, periods=self.config.resolved_periods()),
            orders=pd.DataFrame(self.orders),
            fills=pd.DataFrame(self.fills),
            positions=pd.DataFrame(self.position_samples),
        )

    def _execute_targets(self, ts: pd.Timestamp, targets: list[TargetSignal]) -> None:
        if not targets:
            return
        equity = self._equity_at(ts)
        for signal in targets:
            bar = self._bar_at(signal.symbol, ts)
            if bar is None:
                continue
            target_pct = float(np.clip(
                signal.target_percent,
                -self.config.max_position_pct,
                self.config.max_position_pct,
            ))
            if not self.config.allow_short:
                target_pct = max(0.0, target_pct)

            open_px = float(bar["open"])
            target_qty = self._round_quantity((equity * target_pct) / open_px)
            current_qty = self.positions[signal.symbol].quantity
            delta_qty = target_qty - current_qty
            if abs(delta_qty) < max(self.config.resolved_lot_size(), 1e-12):
                continue

            side = OrderSide.BUY if delta_qty > 0 else OrderSide.SELL
            fill_px = self._slipped_price(open_px, side)
            quantity = abs(delta_qty)
            if side == OrderSide.BUY:
                quantity = self._cap_buy_quantity(quantity, fill_px)
            if quantity <= 0:
                continue

            order = StockOrder(
                symbol=signal.symbol,
                market=self.config.market,
                side=side,
                quantity=quantity,
                order_type=OrderType.MARKET,
                strategy=signal.strategy,
                metadata=dict(signal.metadata),
            )
            fill = self._fill_order(order, ts, fill_px)
            self._record_order(order, ts)
            self._apply_fill(fill)

    def _bar_at(self, symbol: str, ts: pd.Timestamp) -> pd.Series | None:
        df = self.bars.get(symbol)
        if df is None or ts not in df.index:
            return None
        return df.loc[ts]

    def _slipped_price(self, open_price: float, side: OrderSide) -> float:
        slippage = self.config.slippage_bps / 10_000.0
        if side == OrderSide.BUY:
            return open_price * (1 + slippage)
        return open_price * (1 - slippage)

    def _round_quantity(self, quantity: float) -> float:
        lot = self.config.resolved_lot_size()
        if lot <= 0:
            return float(quantity)
        if quantity >= 0:
            return float(np.floor(quantity / lot) * lot)
        return float(np.ceil(quantity / lot) * lot)

    def _cap_buy_quantity(self, quantity: float, price: float) -> float:
        lot = self.config.resolved_lot_size()
        affordable = quantity
        while affordable > 0:
            fee, tax = self.fee_model.estimate(OrderSide.BUY, price, affordable)
            if affordable * price + fee + tax <= self.cash:
                return affordable
            affordable -= lot
        return 0.0

    def _fill_order(self, order: StockOrder, ts: pd.Timestamp, price: float) -> StockFill:
        fee, tax = self.fee_model.estimate(order.side, price, order.quantity)
        return StockFill(
            symbol=order.symbol,
            market=order.market,
            side=order.side,
            quantity=order.quantity,
            price=price,
            fee=fee,
            tax=tax,
            ts=ts,
            order_id=f"bt-{len(self.fills) + 1}",
            client_order_id=order.client_order_id,
            strategy=order.strategy,
            metadata=dict(order.metadata),
        )

    def _apply_fill(self, fill: StockFill) -> None:
        self.cash += fill.cash_flow
        self.positions[fill.symbol].apply_fill(fill)
        self.fills.append({
            "ts": fill.ts,
            "symbol": fill.symbol,
            "market": fill.market.value,
            "side": fill.side.value,
            "quantity": fill.quantity,
            "price": fill.price,
            "fee": fill.fee,
            "tax": fill.tax,
            "cash_flow": fill.cash_flow,
            "strategy": fill.strategy,
            "client_order_id": fill.client_order_id,
        })

    def _record_order(self, order: StockOrder, ts: pd.Timestamp) -> None:
        self.orders.append({
            "ts": ts,
            "symbol": order.symbol,
            "market": order.market.value,
            "side": order.side.value,
            "quantity": order.quantity,
            "order_type": order.order_type.value,
            "strategy": order.strategy,
            "client_order_id": order.client_order_id,
        })

    def _equity_at(self, ts: pd.Timestamp) -> float:
        equity = self.cash
        for symbol, position in self.positions.items():
            price = self._last_close(symbol, ts)
            equity += position.quantity * price
        return float(equity)

    def _last_close(self, symbol: str, ts: pd.Timestamp) -> float:
        df = self.bars[symbol]
        visible = df.loc[:ts]
        if visible.empty:
            return 0.0
        return float(visible["close"].iloc[-1])

    def _portfolio_snapshot(self, ts: pd.Timestamp) -> dict:
        return {
            "cash": self.cash,
            "equity": self._equity_at(ts),
            "positions": {symbol: pos.quantity for symbol, pos in self.positions.items()},
        }

    def _record_equity(self, ts: pd.Timestamp, equity: float) -> None:
        self.equity_samples.append({"ts": ts, "equity": equity})

    def _record_positions(self, ts: pd.Timestamp) -> None:
        for symbol, position in self.positions.items():
            self.position_samples.append({
                "ts": ts,
                "symbol": symbol,
                "quantity": position.quantity,
                "avg_price": position.avg_price,
            })


def _normalize_bar_input(bars: pd.DataFrame | dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    if isinstance(bars, pd.DataFrame):
        symbol = str(bars["symbol"].iloc[0]) if "symbol" in bars.columns and not bars.empty else "UNKNOWN"
        return {symbol: bars.sort_index()}
    return {symbol: df.sort_index() for symbol, df in bars.items()}
