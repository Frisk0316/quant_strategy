"""
Telegram bot for alerts and remote kill switch.
Commands: /kill, /status, /reset, /help
"""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import httpx
from loguru import logger

if TYPE_CHECKING:
    from okx_quant.portfolio.positions import PositionLedger
    from okx_quant.risk.risk_guard import RiskGuard


class TelegramMonitor:
    def __init__(self, token: str, chat_id: str) -> None:
        self._token = token
        self._chat_id = chat_id
        self._base = f"https://api.telegram.org/bot{token}"
        self._client = httpx.AsyncClient(timeout=10.0)
        self._last_update_id = 0

    async def send_alert(self, message: str, level: str = "info") -> None:
        prefix = {"critical": "🔴", "warning": "🟡", "info": "🟢"}.get(level, "📢")
        text = f"{prefix} {message}"
        try:
            await self._client.post(
                f"{self._base}/sendMessage",
                json={"chat_id": self._chat_id, "text": text},
            )
        except Exception as e:
            logger.warning("Telegram send failed", exc=str(e))

    async def command_loop(self, risk_guard: "RiskGuard", positions: "PositionLedger") -> None:
        """Poll for Telegram commands."""
        while True:
            try:
                resp = await self._client.get(
                    f"{self._base}/getUpdates",
                    params={"offset": self._last_update_id + 1, "timeout": 10},
                )
                data = resp.json()
                for update in data.get("result", []):
                    self._last_update_id = update["update_id"]
                    msg = update.get("message", {})
                    text = msg.get("text", "").strip().lower()
                    await self._handle_command(text, risk_guard, positions)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Telegram poll error", exc=str(e))
                await asyncio.sleep(5)

    async def _handle_command(
        self,
        text: str,
        risk_guard: "RiskGuard",
        positions: "PositionLedger",
    ) -> None:
        if text == "/kill":
            risk_guard.trigger_hard_stop("Telegram /kill command")
            await self.send_alert("KILL SWITCH activated. All strategies halted.", level="critical")
        elif text == "/status":
            eq = positions.get_equity()
            dd = risk_guard._dd_tracker.current_drawdown() * 100
            daily = risk_guard._dd_tracker.daily_pnl()
            kill = risk_guard.kill
            status = (
                f"Equity: ${eq:.2f}\n"
                f"Drawdown: {dd:.2f}%\n"
                f"Daily PnL: ${daily:.2f}\n"
                f"Kill: {kill}"
            )
            await self.send_alert(status, level="info")
        elif text == "/reset":
            risk_guard.reset()
            await self.send_alert("RiskGuard reset by operator.", level="warning")
        elif text == "/help":
            await self.send_alert(
                "/kill — hard stop all\n/status — current equity+DD\n/reset — manual reset\n/help — this message",
                level="info",
            )
