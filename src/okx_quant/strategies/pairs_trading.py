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
        dict with theta, mu, sigma, half_life in observed bars
    """
    lag = spread.shift(1).dropna()
    dlt = spread.diff().dropna()
    # Align
    idx = lag.index.intersection(dlt.index)
    lag = lag.loc[idx]
    dlt = dlt.loc[idx]
    if len(lag) < 10:
        return {"theta": 0.0, "mu": float(spread.mean()), "sigma": float(spread.std()), "half_life": np.inf}
    X = sm.add_constant(lag)
    res = sm.OLS(dlt, X).fit()
    a, b = res.params
    if b >= 0:
        return {"theta": 0.0, "mu": float(spread.mean()), "sigma": float(spread.std()), "half_life": np.inf}
    theta = -b
    mu = -a / b
    sigma = float(np.std(res.resid)) * np.sqrt(-2 * b / (1 - np.exp(2 * b)))
    half_life = np.log(2) / theta
    return dict(theta=theta, mu=mu, sigma=sigma, half_life=half_life)


def _payload_ts_ms(payload: object, event: Event) -> int:
    raw = getattr(payload, "ts", None)
    if raw is None:
        raw = event.ts
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0
    if 0 < value < 1e11:
        value *= 1000
    return int(value)


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
        self.bar_seconds: int = int(params.get("bar_seconds", 3600))
        # Unit: hours. OU estimates half-life in bars; the quality gate converts.
        self.max_half_life_hours: float = params.get(
            "max_half_life_hours",
            params.get("max_half_life", 48.0),
        )
        self.max_hedge_uncertainty: float = params.get("max_hedge_uncertainty", 10.0)

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
        self._price_ts_ms: dict[str, int] = {}
        self._spread_history: deque = deque(maxlen=self.lookback_hours * 60)
        self._spread_interval_ms: deque = deque(maxlen=self.lookback_hours * 60)
        self._ou_params: dict = {"theta": 0.0, "mu": np.nan, "sigma": np.nan, "half_life": np.inf}
        self._ou_calibrated: bool = False
        self._z_score: float = 0.0
        self._in_position: bool = False
        self._position_side: str = ""  # 'long_y' or 'short_y'
        self._last_ou_update_ms: int = 0
        self._last_spread_ts_ms: int = 0

    def _quality_gate_passed(self) -> tuple[bool, str]:
        """Return whether current spread parameters are tradeable."""
        if not self._ou_calibrated:
            return False, "not_calibrated"
        half_life_bars = float(self._ou_params.get("half_life", np.inf))
        half_life_hours = half_life_bars * max(self.bar_seconds, 1) / 3600.0
        sigma = float(self._ou_params.get("sigma", 0.0))
        if not np.isfinite(half_life_bars) or half_life_bars <= 0:
            return False, "invalid_half_life"
        if half_life_hours > self.max_half_life_hours:
            return False, "half_life_too_slow"
        if sigma <= 0 or not np.isfinite(sigma):
            return False, "invalid_spread_sigma"
        if self._P > self.max_hedge_uncertainty:
            return False, "hedge_ratio_uncertain"
        return True, "passed"

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
        current_ts_ms = _payload_ts_ms(payload, event)
        self._prices[inst_id].append(mid)
        self._price_ts_ms[inst_id] = current_ts_ms

        # Need prices for both symbols
        if (not self._prices[self.symbol_y] or not self._prices[self.symbol_x]):
            return None
        if self.symbol_y not in self._price_ts_ms or self.symbol_x not in self._price_ts_ms:
            return None

        pair_ts_ms = min(self._price_ts_ms[self.symbol_y], self._price_ts_ms[self.symbol_x])
        if pair_ts_ms <= self._last_spread_ts_ms:
            return None

        price_y = self._prices[self.symbol_y][-1]
        price_x = self._prices[self.symbol_x][-1]

        # Update Kalman filter
        log_y = np.log(price_y)
        log_x = np.log(price_x)
        spread = self._kalman_update(log_y, log_x)
        self._spread_history.append(spread)
        if self._last_spread_ts_ms > 0:
            interval_ms = pair_ts_ms - self._last_spread_ts_ms
            if interval_ms > 0:
                self._spread_interval_ms.append(interval_ms)
        self._last_spread_ts_ms = pair_ts_ms

        # Recalibrate OU parameters every simulated hour.
        if current_ts_ms - self._last_ou_update_ms > 3_600_000 and len(self._spread_history) > 100:
            spread_series = pd.Series(list(self._spread_history))
            self._ou_params = estimate_ou(spread_series)
            self._ou_calibrated = True
            self._last_ou_update_ms = current_ts_ms
            logger.debug("OU recalibrated", **self._ou_params)

        # Compute z-score
        mu = float(self._ou_params["mu"])
        sigma = float(self._ou_params["sigma"])
        if sigma > 0 and np.isfinite(sigma) and np.isfinite(mu):
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
            gate_ok, gate_reason = self._quality_gate_passed()
            if not gate_ok:
                logger.debug("Pairs entry blocked by quality gate", reason=gate_reason, z=z)
                return None
            side_y = "sell" if z > 0 else "buy"  # sell ETH when spread too high
            self._position_side = "short_y" if z > 0 else "long_y"
            logger.info("Pairs entry", z=z, side_y=side_y)
            half_life_bars = float(self._ou_params["half_life"])
            half_life_hours = half_life_bars * max(self.bar_seconds, 1) / 3600.0
            half_life_quality = max(0.0, 1.0 - half_life_hours / self.max_half_life_hours)
            return SignalPayload(
                strategy=self.name,
                inst_id=self.symbol_y,
                side=side_y,
                strength=min(abs(z) / self.entry_z, 1.0) * max(0.25, half_life_quality),
                fair_value=price_y,
                metadata={
                    "action": "entry",
                    "z_score": z,
                    "beta": self._beta,
                    "half_life": half_life_hours,
                    "half_life_bars": half_life_bars,
                    "half_life_hours": half_life_hours,
                    "hedge_uncertainty": self._P,
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
