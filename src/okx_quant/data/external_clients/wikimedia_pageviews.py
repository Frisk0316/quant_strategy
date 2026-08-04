"""Wikimedia per-article daily pageviews adapter."""
from __future__ import annotations

import math
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional
from urllib.parse import quote

import httpx


class WikimediaPageviewsClient:
    """Fetch complete daily pageviews from Wikimedia's public Analytics API."""

    endpoint = (
        "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
        "{project}/{access}/{agent}/{article}/daily/{start}/{end}"
    )
    earliest_day = datetime(2015, 7, 1, tzinfo=timezone.utc)
    chunk_days = 365

    def __init__(
        self,
        timeout: float = 30.0,
        *,
        publish_lag_days: int = 1,
        user_agent: str = "quant_strategy/1.0 (https://github.com/Frisk0316/quant_strategy)",
        retries: int = 2,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.timeout = timeout
        self.publish_lag_days = int(publish_lag_days)
        self.user_agent = user_agent.strip()
        self.retries = int(retries)
        self.sleep = sleep
        if self.publish_lag_days < 1:
            raise ValueError("Wikimedia publish_lag_days must be >= 1")
        if not self.user_agent:
            raise ValueError("Wikimedia User-Agent is required")
        if self.retries < 0:
            raise ValueError("Wikimedia retries must be >= 0")

    def _get(self, url: str) -> dict[str, Any]:
        for attempt in range(self.retries + 1):
            with httpx.Client(
                timeout=self.timeout,
                headers={"Accept": "application/json", "User-Agent": self.user_agent},
            ) as client:
                response = client.get(url)
            retryable = response.status_code == 429 or response.status_code >= 500
            if retryable and attempt < self.retries:
                retry_after = response.headers.get("Retry-After", "")
                try:
                    delay = float(retry_after)
                except ValueError:
                    delay = 0.5 * (2**attempt)
                self.sleep(min(max(delay, 0.0), 10.0))
                continue
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("Wikimedia response is not an object")
            return payload
        raise RuntimeError("Wikimedia retry exhausted")

    def fetch(
        self,
        *,
        project: str = "en.wikipedia.org",
        article: str = "Bitcoin",
        access: str = "all-access",
        agent: str = "user",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> list[dict[str, Any]]:
        if not project or not article:
            raise ValueError("Wikimedia project and article are required")
        if access not in {"all-access", "desktop", "mobile-app", "mobile-web"}:
            raise ValueError(f"unsupported Wikimedia access: {access}")
        if agent not in {"all-agents", "user", "spider", "automated"}:
            raise ValueError(f"unsupported Wikimedia agent: {agent}")

        lower = _as_utc(start) if start else self.earliest_day
        upper = _as_utc(end) if end else _utc_day_start(datetime.now(timezone.utc))
        if upper <= lower:
            return []
        cursor = _utc_day_start(lower)
        last_day = _utc_day_start(upper - timedelta(microseconds=1))
        rows: list[dict[str, Any]] = []
        while cursor <= last_day:
            chunk_end = min(cursor + timedelta(days=self.chunk_days - 1), last_day)
            url = self.endpoint.format(
                project=quote(project, safe=""),
                access=quote(access, safe=""),
                agent=quote(agent, safe=""),
                article=quote(article.replace(" ", "_"), safe=""),
                start=cursor.strftime("%Y%m%d00"),
                end=chunk_end.strftime("%Y%m%d00"),
            )
            payload = self._get(url)
            items = payload.get("items")
            if not isinstance(items, list):
                raise ValueError("Wikimedia response has no items list")
            for item in items:
                row = _parse_row(
                    item,
                    project=project,
                    article=article,
                    access=access,
                    agent=agent,
                    publish_lag_days=self.publish_lag_days,
                )
                if row is not None and lower <= row["observed_at"] < upper:
                    rows.append(row)
            cursor = chunk_end + timedelta(days=1)
        return sorted(rows, key=lambda row: row["observed_at"])


def _parse_row(
    item: Any,
    *,
    project: str,
    article: str,
    access: str,
    agent: str,
    publish_lag_days: int,
) -> Optional[dict[str, Any]]:
    if not isinstance(item, dict):
        return None
    try:
        observed_at = datetime.strptime(str(item["timestamp"]), "%Y%m%d%H").replace(
            tzinfo=timezone.utc
        )
        value_num = float(item["views"])
    except (KeyError, TypeError, ValueError):
        return None
    if not math.isfinite(value_num):
        return None
    return {
        "observed_at": observed_at,
        "published_at": observed_at + timedelta(days=publish_lag_days),
        "value_num": value_num,
        "value_text": None,
        "fields": {
            "project": project,
            "article": article,
            "access": access,
            "agent": agent,
            "unit": "views",
            "publish_lag_days": publish_lag_days,
        },
        "quality_status": "raw",
        "raw_payload": item,
    }


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _utc_day_start(value: datetime) -> datetime:
    value = _as_utc(value)
    return value.replace(hour=0, minute=0, second=0, microsecond=0)
