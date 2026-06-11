"""FRED time-series adapter."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx


class FREDClient:
    """Fetch FRED observations and apply a conservative publish-lag policy."""

    endpoint = "https://api.stlouisfed.org/fred/series/observations"

    def __init__(self, api_key: str, timeout: float = 20.0, publish_lag_days: int = 1) -> None:
        if not api_key:
            raise ValueError("FRED API key is required")
        self.api_key = api_key
        self.timeout = timeout
        self.publish_lag_days = int(publish_lag_days)
        if self.publish_lag_days < 1:
            raise ValueError("FRED publish_lag_days must be >= 1 to avoid lookahead")

    def _get(self, params: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(self.endpoint, params=params)
            response.raise_for_status()
            return response.json()

    def fetch(
        self,
        *,
        series_id: str = "DGS10",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "sort_order": "asc",
        }
        if start:
            params["observation_start"] = _as_utc(start).date().isoformat()
        if end:
            params["observation_end"] = _as_utc(end).date().isoformat()

        payload = self._get(params)
        rows: list[dict[str, Any]] = []
        for item in payload.get("observations", []) or []:
            raw_value = item.get("value")
            if raw_value in (None, "", "."):
                continue
            try:
                observed_at = datetime.fromisoformat(str(item["date"])).replace(tzinfo=timezone.utc)
                value_num = float(raw_value)
            except (KeyError, TypeError, ValueError):
                continue
            published_at = observed_at + timedelta(days=self.publish_lag_days)
            rows.append({
                "observed_at": observed_at,
                "published_at": published_at,
                "value_num": value_num,
                "value_text": None,
                "fields": {"series_id": series_id, "publish_lag_days": self.publish_lag_days},
                "quality_status": "raw",
                "raw_payload": item,
            })
        return rows


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
