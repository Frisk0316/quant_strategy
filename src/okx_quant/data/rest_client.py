"""
OKX REST API v5 authenticated client.
Implements HMAC-SHA256 signing as specified in the OKX API docs.
Clock sync is critical: timestamp drift > 30s returns error 50102.
"""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import json
from typing import Any, Optional
from urllib.parse import urlencode

import httpx
from loguru import logger


class OKXRestClient:
    def __init__(
        self,
        api_key: str,
        secret: str,
        passphrase: str,
        base_url: str = "https://www.okx.com",
        demo: bool = True,
        clock_offset_ms: float = 0.0,
    ) -> None:
        self._key = api_key
        self._secret = secret
        self._passphrase = passphrase
        self._base = base_url.rstrip("/")
        self._demo = demo
        self._clock_offset_ms = clock_offset_ms
        self._client = httpx.Client(timeout=10.0)

    # ------------------------------------------------------------------
    # Auth helpers (extracted from §2.1)
    # ------------------------------------------------------------------

    def _ts(self) -> str:
        """ISO-8601 ms UTC timestamp, adjusted for server clock offset."""
        now = dt.datetime.utcnow() + dt.timedelta(milliseconds=self._clock_offset_ms)
        return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"

    def _sign(self, ts: str, method: str, path: str, body: str = "") -> str:
        """HMAC-SHA256 + base64 signature."""
        msg = f"{ts}{method}{path}{body}".encode()
        return base64.b64encode(
            hmac.new(self._secret.encode(), msg, hashlib.sha256).digest()
        ).decode()

    def _headers(self, method: str, path: str, body: str = "") -> dict:
        ts = self._ts()
        headers = {
            "OK-ACCESS-KEY": self._key,
            "OK-ACCESS-SIGN": self._sign(ts, method, path, body),
            "OK-ACCESS-TIMESTAMP": ts,
            "OK-ACCESS-PASSPHRASE": self._passphrase,
            "Content-Type": "application/json",
        }
        if self._demo:
            headers["x-simulated-trading"] = "1"
        return headers

    # ------------------------------------------------------------------
    # Core request method
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        body: Optional[dict] = None,
    ) -> dict:
        body_str = json.dumps(body) if body else ""
        full_path = path
        if params and method == "GET":
            full_path += "?" + urlencode({k: v for k, v in params.items() if v is not None})
        headers = self._headers(method, full_path, body_str)
        url = self._base + full_path
        try:
            resp = self._client.request(
                method,
                url,
                headers=headers,
                content=body_str if body else None,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error("OKX REST HTTP error", status=e.response.status_code, url=url)
            raise
        except httpx.RequestError as e:
            logger.error("OKX REST request error", url=url, exc=str(e))
            raise

    def get(self, path: str, params: Optional[dict] = None) -> dict:
        return self._request("GET", path, params=params)

    def post(self, path: str, body: Optional[dict] = None) -> dict:
        return self._request("POST", path, body=body)

    # ------------------------------------------------------------------
    # Clock sync — must be called at startup and every ~5 minutes
    # ------------------------------------------------------------------

    def sync_clock(self) -> float:
        """
        Sync with OKX server time. Returns clock offset in milliseconds.
        Positive offset means local clock is ahead of server.
        """
        local_before = dt.datetime.utcnow().timestamp() * 1000
        resp = self.get("/api/v5/public/time")
        local_after = dt.datetime.utcnow().timestamp() * 1000
        server_ts_ms = float(resp["data"][0]["ts"])
        local_mid = (local_before + local_after) / 2
        offset_ms = local_mid - server_ts_ms
        self._clock_offset_ms = -offset_ms  # adjust to match server
        logger.info("Clock synced", offset_ms=offset_ms)
        return offset_ms

    # ------------------------------------------------------------------
    # Market data endpoints
    # ------------------------------------------------------------------

    def get_books(self, inst_id: str, sz: int = 400) -> dict:
        return self.get("/api/v5/market/books", {"instId": inst_id, "sz": sz})

    def get_candles(self, inst_id: str, bar: str = "1m", limit: int = 300) -> dict:
        return self.get("/api/v5/market/candles", {"instId": inst_id, "bar": bar, "limit": limit})

    def get_history_candles(self, inst_id: str, bar: str = "1m", limit: int = 100) -> dict:
        return self.get("/api/v5/market/history-candles", {"instId": inst_id, "bar": bar, "limit": limit})

    def get_trades(self, inst_id: str, limit: int = 100) -> dict:
        return self.get("/api/v5/market/trades", {"instId": inst_id, "limit": limit})

    def get_ticker(self, inst_id: str) -> dict:
        return self.get("/api/v5/market/ticker", {"instId": inst_id})

    def get_funding_rate(self, inst_id: str) -> dict:
        return self.get("/api/v5/public/funding-rate", {"instId": inst_id})

    def get_funding_rate_history(self, inst_id: str, limit: int = 100) -> dict:
        return self.get("/api/v5/public/funding-rate-history", {"instId": inst_id, "limit": limit})

    def get_open_interest(self, inst_id: str) -> dict:
        return self.get("/api/v5/public/open-interest", {"instId": inst_id})

    def get_mark_price(self, inst_id: str) -> dict:
        return self.get("/api/v5/public/mark-price", {"instId": inst_id})

    def get_instruments(self, inst_type: str = "SWAP") -> dict:
        return self.get("/api/v5/public/instruments", {"instType": inst_type})

    def get_position_tiers(self, inst_type: str = "SWAP", inst_id: str = "") -> dict:
        params: dict = {"instType": inst_type}
        if inst_id:
            params["instId"] = inst_id
        return self.get("/api/v5/public/position-tiers", params)

    # ------------------------------------------------------------------
    # Account endpoints
    # ------------------------------------------------------------------

    def get_balance(self, ccy: Optional[str] = None) -> dict:
        params = {"ccy": ccy} if ccy else None
        return self.get("/api/v5/account/balance", params)

    def get_positions(self, inst_type: str = "SWAP") -> dict:
        return self.get("/api/v5/account/positions", {"instType": inst_type})

    def set_leverage(self, inst_id: str, lever: int, mgn_mode: str = "cross") -> dict:
        return self.post("/api/v5/account/set-leverage", {
            "instId": inst_id, "lever": str(lever), "mgnMode": mgn_mode
        })

    def get_trade_fee(self, inst_type: str = "SWAP") -> dict:
        return self.get("/api/v5/account/trade-fee", {"instType": inst_type})

    def get_max_size(self, inst_id: str, td_mode: str = "cross") -> dict:
        return self.get("/api/v5/account/max-size", {"instId": inst_id, "tdMode": td_mode})

    # ------------------------------------------------------------------
    # Trading endpoints
    # ------------------------------------------------------------------

    def place_order(
        self,
        inst_id: str,
        td_mode: str,
        side: str,
        ord_type: str,
        sz: str,
        px: str = "",
        cl_ord_id: str = "",
        reduce_only: bool = False,
        pos_side: str = "net",
    ) -> dict:
        body: dict[str, Any] = {
            "instId": inst_id,
            "tdMode": td_mode,
            "side": side,
            "ordType": ord_type,
            "sz": sz,
        }
        if px:
            body["px"] = px
        if cl_ord_id:
            body["clOrdId"] = cl_ord_id[:32]  # OKX max 32 chars
        if reduce_only:
            body["reduceOnly"] = "true"
        if pos_side != "net":
            body["posSide"] = pos_side
        return self.post("/api/v5/trade/order", body)

    def cancel_order(self, inst_id: str, ord_id: str = "", cl_ord_id: str = "") -> dict:
        body: dict[str, str] = {"instId": inst_id}
        if ord_id:
            body["ordId"] = ord_id
        elif cl_ord_id:
            body["clOrdId"] = cl_ord_id
        return self.post("/api/v5/trade/cancel-order", body)

    def batch_cancel_orders(self, orders: list[dict]) -> dict:
        """Cancel up to 20 orders at once."""
        return self.post("/api/v5/trade/batch-cancel-orders", orders)

    def amend_order(
        self,
        inst_id: str,
        new_sz: str = "",
        new_px: str = "",
        ord_id: str = "",
        cl_ord_id: str = "",
    ) -> dict:
        body: dict[str, str] = {"instId": inst_id}
        if ord_id:
            body["ordId"] = ord_id
        elif cl_ord_id:
            body["clOrdId"] = cl_ord_id
        if new_sz:
            body["newSz"] = new_sz
        if new_px:
            body["newPx"] = new_px
        return self.post("/api/v5/trade/amend-order", body)

    def close_position(self, inst_id: str, mgn_mode: str = "cross") -> dict:
        return self.post("/api/v5/trade/close-position", {
            "instId": inst_id, "mgnMode": mgn_mode
        })

    def get_pending_orders(self, inst_type: str = "SWAP") -> dict:
        return self.get("/api/v5/trade/orders-pending", {"instType": inst_type})

    def get_order_history(self, inst_type: str = "SWAP", limit: int = 100) -> dict:
        return self.get("/api/v5/trade/orders-history", {"instType": inst_type, "limit": limit})

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
