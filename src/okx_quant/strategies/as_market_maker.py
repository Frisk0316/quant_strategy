"""
Avellaneda-Stoikov Market Making Strategy.
Strategy 2 from the plan (built first because most complete in §1.3).

Key design decisions:
- T_minus_t = 1.0 (ergodic limit for 24/7 markets — do NOT use finite T).
- VPIN controls SPREAD WIDTH only, never trade direction.
- Direction comes from OBI/OFI alpha_signal.
- kappa recalibrated hourly from recent trade data.

Reference: Avellaneda-Stoikov (2008), GLFT ergodic limit (2013)
"""
from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import Optional

import numpy as np
import pandas as pd
from loguru import logger

from okx_quant.core.events import Event, SignalPayload
from okx_quant.data.okx_book import OkxBook
from okx_quant.signals.obi_ofi import compute_obi_features, compute_ofi, ewma_ofi, book_to_l1_snap
from okx_quant.signals.vpin import compute_vpin, vpin_spread_multiplier
from okx_quant.strategies.base import Strategy


def as_quote(
    mid: float,
    inventory: float,
    alpha_signal: float,
    vpin: float,
    gamma: float = 0.1,
    sigma: float = 0.003,
    kappa: float = 1.5,
    T_minus_t: float = 1.0,
    tick: float = 0.1,
    max_pos: int = 50,
    c_alpha: float = 100.0,
    beta_vpin: float = 2.0,
) -> tuple[float, float]:
    """
    Compute Avellaneda-Stoikov bid and ask quotes.
    Extracted from §1.3 of Crypto_Quant_Plan_v1.md.

    Args:
        mid: Current mid-price.
        inventory: Current inventory in contracts (+long, -short).
        alpha_signal: OFI-based directional alpha (scaled to tick units).
        vpin: Current VPIN CDF value in [0, 1].
        gamma: Risk aversion (0.01–0.5).
        sigma: Short-term price volatility (EWMA over 5min).
        kappa: Order arrival intensity decay.
        T_minus_t: Time horizon (1.0 = ergodic limit for 24/7 markets).
        tick: Minimum price increment.
        max_pos: Maximum inventory before cancelling that side.
        c_alpha: Alpha scaling coefficient (~100 ticks).
        beta_vpin: VPIN spread sensitivity (default 2.0).

    Returns:
        (bid, ask) rounded to tick size.
    """
    fair = mid + c_alpha * alpha_signal
    reservation = fair - inventory * gamma * sigma ** 2 * T_minus_t
    spread_AS = gamma * sigma ** 2 * T_minus_t + (2 / gamma) * np.log(1 + gamma / kappa)

    # VPIN widens spread in toxic flow — does NOT change direction
    spread = spread_AS * vpin_spread_multiplier(vpin, beta_vpin)
    half = 0.5 * spread

    bid = reservation - half
    ask = reservation + half

    # Cancel side if inventory limit reached
    if inventory >= max_pos:
        bid = -np.inf
    if inventory <= -max_pos:
        ask = np.inf

    bid_rounded = round(bid / tick) * tick if bid != -np.inf else -np.inf
    ask_rounded = round(ask / tick) * tick if ask != np.inf else np.inf

    return bid_rounded, ask_rounded


