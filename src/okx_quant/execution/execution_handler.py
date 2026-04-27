"""
Order execution lifecycle.
Validates, submits, and tracks fills. Emits FillEvents on confirmation.

KEY RULE: post_only rejection (error 51026) is logged but NEVER retried
as market order. This preserves the maker-only trading principle.
"""
from __future__ import annotations

import asyncio
import time

from loguru import logger

from okx_quant.core.bus import EventBus
from okx_quant.core.events import Event, EvtType, FillPayload, OrderPayload
from okx_quant.execution.broker import is_shadow_mirror_cl_ord_id
from okx_quant.execution.order_manager import OrderManager


class ExecutionHandler:
    def __init__(
        self,
        bus: EventBus,
        order_manager: OrderManager,
        stale_quote_pct: float = 0.02,
        fill_timeout_secs: float = 5.0,
    ) -> None:
        self._bus = bus
        self._order_manager = order_manager
        self._stale_quote_pct = stale_quote_pct
        self._fill_timeout = fill_timeout_secs

        # Last known mid prices per instrument (for stale check)
        self._last_mids: dict[str, float] = {}
        # Fill confirmations received via WS (cl_ord_id → FillPayload)
        self._ws_fills: dict[str, FillPayload] = {}

    # ------------------------------------------------------------------
    # Market event handler — update mid prices for stale check
    # ------------------------------------------------------------------

    async def on_market(self, event: Event) -> None:
        payload = event.payload
        if hasattr(payload, "bids") and payload.bids and payload.asks:
            try:
                mid = 0.5 * (float(payload.bids[0][0]) + float(payload.asks[0][0]))
                self._last_mids[payload.inst_id] = mid
            except (IndexError, TypeError, ValueError):
                pass

    # ------------------------------------------------------------------
    # Order event handler
    # ------------------------------------------------------------------

    async def on_order(self, event: Event) -> None:
        """
        Process an OrderEvent.
        1. Stale quote check (price vs current mid).
        2. Submit via OrderManager.
        3. Await fill confirmation (WS-based) or timeout.
        4. Emit FillEvent.
        """
        order: OrderPayload = event.payload

        # Stale quote check
        mid = self._last_mids.get(order.inst_id, 0.0)
        if mid > 0:
            try:
                price = float(order.px)
                drift = abs(price - mid) / mid
                if drift > self._stale_quote_pct:
                    logger.debug(
                        "Stale quote discarded",
                        inst_id=order.inst_id,
                        px=price,
                        mid=mid,
                        drift_pct=drift * 100,
                    )
                    return
            except (ValueError, TypeError):
                pass

        # Submit order
        fill = await self._order_manager.submit(order)
        if fill is None:
            return  # post_only rejected or error — already logged

        if fill.state == "filled":
            await self._bus.put(Event(EvtType.FILL, payload=fill))
            logger.debug("Immediate simulated fill", cl_ord_id=fill.cl_ord_id, inst_id=order.inst_id)
            return

        # For live/demo venues, fills come asynchronously via WS private channel.
        logger.debug("Order accepted by exchange", cl_ord_id=fill.cl_ord_id, inst_id=order.inst_id)

    # ------------------------------------------------------------------
    # WebSocket fill confirmation
    # ------------------------------------------------------------------

    async def on_fill_ws(self, raw_msg: dict) -> None:
        """
        Process order update from private WS channel.
        Called when WS receives 'orders' channel update.
        Emits FillEvent when state is 'filled' or 'partially_filled'.
        """
        for d in raw_msg.get("data", []):
            cl_ord_id = d.get("clOrdId", "")
            if is_shadow_mirror_cl_ord_id(cl_ord_id):
                logger.info(
                    "Shadow mirror fill received",
                    inst_id=d.get("instId", ""),
                    cl_ord_id=cl_ord_id,
                    state=d.get("state", ""),
                )
                continue

            state = d.get("state", "")
            if state not in ("filled", "partially_filled"):
                continue

            fill = FillPayload(
                cl_ord_id=cl_ord_id,
                ord_id=d.get("ordId", ""),
                inst_id=d.get("instId", ""),
                fill_px=float(d.get("fillPx", d.get("avgPx", 0))),
                fill_sz=float(d.get("fillSz", d.get("accFillSz", 0))),
                fee=float(d.get("fee", 0)),
                fee_ccy=d.get("feeCcy", "USDT"),
                side=d.get("side", ""),
                ts=int(d.get("uTime", time.time() * 1000)),
                strategy=d.get("tag", ""),
                state=state,
            )
            pending_order = self._order_manager.get_pending_order(cl_ord_id)
            if pending_order is not None:
                fill.strategy = pending_order.strategy
                fill.metadata = dict(pending_order.metadata)

            self._order_manager.on_fill(fill.cl_ord_id, fill.side, fill.strategy, fill.inst_id)
            await self._bus.put(Event(EvtType.FILL, payload=fill))
            logger.info(
                "Fill received",
                inst_id=fill.inst_id,
                side=fill.side,
                px=fill.fill_px,
                sz=fill.fill_sz,
                fee=fill.fee,
            )
