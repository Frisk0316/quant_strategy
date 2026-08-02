"""Cboe official CSV adapter for volatility indices and total put/call ratio."""
from __future__ import annotations

import csv
import io
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx


class CBOEClient:
    """Fetch one configured daily Cboe CSV series."""

    def __init__(self, timeout: float = 60.0, publish_lag_days: int = 1) -> None:
        self.timeout = timeout
        self.publish_lag_days = int(publish_lag_days)
        if self.publish_lag_days < 1:
            raise ValueError("Cboe publish_lag_days must be >= 1")

    def _get_text(self, source_url: str) -> str:
        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            response = client.get(source_url)
        response.raise_for_status()
        return response.text

    def fetch(
        self,
        *,
        source_url: str,
        series: str,
        kind: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> list[dict[str, Any]]:
        text = self._get_text(source_url)
        if kind == "index":
            source_rows = _read_index_csv(text)
        elif kind == "put_call":
            source_rows = _read_put_call_csv(text)
        else:
            raise ValueError(f"unsupported Cboe CSV kind: {kind}")

        lower = _as_utc(start).date() if start else None
        upper = _as_utc(end).date() if end else None
        rows = []
        for item in source_rows:
            parsed = _parse_cboe_row(
                item,
                series=series,
                kind=kind,
                publish_lag_days=self.publish_lag_days,
            )
            if parsed is None:
                continue
            day = parsed["observed_at"].date()
            if lower and day < lower:
                continue
            if upper and day > upper:
                continue
            rows.append(parsed)
        return sorted(rows, key=lambda row: row["observed_at"])


def _read_index_csv(text: str) -> list[dict[str, str]]:
    rows = list(csv.DictReader(io.StringIO(text.lstrip("\ufeff"))))
    if not rows or "DATE" not in rows[0] or "CLOSE" not in rows[0]:
        raise ValueError("Cboe index CSV header not found")
    return rows


def _read_put_call_csv(text: str) -> list[dict[str, str]]:
    lines = text.lstrip("\ufeff").splitlines()
    header = next(
        (
            index
            for index, line in enumerate(lines)
            if line.strip().upper().startswith("DATE,CALLS,PUTS,TOTAL,P/C RATIO")
        ),
        None,
    )
    if header is None:
        raise ValueError("Cboe total put/call CSV header not found")
    return list(csv.DictReader(lines[header:]))


def _parse_cboe_row(
    item: dict[str, Any],
    *,
    series: str,
    kind: str,
    publish_lag_days: int,
) -> Optional[dict[str, Any]]:
    try:
        observed_at = datetime.strptime(str(item["DATE"]).strip(), "%m/%d/%Y").replace(
            tzinfo=timezone.utc
        )
    except (KeyError, ValueError):
        return None
    published_at = observed_at + timedelta(days=publish_lag_days)
    if kind == "index":
        fields = {
            "series": series,
            "unit": "index_points",
            "open": _number(item.get("OPEN")),
            "high": _number(item.get("HIGH")),
            "low": _number(item.get("LOW")),
            "close": _number(item.get("CLOSE")),
            "publish_lag_days": publish_lag_days,
        }
        value_num = fields["close"]
    else:
        fields = {
            "series": series,
            "unit": "ratio",
            "calls": _number(item.get("CALLS")),
            "puts": _number(item.get("PUTS")),
            "total": _number(item.get("TOTAL")),
            "put_call_ratio": _number(item.get("P/C Ratio")),
            "publish_lag_days": publish_lag_days,
        }
        value_num = fields["put_call_ratio"]
    if value_num is None:
        return None
    return {
        "observed_at": observed_at,
        "published_at": published_at,
        "value_num": value_num,
        "value_text": None,
        "fields": fields,
        "quality_status": "raw",
        "raw_payload": item,
    }


def _number(value: Any) -> Optional[float]:
    if value in (None, "", "."):
        return None
    try:
        parsed = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
