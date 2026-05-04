"""
Portfolio manager — converts signals to sized, risk-checked orders.
Signal → position sizing → RiskGuard check → OrderEvent.
"""
from __future__ import annotations

import uuid
from decimal import Decimal, ROUND_DOWN

from loguru import logger

from okx_quant.core.bus import EventBus
from okx_quant.core.events import Event, EvtType, FillPayload, MarketPayload, OrderPayload, SignalPayload
from okx_quant.portfolio.positions import PositionLedger
from okx_quant.portfolio.sizing import fixed_fractional, validate_ct_val, vol_target_size
from okx_quant.risk.risk_guard import RiskGuard


class PortfolioManager:
    def __init__(
        self,
        bus: EventBus,
        positions: PositionLedger,
        risk_guard: RiskGuard,
        target_ann_vol: float = 0.20,
        # Instrument specs keyed by inst_id: {ct_val, min_sz, lot_sz, tick_sz}
        instrument_specs: dict = None,
    ) -> None:
        self._bus = bus
        self._positions = positions
        self._risk = risk_guard
        self._target_vol = target_ann_vol
        self._specs = instrument_specs or {}
        # Recent returns per inst_id for vol targeting
        self._returns: dict[str, list[float]] = {}
        self._last_fill_px: dict[str, float] = {}
        self._last_mids: dict[str, float] = {}

    def set_instrument_specs(self, specs: dict) -> None:
        self._specs = specs

    def update_return(self, inst_id: str, ret: float) -> None:
        """Feed in a return observation for vol targeting."""
        if inst_id not in self._returns:
            self._returns[inst_id] = []
        self._returns[inst_id].append(ret)
        if len(self._returns[inst_id]) > 500:
            self._returns[inst_id].pop(0)

    def on_market(self, payload: MarketPayload) -> None:
        if payload.bids and payload.asks:
            try:
                bid = float(payload.bids[0][0])
                ask = float(payload.asks[0][0])
            except (IndexError, TypeError, ValueError):
                return
            mid = 0.5 * (bid + ask)
            self._last_mids[payload.inst_id] = mid
            self._positions.update_price(payload.inst_id, mid)

    async def on_signal(self, event: Event) -> None:
        """Convert a SignalPayload to one or two OrderPayloads (bid + ask for MM strategies)."""
        sig: SignalPayload = event.payload
        strategy = sig.strategy
        inst_id = sig.inst_id

        signal_mult = _signal_size_multiplier(sig)
        if signal_mult <= 0:
            return

        size_mult = self._risk.get_size_multiplier(strategy) * signal_mult
        if size_mult <= 0:
            return

        equity = self._positions.get_equity()
        specs = self._specs.get(inst_id, {})

        # Vol-targeted size in USD
        import pandas as pd
        returns_list = self._returns.get(inst_id, [])
        if len(returns_list) >= 5:
            r_series = pd.Series(returns_list)
            size_usd = vol_target_size(r_series, equity, self._target_vol) * size_mult
        else:
            # Fallback to 1% fixed-fractional
            size_usd = fixed_fractional(equity, risk_pct=0.01) * size_mult
        max_order_notional = float(getattr(self._risk, "max_order_notional", 0.0) or 0.0)
        if max_order_notional > 0:
            size_usd = min(size_usd, max_order_notional)

        ref_price = self._resolve_price(inst_id, sig.fair_value)
        if ref_price <= 0:
            return

        td_mode = specs.get("tdMode", "cross")

        # Market-making: place bid and ask simultaneously
        if sig.target_bid is not None and sig.target_ask is not None:
            await self._place_mm_quotes(sig, size_usd, td_mode)
        elif sig.side in ("buy", "sell"):
            await self._place_directional(sig, size_usd, td_mode)
            await self._place_linked_hedges(sig, size_usd)

    def _resolve_price(self, inst_id: str, preferred: float = 0.0) -> float:
        if preferred and preferred > 0:
            return preferred
        return self._last_mids.get(inst_id, 0.0)

    def _format_size(self, raw_size: float, lot_sz: float) -> str:
        if lot_sz >= 1:
            return str(int(raw_size))
        quant = Decimal(str(lot_sz))
        size = Decimal(str(raw_size)).quantize(quant, rounding=ROUND_DOWN)
        return format(size, "f")

    def _compute_order_quantity(
        self,
        inst_id: str,
        price: float,
        size_usd: float,
    ) -> tuple[str, float]:
        specs = self._specs.get(inst_id, {})
        if "ctVal" in specs:
            ct_val = validate_ct_val(float(specs["ctVal"]), inst_id)
        else:
            ct_val = _fallback_ct_val(inst_id)
        min_sz = float(specs.get("minSz", 1 if "SWAP" in inst_id else 0.0001))
        lot_sz = float(specs.get("lotSz", 1 if "SWAP" in inst_id else 0.0001))
        contract_value = ct_val * price
        if contract_value <= 0 or lot_sz <= 0:
            return "", 0.0

        raw_qty = size_usd / contract_value
        rounded_qty = float(int(raw_qty / lot_sz)) * lot_sz
        if rounded_qty < min_sz:
            return "", 0.0

        notional_usd = rounded_qty * contract_value
        return self._format_size(rounded_qty, lot_sz), notional_usd

    async def _place_mm_quotes(
        self,
        sig: SignalPayload,
        size_usd: float,
        td_mode: str,
    ) -> None:
        """Place bid and ask quotes for market-making strategies."""
        pos = self._positions.get_position(sig.inst_id)
        tick_sz = float(self._specs.get(sig.inst_id, {}).get("tickSz", 0.1))

        for side, target_px in [("buy", sig.target_bid), ("sell", sig.target_ask)]:
            if target_px is None or target_px <= 0 or target_px == float("inf"):
                continue

            # Skip if inventory limit reached on this side
            if side == "buy" and pos.size >= 50:
                continue
            if side == "sell" and pos.size <= -50:
                continue

            sz_str, notional_usd = self._compute_order_quantity(sig.inst_id, target_px, size_usd)
            if not sz_str:
                continue
            px_str = f"{round(target_px / tick_sz) * tick_sz:.{_decimals(tick_sz)}f}"
            cl_ord_id = uuid.uuid4().hex[:32]
            order = OrderPayload(
                cl_ord_id=cl_ord_id,
                inst_id=sig.inst_id,
                side=side,
                ord_type="post_only",
                sz=sz_str,
                px=px_str,
                td_mode=td_mode,
                strategy=sig.strategy,
                notional_usd=notional_usd,
                metadata=dict(sig.metadata),
            )

            current_mid = sig.fair_value
            pos_notional = pos.notional
            if self._risk.check(order, pos_notional, current_mid):
                await self._bus.put(Event(EvtType.ORDER, payload=order))

    async def _place_directional(
        self,
        sig: SignalPayload,
        size_usd: float,
        td_mode: str,
        inst_id: str | None = None,
        side: str | None = None,
        price: float | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Place a single directional order."""
        inst_id = inst_id or sig.inst_id
        side = side or sig.side
        price = price if price is not None else self._resolve_price(inst_id, sig.fair_value)
        if price <= 0:
            return
        sz_str, notional_usd = self._compute_order_quantity(inst_id, price, size_usd)
        if not sz_str:
            return
        cl_ord_id = uuid.uuid4().hex[:32]
        order = OrderPayload(
            cl_ord_id=cl_ord_id,
            inst_id=inst_id,
            side=side,
            ord_type="post_only",
            sz=sz_str,
            px=str(price),
            td_mode=td_mode,
            strategy=sig.strategy,
            notional_usd=notional_usd,
            metadata=metadata if metadata is not None else dict(sig.metadata),
        )
        pos = self._positions.get_position(inst_id)
        if self._risk.check(order, pos.notional, self._resolve_price(inst_id, price)):
            await self._bus.put(Event(EvtType.ORDER, payload=order))

    async def _place_linked_hedges(self, sig: SignalPayload, base_size_usd: float) -> None:
        metadata = sig.metadata or {}
        td_mode = self._specs.get(sig.inst_id, {}).get("tdMode", "cross")

        hedge_inst_id = metadata.get("hedge_inst_id")
        hedge_side = metadata.get("hedge_side")
        if hedge_inst_id and hedge_side:
            hedge_ratio = abs(float(metadata.get("beta", 1.0)))
            hedge_price = self._resolve_price(hedge_inst_id)
            await self._place_directional(
                sig,
                size_usd=base_size_usd * max(hedge_ratio, 1e-6),
                td_mode=td_mode,
                inst_id=hedge_inst_id,
                side=hedge_side,
                price=hedge_price,
                metadata=dict(metadata),
            )

        if metadata.get("leg") == "dual":
            spot_symbol = metadata.get("spot_symbol")
            if not spot_symbol:
                return
            spot_side = "buy" if sig.side == "sell" else "sell"
            spot_price = self._resolve_price(spot_symbol, self._resolve_price(sig.inst_id))
            await self._place_directional(
                sig,
                size_usd=base_size_usd,
                td_mode=self._specs.get(spot_symbol, {}).get("tdMode", td_mode),
                inst_id=spot_symbol,
                side=spot_side,
                price=spot_price,
                metadata=dict(metadata),
            )

    async def on_fill(self, event: Event) -> None:
        """Update positions on fill confirmation."""
        fill: FillPayload = event.payload
        if fill.fill_sz > 0 and fill.fill_px > 0:
            prev_fill_px = self._last_fill_px.get(fill.inst_id, 0.0)
            self._positions.on_fill(
                inst_id=fill.inst_id,
                side=fill.side,
                fill_px=fill.fill_px,
                fill_sz=fill.fill_sz,
                fee=abs(fill.fee),
                strategy=fill.strategy,
            )
            if prev_fill_px > 0:
                self.update_return(fill.inst_id, fill.fill_px / prev_fill_px - 1.0)
            self._last_fill_px[fill.inst_id] = fill.fill_px


def _decimals(tick_sz: float) -> int:
    """Count decimal places of a tick size float."""
    s = str(tick_sz)
    if "." in s:
        return len(s.rstrip("0").split(".")[-1])
    return 0


def _fallback_ct_val(inst_id: str) -> float:
    if "SWAP" not in inst_id:
        logger.warning("Instrument ctVal missing; falling back to spot ctVal=1.0", inst_id=inst_id)
        return 1.0
    if inst_id.startswith(("BTC-", "ETH-")):
        logger.warning("Instrument ctVal missing; falling back to known BTC/ETH swap ctVal=0.01", inst_id=inst_id)
        return 0.01
    logger.error("Instrument ctVal missing for non-BTC/ETH swap; refusing silent fallback", inst_id=inst_id)
    raise ValueError(f"Missing ctVal for non-BTC/ETH swap: {inst_id}")


def _signal_size_multiplier(sig: SignalPayload) -> float:
    """
    Resolve per-signal sizing strength.

    Strategies can provide an explicit metadata size multiplier, otherwise the
    standard SignalPayload.strength field is used.
    """
    metadata = sig.metadata or {}
    raw = metadata.get("size_multiplier", sig.strength)
    try:
        return max(0.0, min(1.0, float(raw)))
    except (TypeError, ValueError):
        return 1.0
