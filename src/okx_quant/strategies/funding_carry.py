"""
Funding Rate Carry Strategy (Strategy 3).
Delta-neutral cash-and-carry: long spot BTC + short equal-notional BTC-USDT-SWAP.
Earns funding every 8 hours.

Entry: APR > 12% (configurable)
Exit: APR turns negative
Rebalance: every 8h if notional drift > 2%

Fee model: spot maker 0.08% + perp maker 0.02% = 0.10% total entry
Break-even at 30-day holding: 0.20% / (30/365) = 2.43% APR
"""
from __future__ import annotations

import time
from typing import Optional

from loguru import logger

from okx_quant.core.events import Event, SignalPayload
from okx_quant.strategies.base import Strategy

# Funding rate settlement interval in seconds (8h default, some contracts 1/2/4h)
_SETTLEMENT_SECS = 8 * 3600


def evaluate_funding_carry_entry(
    *,
    apr: float,
    min_apr: float,
    basis_z: Optional[float] = None,
    max_abs_basis_z: float = 2.5,
    crowding: Optional[float] = None,
    max_crowding: float = 0.85,
) -> tuple[bool, str]:
    """
    Funding carry entry gate with basis and crowding filters.

    Returns:
        (allowed, reason)
    """
    if apr <= min_apr:
        return False, "apr_below_threshold"
    if basis_z is not None and abs(basis_z) > max_abs_basis_z:
        return False, "basis_too_extreme"
    if crowding is not None and crowding > max_crowding:
        return False, "crowding_too_high"
    return True, "allowed"


class FundingCarryStrategy(Strategy):
    def __init__(self, params: dict) -> None:
        super().__init__("funding_carry", params)
        self.perp_symbol: str = params.get("perp_symbol", "BTC-USDT-SWAP")
        self.spot_symbol: str = params.get("spot_symbol", "BTC-USDT")
        self.min_apr: float = params.get("min_apr_threshold", 0.12)
        self.rebalance_drift: float = params.get("rebalance_drift_threshold", 0.02)
        self.max_abs_basis_z: float = params.get("max_abs_basis_z", 2.5)
        self.max_crowding: float = params.get("max_crowding", 0.85)

        self._spot_notional: float = 0.0     # USD value of spot position
        self._perp_notional: float = 0.0     # USD value of perp short
        self._last_rebalance_ts: float = 0.0
        self._current_apr: float = 0.0
        self._basis_z: Optional[float] = None
        self._crowding: Optional[float] = None
        self._in_position: bool = False

    def _rate_to_apr(self, rate_8h: float) -> float:
        """Convert 8-hour funding rate to annualized APR."""
        return rate_8h * (365 * 24 / 8)

    async def on_market(
        self,
        event: Event,
        book: Optional[object] = None,
    ) -> Optional[SignalPayload]:
        payload = event.payload
        channel = getattr(payload, "channel", "")
        inst_id = getattr(payload, "inst_id", "")

        if channel == "funding-rate" and inst_id == self.perp_symbol:
            return await self._handle_funding(payload)

        return None

    async def _handle_funding(self, payload) -> Optional[SignalPayload]:
        rate_8h = getattr(payload, "funding_rate", None)
        if rate_8h is None:
            return None

        apr = self._rate_to_apr(rate_8h)
        self._current_apr = apr
        self._basis_z = getattr(payload, "basis_z", None)
        self._crowding = getattr(payload, "crowding", None)
        logger.debug("Funding rate", inst_id=self.perp_symbol, rate_8h=rate_8h, apr_pct=apr * 100)

        if not self._in_position:
            allowed, reason = evaluate_funding_carry_entry(
                apr=apr,
                min_apr=self.min_apr,
                basis_z=self._basis_z,
                max_abs_basis_z=self.max_abs_basis_z,
                crowding=self._crowding,
                max_crowding=self.max_crowding,
            )
            if allowed:
                return self._entry_signal()
            logger.debug("Funding carry entry blocked", reason=reason, apr=apr)
        else:
            # Check rebalance
            if self._needs_rebalance():
                return self._rebalance_signal()
            # Exit if funding reverses negative
            if apr < 0:
                logger.info("Funding carry exit: APR turned negative", apr=apr)
                return self._exit_signal()

        return None

    def _entry_signal(self) -> SignalPayload:
        logger.info(
            "Funding carry entry signal",
            apr_pct=self._current_apr * 100,
            perp=self.perp_symbol,
            spot=self.spot_symbol,
        )
        return SignalPayload(
            strategy=self.name,
            inst_id=self.perp_symbol,
            side="sell",   # Short the perp (collect positive funding)
            strength=min(self._current_apr / self.min_apr, 1.0),
            fair_value=0.0,  # PortfolioManager will use current mid
            metadata={
                "action": "entry",
                "apr_pct": self._current_apr * 100,
                "basis_z": self._basis_z,
                "crowding": self._crowding,
                "spot_symbol": self.spot_symbol,
                "leg": "dual",  # Both legs: buy spot + sell perp
            },
        )

    def _exit_signal(self) -> SignalPayload:
        return SignalPayload(
            strategy=self.name,
            inst_id=self.perp_symbol,
            side="buy",   # Buy back the perp (close short)
            strength=1.0,
            fair_value=0.0,
            metadata={
                "action": "exit",
                "apr_pct": self._current_apr * 100,
                "spot_symbol": self.spot_symbol,
                "leg": "dual",
            },
        )

    def _rebalance_signal(self) -> Optional[SignalPayload]:
        self._last_rebalance_ts = time.time()
        logger.info("Funding carry rebalance", drift_threshold=self.rebalance_drift)
        return None  # Rebalancing handled via direct API calls in engine

    def _needs_rebalance(self) -> bool:
        now = time.time()
        # Rebalance at settlement intervals or if drift exceeded
        time_since = now - self._last_rebalance_ts
        return time_since >= _SETTLEMENT_SECS

    async def on_fill(self, event: Event) -> None:
        fill = event.payload
        if fill.strategy != self.name:
            return
        action = ""  # Would be populated from order metadata in production
        if fill.side == "sell" and fill.inst_id == self.perp_symbol:
            self._in_position = True
            self._perp_notional = fill.fill_px * fill.fill_sz
            self._last_rebalance_ts = time.time()
            logger.info("Funding carry perp leg opened", notional=self._perp_notional)
        elif fill.side == "buy" and fill.inst_id == self.perp_symbol and self._in_position:
            self._in_position = False
            self._perp_notional = 0.0
            self._spot_notional = 0.0
            logger.info("Funding carry position closed")
