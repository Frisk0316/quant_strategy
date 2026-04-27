"""
Equity curve tracking and drawdown calculation.
Triggers soft/hard stops based on config thresholds.
"""
from __future__ import annotations

import time
from collections import deque
from enum import Enum

from loguru import logger


class RiskLevel(Enum):
    NORMAL = "normal"
    SOFT_STOP = "soft_stop"
    HARD_STOP = "hard_stop"


class DrawdownTracker:
    def __init__(
        self,
        soft_drawdown_pct: float = 0.10,
        hard_drawdown_pct: float = 0.15,
        max_daily_loss_pct: float = 0.05,
        equity_buffer_size: int = 10_000,
    ) -> None:
        self._soft_dd = soft_drawdown_pct
        self._hard_dd = hard_drawdown_pct
        self._max_daily_loss = max_daily_loss_pct

        self._peak_equity: float = 0.0
        self._current_equity: float = 0.0
        self._day_start_equity: float = 0.0
        self._day_start_ts: float = time.time()

        # Ring buffer of (timestamp, equity) for Grafana
        self._equity_history: deque = deque(maxlen=equity_buffer_size)

    def update(self, equity: float) -> None:
        """Call after every fill or mark-to-market update."""
        self._current_equity = equity
        if equity > self._peak_equity:
            self._peak_equity = equity
        if self._day_start_equity == 0:
            self._day_start_equity = equity
        self._equity_history.append((time.time(), equity))

    def set_initial_equity(self, equity: float) -> None:
        self._peak_equity = equity
        self._current_equity = equity
        self._day_start_equity = equity

    def current_drawdown(self) -> float:
        """
        Rolling drawdown from peak equity.
        Returns negative number: e.g., -0.05 = 5% drawdown.
        """
        if self._peak_equity <= 0:
            return 0.0
        return (self._current_equity - self._peak_equity) / self._peak_equity

    def daily_pnl(self) -> float:
        """Absolute PnL since start of UTC day."""
        return self._current_equity - self._day_start_equity

    def daily_pnl_pct(self) -> float:
        if self._day_start_equity <= 0:
            return 0.0
        return self.daily_pnl() / self._day_start_equity

    def check_thresholds(self) -> RiskLevel:
        dd = self.current_drawdown()
        if dd <= -self._hard_dd:
            logger.error("Hard drawdown threshold hit", drawdown_pct=dd * 100)
            return RiskLevel.HARD_STOP
        if dd <= -self._soft_dd:
            logger.warning("Soft drawdown threshold hit", drawdown_pct=dd * 100)
            return RiskLevel.SOFT_STOP
        if self._day_start_equity > 0 and self.daily_pnl_pct() < -self._max_daily_loss:
            logger.error("Daily loss limit hit", daily_pnl_pct=self.daily_pnl_pct() * 100)
            return RiskLevel.HARD_STOP
        return RiskLevel.NORMAL

    def reset_daily(self) -> None:
        """Reset daily tracking at UTC midnight."""
        self._day_start_equity = self._current_equity
        self._day_start_ts = time.time()
        logger.info("Daily drawdown tracker reset", equity=self._current_equity)

    def get_equity_history(self) -> list[tuple[float, float]]:
        """Returns list of (timestamp, equity) tuples."""
        return list(self._equity_history)

    def stats(self) -> dict:
        return {
            "current_equity": self._current_equity,
            "peak_equity": self._peak_equity,
            "current_drawdown_pct": self.current_drawdown() * 100,
            "daily_pnl": self.daily_pnl(),
            "daily_pnl_pct": self.daily_pnl_pct() * 100,
        }
