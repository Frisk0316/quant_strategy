"""Nasdaq Data Link adapter for official, API-key backed datasets."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import quote

import httpx


class NasdaqDataLinkClient:
    """Fetch a configured Nasdaq Data Link dataset code."""

    base_url = "https://data.nasdaq.com/api/v3/datasets"

    def __init__(self, api_key: str, timeout: float = 30.0, publish_lag_days: int = 1) -> None:
        if not api_key:
            raise ValueError("Nasdaq Data Link API key is required")
        self.api_key = api_key
        self.timeout = timeout
        self.publish_lag_days = int(publish_lag_days)

    def _get(self, dataset_code: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/{quote(dataset_code, safe='/')}.json"
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            return response.json()

    def fetch(
        self,
        *,
        dataset_code: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "api_key": self.api_key,
            "order": "asc",
        }
        if start:
            params["start_date"] = _as_utc(start).date().isoformat()
        if end:
            params["end_date"] = _as_utc(end).date().isoformat()

        payload = self._get(dataset_code, params)
        dataset = payload.get("dataset", {}) or {}
        columns = [str(c).strip() for c in dataset.get("column_names", []) or []]
        rows: list[dict[str, Any]] = []
        for values in dataset.get("data", []) or []:
            item = dict(zip(columns, values))
            date_value = _pick(item, "Date", "date")
            if not date_value:
                continue
            try:
                observed_at = datetime.fromisoformat(str(date_value)).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            fields = {
                _normalize_key(key): value
                for key, value in item.items()
                if key and key.lower() != "date"
            }
            ohlc = {
                "open": _to_float(_pick(item, "Open", "open")),
                "high": _to_float(_pick(item, "High", "high")),
                "low": _to_float(_pick(item, "Low", "low")),
                "close": _to_float(_pick(item, "Settle", "Last", "Close", "close")),
                "volume": _to_float(_pick(item, "Volume", "volume")),
            }
            fields.update({k: v for k, v in ohlc.items() if v is not None})
            rows.append({
                "observed_at": observed_at,
                "published_at": observed_at + timedelta(days=self.publish_lag_days),
                "value_num": ohlc["close"],
                "value_text": None,
                "fields": {
                    **fields,
                    "dataset_code": dataset_code,
                    "publish_lag_days": self.publish_lag_days,
                },
                "quality_status": "raw",
                "raw_payload": item,
            })
        return rows


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _pick(item: dict[str, Any], *names: str) -> Any:
    lower = {str(k).lower(): v for k, v in item.items()}
    for name in names:
        if name in item:
            return item[name]
        if name.lower() in lower:
            return lower[name.lower()]
    return None


def _to_float(value: Any) -> Optional[float]:
    if value in (None, "", "."):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_key(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_")
