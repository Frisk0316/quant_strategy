"""Alternative.me Fear & Greed Index adapter."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

import httpx

KNOWN_CLASSIFICATIONS = {
    "extreme fear": "Extreme Fear",
    "fear": "Fear",
    "neutral": "Neutral",
    "greed": "Greed",
    "extreme greed": "Extreme Greed",
}


class FearGreedClient:
    """Fetch and normalize the BTC Crypto Fear & Greed Index."""

    endpoint = "https://api.alternative.me/fng/"

    def __init__(self, timeout: float = 20.0) -> None:
        self.timeout = timeout

    def _get(self, params: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(self.endpoint, params=params)
            response.raise_for_status()
            return response.json()

    def fetch(
        self,
        *,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 0,
    ) -> list[dict[str, Any]]:
        payload = self._get({"limit": limit, "format": "json"})
        rows: list[dict[str, Any]] = []
        for item in payload.get("data", []) or []:
            try:
                observed_at = datetime.fromtimestamp(int(item["timestamp"]), tz=timezone.utc)
                value_num = float(item["value"])
            except (KeyError, TypeError, ValueError):
                continue
            if start and observed_at < _as_utc(start):
                continue
            if end and observed_at >= _as_utc(end):
                continue
            fields = {}
            if item.get("time_until_update") not in (None, ""):
                fields["time_until_update"] = item.get("time_until_update")
            rows.append({
                "observed_at": observed_at,
                "published_at": observed_at,
                "value_num": value_num,
                "value_text": canonicalize_classification(item.get("value_classification", "")),
                "fields": fields,
                "quality_status": "raw",
                "raw_payload": item,
            })
        return sorted(rows, key=lambda row: row["observed_at"])


def canonicalize_classification(value: object) -> str:
    text = str(value or "").strip()
    return KNOWN_CLASSIFICATIONS.get(text.casefold(), text)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
