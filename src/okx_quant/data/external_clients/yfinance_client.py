"""Yahoo Finance/yfinance adapter for research-only futures data."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from importlib import import_module
from typing import Any, Optional

import pandas as pd


class YFinanceClient:
    """Fetch OHLCV from yfinance.

    This adapter is intentionally research-only. Yahoo/yfinance data is not an
    official CME feed and can contain roll and adjustment artefacts.
    """

    def __init__(self, publish_lag_days: int = 1) -> None:
        self.publish_lag_days = int(publish_lag_days)
        if self.publish_lag_days < 1:
            raise ValueError("yfinance publish_lag_days must be >= 1 to avoid daily-bar lookahead")

    def _download(
        self,
        ticker: str,
        *,
        start: Optional[datetime],
        end: Optional[datetime],
        interval: str,
    ) -> pd.DataFrame:
        try:
            yf = import_module("yfinance")
        except ImportError as exc:
            raise RuntimeError(
                "yfinance is not installed. Install it before ingesting yfinance datasets."
            ) from exc
        return yf.download(
            ticker,
            start=_date_str(start),
            end=_date_str(end),
            interval=interval,
            auto_adjust=False,
            progress=False,
            group_by="column",
        )

    def fetch(
        self,
        *,
        ticker: str = "BTC=F",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        interval: str = "1d",
    ) -> list[dict[str, Any]]:
        frame = self._download(ticker, start=start, end=end, interval=interval)
        if frame.empty:
            return []
        normalized = _normalize_yfinance_frame(frame)
        rows: list[dict[str, Any]] = []
        for row in normalized.itertuples(index=False):
            observed_at = pd.Timestamp(row.observed_at).tz_convert("UTC").to_pydatetime()
            published_at = observed_at + timedelta(days=self.publish_lag_days)
            fields = {
                "open": _to_optional_float(row.open),
                "high": _to_optional_float(row.high),
                "low": _to_optional_float(row.low),
                "close": _to_optional_float(row.close),
                "volume": _to_optional_float(row.volume),
                "ticker": ticker,
                "interval": interval,
                "publish_lag_days": self.publish_lag_days,
                "research_only": True,
                "source_caveat": "Yahoo/yfinance is not an official CME source",
            }
            if any(fields[key] is None for key in ("open", "high", "low", "close")):
                continue
            rows.append({
                "observed_at": observed_at,
                "published_at": published_at,
                "value_num": fields["close"],
                "value_text": None,
                "fields": fields,
                "quality_status": "raw",
                "raw_payload": {
                    "ticker": ticker,
                    "interval": interval,
                    "observed_at": observed_at.isoformat(),
                    "open": fields["open"],
                    "high": fields["high"],
                    "low": fields["low"],
                    "close": fields["close"],
                    "volume": fields["volume"],
                },
            })
        return rows


def _normalize_yfinance_frame(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy()
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = [
            next((str(part) for part in col if str(part).lower() in {"open", "high", "low", "close", "volume"}), str(col[-1]))
            for col in data.columns
        ]
    data = data.reset_index()
    rename = {str(col): str(col).strip().lower().replace(" ", "_") for col in data.columns}
    data = data.rename(columns=rename)
    date_col = "date" if "date" in data.columns else "datetime"
    data["observed_at"] = pd.to_datetime(data[date_col], utc=True, errors="coerce")
    if "adj_close" in data.columns and "close" not in data.columns:
        data["close"] = data["adj_close"]
    for col in ("open", "high", "low", "close", "volume"):
        if col not in data.columns:
            data[col] = None
    return data.dropna(subset=["observed_at"]).sort_values("observed_at")


def _date_str(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return ts.date().isoformat()


def _to_optional_float(value: Any) -> Optional[float]:
    if value in (None, "", "."):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed
