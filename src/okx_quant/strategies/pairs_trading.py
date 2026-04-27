"""
BTC-ETH Pairs Trading Strategy (Strategy 4).
Kalman filter dynamic hedge ratio + OU spread z-score.

Extracted from §1.6 of Crypto_Quant_Plan_v1.md.

Entry: |z| > 2.0  (buy laggard, sell leader)
Exit:  |z| < 0.3  (close both legs)
Stop:  |z| > 4.0  (emergency close)

Uses post_only limit orders. Both legs placed simultaneously.
"""
from __future__ import annotations

import time
from collections import deque
from typing import Optional

import numpy as np
import pandas as pd
import statsmodels.api as sm
from loguru import logger

from okx_quant.core.events import Event, SignalPayload
from okx_quant.strategies.base import Strategy


def estimate_ou(spread: pd.Series) -> dict:
    """
    Estimate Ornstein-Uhlenbeck parameters via AR(1) regression.
    From §1.6 of Crypto_Quant_Plan_v1.md.

    Returns:
        dict with theta, mu, sigma, half_life
    """
    lag = spread.shift(1).dropna()
    dlt = spread.diff().dropna()
    # Align
    idx = lag.index.intersection(dlt.index)
    lag = lag.loc[idx]
    dlt = dlt.loc[idx]
    if len(lag) < 10:
        return {"theta": 0.1, "mu": 0.0, "sigma": 0.01, "half_life": 6.93}
    X = sm.add_constant(lag)
    res = sm.OLS(dlt, X).fit()
    a, b = res.params
    if b >= 0:
        return {"theta": 0.01, "mu": float(spread.mean()), "sigma": float(spread.std()), "half_life": 69.3}
    theta = -b
    mu = -a / b
    sigma = float(np.std(res.resid)) * np.sqrt(-2 * b / (1 - np.exp(2 * b)))
    half_life = np.log(2) / theta
    return dict(theta=theta, mu=mu, sigma=sigma, half_life=half_life)


class PairsTradingStrategy(Strategy):
    def __init__(self, params: dict) -> None:
        super().__init__("pairs_trading", params)
        self.symbol_y: str = params.get("symbol_y", "ETH-USDT-SWAP")  # dependent
        self.symbol_x: str = params.get("symbol_x", "BTC-USDT-SWAP")  # independent
        self.kalman_delta: float = params.get("kalman_delta", 1e-4)
        self.entry_z: float = params.get("entry_z", 2.0)
        self.exit_z: float = params.get("exit_z", 0.3)
        self.stop_z: float = params.get("stop_z", 4.0)
        self.lookback_hours: int = params.get("lookback_hours", 168)

        # Kalman filter state: beta (hedge ratio)
        self._beta = 1.0
        self._P = 1.0  # Kalman covariance
        self._R = 1.0  # Observation noise (calibrated from data)
        self._Ve = self.kalman_delta / (1 - self.kalman_delta)  # Process noise variance

        # Price history for spread calculation
        self._prices: dict[str, deque] = {
            self.symbol_y: deque(maxlen=self.lookback_hours * 60),
            self.symbol_x: deque(maxlen=self.lookback_hours * 60),
        }
        self._spread_history: deque = deque(maxlen=self.lookback_hours * 60)
        self._ou_params: dict = {"theta": 0.1, "mu": 0.0, "sigma": 0.01, "half_life": 6.93}
        self._z_score: float = 0.0
        self._in_position: bool = False
        self._position_side: str = ""  # 'long_y' or 'short_y'
        self._last_ou_update: float = 0.0

    def _kalman_update(self, y: float, x: float) -> float:
        """
        Kalman filter update for dynamic hedge ratio.
        State: beta_t = beta_{t-1} + w_t (random walk)
        Observation: y_t = beta_t * x_t + v_t
        """
        # Prediction
        P_pred = self._P + self._Ve
        # Innovation
        y_pred = self._beta * x
        innov = y - y_pred
        # Innovation variance
        S = P_pred * x ** 2 + self._R
        if S == 0:
            return y - self._beta * x
        # Kalman gain
        K = P_pred * x / S
        # Update
        self._beta += K * innov
        self._P = (1 - K * x) * P_pred
        return innov  # residual / spread

    async def on_market(
        self,
        event: Event,
        book: Optional[object] = None,
    ) -> Optional[SignalPayload]:
        payload = event.payload
        inst_id = getattr(payload, "inst_id", "")
        channel = getattr(payload, "channel", "")

        if channel != "books" or inst_id not in (self.symbol_y, self.symbol_x):
            return None
        if not self.is_active:
            return None

        # Get current mid price from book
        if book is None or not book.is_valid():
            return None

        mid = book.mid()
        self._prices[inst_id].append(mid)

        # Need prices for both symbols
        if (len(self._prices[self.symbol_y]) < 2 or len(self._prices[self.symbol_x]) < 2):
            return None

        price_y = self._prices[self.symbol_y][-1]
        price_x = self._prices[self.symbol_x][-1]

        # Update Kalman filter
        log_y = np.log(price_y)
        log_x = np.log(price_x)
        spread = self._kalman_update(log_y, log_x)
        self._spread_history.append(spread)

        # Recalibrate OU parameters every hour
        now = time.time()
        if now - self._last_ou_update > 3600 and len(self._spread_history) > 100:
            spread_series = pd.Series(list(self._spread_history))
            self._ou_params = estimate_ou(spread_series)
            self._last_ou_update = now
            logger.debug("OU recalibrated", **self._ou_params)

        # Compute z-score
        mu = self._ou_params["mu"]
        sigma = self._ou_params["sigma"]
        if sigma > 0:
            self._z_score = (spread - mu) / sigma
        else:
            return None

        z = self._z_score

        # Emergency stop
        if abs(z) > self.stop_z and self._in_position:
            logger.warning("Pairs stop-loss triggered", z=z, inst_id=inst_id)
            return SignalPayload(
                strategy=self.name,
                inst_id=self.symbol_y,
                side="buy" if self._position_side == "short_y" else "sell",
                strength=1.0,
                fair_value=price_y,
                metadata={"action": "stop", "z_score": z, "beta": self._beta},
            )

        # Exit
        if self._in_position and abs(z) < self.exit_z:
            logger.info("Pairs exit", z=z)
            return SignalPayload(
                strategy=self.name,
                inst_id=self.symbol_y,
                side="buy" if self._position_side == "short_y" else "sell",
                strength=1.0 - abs(z) / self.exit_z,
                fair_value=price_y,
                metadata={"action": "exit", "z_score": z, "beta": self._beta},
            )

        # Entry
        if not self._in_position and abs(z) > self.entry_z:
            side_y = "sell" if z > 0 else "buy"  # sell ETH when spread too high
            self._position_side = "short_y" if z > 0 else "long_y"
            logger.info("Pairs entry", z=z, side_y=side_y)
            return SignalPayload(
                strategy=self.name,
                inst_id=self.symbol_y,
                side=side_y,
                strength=min(abs(z) / self.entry_z, 1.0),
                fair_value=price_y,
                metadata={
                    "action": "entry",
                    "z_score": z,
                    "beta": self._beta,
                    "hedge_inst_id": self.symbol_x,
                    "hedge_side": "buy" if side_y == "sell" else "sell",
                },
            )

        return None

    async def on_fill(self, event: Event) -> None:
        fill = event.payload
        if fill.strategy != self.name:
            return
        meta = getattr(fill, "metadata", {}) or {}
        action = meta.get("action", "")
        if action == "entry":
            self._in_position = True
        elif action in ("exit", "stop"):
            self._in_position = False
            self._position_side = ""
