"""Small signed REST client for the Binance USD-M Futures test environment."""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import time
from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx
from dotenv import dotenv_values


class BinanceFuturesTestnetClient:
    """Authenticated USD-M test client whose order API is reduce-only-only."""

    BASE_URL = "https://demo-fapi.binance.com"
    _CLIENT_ORDER_ID = re.compile(r"^[A-Za-z0-9_-]{1,36}$")

    def __init__(
        self,
        api_key: str,
        secret: str,
        *,
        timeout: float = 20.0,
        transport: httpx.BaseTransport | None = None,
        clock_ms: Callable[[], int] | None = None,
    ) -> None:
        api_key = str(api_key).strip()
        secret = str(secret).strip()
        if not api_key or not secret:
            raise RuntimeError(
                "Binance USD-M Futures Testnet requires "
                "BINANCE_FUTURES_API_KEY and BINANCE_FUTURES_SECRET"
            )
        self._secret = secret.encode("utf-8")
        self._clock_ms = clock_ms or (lambda: time.time_ns() // 1_000_000)
        self._clock_offset_ms = 0
        self._client = httpx.Client(
            base_url=self.BASE_URL,
            timeout=timeout,
            transport=transport,
            follow_redirects=False,
            headers={
                "User-Agent": "quant-strategy-binance-testnet/1",
                "X-MBX-APIKEY": api_key,
            },
        )

    @classmethod
    def from_env(
        cls,
        *,
        env_file: str | Path = ".env",
        **kwargs: Any,
    ) -> "BinanceFuturesTestnetClient":
        values = dotenv_values(env_file) if env_file and Path(env_file).exists() else {}
        api_key = (
            os.environ.get("BINANCE_FUTURES_API_KEY")
            or values.get("BINANCE_FUTURES_API_KEY")
            or os.environ.get("BINANCE_API_KEY")
            or values.get("BINANCE_API_KEY")
        )
        secret = (
            os.environ.get("BINANCE_FUTURES_SECRET")
            or values.get("BINANCE_FUTURES_SECRET")
            or os.environ.get("BINANCE_SECRET")
            or values.get("BINANCE_SECRET")
        )
        return cls(str(api_key or ""), str(secret or ""), **kwargs)

    def close(self) -> None:
        self._client.close()

    @staticmethod
    def _symbol(value: str) -> str:
        symbol = str(value).strip().upper()
        if not symbol:
            raise ValueError("symbol is required")
        return symbol

    @staticmethod
    def _side(value: str) -> str:
        side = str(value).strip().upper()
        if side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        return side

    @staticmethod
    def _positive(value: str | int | float | Decimal, name: str) -> str:
        text = str(value).strip()
        try:
            number = Decimal(text)
        except InvalidOperation as exc:
            raise ValueError(f"{name} must be a positive finite number") from exc
        if not number.is_finite() or number <= 0:
            raise ValueError(f"{name} must be a positive finite number")
        return text

    @classmethod
    def _client_order_id(cls, value: str) -> str:
        client_order_id = str(value).strip()
        if not cls._CLIENT_ORDER_ID.fullmatch(client_order_id):
            raise ValueError("client_order_id must be 1-36 ASCII letters, digits, '_' or '-'")
        return client_order_id

    @staticmethod
    def _decode(response: httpx.Response, endpoint: str) -> Any:
        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError(
                f"Binance USD-M Futures Testnet returned non-JSON for {endpoint} "
                f"(HTTP {response.status_code})"
            ) from exc
        if response.is_error:
            detail = payload.get("msg") if isinstance(payload, dict) else None
            suffix = f": {detail}" if detail else ""
            raise RuntimeError(
                f"Binance USD-M Futures Testnet HTTP {response.status_code} for {endpoint}{suffix}"
            )
        if (
            isinstance(payload, dict)
            and isinstance(payload.get("code"), int)
            and payload["code"] < 0
        ):
            raise RuntimeError(
                f"Binance USD-M Futures Testnet API error for {endpoint}: "
                f"{payload['code']} {payload.get('msg', '')}".rstrip()
            )
        return payload

    def _signed_request(
        self,
        method: str,
        endpoint: str,
        params: list[tuple[str, str]] | None = None,
    ) -> Any:
        signed_params = list(params or ())
        signed_params.extend(
            [
                ("recvWindow", "5000"),
                ("timestamp", str(int(self._clock_ms()) + self._clock_offset_ms)),
            ]
        )
        payload = urlencode(signed_params)
        signature = hmac.new(self._secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
        response = self._client.request(
            method,
            f"{endpoint}?{payload}&signature={signature}",
        )
        return self._decode(response, endpoint)

    def sync_clock(self) -> int:
        payload = self._public_get("/fapi/v1/time", [])
        if not isinstance(payload, dict) or not isinstance(payload.get("serverTime"), int):
            raise RuntimeError(
                "Binance USD-M Futures Testnet time response must include integer serverTime"
            )
        self._clock_offset_ms = payload["serverTime"] - int(self._clock_ms())
        return self._clock_offset_ms

    def _public_get(
        self,
        endpoint: str,
        params: list[tuple[str, str]],
    ) -> Any:
        response = self._client.get(endpoint, params=params)
        return self._decode(response, endpoint)

    def balance(self) -> list[dict[str, Any]]:
        payload = self._signed_request("GET", "/fapi/v3/balance")
        if not isinstance(payload, list):
            raise RuntimeError("Binance USD-M Futures balance response must be an array")
        return payload

    def positions(self, symbol: str | None = None) -> list[dict[str, Any]]:
        params = [("symbol", self._symbol(symbol))] if symbol else []
        payload = self._signed_request("GET", "/fapi/v3/positionRisk", params)
        if not isinstance(payload, list):
            raise RuntimeError("Binance USD-M Futures positions response must be an array")
        return payload

    def test_limit_order(
        self,
        symbol: str,
        side: str,
        quantity: str | int | float | Decimal,
        price: str | int | float | Decimal,
    ) -> dict[str, Any]:
        payload = self._signed_request(
            "POST",
            "/fapi/v1/order/test",
            self._limit_params(symbol, side, quantity, price),
        )
        if not isinstance(payload, dict):
            raise RuntimeError("Binance USD-M Futures test-order response must be an object")
        return payload

    def place_limit_order(
        self,
        symbol: str,
        side: str,
        quantity: str | int | float | Decimal,
        price: str | int | float | Decimal,
        *,
        client_order_id: str | None = None,
    ) -> dict[str, Any]:
        params = self._limit_params(symbol, side, quantity, price)
        if client_order_id is not None:
            params.append(("newClientOrderId", self._client_order_id(client_order_id)))
        payload = self._signed_request(
            "POST",
            "/fapi/v1/order",
            params,
        )
        if not isinstance(payload, dict):
            raise RuntimeError("Binance USD-M Futures order response must be an object")
        return payload

    def cancel_order(
        self,
        symbol: str,
        order_id: str | int | None = None,
        *,
        orig_client_order_id: str | None = None,
    ) -> dict[str, Any]:
        if (order_id is None) == (orig_client_order_id is None):
            raise ValueError("provide exactly one of order_id or orig_client_order_id")
        identifier = (
            ("orderId", str(order_id).strip())
            if order_id is not None
            else ("origClientOrderId", self._client_order_id(str(orig_client_order_id)))
        )
        if not identifier[1]:
            raise ValueError("order_id is required")
        payload = self._signed_request(
            "DELETE",
            "/fapi/v1/order",
            [("symbol", self._symbol(symbol)), identifier],
        )
        if not isinstance(payload, dict):
            raise RuntimeError("Binance USD-M Futures cancel response must be an object")
        return payload

    def open_orders(self, symbol: str | None = None) -> list[dict[str, Any]]:
        params = [("symbol", self._symbol(symbol))] if symbol else []
        payload = self._signed_request("GET", "/fapi/v1/openOrders", params)
        if not isinstance(payload, list):
            raise RuntimeError("Binance USD-M Futures open-orders response must be an array")
        return payload

    def book_ticker(self, symbol: str) -> dict[str, Any]:
        payload = self._public_get(
            "/fapi/v1/ticker/bookTicker",
            [("symbol", self._symbol(symbol))],
        )
        if not isinstance(payload, dict):
            raise RuntimeError("Binance USD-M Futures book-ticker response must be an object")
        return payload

    def exchange_info(self) -> dict[str, Any]:
        payload = self._public_get("/fapi/v1/exchangeInfo", [])
        if not isinstance(payload, dict):
            raise RuntimeError("Binance USD-M Futures exchange-info response must be an object")
        return payload

    def _limit_params(
        self,
        symbol: str,
        side: str,
        quantity: str | int | float | Decimal,
        price: str | int | float | Decimal,
    ) -> list[tuple[str, str]]:
        return [
            ("symbol", self._symbol(symbol)),
            ("side", self._side(side)),
            ("positionSide", "BOTH"),
            ("type", "LIMIT"),
            ("timeInForce", "GTC"),
            ("quantity", self._positive(quantity, "quantity")),
            ("price", self._positive(price, "price")),
            ("reduceOnly", "true"),
        ]
