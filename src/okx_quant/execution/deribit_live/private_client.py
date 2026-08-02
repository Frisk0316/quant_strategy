"""Minimal authenticated Deribit order lifecycle client for ADR-0017."""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any

import httpx
from dotenv import dotenv_values


class DeribitPrivateClient:
    """Bearer-authenticated client whose public order API cannot express a plain taker."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        *,
        env: str = "test",
        timeout: float = 20.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        client_id = str(client_id).strip()
        client_secret = str(client_secret).strip()
        if not client_id or not client_secret:
            raise RuntimeError(
                "H-014 live execution requires DERIBIT_API_KEY and DERIBIT_API_SECRET"
            )
        if env != "test":
            raise ValueError("ADR-0018 permits H-014 private execution on testnet only")
        self._client_id = client_id
        self._client_secret = client_secret
        self._token: str | None = None
        self._client = httpx.Client(
            base_url="https://test.deribit.com/api/v2/",
            timeout=timeout,
            transport=transport,
            headers={"User-Agent": "quant-strategy-h014-live/1"},
        )

    @classmethod
    def from_env(
        cls,
        *,
        env: str = "test",
        env_file: str | Path = ".env",
        **kwargs: Any,
    ) -> "DeribitPrivateClient":
        values = dotenv_values(env_file) if env_file and Path(env_file).exists() else {}
        client_id = os.environ.get("DERIBIT_API_KEY") or values.get("DERIBIT_API_KEY")
        client_secret = os.environ.get("DERIBIT_API_SECRET") or values.get(
            "DERIBIT_API_SECRET"
        )
        return cls(str(client_id or ""), str(client_secret or ""), env=env, **kwargs)

    def close(self) -> None:
        self._client.close()

    def _authenticate(self) -> str:
        response = self._client.post(
            "public/auth",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "public/auth",
                "params": {
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
            },
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("error"):
            raise RuntimeError(f"Deribit authentication failed: {payload['error']}")
        token = str((payload.get("result") or {}).get("access_token") or "")
        if not token:
            raise RuntimeError("Deribit authentication returned no access token")
        self._token = token
        return token

    def _private_get(self, method: str, **params: Any) -> Any:
        token = self._token or self._authenticate()
        response = self._client.get(
            method,
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code == 401:
            token = self._authenticate()
            response = self._client.get(
                method,
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
        response.raise_for_status()
        payload = response.json()
        if payload.get("error"):
            raise RuntimeError(f"Deribit API error for {method}: {payload['error']}")
        return payload.get("result")

    @staticmethod
    def _positive(value: float, name: str) -> float:
        out = float(value)
        if not math.isfinite(out) or out <= 0:
            raise ValueError(f"{name} must be a positive finite number")
        return out

    def _order(
        self,
        side: str,
        instrument_name: str,
        amount: float,
        price: float,
        *,
        reduce_only: bool = False,
        label: str | None = None,
    ) -> dict[str, Any]:
        instrument_name = str(instrument_name).strip()
        if not instrument_name:
            raise ValueError("instrument_name is required")
        params: dict[str, Any] = {
            "instrument_name": instrument_name,
            "amount": self._positive(amount, "amount"),
            "type": "limit",
            "price": self._positive(price, "price"),
            "post_only": not reduce_only,
        }
        if reduce_only:
            params["reduce_only"] = True
        if label:
            params["label"] = str(label)[:64]
        return dict(self._private_get(f"private/{side}", **params) or {})

    def buy(
        self,
        instrument_name: str,
        amount: float,
        price: float,
        *,
        reduce_only: bool = False,
        label: str | None = None,
    ) -> dict[str, Any]:
        return self._order(
            "buy",
            instrument_name,
            amount,
            price,
            reduce_only=reduce_only,
            label=label,
        )

    def sell(
        self,
        instrument_name: str,
        amount: float,
        price: float,
        *,
        reduce_only: bool = False,
        label: str | None = None,
    ) -> dict[str, Any]:
        return self._order(
            "sell",
            instrument_name,
            amount,
            price,
            reduce_only=reduce_only,
            label=label,
        )

    def cancel(self, order_id: str) -> dict[str, Any]:
        order_id = str(order_id).strip()
        if not order_id:
            raise ValueError("order_id is required")
        return dict(self._private_get("private/cancel", order_id=order_id) or {})

    def cancel_by_label(self, label: str, *, currency: str | None = None) -> Any:
        label = str(label).strip()
        if not label:
            raise ValueError("label is required")
        params = {"label": label[:64]}
        if currency:
            params["currency"] = str(currency).upper()
        return self._private_get("private/cancel_by_label", **params)

    def get_order_state(self, order_id: str) -> dict[str, Any]:
        order_id = str(order_id).strip()
        if not order_id:
            raise ValueError("order_id is required")
        return dict(
            self._private_get("private/get_order_state", order_id=order_id) or {}
        )

    def cancel_all_by_currency(self, currency: str) -> Any:
        return self._private_get(
            "private/cancel_all_by_currency",
            currency=str(currency).upper(),
            kind="option",
        )

    def get_positions(self, currency: str) -> list[dict[str, Any]]:
        return list(
            self._private_get(
                "private/get_positions",
                currency=str(currency).upper(),
                kind="option",
            )
            or []
        )

    def get_account_summary(self, currency: str) -> dict[str, Any]:
        return dict(
            self._private_get(
                "private/get_account_summary",
                currency=str(currency).upper(),
                extended=False,
            )
            or {}
        )
