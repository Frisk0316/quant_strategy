"""MA/EMA/MACD crossover strategies for replay backtesting.

These strategies are intentionally Long/Flat for v1. They consume replay
``books`` events at the selected bar cadence and emit directional signals only
on crossover transitions.
"""
from __future__ import annotations

from collections import deque
from typing import Optional

import pandas as pd

from okx_quant.core.events import Event, SignalPayload
from okx_quant.data.okx_book import OkxBook
from okx_quant.strategies.base import Strategy


def _validate_positive_int(value: object, name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if parsed <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return parsed


def _validate_fast_slow(fast: int, slow: int) -> None:
    if fast >= slow:
        raise ValueError("fast period/span must be smaller than slow period/span")


class _LongFlatCrossoverStrategy(Strategy):
    """Base class for single-leg Long/Flat crossover strategies."""

    warmup_bars: int

    def __init__(self, name: str, params: dict) -> None:
        super().__init__(name, params)
        symbols = params.get("symbols") or ["BTC-USDT-SWAP"]
        self.symbols: list[str] = list(dict.fromkeys(str(s) for s in symbols if s))
        if not self.symbols:
            raise ValueError(f"{name} requires at least one symbol")
        self._prices: dict[str, deque[float]] = {
            symbol: deque(maxlen=max(self.warmup_bars * 4, self.warmup_bars + 8))
            for symbol in self.symbols
        }
        self._prev_fast: dict[str, float | None] = {symbol: None for symbol in self.symbols}
        self._prev_slow: dict[str, float | None] = {symbol: None for symbol in self.symbols}
        self._in_position: dict[str, bool] = {symbol: False for symbol in self.symbols}

    async def on_market(
        self,
        event: Event,
        book: Optional[OkxBook] = None,
    ) -> Optional[SignalPayload]:
        payload = event.payload
        inst_id = getattr(payload, "inst_id", "")
        if not self.is_active or inst_id not in self.symbols:
            return None
        if getattr(payload, "channel", "") != "books" or book is None or not book.is_valid():
            return None

        price = float(book.mid())
        prices = self._prices[inst_id]
        prices.append(price)
        if len(prices) < self.warmup_bars:
            return None

        fast_value, slow_value, metadata = self._indicator_values(list(prices))
        prev_fast = self._prev_fast[inst_id]
        prev_slow = self._prev_slow[inst_id]
        self._prev_fast[inst_id] = fast_value
        self._prev_slow[inst_id] = slow_value

        if prev_fast is None or prev_slow is None:
            return None

        crossed_up = prev_fast <= prev_slow and fast_value > slow_value
        crossed_down = prev_fast >= prev_slow and fast_value < slow_value

        if crossed_up and not self._in_position[inst_id]:
            return self._signal(inst_id, "buy", price, "entry", metadata)
        if crossed_down and self._in_position[inst_id]:
            return self._signal(inst_id, "sell", price, "exit", metadata)
        return None

    def _signal(
        self,
        inst_id: str,
        side: str,
        price: float,
        action: str,
        metadata: dict,
    ) -> SignalPayload:
        return SignalPayload(
            strategy=self.name,
            inst_id=inst_id,
            side=side,
            strength=1.0,
            fair_value=price,
            metadata={
                **metadata,
                "action": action,
                "mode": "long_flat",
            },
        )

    async def on_fill(self, event: Event) -> None:
        fill = event.payload
        if fill.strategy != self.name or fill.inst_id not in self._in_position:
            return
        if fill.fill_sz <= 0:
            return
        if fill.side == "buy":
            self._in_position[fill.inst_id] = True
        elif fill.side == "sell":
            self._in_position[fill.inst_id] = False

    def _indicator_values(self, prices: list[float]) -> tuple[float, float, dict]:
        raise NotImplementedError


class MACrossoverStrategy(_LongFlatCrossoverStrategy):
    def __init__(self, params: dict) -> None:
        self.fast_window = _validate_positive_int(params.get("fast_window", 20), "fast_window")
        self.slow_window = _validate_positive_int(params.get("slow_window", 50), "slow_window")
        _validate_fast_slow(self.fast_window, self.slow_window)
        self.warmup_bars = self.slow_window
        super().__init__("ma_crossover", params)

    def _indicator_values(self, prices: list[float]) -> tuple[float, float, dict]:
        series = pd.Series(prices, dtype=float)
        fast = float(series.rolling(self.fast_window).mean().iloc[-1])
        slow = float(series.rolling(self.slow_window).mean().iloc[-1])
        return fast, slow, {
            "fast_window": self.fast_window,
            "slow_window": self.slow_window,
            "fast_ma": fast,
            "slow_ma": slow,
        }


class EMACrossoverStrategy(_LongFlatCrossoverStrategy):
    def __init__(self, params: dict) -> None:
        self.fast_span = _validate_positive_int(params.get("fast_span", 20), "fast_span")
        self.slow_span = _validate_positive_int(params.get("slow_span", 50), "slow_span")
        _validate_fast_slow(self.fast_span, self.slow_span)
        self.warmup_bars = self.slow_span
        super().__init__("ema_crossover", params)

    def _indicator_values(self, prices: list[float]) -> tuple[float, float, dict]:
        series = pd.Series(prices, dtype=float)
        fast = float(series.ewm(span=self.fast_span, adjust=False).mean().iloc[-1])
        slow = float(series.ewm(span=self.slow_span, adjust=False).mean().iloc[-1])
        return fast, slow, {
            "fast_span": self.fast_span,
            "slow_span": self.slow_span,
            "fast_ema": fast,
            "slow_ema": slow,
        }


class MACDCrossoverStrategy(_LongFlatCrossoverStrategy):
    def __init__(self, params: dict) -> None:
        self.fast_span = _validate_positive_int(params.get("fast_span", 12), "fast_span")
        self.slow_span = _validate_positive_int(params.get("slow_span", 26), "slow_span")
        self.signal_span = _validate_positive_int(params.get("signal_span", 9), "signal_span")
        _validate_fast_slow(self.fast_span, self.slow_span)
        self.warmup_bars = self.slow_span + self.signal_span
        super().__init__("macd_crossover", params)

    def _indicator_values(self, prices: list[float]) -> tuple[float, float, dict]:
        series = pd.Series(prices, dtype=float)
        fast_ema = series.ewm(span=self.fast_span, adjust=False).mean()
        slow_ema = series.ewm(span=self.slow_span, adjust=False).mean()
        macd = fast_ema - slow_ema
        signal = macd.ewm(span=self.signal_span, adjust=False).mean()
        macd_value = float(macd.iloc[-1])
        signal_value = float(signal.iloc[-1])
        return macd_value, signal_value, {
            "fast_span": self.fast_span,
            "slow_span": self.slow_span,
            "signal_span": self.signal_span,
            "macd": macd_value,
            "macd_signal": signal_value,
        }
