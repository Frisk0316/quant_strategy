"""OKX public liquidation-order adapter."""
from __future__ import annotations

import math
import time
from datetime import datetime, timezone
from typing import Any, Callable, Optional

import httpx


class OKXLiquidationClient:
    """Fetch recent OKX public liquidation orders for forward accumulation."""

    endpoint = "https://www.okx.com/api/v5/public/liquidation-orders"

    def __init__(
        self,
        timeout: float = 20.0,
        retries: int = 2,
        sleep: Callable[[float], None] = time.sleep,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self.timeout = timeout
        self.retries = retries
        self.sleep = sleep
        self.transport = transport

    def _get(self, params: dict[str, Any]) -> dict[str, Any]:
        client_kwargs: dict[str, Any] = {"timeout": self.timeout}
        if self.transport is not None:
            client_kwargs["transport"] = self.transport
        for attempt in range(self.retries + 1):
            with httpx.Client(**client_kwargs) as client:
                response = client.get(self.endpoint, params=params)
            if response.status_code == 429 and attempt < self.retries:
                self.sleep(_retry_after_seconds(response.headers.get("Retry-After"), attempt))
                continue
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("OKX liquidation response must be a JSON object")
            if str(payload.get("code", "0")) != "0":
                raise ValueError(f"OKX liquidation API error: {payload.get('msg') or payload.get('code')}")
            return payload
        raise RuntimeError("unreachable")

    def fetch(
        self,
        *,
        inst_type: str,
        uly: Optional[str] = None,
        inst_family: Optional[str] = None,
        inst_id: Optional[str] = None,
        state: str = "filled",
        contract_value: Optional[float] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "instType": str(inst_type).upper(),
            "state": str(state),
            "limit": int(limit),
        }
        if uly:
            params["uly"] = str(uly).upper()
        elif inst_family:
            params["instFamily"] = str(inst_family).upper()
        elif inst_id:
            params["uly"] = _derive_uly(str(inst_id))

        payload = self._get(params)
        rows: list[dict[str, Any]] = []
        for parent in payload.get("data", []) or []:
            if not isinstance(parent, dict):
                continue
            parent_inst_id = parent.get("instId")
            if inst_id and parent_inst_id and str(parent_inst_id).upper() != str(inst_id).upper():
                continue
            details = parent.get("details")
            if not isinstance(details, list):
                details = [parent]
            for detail in details:
                if not isinstance(detail, dict):
                    continue
                observed_at = _extract_timestamp(detail) or _extract_timestamp(parent)
                if observed_at is None:
                    continue
                if start and observed_at < _as_utc(start):
                    continue
                if end and observed_at >= _as_utc(end):
                    continue

                value_num, source_field, notional_status = _notional(detail, contract_value)
                price = _first_float(detail, "bkPx", "liqPx", "px", "price")
                size = _first_float(detail, "sz", "size")
                rows.append({
                    "observed_at": observed_at,
                    "published_at": observed_at,
                    "value_num": value_num,
                    "value_text": None,
                    "fields": {
                        "exchange": "okx",
                        "source": "okx_public_liquidation_orders",
                        "history_policy": "forward_accumulation_public_recent_window",
                        "inst_type": parent.get("instType") or str(inst_type).upper(),
                        "inst_id": parent.get("instId") or inst_id,
                        "uly": parent.get("uly"),
                        "side": detail.get("side"),
                        "pos_side": detail.get("posSide"),
                        "price": price,
                        "size": size,
                        "contract_value": contract_value,
                        "unit": "USDT_notional",
                        "value_unit": "USDT_notional",
                        "source_value_field": source_field,
                        "notional_status": notional_status,
                    },
                    "quality_status": "raw",
                    "raw_payload": {"parent": parent, "detail": detail},
                })
        return sorted(rows, key=lambda row: row["observed_at"])


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _derive_uly(inst_id: str) -> str:
    parts = inst_id.upper().split("-")
    return "-".join(parts[:2]) if len(parts) >= 2 else inst_id.upper()


def _extract_timestamp(item: dict[str, Any]) -> Optional[datetime]:
    for key in ("ts", "uTime", "cTime", "time"):
        raw = item.get(key)
        if raw in (None, ""):
            continue
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value < 10_000_000_000:
            value *= 1000
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    return None


def _notional(detail: dict[str, Any], contract_value: Optional[float]) -> tuple[Optional[float], str, str]:
    raw_notional = _first_named_float(
        detail,
        "notionalUsd",
        "notionalUSD",
        "notional",
        "usdValue",
        "value",
    )
    if raw_notional is not None:
        key, value = raw_notional
        return abs(value), key, "provided_by_source"

    price = _first_float(detail, "bkPx", "liqPx", "px", "price")
    size = _first_float(detail, "sz", "size")
    if price is not None and size is not None and contract_value is not None:
        return abs(price * size * float(contract_value)), "sz*bkPx*contract_value", "computed_from_contract_value"
    return None, "none", "missing_price_or_size"


def _first_named_float(item: dict[str, Any], *keys: str) -> Optional[tuple[str, float]]:
    for key in keys:
        value = _to_float(item.get(key))
        if value is not None:
            return key, value
    return None


def _first_float(item: dict[str, Any], *keys: str) -> Optional[float]:
    named = _first_named_float(item, *keys)
    return named[1] if named else None


def _to_float(value: Any) -> Optional[float]:
    if value in (None, "", "."):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _retry_after_seconds(value: Optional[str], attempt: int) -> float:
    parsed = _to_float(value)
    if parsed is not None and parsed >= 0:
        return parsed
    return min(2.0 ** attempt, 30.0)
