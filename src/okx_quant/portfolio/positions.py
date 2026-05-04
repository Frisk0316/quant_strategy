"""
Position ledger — single source of truth for current holdings and PnL.
Synchronized with OKX REST on startup; updated on every fill event.
Redis backup for crash recovery.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Optional

from loguru import logger


@dataclass
class Position:
    inst_id: str
    size: float = 0.0          # positive = long, negative = short
    avg_entry: float = 0.0
    realized_pnl: float = 0.0
    last_price: float = 0.0
    strategy: str = ""
    updated_at: float = field(default_factory=time.time)

    @property
    def unrealized_pnl(self) -> float:
        if self.size == 0 or self.avg_entry == 0:
            return 0.0
        return self.size * (self.last_price - self.avg_entry)

    @property
    def notional(self) -> float:
        return abs(self.size) * self.last_price


class PositionLedger:
    def __init__(
        self,
        initial_equity: float = 0.0,
        redis_url: Optional[str] = None,
        redis_key: str = "okx_quant:positions",
    ) -> None:
        self._positions: dict[str, Position] = {}
        self._cash_equity = initial_equity
        self._redis_url = redis_url
        self._redis_key = redis_key
        self._redis = None
        self._trade_log: list[dict] = []

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def load_from_okx(self, okx_positions: list[dict]) -> None:
        """
        Initialize from OKX REST GET /api/v5/account/positions response.
        Called at startup to sync with exchange state.
        """
        for p in okx_positions:
            inst_id = p.get("instId", "")
            pos = p.get("pos", "0")
            avg_px = p.get("avgPx", "0")
            upl = p.get("upl", "0")
            size = float(pos)
            if size == 0:
                continue
            position = Position(
                inst_id=inst_id,
                size=size,
                avg_entry=float(avg_px),
                realized_pnl=0.0,
                last_price=float(avg_px),
            )
            self._positions[inst_id] = position
        logger.info("Positions loaded from OKX", count=len(self._positions))

    def load_snapshot(self) -> bool:
        """Load last snapshot from Redis. Returns True if successful."""
        if not self._redis:
            return False
        try:
            data = self._redis.get(self._redis_key)
            if data:
                snapshot = json.loads(data)
                self._cash_equity = snapshot.get("cash_equity", self._cash_equity)
                for inst_id, pos_data in snapshot.get("positions", {}).items():
                    self._positions[inst_id] = Position(**pos_data)
                logger.info("Positions restored from Redis")
                return True
        except Exception as e:
            logger.warning("Redis position restore failed", exc=str(e))
        return False

    def save_snapshot(self) -> None:
        """Persist current state to Redis for crash recovery."""
        if not self._redis:
            return
        try:
            snapshot = {
                "cash_equity": self._cash_equity,
                "positions": {
                    inst_id: {
                        "inst_id": p.inst_id,
                        "size": p.size,
                        "avg_entry": p.avg_entry,
                        "realized_pnl": p.realized_pnl,
                        "last_price": p.last_price,
                        "strategy": p.strategy,
                        "updated_at": p.updated_at,
                    }
                    for inst_id, p in self._positions.items()
                },
            }
            self._redis.setex(self._redis_key, 86400, json.dumps(snapshot))
        except Exception as e:
            logger.warning("Redis snapshot save failed", exc=str(e))

    # ------------------------------------------------------------------
    # Fill handling
    # ------------------------------------------------------------------

    def on_fill(
        self,
        inst_id: str,
        side: str,
        fill_px: float,
        fill_sz: float,
        fee: float,
        strategy: str = "",
    ) -> None:
        """Update position on fill. side: 'buy' | 'sell'."""
        pos = self._positions.get(inst_id)
        if pos is None:
            pos = Position(inst_id=inst_id, strategy=strategy)
            self._positions[inst_id] = pos

        signed_size = fill_sz if side == "buy" else -fill_sz
        new_size = pos.size + signed_size
        realized_pnl = 0.0

        same_direction = pos.size == 0 or pos.size * signed_size > 0
        if same_direction:
            if new_size != 0:
                weighted_notional = abs(pos.size) * pos.avg_entry + abs(signed_size) * fill_px
                pos.avg_entry = weighted_notional / abs(new_size)
        else:
            closed = min(abs(pos.size), abs(signed_size))
            realized_pnl = closed * (fill_px - pos.avg_entry) * (1 if pos.size > 0 else -1)
            logger.info("Trade closed", inst_id=inst_id, pnl=realized_pnl - fee, side=side)

            if abs(new_size) < 1e-9:
                pos.avg_entry = 0.0
            elif pos.size * new_size < 0:
                # Position reversed: the residual opens a fresh position at the fill price.
                pos.avg_entry = fill_px

        net_realized = realized_pnl - fee
        pos.realized_pnl += net_realized
        self._cash_equity += net_realized

        pos.size = new_size
        pos.last_price = fill_px
        pos.strategy = strategy or pos.strategy
        pos.updated_at = time.time()

        # Remove flat positions
        if abs(pos.size) < 1e-9:
            self._positions.pop(inst_id, None)

        self._trade_log.append({
            "ts": time.time(), "inst_id": inst_id, "side": side,
            "fill_px": fill_px, "fill_sz": fill_sz, "fee": fee,
            "strategy": strategy,
        })
        self.save_snapshot()

    def apply_cashflow(
        self,
        amount: float,
        *,
        inst_id: str = "",
        reason: str = "cashflow",
        strategy: str = "",
        ts: float | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Apply non-trade cashflows such as funding settlements."""
        if amount == 0:
            return
        event_ts = time.time() if ts is None else ts
        self._cash_equity += amount
        self._trade_log.append({
            "ts": event_ts,
            "inst_id": inst_id,
            "side": reason,
            "fill_px": 0.0,
            "fill_sz": 0.0,
            "fee": 0.0,
            "cashflow": amount,
            "strategy": strategy,
            "metadata": metadata or {},
        })
        self.save_snapshot()

    def update_price(self, inst_id: str, price: float) -> None:
        """Update mark price for unrealized PnL calculation."""
        if inst_id in self._positions:
            self._positions[inst_id].last_price = price

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_position(self, inst_id: str) -> Position:
        return self._positions.get(inst_id, Position(inst_id=inst_id))

    def get_equity(self) -> float:
        """Total equity = cash + unrealized PnL across all positions."""
        unrealized = sum(p.unrealized_pnl for p in self._positions.values())
        return self._cash_equity + unrealized

    def get_all_positions(self) -> dict[str, Position]:
        return dict(self._positions)

    def get_trade_log(self) -> list[dict]:
        return list(self._trade_log)

    def set_initial_equity(self, equity: float) -> None:
        self._cash_equity = equity
