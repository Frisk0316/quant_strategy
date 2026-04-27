"""
OBI/OFI Market Making Strategy.
Strategy 1: OBI + OFI driven post_only maker-only quoting.

Fair value = mid + c_alpha * ewma_ofi
Quotes refresh every 500ms (configurable).
Cancels bid (ask) side when inventory limit reached.
"""
from __future__ import annotations

import time
from collections import deque
from typing import Optional

import numpy as np
from loguru import logger

from okx_quant.core.events import Event, SignalPayload
from okx_quant.data.okx_book import OkxBook
from okx_quant.signals.obi_ofi import (
    book_to_l1_snap,
    compute_mlofi_increment,
    compute_obi_features,
    compute_ofi,
    ewma_ofi,
)
from okx_quant.strategies.base import Strategy


class OBIMarketMaker(Strategy):
    def __init__(self, params: dict) -> None:
        super().__init__("obi_market_maker", params)
        self.symbols: list[str] = params.get("symbols", ["BTC-USDT-SWAP"])
        self.depth: int = params.get("depth", 5)
        self.alpha_decay: float = params.get("alpha_decay", 0.5)
        self.ewma_halflife_ms: float = params.get("ewma_halflife_ms", 200.0)
        self.obi_threshold: float = params.get("obi_threshold", 0.15)
        self.c_alpha: float = params.get("c_alpha", 100.0)
        self.mlofi_weight: float = params.get("mlofi_weight", 1.0)
        self.refresh_ms: float = params.get("refresh_interval_ms", 500.0)
        self.max_inventory: int = params.get("max_inventory", 50)
        self.min_half_spread_ticks: int = 1

        # Per-symbol state
        self._inventory: dict[str, float] = {s: 0.0 for s in self.symbols}
        self._prev_snap: dict[str, Optional[dict]] = {s: None for s in self.symbols}
        self._prev_book: dict[str, Optional[tuple[np.ndarray, np.ndarray]]] = {
            s: None for s in self.symbols
        }
        self._ofi_series: dict[str, deque] = {s: deque(maxlen=50) for s in self.symbols}
        self._last_quote_ts: dict[str, float] = {s: 0.0 for s in self.symbols}

    async def on_market(
        self,
        event: Event,
        book: Optional[OkxBook] = None,
    ) -> Optional[SignalPayload]:
        payload = event.payload
        inst_id = getattr(payload, "inst_id", "")

        if inst_id not in self.symbols or not self.is_active:
            return None

        channel = getattr(payload, "channel", "")
        if channel != "books" or book is None or not book.is_valid():
            return None

        # Throttle refresh
        now = time.time()
        if now - self._last_quote_ts[inst_id] < self.refresh_ms / 1000:
            return None
        self._last_quote_ts[inst_id] = now

        bids, asks = book.to_array(depth=max(self.depth, 5))
        if len(bids) == 0:
            return None

        bids_list = [(bids[i, 0], bids[i, 1]) for i in range(len(bids)) if bids[i, 0] > 0]
        asks_list = [(asks[i, 0], asks[i, 1]) for i in range(len(asks)) if asks[i, 0] > 0]

        if not bids_list or not asks_list:
            return None

        features = compute_obi_features(bids_list, asks_list, depth=self.depth, alpha=self.alpha_decay)
        mid = features["mid"]
        spread = features["spread"]
        obi_l1 = features["obi_l1"]
        tick = spread / 2 if spread > 0 else 0.1

        # Compute OFI
        curr_snap = book_to_l1_snap(bids, asks)
        prev_snap = self._prev_snap[inst_id]
        if prev_snap is not None:
            ofi = compute_ofi(prev_snap, curr_snap)
            self._ofi_series[inst_id].append(ofi)
        self._prev_snap[inst_id] = curr_snap

        mlofi_signal = 0.0
        prev_book = self._prev_book[inst_id]
        if prev_book is not None:
            prev_bids, prev_asks = prev_book
            mlofi_signal = compute_mlofi_increment(
                prev_bids,
                prev_asks,
                bids,
                asks,
                depth=self.depth,
                decay_alpha=self.alpha_decay,
                normalize=True,
            )
        self._prev_book[inst_id] = (bids.copy(), asks.copy())

        ewma_ofi_val = ewma_ofi(
            np.array(self._ofi_series[inst_id]),
            halflife_ms=self.ewma_halflife_ms,
        )
        alpha_signal = ewma_ofi_val + self.mlofi_weight * mlofi_signal

        # Only generate signal when OBI exceeds threshold (filter noise)
        if abs(obi_l1) < self.obi_threshold and abs(alpha_signal) < 1e-6:
            return None

        # Fair value = mid + c_alpha * ewma_ofi
        fair = mid + self.c_alpha * alpha_signal

        # Minimum half-spread of 1 tick
        half_spread = max(tick * self.min_half_spread_ticks, spread * 0.3)
        bid = round((fair - half_spread) / tick) * tick
        ask = round((fair + half_spread) / tick) * tick

        inventory = self._inventory[inst_id]

        # Cancel side at inventory limit
        target_bid = bid if inventory < self.max_inventory else None
        target_ask = ask if inventory > -self.max_inventory else None

        if target_bid is None and target_ask is None:
            return None

        return SignalPayload(
            strategy=self.name,
            inst_id=inst_id,
            side="neutral",
            strength=min(abs(obi_l1), 1.0),
            fair_value=fair,
            target_bid=target_bid,
            target_ask=target_ask,
            metadata={
                "obi_l1": obi_l1,
                "obi_multi": features["obi_multi"],
                "ewma_ofi": ewma_ofi_val,
                "mlofi_signal": mlofi_signal,
                "alpha_signal": alpha_signal,
                "mid": mid,
                "spread": spread,
                "inventory": inventory,
            },
        )

    async def on_fill(self, event: Event) -> None:
        fill = event.payload
        if fill.inst_id not in self._inventory:
            return
        delta = fill.fill_sz if fill.side == "buy" else -fill.fill_sz
        self._inventory[fill.inst_id] += delta
