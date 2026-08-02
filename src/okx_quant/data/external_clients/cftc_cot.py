"""CFTC Commitments of Traders futures-only adapter."""
from __future__ import annotations

import math
import re
import time
from datetime import date, datetime, time as clock_time, timedelta, timezone
from typing import Any, Callable, Optional
from zoneinfo import ZoneInfo

import httpx


class CFTCCOTClient:
    """Fetch one configured contract from CFTC's public Socrata datasets."""

    ENDPOINTS = {
        "tff": "https://publicreporting.cftc.gov/resource/gpe5-46if.json",
        "disaggregated": "https://publicreporting.cftc.gov/resource/72hh-3qpy.json",
    }
    PAGE_SIZE = 50_000

    def __init__(
        self,
        timeout: float = 60.0,
        *,
        sleep: Callable[[float], None] = time.sleep,
        retries: int = 2,
    ) -> None:
        self.timeout = timeout
        self.sleep = sleep
        self.retries = retries

    def _get(self, endpoint: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        for attempt in range(self.retries + 1):
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(endpoint, params=params)
            if response.status_code == 429 and attempt < self.retries:
                self.sleep(0.5 * (attempt + 1))
                continue
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list):
                raise ValueError("CFTC Socrata response is not a row list")
            return [row for row in payload if isinstance(row, dict)]
        raise RuntimeError("CFTC Socrata retry exhausted")

    def fetch(
        self,
        *,
        report_type: str,
        contract_market_code: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> list[dict[str, Any]]:
        report_type = report_type.lower()
        if report_type not in self.ENDPOINTS:
            raise ValueError(f"unsupported CFTC COT report_type: {report_type}")
        contract_market_code = contract_market_code.upper()
        if not re.fullmatch(r"[A-Z0-9]+", contract_market_code):
            raise ValueError("CFTC contract_market_code must be alphanumeric")

        filters = [f"cftc_contract_market_code = '{contract_market_code}'"]
        if start:
            filters.append(
                "report_date_as_yyyy_mm_dd >= "
                f"'{_as_utc(start).date().isoformat()}T00:00:00.000'"
            )
        if end:
            filters.append(
                "report_date_as_yyyy_mm_dd <= "
                f"'{_as_utc(end).date().isoformat()}T23:59:59.999'"
            )
        params: dict[str, Any] = {
            "$where": " AND ".join(filters),
            "$order": "report_date_as_yyyy_mm_dd ASC",
            "$limit": self.PAGE_SIZE,
        }
        source_rows: list[dict[str, Any]] = []
        for offset in range(0, 1_000_000, self.PAGE_SIZE):
            page = self._get(
                self.ENDPOINTS[report_type],
                {**params, "$offset": offset},
            )
            source_rows.extend(page)
            if len(page) < self.PAGE_SIZE:
                break
        else:
            raise RuntimeError("CFTC COT pagination exceeded one million rows")

        return [
            row
            for item in source_rows
            if (row := _parse_cot_row(item, report_type)) is not None
        ]


def _parse_cot_row(
    item: dict[str, Any],
    report_type: str,
) -> Optional[dict[str, Any]]:
    try:
        report_date = datetime.fromisoformat(
            str(item["report_date_as_yyyy_mm_dd"]).replace("Z", "+00:00")
        ).date()
    except (KeyError, ValueError):
        return None
    if report_type == "tff":
        long_field = "lev_money_positions_long"
        short_field = "lev_money_positions_short"
        spread_field = "lev_money_positions_spread"
        position_class = "leveraged_money"
        category_fields = (
            "dealer_positions_long_all",
            "dealer_positions_short_all",
            "dealer_positions_spread_all",
            "asset_mgr_positions_long",
            "asset_mgr_positions_short",
            "asset_mgr_positions_spread",
            long_field,
            short_field,
            spread_field,
            "other_rept_positions_long",
            "other_rept_positions_short",
            "other_rept_positions_spread",
            "nonrept_positions_long_all",
            "nonrept_positions_short_all",
        )
    else:
        long_field = "m_money_positions_long_all"
        short_field = "m_money_positions_short_all"
        spread_field = "m_money_positions_spread"
        position_class = "managed_money"
        category_fields = (
            "prod_merc_positions_long",
            "prod_merc_positions_short",
            "swap_positions_long_all",
            "swap__positions_short_all",
            "swap__positions_spread_all",
            long_field,
            short_field,
            spread_field,
            "other_rept_positions_long",
            "other_rept_positions_short",
            "other_rept_positions_spread",
            "nonrept_positions_long_all",
            "nonrept_positions_short_all",
        )
    long_position = _number(item.get(long_field))
    short_position = _number(item.get(short_field))
    if long_position is None or short_position is None:
        return None

    observed_at = datetime.combine(report_date, clock_time(), tzinfo=timezone.utc)
    published_at = _scheduled_release_at(report_date)
    fields: dict[str, Any] = {
        "report_type": report_type,
        "position_class": position_class,
        "net_position": long_position - short_position,
        "position_long": long_position,
        "position_short": short_position,
        "position_spread": _number(item.get(spread_field)),
        "open_interest": _number(item.get("open_interest_all")),
        "unit": "contracts",
        "market_and_exchange_names": item.get("market_and_exchange_names"),
        "contract_market_name": item.get("contract_market_name"),
        "cftc_contract_market_code": item.get("cftc_contract_market_code"),
        "cftc_market_code": item.get("cftc_market_code"),
        "cftc_commodity_code": item.get("cftc_commodity_code"),
        "commodity_name": item.get("commodity_name"),
        "contract_units": item.get("contract_units"),
        "report_reference_weekday": report_date.strftime("%A"),
        "release_policy": "following_friday_1530_america_new_york",
    }
    fields.update({name: _number(item.get(name)) for name in category_fields})
    return {
        "observed_at": observed_at,
        "published_at": published_at,
        "value_num": fields["net_position"],
        "value_text": None,
        "fields": fields,
        "quality_status": "raw",
        "raw_payload": item,
    }


def _scheduled_release_at(report_date: date) -> datetime:
    friday = report_date + timedelta(days=(4 - report_date.weekday()) % 7)
    release = datetime.combine(
        friday,
        clock_time(hour=15, minute=30),
        tzinfo=ZoneInfo("America/New_York"),
    )
    if release.date() < report_date + timedelta(days=2):
        release += timedelta(days=7)
    return release.astimezone(timezone.utc)


def _number(value: Any) -> Optional[float]:
    if value in (None, "", "."):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
