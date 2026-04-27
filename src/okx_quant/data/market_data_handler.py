"""
WebSocket market data handler.
Manages public (L2 books, trades, funding) and private (fills, positions)
channels. Handles reconnection, heartbeat, and WS login for private channels.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import time
from typing import Optional

import websockets
from loguru import logger

from okx_quant.core.bus import EventBus
from okx_quant.core.events import Event, EvtType, MarketPayload
from okx_quant.data.okx_book import OkxBook


class MarketDataHandler:
    def __init__(
        self,
        bus: EventBus,
        symbols: list[str],
        api_key: str,
        secret: str,
        passphrase: str,
        ws_public_url: str = "wss://ws.okx.com:8443/ws/v5/public",
        ws_private_url: str = "wss://ws.okx.com:8443/ws/v5/private",
        demo: bool = True,
        reconnect_limit: int = 3,
        reconnect_window_secs: float = 60.0,
    ) -> None:
        self._bus = bus
        self._symbols = symbols
        self._key = api_key
        self._secret = secret
        self._passphrase = passphrase
        self._ws_public_url = ws_public_url
        self._ws_private_url = ws_private_url
        self._demo = demo
        self._reconnect_limit = reconnect_limit
        self._reconnect_window_secs = reconnect_window_secs

        # Live order books, one per symbol
        self.books: dict[str, OkxBook] = {s: OkxBook(s) for s in symbols}

        # Reconnect tracking for circuit breaker
        self._reconnect_times: list[float] = []

    # ------------------------------------------------------------------
    # Entry points
    # ------------------------------------------------------------------

    async def run_public(self) -> None:
        """Subscribe to public channels: books, trades, funding-rate."""
        url = self._ws_public_url
        if self._demo:
            # Demo WS: replace host, add brokerId
            url = url.replace("ws.okx.com:8443", "wspap.okx.com") + "?brokerId=9999"

        async for ws in websockets.connect(url, ping_interval=None, max_size=2**23):
            logger.info("WS public connected", url=url)
            self._record_reconnect()
            try:
                await self._subscribe_books(ws)
                await self._subscribe_trades(ws)
                await self._subscribe_funding(ws)
                heartbeat_task = asyncio.create_task(self._heartbeat(ws))
                async for raw in ws:
                    if raw == "pong":
                        continue
                    await self._handle_public_message(json.loads(raw))
            except Exception as e:
                logger.warning("WS public error, reconnecting", exc=str(e))
            finally:
                heartbeat_task.cancel()
                await asyncio.sleep(1)

    async def run_private(self) -> None:
        """Subscribe to private channels: order fills, position updates."""
        url = self._ws_private_url
        if self._demo:
            url = url.replace("ws.okx.com:8443", "wspap.okx.com") + "?brokerId=9999"

        async for ws in websockets.connect(url, ping_interval=None, max_size=2**23):
            logger.info("WS private connected")
            self._record_reconnect()
            try:
                await self._ws_login(ws)
                await self._subscribe_private(ws)
                heartbeat_task = asyncio.create_task(self._heartbeat(ws))
                async for raw in ws:
                    if raw == "pong":
                        continue
                    await self._handle_private_message(json.loads(raw))
            except Exception as e:
                logger.warning("WS private error, reconnecting", exc=str(e))
            finally:
                heartbeat_task.cancel()
                await asyncio.sleep(1)

    # ------------------------------------------------------------------
    # Subscriptions
    # ------------------------------------------------------------------

    async def _subscribe_books(self, ws) -> None:
        args = [{"channel": "books", "instId": s} for s in self._symbols]
        await ws.send(json.dumps({"op": "subscribe", "args": args}))
        logger.info("Subscribed to books", symbols=self._symbols)

    async def _subscribe_trades(self, ws) -> None:
        args = [{"channel": "trades", "instId": s} for s in self._symbols]
        await ws.send(json.dumps({"op": "subscribe", "args": args}))

    async def _subscribe_funding(self, ws) -> None:
        # Only SWAP instruments have funding rate
        swap_symbols = [s for s in self._symbols if "SWAP" in s]
        if swap_symbols:
            args = [{"channel": "funding-rate", "instId": s} for s in swap_symbols]
            await ws.send(json.dumps({"op": "subscribe", "args": args}))

    async def _subscribe_private(self, ws) -> None:
        args = [
            {"channel": "orders", "instType": "SWAP"},
            {"channel": "positions", "instType": "SWAP"},
        ]
        await ws.send(json.dumps({"op": "subscribe", "args": args}))

    # ------------------------------------------------------------------
    # Message handlers
    # ------------------------------------------------------------------

    async def _handle_public_message(self, msg: dict) -> None:
        if "event" in msg:
            logger.debug("WS event", event=msg.get("event"), msg=msg)
            return

        channel = msg.get("arg", {}).get("channel", "")
        inst_id = msg.get("arg", {}).get("instId", "")

        if channel == "books":
            await self._handle_book_update(msg, inst_id)
        elif channel == "trades":
            await self._handle_trade(msg, inst_id)
        elif channel == "funding-rate":
            await self._handle_funding(msg, inst_id)

    async def _handle_book_update(self, msg: dict, inst_id: str) -> None:
        book = self.books.get(inst_id)
        if book is None:
            return
        try:
            book.handle(msg)
        except RuntimeError as e:
            logger.warning("Book error", inst_id=inst_id, exc=str(e))
            # Signal to re-subscribe (caller's reconnect loop handles it)
            raise

        if not book.is_valid():
            return

        d = msg["data"][0]
        payload = MarketPayload(
            inst_id=inst_id,
            ts=int(d.get("ts", 0)),
            bids=d.get("bids", []),
            asks=d.get("asks", []),
            seq_id=d.get("seqId", 0),
            channel="books",
            checksum=d.get("checksum"),
            action=msg.get("action"),
        )
        await self._bus.put(Event(EvtType.MARKET, payload=payload))

    async def _handle_trade(self, msg: dict, inst_id: str) -> None:
        for trade in msg.get("data", []):
            payload = MarketPayload(
                inst_id=inst_id,
                ts=int(trade.get("ts", 0)),
                bids=[],
                asks=[],
                seq_id=0,
                channel="trades",
                trade_id=trade.get("tradeId"),
                trade_price=float(trade.get("px", 0)),
                trade_size=float(trade.get("sz", 0)),
                trade_side=trade.get("side"),
            )
            await self._bus.put(Event(EvtType.MARKET, payload=payload))

    async def _handle_funding(self, msg: dict, inst_id: str) -> None:
        for d in msg.get("data", []):
            payload = MarketPayload(
                inst_id=inst_id,
                ts=int(d.get("ts", 0)),
                bids=[],
                asks=[],
                seq_id=0,
                channel="funding-rate",
                funding_rate=float(d.get("fundingRate", 0)),
                next_funding_time=int(d.get("nextFundingTime", 0)),
            )
            await self._bus.put(Event(EvtType.FUNDING, payload=payload))

    async def _handle_private_message(self, msg: dict) -> None:
        if msg.get("event") == "login":
            logger.info("WS private login successful")
            return
        # Fill and position updates handled by ExecutionHandler via bus
        channel = msg.get("arg", {}).get("channel", "")
        if channel in ("orders", "positions"):
            await self._bus.put(Event(EvtType.FILL, payload=msg))

    # ------------------------------------------------------------------
    # Heartbeat & login
    # ------------------------------------------------------------------

    async def _heartbeat(self, ws) -> None:
        """Send ping every 25 seconds. OKX drops connection after 30s silence."""
        while True:
            await asyncio.sleep(25)
            try:
                await ws.send("ping")
            except Exception:
                break

    async def _ws_login(self, ws) -> None:
        """HMAC-SHA256 WS login for private channel access."""
        ts = str(int(time.time()))
        msg_str = f"{ts}GET/users/self/verify"
        sign = base64.b64encode(
            hmac.new(self._secret.encode(), msg_str.encode(), hashlib.sha256).digest()
        ).decode()
        login_msg = {
            "op": "login",
            "args": [{"apiKey": self._key, "passphrase": self._passphrase, "timestamp": ts, "sign": sign}],
        }
        await ws.send(json.dumps(login_msg))
        # Wait for login confirmation
        resp = json.loads(await ws.recv())
        if resp.get("event") != "login":
            raise RuntimeError(f"WS login failed: {resp}")

    # ------------------------------------------------------------------
    # Circuit breaker tracking
    # ------------------------------------------------------------------

    def _record_reconnect(self) -> None:
        now = time.time()
        self._reconnect_times.append(now)
        # Keep only reconnects within the window
        window = self._reconnect_window_secs
        self._reconnect_times = [t for t in self._reconnect_times if now - t <= window]
        count = len(self._reconnect_times)
        if count > self._reconnect_limit:
            logger.error(
                "Circuit breaker: too many WS reconnects",
                count=count,
                window_secs=window,
            )
            # Raise to propagate to risk layer via bus
            raise RuntimeError(f"WS circuit breaker: {count} reconnects in {window}s")
