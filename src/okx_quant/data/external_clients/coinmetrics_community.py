"""Coin Metrics Community API daily asset-metrics adapter."""
from __future__ import annotations

import math
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator, Optional
from urllib.parse import urlparse

import httpx


class CoinMetricsCommunityClient:
    """Fetch one catalog-verified metric from the keyless Community API."""

    endpoint = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
    catalog_endpoint = "https://community-api.coinmetrics.io/v4/catalog-v2/asset-metrics"

    def __init__(self, timeout: float = 30.0, publish_lag_days: int = 1) -> None:
        self.timeout = timeout
        self.publish_lag_days = int(publish_lag_days)
        if self.publish_lag_days < 1:
            raise ValueError("Coin Metrics publish_lag_days must be >= 1")

    def _get(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            response = client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Coin Metrics response is not an object")
        return payload

    def _pages(
        self,
        endpoint: str,
        params: dict[str, Any],
    ) -> Iterator[dict[str, Any]]:
        url: Optional[str] = endpoint
        request_params: Optional[dict[str, Any]] = params
        for _ in range(10_000):
            if url is None:
                return
            payload = self._get(url, request_params)
            yield payload
            next_url = payload.get("next_page_url")
            if not next_url:
                if payload.get("next_page_token"):
                    raise ValueError("Coin Metrics pagination token has no next_page_url")
                return
            url = str(next_url)
            parsed = urlparse(url)
            if (
                parsed.scheme != "https"
                or parsed.hostname != "community-api.coinmetrics.io"
                or not parsed.path.startswith("/v4/")
            ):
                raise ValueError("Coin Metrics next_page_url left the Community API")
            request_params = None
        raise RuntimeError("Coin Metrics pagination exceeded 10,000 pages")

    def _assert_catalog_support(self, asset: str, metric: str, frequency: str) -> None:
        for payload in self._pages(
            self.catalog_endpoint,
            {"assets": asset, "metrics": metric, "page_size": 10_000},
        ):
            data = payload.get("data")
            if not isinstance(data, list):
                raise ValueError("Coin Metrics catalog has no data list")
            for item in data:
                if not isinstance(item, dict) or item.get("asset") != asset:
                    continue
                for candidate in item.get("metrics") or []:
                    if not isinstance(candidate, dict) or candidate.get("metric") != metric:
                        continue
                    frequencies = candidate.get("frequencies") or []
                    if any(
                        entry.get("frequency") == frequency
                        for entry in frequencies
                        if isinstance(entry, dict)
                    ):
                        return
        raise ValueError(
            f"Coin Metrics Community catalog does not expose {asset}/{metric}/{frequency}"
        )

    def fetch(
        self,
        *,
        asset: str,
        metric: str,
        frequency: str = "1d",
        unit: str = "metric_value",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> list[dict[str, Any]]:
        asset = asset.lower()
        if not re.fullmatch(r"[a-z0-9-]+", asset):
            raise ValueError("Coin Metrics asset must be lowercase alphanumeric")
        if not re.fullmatch(r"[A-Za-z0-9_]+", metric):
            raise ValueError("Coin Metrics metric must be alphanumeric")
        if frequency != "1d":
            raise ValueError("Coin Metrics research adapter supports only 1d frequency")
        self._assert_catalog_support(asset, metric, frequency)

        lower = _as_utc(start) if start else None
        upper = _as_utc(end) if end else None
        if lower is not None and upper is not None and upper <= lower:
            return []
        params: dict[str, Any] = {
            "assets": asset,
            "metrics": metric,
            "frequency": frequency,
            "page_size": 10_000,
        }
        if lower is not None:
            params["start_time"] = lower.isoformat().replace("+00:00", "Z")
        if upper is not None:
            params["end_time"] = upper.isoformat().replace("+00:00", "Z")

        rows: list[dict[str, Any]] = []
        for payload in self._pages(self.endpoint, params):
            data = payload.get("data")
            if not isinstance(data, list):
                raise ValueError("Coin Metrics timeseries has no data list")
            for item in data:
                row = _parse_row(
                    item,
                    asset=asset,
                    metric=metric,
                    frequency=frequency,
                    unit=unit,
                    publish_lag_days=self.publish_lag_days,
                )
                if row is None:
                    continue
                observed_at = row["observed_at"]
                if lower is not None and observed_at < lower:
                    continue
                if upper is not None and observed_at >= upper:
                    continue
                rows.append(row)
        return sorted(rows, key=lambda row: row["observed_at"])


def _parse_row(
    item: Any,
    *,
    asset: str,
    metric: str,
    frequency: str,
    unit: str,
    publish_lag_days: int,
) -> Optional[dict[str, Any]]:
    if not isinstance(item, dict) or item.get("asset") != asset:
        return None
    try:
        observed_at = datetime.fromisoformat(str(item["time"]).replace("Z", "+00:00"))
        observed_at = _as_utc(observed_at)
        value_num = float(item[metric])
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
            "asset": asset,
            "metric": metric,
            "frequency": frequency,
            "unit": unit,
            "publish_lag_days": publish_lag_days,
        },
        "quality_status": "raw",
        "raw_payload": item,
    }


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
