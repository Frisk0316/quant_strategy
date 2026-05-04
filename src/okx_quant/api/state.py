"""
Shared state container bridging the trading engine and the HTTP/WS API layer.

EngineState holds references to live engine components (positions, risk, etc.)
and provides accessor methods that match the window.MOCK schema the frontend expects.
It also manages the WebSocket client registry for live broadcasts.
"""
from __future__ import annotations

import time
from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi.websockets import WebSocket

from okx_quant.core.events import FillPayload
from okx_quant.execution.order_manager import OrderManager
from okx_quant.portfolio.positions import PositionLedger
from okx_quant.risk.circuit_breaker import CircuitBreaker
from okx_quant.risk.drawdown_tracker import DrawdownTracker
from okx_quant.risk.risk_guard import RiskGuard


class EngineState:
    def __init__(
        self,
        positions: PositionLedger,
        dd_tracker: DrawdownTracker,
        risk_guard: RiskGuard,
        order_manager: OrderManager,
        circuit_breaker: CircuitBreaker,
        mode: str = "demo",
        strategy_count: int = 0,
    ) -> None:
        self._positions = positions
        self._dd_tracker = dd_tracker
        self._risk_guard = risk_guard
        self._order_manager = order_manager
        self._circuit_breaker = circuit_breaker
        self._mode = mode
        self._strategy_count = strategy_count

        self._ws_clients: set = set()
        self._recent_trades: deque = deque(maxlen=500)
        self._last_order_notional: float = 0.0
        self._start_time: float = time.time()
        self._trade_counter: int = 0

    # ------------------------------------------------------------------
    # WebSocket client registry
    # ------------------------------------------------------------------

    def register_ws(self, ws: "WebSocket") -> None:
        self._ws_clients.add(ws)

    def unregister_ws(self, ws: "WebSocket") -> None:
        self._ws_clients.discard(ws)

    # ------------------------------------------------------------------
    # Engine event callbacks
    # ------------------------------------------------------------------

    def record_fill(self, payload: FillPayload) -> None:
        if not isinstance(payload, FillPayload):
            return
        self._trade_counter += 1
        notional = payload.fill_px * payload.fill_sz
        self._last_order_notional = notional
        self._recent_trades.appendleft({
            "id": self._trade_counter,
            "ts": int(payload.ts),          # already epoch ms from OKX
            "symbol": payload.inst_id,
            "side": payload.side.upper(),
            "type": "post_only",
            "price": payload.fill_px,
            "qty": payload.fill_sz,
            "notional": notional,
            "fee": payload.fee,
            "pnl": 0.0,                     # computed later when position closes
            "status": "FILLED" if payload.state == "filled" else "PARTIALLY_FILLED",
            "strategy": payload.strategy,
        })

    def tick_risk_snapshot(self) -> None:
        """Called periodically. Accessor methods already read live state; nothing to update."""
        pass

    # ------------------------------------------------------------------
    # REST accessors
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        return {
            "mode": self._mode,
            "uptime_secs": time.time() - self._start_time,
            "strategy_count": self._strategy_count,
            "kill_switch": self._risk_guard.kill,
            "soft_stop": self._risk_guard.soft_stop,
        }

    def get_live_risk(self) -> dict:
        equity = self._positions.get_equity()
        dd_stats = self._dd_tracker.stats()

        # Leverage = sum of abs position notionals / equity
        all_pos = self._positions.get_all_positions()
        pos_notionals = [
            abs(p.size) * p.last_price
            for p in all_pos.values()
            if p.last_price > 0
        ]
        total_notional = sum(pos_notionals)
        leverage = total_notional / equity if equity > 0 else 0.0

        # Largest single position as fraction of equity
        max_pos_notional = max(pos_notionals) if pos_notionals else 0.0
        pos_pct_equity = max_pos_notional / equity if equity > 0 else 0.0

        # WS reconnects in the current window
        ws_reconnects = len(self._circuit_breaker._ws_reconnect_times)

        # REST error rate over last N calls
        rest_results = list(self._circuit_breaker._rest_results)
        rest_error_rate = (
            sum(1 for r in rest_results if not r) / len(rest_results)
            if rest_results else 0.0
        )

        # dd_tracker.stats() returns daily_pnl_pct as percentage (e.g. -1.8 = -1.8%)
        # frontend expects fraction (e.g. -0.018)
        return {
            "equity_usd": equity,
            "daily_pnl_pct": dd_stats["daily_pnl_pct"] / 100.0,
            "daily_pnl_usd": dd_stats["daily_pnl"],
            "soft_dd_used": abs(self._dd_tracker.current_drawdown()),
            "leverage": leverage,
            "max_leverage": self._risk_guard.max_leverage,
            "max_pos_pct_equity": self._risk_guard.max_pos_pct,
            "pos_pct_equity": pos_pct_equity,
            "max_order_notional": self._risk_guard.max_order_notional,
            "last_order_notional": self._last_order_notional,
            "ws_reconnects": ws_reconnects,
            "rest_error_rate": rest_error_rate,
        }

    def get_positions(self) -> list:
        return [
            {
                "inst_id": p.inst_id,
                "size": p.size,
                "avg_entry": p.avg_entry,
                "last_price": p.last_price,
                "unrealized_pnl": p.unrealized_pnl,
                "notional": p.notional,
                "strategy": p.strategy,
            }
            for p in self._positions.get_all_positions().values()
        ]

    def get_trades(self, limit: int = 200) -> list:
        return list(self._recent_trades)[:limit]

    # ------------------------------------------------------------------
    # WebSocket broadcast
    # ------------------------------------------------------------------

    async def broadcast(self, msg: dict) -> None:
        dead: set = set()
        for ws in self._ws_clients:
            try:
                await ws.send_json(msg)
            except Exception:
                dead.add(ws)
        self._ws_clients -= dead