class ASMarketMaker(Strategy):
    def __init__(self, params: dict) -> None:
        super().__init__("as_market_maker", params)
        self.symbols: list[str] = params.get("symbols", ["BTC-USDT-SWAP"])
        self.gamma: float = params.get("gamma", 0.1)
        self.kappa: float = params.get("kappa", 1.5)
        self.max_pos: int = params.get("max_pos_contracts", 50)
        self.c_alpha: float = params.get("c_alpha", 100.0)
        self.beta_vpin: float = params.get("beta_vpin", 2.0)
        self.vpin_bucket_divisor: int = params.get("vpin_bucket_divisor", 75)
        self.vpin_window: int = params.get("vpin_window", 50)
        self.refresh_ms: float = params.get("refresh_interval_ms", 500.0)
        self.sigma_lookback: int = params.get("sigma_lookback_min", 5)

        # Per-symbol state
        self._inventory: dict[str, float] = {s: 0.0 for s in self.symbols}
        self._sigma_ewma: dict[str, float] = {s: 0.003 for s in self.symbols}
        self._vpin_cdf: dict[str, float] = {s: 0.1 for s in self.symbols}
        self._last_mid: dict[str, float] = {s: 0.0 for s in self.symbols}
        self._ofi_series: dict[str, deque] = {s: deque(maxlen=100) for s in self.symbols}
        self._prev_snap: dict[str, Optional[dict]] = {s: None for s in self.symbols}
        self._last_quote_ts: dict[str, float] = {s: 0.0 for s in self.symbols}
        # Trade buffer for VPIN (recent trades as dicts with ts, price, size)
        self._trade_buffer: dict[str, list] = {s: [] for s in self.symbols}
        self._last_kappa_recal: float = time.time()

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

        # Accumulate trades for VPIN
        if channel == "trades":
            self._trade_buffer[inst_id].append({
                "ts": pd.Timestamp(payload.ts, unit="ms"),
                "price": payload.trade_price,
                "size": payload.trade_size,
            })
            # Keep last ~10k trades
            if len(self._trade_buffer[inst_id]) > 10_000:
                self._trade_buffer[inst_id] = self._trade_buffer[inst_id][-5_000:]
            return None

        if channel != "books" or book is None or not book.is_valid():
            return None

        # Throttle quote refresh
        now = time.time()
        if now - self._last_quote_ts[inst_id] < self.refresh_ms / 1000:
            return None
        self._last_quote_ts[inst_id] = now

        bids, asks = book.to_array(depth=max(self.max_pos, 5))
        if len(bids) == 0 or len(asks) == 0:
            return None

        bids_list = [(bids[i, 0], bids[i, 1]) for i in range(len(bids)) if bids[i, 0] > 0]
        asks_list = [(asks[i, 0], asks[i, 1]) for i in range(len(asks)) if asks[i, 0] > 0]

        features = compute_obi_features(bids_list, asks_list, depth=min(5, len(bids_list)))
        mid = features["mid"]
        if mid <= 0:
            return None

        # Update sigma EWMA from mid-price returns
        last_mid = self._last_mid[inst_id]
        if last_mid > 0 and mid > 0:
            ret = (mid - last_mid) / last_mid
            alpha_sigma = 1 - np.exp(-np.log(2) * 1 / max(self.sigma_lookback * 60, 1))
            self._sigma_ewma[inst_id] = (
                alpha_sigma * abs(ret) + (1 - alpha_sigma) * self._sigma_ewma[inst_id]
            )
        self._last_mid[inst_id] = mid

        # Compute OFI
        curr_snap = book_to_l1_snap(bids, asks)
        prev_snap = self._prev_snap[inst_id]
        if prev_snap is not None:
            ofi = compute_ofi(prev_snap, curr_snap)
            self._ofi_series[inst_id].append(ofi)
        self._prev_snap[inst_id] = curr_snap

        alpha_signal = ewma_ofi(
            np.array(self._ofi_series[inst_id]),
            halflife_ms=200.0,
        )

        # Compute VPIN from trade buffer
        trades = self._trade_buffer[inst_id]
        if len(trades) > 200:
            try:
                trades_df = pd.DataFrame(trades)
                # Estimate daily volume from recent trades
                daily_vol_est = float(trades_df["size"].sum()) * 24 * 3600 / max(1, len(trades))
                V_bucket = max(daily_vol_est / self.vpin_bucket_divisor, 1.0)
                vpin_df = compute_vpin(trades_df, V_bucket, n_window=self.vpin_window)
                if not vpin_df.empty and "CDF" in vpin_df.columns:
                    last_cdf = float(vpin_df["CDF"].iloc[-1])
                    if not np.isnan(last_cdf):
                        self._vpin_cdf[inst_id] = last_cdf
            except Exception:
                pass

        # Get tick size from instrument specs (default 0.1 for BTC perp)
        tick = 0.1

        bid, ask = as_quote(
            mid=mid,
            inventory=self._inventory[inst_id],
            alpha_signal=alpha_signal,
            vpin=self._vpin_cdf[inst_id],
            gamma=self.gamma,
            sigma=self._sigma_ewma[inst_id],
            kappa=self.kappa,
            T_minus_t=1.0,  # Ergodic limit — always 1.0 for 24/7 markets
            tick=tick,
            max_pos=self.max_pos,
            c_alpha=self.c_alpha,
            beta_vpin=self.beta_vpin,
        )

        return SignalPayload(
            strategy=self.name,
            inst_id=inst_id,
            side="neutral",
            strength=0.5,
            fair_value=mid,
            target_bid=bid if bid != -np.inf else None,
            target_ask=ask if ask != np.inf else None,
            metadata={
                "obi_l1": features["obi_l1"],
                "alpha_signal": alpha_signal,
                "vpin_cdf": self._vpin_cdf[inst_id],
                "sigma": self._sigma_ewma[inst_id],
                "inventory": self._inventory[inst_id],
            },
        )

    async def on_fill(self, event: Event) -> None:
        fill = event.payload
        if fill.inst_id not in self._inventory:
            return
        delta = fill.fill_sz if fill.side == "buy" else -fill.fill_sz
        self._inventory[fill.inst_id] += delta
        logger.debug(
            "AS MM inventory updated",
            inst_id=fill.inst_id,
            inventory=self._inventory[fill.inst_id],
        )
