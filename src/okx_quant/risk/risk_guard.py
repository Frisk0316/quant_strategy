"""
Hard-coded risk gate — every order MUST pass through this.
No strategy can bypass it.

Extracted from §5.5 of Crypto_Quant_Plan_v1.md.
Iron laws from §6: 5% daily loss, 10% soft stop, 15% hard stop.
"""
from __future__ import annotations

import time
from typing import Callable

from loguru import logger

from okx_quant.core.events import OrderPayload
from okx_quant.risk.drawdown_tracker import DrawdownTracker, RiskLevel


class RiskGuard:
    def __init__(
        self,
        equity_fn: Callable[[], float],
        drawdown_tracker: DrawdownTracker,
        # Limits (defaults match config/risk.yaml)
        max_order_notional_usd: float = 500.0,
        max_pos_pct_equity: float = 0.30,
        max_leverage: float = 3.0,
        max_daily_loss_pct: float = 0.05,
        soft_drawdown_pct: float = 0.10,
        hard_drawdown_pct: float = 0.15,
        stale_quote_pct: float = 0.02,
    ) -> None:
        self._equity_fn = equity_fn
        self._dd_tracker = drawdown_tracker
        self.max_order_notional = max_order_notional_usd
        self.max_pos_pct = max_pos_pct_equity
        self.max_leverage = max_leverage
        self.max_daily_loss_pct = max_daily_loss_pct
        self.soft_drawdown_pct = soft_drawdown_pct
        self.hard_drawdown_pct = hard_drawdown_pct
        self.stale_quote_pct = stale_quote_pct

        # State
        self.kill: bool = False
        self._kill_reason: str | None = None
        self.soft_stop: bool = False
        self._strategy_size_multipliers: dict[str, float] = {}
        self.last_block_reason: str | None = None
        self.last_bypass_reason: str | None = None

    # ------------------------------------------------------------------
    # Main gate
    # ------------------------------------------------------------------

    def check(
        self,
        order: OrderPayload,
        current_pos_notional: float = 0.0,
        current_mid: float = 0.0,
    ) -> bool:
        """
        Synchronous risk check. Called for every order before submission.
        Returns False (block) if any limit is breached.
        """
        self.last_block_reason = None
        self.last_bypass_reason = None
        is_reduce_only = bool(getattr(order, "reduce_only", False))

        def note_reduce_only_bypass(reason: str) -> None:
            if not is_reduce_only:
                return
            if self.last_bypass_reason:
                self.last_bypass_reason = f"{self.last_bypass_reason}+{reason}"
            else:
                self.last_bypass_reason = reason

        if self.kill:
            if not is_reduce_only:
                logger.warning("Order blocked: kill switch active", inst_id=order.inst_id, reason=self._kill_reason)
                self.last_block_reason = self._kill_reason or "kill_switch"
                return False
            note_reduce_only_bypass(self._kill_reason or "kill_switch")

        eq = self._equity_fn()
        if eq <= 0:
            logger.error("Order blocked: equity is zero or negative", equity=eq)
            self.last_block_reason = "non_positive_equity"
            return False

        # Fat-finger guard
        if order.notional_usd > 0:
            notional = order.notional_usd
        else:
            try:
                notional = float(order.sz) * float(order.px)
            except (ValueError, TypeError):
                logger.warning("Order blocked: cannot parse sz/px", sz=order.sz, px=order.px)
                self.last_block_reason = "invalid_order_size_or_price"
                return False

        if notional > self.max_order_notional:
            logger.warning(
                "Order blocked: fat-finger",
                notional=notional,
                limit=self.max_order_notional,
                inst_id=order.inst_id,
            )
            self.last_block_reason = "fat_finger"
            return False

        # Position size limit
        if current_pos_notional + notional > self.max_pos_pct * eq:
            if not is_reduce_only:
                logger.warning(
                    "Order blocked: position limit",
                    pos_notional=current_pos_notional + notional,
                    limit=self.max_pos_pct * eq,
                )
                self.last_block_reason = "position_limit"
                return False
            note_reduce_only_bypass("position_limit")

        # Stale quote check
        if current_mid > 0:
            price = float(order.px)
            drift = abs(price - current_mid) / current_mid
            if drift > self.stale_quote_pct:
                logger.debug(
                    "Order blocked: stale quote",
                    price=price,
                    mid=current_mid,
                    drift_pct=drift * 100,
                )
                self.last_block_reason = "stale_quote"
                return False

        # Daily loss check
        risk_level = self._dd_tracker.check_thresholds()
        if risk_level == RiskLevel.HARD_STOP:
            daily_loss_hit = self._dd_tracker.daily_pnl_pct() < -self.max_daily_loss_pct
            hard_drawdown_hit = self._dd_tracker.current_drawdown() <= -self.hard_drawdown_pct
            reason = "drawdown threshold breached" if hard_drawdown_hit else (
                "daily_loss_limit" if daily_loss_hit else "drawdown threshold breached"
            )
            self.trigger_hard_stop(reason)
            if not is_reduce_only:
                self.last_block_reason = reason
                return False
            note_reduce_only_bypass(reason)
        if risk_level == RiskLevel.SOFT_STOP and not self.soft_stop:
            self.trigger_soft_stop()

        # Daily loss hard limit
        daily_pnl_pct = self._dd_tracker.daily_pnl() / eq
        if daily_pnl_pct < -self.max_daily_loss_pct:
            logger.error(
                "Order blocked: daily loss limit",
                daily_pnl_pct=daily_pnl_pct * 100,
            )
            self.kill = True
            self._kill_reason = "daily_loss_limit"
            if not is_reduce_only:
                self.last_block_reason = "daily_loss_limit"
                return False
            note_reduce_only_bypass("daily_loss_limit")

        if self.last_bypass_reason:
            logger.warning(
                "Reduce-only risk bypass",
                inst_id=order.inst_id,
                strategy=order.strategy,
                cl_ord_id=order.cl_ord_id,
                reason=self.last_bypass_reason,
                notional=notional,
            )

        return True

    # ------------------------------------------------------------------
    # Soft / Hard stops
    # ------------------------------------------------------------------

    def trigger_soft_stop(self, reason: str = "drawdown soft threshold") -> None:
        """Halve all strategy size multipliers."""
        if self.soft_stop:
            return
        self.soft_stop = True
        for k in self._strategy_size_multipliers:
            self._strategy_size_multipliers[k] = 0.5
        logger.warning("Soft stop triggered", reason=reason)

    def trigger_hard_stop(self, reason: str = "drawdown hard threshold") -> None:
        """Kill all trading. Caller must close positions."""
        self.kill = True
        self._kill_reason = reason
        self.soft_stop = True
        logger.error("HARD STOP triggered", reason=reason)

    def reset(self) -> None:
        """Manual reset after cooldown period. Requires operator confirmation."""
        self.kill = False
        self._kill_reason = None
        self.soft_stop = False
        for k in self._strategy_size_multipliers:
            self._strategy_size_multipliers[k] = 1.0
        logger.info("RiskGuard reset by operator")

    # ------------------------------------------------------------------
    # Strategy size multipliers
    # ------------------------------------------------------------------

    def get_size_multiplier(self, strategy: str) -> float:
        """Returns current size multiplier for a strategy [0, 1]."""
        if self.kill:
            return 0.0
        return self._strategy_size_multipliers.get(strategy, 1.0)

    def register_strategy(self, strategy: str) -> None:
        self._strategy_size_multipliers[strategy] = 1.0

    def reset_daily(self) -> None:
        """Reset daily loss counter. Call at UTC midnight."""
        self._dd_tracker.reset_daily()
        if self.kill and self._kill_reason == "daily_loss_limit":
            self.kill = False
            self._kill_reason = None
        if self.soft_stop and not self.kill:
            self.soft_stop = False
            for k in self._strategy_size_multipliers:
                self._strategy_size_multipliers[k] = 1.0
        logger.info("Daily risk reset")
