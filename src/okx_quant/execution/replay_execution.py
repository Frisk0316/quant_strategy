"""Deterministic replay execution model for simulated maker orders."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Optional

from loguru import logger

from okx_quant.core.events import FillPayload, MarketPayload
from okx_quant.portfolio.sizing import validate_ct_val


@dataclass
class RestingOrder:
    order: dict
    remaining_sz: float
    submitted_ts: int
    active_ts: int
    cancel_requested_ts: Optional[int] = None
    cancel_effective_ts: Optional[int] = None


@dataclass
class ReplayExecutionModel:
    """Queue-aware-ish L1 replay model for post-only maker orders.

    This is intentionally deterministic and conservative. It does not claim L2
    price-time priority, but it models the key lifecycle missing from immediate
    fills: resting orders, post-only rejection, partial fills, and cancel
    latency.

    ``queue_fill_fraction`` represents the expected allocation share of local
    orders in the queue and should be calibrated from demo fill rate. ``1.0``
    is only an upper bound, not the default research value.
    """

    instrument_specs: dict
    maker_fee_rate: float = 0.0002
    order_latency_ms: int = 0
    cancel_latency_ms: int = 0
    queue_fill_fraction: float = 1.0
    default_ts: int = 0
    books: dict[str, dict[str, float]] = field(default_factory=dict)
    resting_orders: dict[str, RestingOrder] = field(default_factory=dict)
    rejected_log: list[dict] = field(default_factory=list)
    cancel_log: list[dict] = field(default_factory=list)

    def submit(self, order: dict) -> Optional[FillPayload]:
        inst_id = order["inst_id"]
        cl_ord_id = order.get("cl_ord_id", str(uuid.uuid4()))
        order = dict(order)
        order["cl_ord_id"] = cl_ord_id
        ts = self._current_ts(inst_id)

        if self._would_cross_book(order):
            self.rejected_log.append({
                "ts": ts,
                "cl_ord_id": cl_ord_id,
                "inst_id": inst_id,
                "side": order["side"],
                "px": float(order["px"]),
                "reason": "post_only_cross",
            })
            logger.debug("Replay post_only rejected", inst_id=inst_id, cl_ord_id=cl_ord_id)
            return None

        self.resting_orders[cl_ord_id] = RestingOrder(
            order=order,
            remaining_sz=float(order["sz"]),
            submitted_ts=ts,
            active_ts=ts + self.order_latency_ms,
        )

        return FillPayload(
            cl_ord_id=cl_ord_id,
            ord_id=f"replay-{cl_ord_id}",
            inst_id=inst_id,
            fill_px=0.0,
            fill_sz=0.0,
            fee=0.0,
            fee_ccy="USDT",
            side=order["side"],
            ts=ts,
            strategy=order.get("strategy", "sim"),
            state="pending",
            metadata=dict(order.get("metadata", {})),
        )

    def cancel(self, inst_id: str, cl_ord_id: str) -> bool:
        resting = self.resting_orders.get(cl_ord_id)
        if resting is None or resting.order["inst_id"] != inst_id:
            return False

        ts = self._current_ts(inst_id)
        if self.cancel_latency_ms <= 0:
            self.resting_orders.pop(cl_ord_id, None)
            self.cancel_log.append({"ts": ts, "cl_ord_id": cl_ord_id, "inst_id": inst_id, "state": "cancelled"})
            return True

        resting.cancel_requested_ts = ts
        resting.cancel_effective_ts = ts + self.cancel_latency_ms
        self.cancel_log.append({
            "ts": ts,
            "cl_ord_id": cl_ord_id,
            "inst_id": inst_id,
            "state": "cancel_requested",
            "effective_ts": resting.cancel_effective_ts,
        })
        return True

    def close_all(self) -> None:
        self.resting_orders.clear()

    def on_market(self, payload: MarketPayload) -> list[FillPayload]:
        if not payload.bids or not payload.asks:
            return []

        try:
            bid_px = float(payload.bids[0][0])
            bid_sz = float(payload.bids[0][1])
            ask_px = float(payload.asks[0][0])
            ask_sz = float(payload.asks[0][1])
        except (IndexError, TypeError, ValueError):
            return []

        self.books[payload.inst_id] = {
            "ts": int(payload.ts),
            "bid_px": bid_px,
            "bid_sz": bid_sz,
            "ask_px": ask_px,
            "ask_sz": ask_sz,
        }

        fills: list[FillPayload] = []
        for cl_ord_id, resting in list(self.resting_orders.items()):
            if resting.order["inst_id"] != payload.inst_id:
                continue
            if resting.cancel_effective_ts is not None and payload.ts >= resting.cancel_effective_ts:
                self.resting_orders.pop(cl_ord_id, None)
                self.cancel_log.append({
                    "ts": int(payload.ts),
                    "cl_ord_id": cl_ord_id,
                    "inst_id": payload.inst_id,
                    "state": "cancelled",
                })
                continue
            if payload.ts < resting.active_ts:
                continue

            fill = self._maybe_fill(resting, payload.ts, bid_px, bid_sz, ask_px, ask_sz)
            if fill is not None:
                fills.append(fill)
                if resting.remaining_sz <= 1e-12:
                    self.resting_orders.pop(cl_ord_id, None)

        return fills

    def _maybe_fill(
        self,
        resting: RestingOrder,
        ts: int,
        bid_px: float,
        bid_sz: float,
        ask_px: float,
        ask_sz: float,
    ) -> Optional[FillPayload]:
        order = resting.order
        side = order["side"]
        px = float(order["px"])

        if side == "buy":
            touched = ask_px <= px
            available = ask_sz
        else:
            touched = bid_px >= px
            available = bid_sz
        if not touched:
            return None

        queue_fraction = max(0.0, min(1.0, self.queue_fill_fraction))
        local_order_sz = float(order["sz"])
        fill_capacity = min(max(available, 0.0), local_order_sz) * queue_fraction
        fill_sz = min(resting.remaining_sz, fill_capacity)
        if fill_sz <= 0:
            return None

        resting.remaining_sz -= fill_sz
        state = "filled" if resting.remaining_sz <= 1e-12 else "partially_filled"
        ct_val = validate_ct_val(float(self.instrument_specs.get(order["inst_id"], {}).get("ctVal", 1.0)), order["inst_id"])
        notional_usd = px * fill_sz * ct_val
        fee = notional_usd * self.maker_fee_rate
        metadata = dict(order.get("metadata", {}))
        metadata.update({
            "notional_usd": notional_usd,
            "fee_rate": self.maker_fee_rate,
            "ct_val": ct_val,
            "remaining_sz": max(resting.remaining_sz, 0.0),
            "execution_model": "replay_l1_resting",
        })

        return FillPayload(
            cl_ord_id=order["cl_ord_id"],
            ord_id=f"replay-{order['cl_ord_id']}",
            inst_id=order["inst_id"],
            fill_px=px,
            fill_sz=fill_sz,
            fee=fee,
            fee_ccy="USDT",
            side=side,
            ts=int(ts),
            strategy=order.get("strategy", "sim"),
            state=state,
            metadata=metadata,
        )

    def _would_cross_book(self, order: dict) -> bool:
        book = self.books.get(order["inst_id"])
        if book is None:
            return False
        px = float(order["px"])
        if order["side"] == "buy":
            return px >= book["ask_px"]
        return px <= book["bid_px"]

    def _current_ts(self, inst_id: str) -> int:
        return self.current_ts(inst_id)

    def current_ts(self, inst_id: str) -> int:
        book = self.books.get(inst_id)
        if book is not None:
            return int(book["ts"])
        return self.default_ts
