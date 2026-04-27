"""
Idempotent order lifecycle management.
Tracks in-flight orders, handles cancel/amend, supports batch operations.
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Optional

from loguru import logger

from okx_quant.core.events import FillPayload, OrderPayload
from okx_quant.execution.broker import Broker
from okx_quant.execution.rate_limiter import RateLimiter


class OrderManager:
    def __init__(
        self,
        broker: Broker,
        rate_limiter: RateLimiter,
    ) -> None:
        self._broker = broker
        self._rate_limiter = rate_limiter
        # In-flight orders: cl_ord_id → OrderPayload
        self._pending: dict[str, OrderPayload] = {}
        # Per-strategy, per-instrument outstanding quote IDs
        self._quotes: dict[str, dict[str, list[str]]] = {}

    def generate_cl_ord_id(self) -> str:
        """Generate a UUID-based client order ID (max 32 chars for OKX)."""
        return uuid.uuid4().hex[:32]

    async def submit(self, order: OrderPayload) -> Optional[FillPayload]:
        """
        Submit an order. Returns broker response payload if accepted, None if rejected.
        Enforces rate limiting before submission.
        """
        await self._rate_limiter.acquire_trade(order.inst_id)

        order_dict = {
            "inst_id": order.inst_id,
            "side": order.side,
            "ord_type": order.ord_type,
            "sz": order.sz,
            "px": order.px,
            "td_mode": order.td_mode,
            "cl_ord_id": order.cl_ord_id,
            "reduce_only": order.reduce_only,
            "strategy": order.strategy,
            "metadata": order.metadata,
        }

        fill = await self._broker.submit(order_dict)
        if fill is not None:
            if fill.state == "pending":
                self._pending[order.cl_ord_id] = order
                # Track outstanding quotes per (strategy, inst_id)
                key = f"{order.strategy}:{order.inst_id}"
                if key not in self._quotes:
                    self._quotes[key] = {"buy": [], "sell": []}
                self._quotes[key][order.side].append(order.cl_ord_id)
            logger.debug("Order submitted", cl_ord_id=order.cl_ord_id, inst_id=order.inst_id, side=order.side)
            return fill
        return None

    async def cancel(self, inst_id: str, cl_ord_id: str) -> bool:
        """Cancel a single order."""
        await self._rate_limiter.acquire_trade(inst_id)
        result = await self._broker.cancel(inst_id, cl_ord_id)
        if result:
            self._pending.pop(cl_ord_id, None)
        return result

    async def cancel_all_quotes(self, strategy: str, inst_id: str, side: Optional[str] = None) -> int:
        """
        Cancel all outstanding quotes for a strategy/instrument pair.
        side: 'buy' | 'sell' | None (both sides).
        Returns number of cancels sent.
        """
        key = f"{strategy}:{inst_id}"
        if key not in self._quotes:
            return 0

        sides = [side] if side else ["buy", "sell"]
        cancelled = 0
        for s in sides:
            ids = list(self._quotes[key].get(s, []))
            # Batch cancel (max 20 per OKX)
            for i in range(0, len(ids), 20):
                batch = ids[i:i + 20]
                tasks = [self.cancel(inst_id, cid) for cid in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                cancelled += sum(1 for r in results if r is True)
            self._quotes[key][s] = []

        return cancelled

    def on_fill(self, cl_ord_id: str, side: str, strategy: str, inst_id: str) -> None:
        """Call when a fill is confirmed to remove from pending."""
        self._pending.pop(cl_ord_id, None)
        key = f"{strategy}:{inst_id}"
        if key in self._quotes:
            lst = self._quotes[key].get(side, [])
            if cl_ord_id in lst:
                lst.remove(cl_ord_id)

    def get_pending(self) -> dict[str, OrderPayload]:
        return dict(self._pending)

    def get_pending_order(self, cl_ord_id: str) -> Optional[OrderPayload]:
        return self._pending.get(cl_ord_id)
