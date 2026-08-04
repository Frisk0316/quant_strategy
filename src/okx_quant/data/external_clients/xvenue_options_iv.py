"""Cross-venue BTC/ETH option-IV snapshots from public venue APIs."""
from __future__ import annotations

import math
import time
from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Any, Callable, Optional

import httpx


class CrossVenueOptionsIVClient:
    """Fetch a full option summary and derive one 30-day IV row."""

    OKX_SUMMARY = "https://www.okx.com/api/v5/public/opt-summary"
    OKX_OI = "https://www.okx.com/api/v5/public/open-interest"
    BYBIT_TICKERS = "https://api.bybit.com/v5/market/tickers"
    DERIBIT_SUMMARY = "https://www.deribit.com/api/v2/public/get_book_summary_by_currency"
    DERIBIT_BOOK = "https://www.deribit.com/api/v2/public/get_order_book"

    def __init__(
        self,
        timeout: float = 30.0,
        *,
        sleep: Callable[[float], None] = time.sleep,
        retries: int = 2,
        now: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self.timeout = timeout
        self.sleep = sleep
        self.retries = retries
        self.now = now or (lambda: datetime.now(timezone.utc))

    def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(self.retries + 1):
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, params=params)
            if response.status_code == 429 and attempt < self.retries:
                self.sleep(0.5 * (attempt + 1))
                continue
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError(f"{url}: response is not an object")
            return payload
        raise RuntimeError(f"{url}: retry exhausted")

    def fetch(self, *, venue: str, currency: str) -> list[dict[str, Any]]:
        venue = venue.lower()
        currency = currency.upper()
        if currency not in {"BTC", "ETH"}:
            raise ValueError(f"unsupported option currency: {currency}")
        if venue == "okx":
            return [self._fetch_okx(currency)]
        if venue == "bybit":
            return [self._fetch_bybit(currency)]
        if venue == "deribit":
            return [self._fetch_deribit(currency)]
        raise ValueError(f"unsupported option venue: {venue}")

    def _fetch_okx(self, currency: str) -> dict[str, Any]:
        family = f"{currency}-USD"
        summary = self._get(self.OKX_SUMMARY, {"instFamily": family})
        oi_payload = self._get(
            self.OKX_OI,
            {"instType": "OPTION", "instFamily": family},
        )
        _check_code(summary.get("code") == "0", "OKX option summary", summary.get("msg"))
        _check_code(oi_payload.get("code") == "0", "OKX option OI", oi_payload.get("msg"))

        oi_rows = list(oi_payload.get("data") or [])
        oi_by_instrument = {str(row.get("instId")): row for row in oi_rows}
        options = [
            option
            for row in list(summary.get("data") or [])
            if (option := _normalize_okx(row, oi_by_instrument.get(str(row.get("instId")), {})))
        ]
        snapshot_at = _latest_timestamp(
            [
                *(row.get("ts") for row in summary.get("data") or []),
                *(row.get("ts") for row in oi_rows),
            ],
            self.now(),
        )
        return aggregate_options_iv(
            "okx",
            currency,
            options,
            snapshot_at,
            oi_unit="contracts",
            oi_total_usd=sum(_number(row.get("oiUsd")) or 0.0 for row in oi_rows),
        )

    def _fetch_bybit(self, currency: str) -> dict[str, Any]:
        payload = self._get(
            self.BYBIT_TICKERS,
            {"category": "option", "baseCoin": currency},
        )
        _check_code(payload.get("retCode") == 0, "Bybit option tickers", payload.get("retMsg"))
        rows = list((payload.get("result") or {}).get("list") or [])
        options = [option for row in rows if (option := _normalize_bybit(row))]
        return aggregate_options_iv(
            "bybit",
            currency,
            options,
            _timestamp(payload.get("time")) or self.now(),
            oi_unit="venue_native_size",
        )

    def _fetch_deribit(self, currency: str) -> dict[str, Any]:
        payload = self._get(
            self.DERIBIT_SUMMARY,
            {"currency": currency, "kind": "option"},
        )
        _check_code(not payload.get("error"), "Deribit option summary", payload.get("error"))
        rows = list(payload.get("result") or [])
        snapshot_at = _latest_timestamp(
            (row.get("creation_timestamp") for row in rows),
            self.now(),
        )
        options = [
            option
            for row in rows
            if (option := _normalize_deribit_summary(row, snapshot_at))
        ]
        for option in _deribit_candidates(options, snapshot_at):
            book_payload = self._get(
                self.DERIBIT_BOOK,
                {"instrument_name": option["instrument"], "depth": 1},
            )
            _check_code(
                not book_payload.get("error"),
                "Deribit option book",
                book_payload.get("error"),
            )
            book = dict(book_payload.get("result") or {})
            greeks = book.get("greeks") or {}
            option.update(
                {
                    "delta": _number(greeks.get("delta")) or option["delta"],
                    "mark_iv": _percent_iv(book.get("mark_iv")) or option["mark_iv"],
                    "bid_iv": _percent_iv(book.get("bid_iv")),
                    "ask_iv": _percent_iv(book.get("ask_iv")),
                    "open_interest": _number(book.get("open_interest"))
                    or option["open_interest"],
                    "source": {"summary": option["source"], "book": book},
                }
            )
            snapshot_at = max(
                snapshot_at,
                _timestamp(book.get("timestamp")) or snapshot_at,
            )
        return aggregate_options_iv(
            "deribit",
            currency,
            options,
            snapshot_at,
            oi_unit="base_coin",
            oi_total_usd=sum(
                (_number(row.get("open_interest")) or 0.0)
                * (_number(row.get("underlying_price")) or 0.0)
                for row in rows
            ),
        )


def aggregate_options_iv(
    venue: str,
    currency: str,
    options: list[dict[str, Any]],
    snapshot_at: datetime,
    *,
    oi_unit: str,
    oi_total_usd: Optional[float] = None,
) -> dict[str, Any]:
    """Interpolate bracketing expiries to a 30-day constant-maturity snapshot."""
    snapshot_at = _utc(snapshot_at)
    active = [
        row
        for row in options
        if row.get("expiry")
        and row["expiry"] > snapshot_at
        and row.get("option_type") in {"call", "put"}
    ]
    metrics = [
        metric
        for expiry in sorted({row["expiry"] for row in active})
        if (metric := _expiry_metrics(
            [row for row in active if row["expiry"] == expiry],
            snapshot_at,
        ))
    ]
    if not metrics:
        raise ValueError(f"{venue} {currency}: no expiry has ATM and 25-delta legs")

    lower, upper = _bracket_metrics(metrics, snapshot_at + timedelta(days=30))
    target_years = 30 / 365
    atm_iv = _constant_maturity_iv(lower, upper, "atm_iv", target_years)
    call25_iv = _constant_maturity_iv(lower, upper, "call25_iv", target_years)
    put25_iv = _constant_maturity_iv(lower, upper, "put25_iv", target_years)
    atm_spread = _linear_metric(lower, upper, "atm_spread", target_years)
    observed_at = snapshot_at.replace(minute=0, second=0, microsecond=0)
    published_at = observed_at + timedelta(hours=1)
    selected = [lower] if lower is upper else [lower, upper]

    fields = {
        "venue": venue,
        "currency": currency,
        "unit": "iv_decimal",
        "tenor_days": 30,
        "atm_iv_30d": atm_iv,
        "rr_25d": call25_iv - put25_iv,
        "rr_25d_convention": "call_iv_minus_put_iv",
        "atm_top_of_book_iv_spread": atm_spread,
        "interp": "nearest" if lower is upper else "total_variance",
        "expiry_lower": lower["expiry"].date().isoformat(),
        "expiry_upper": upper["expiry"].date().isoformat(),
        "dte_lower_days": lower["dte_years"] * 365,
        "dte_upper_days": upper["dte_years"] * 365,
        "oi_total": sum(row.get("open_interest") or 0.0 for row in active),
        "oi_total_usd": oi_total_usd,
        "oi_unit": oi_unit,
        "n_instruments": len(active),
        "selected_legs": {
            metric["expiry"].date().isoformat(): metric["selected_legs"]
            for metric in selected
        },
    }
    return {
        "observed_at": observed_at,
        "published_at": published_at,
        "value_num": atm_iv,
        "value_text": None,
        "fields": fields,
        "quality_status": "raw" if atm_spread is not None else "suspect",
        "raw_payload": {
            "scope": "full_current_chain",
            "source_snapshot_at": snapshot_at.isoformat(),
            "instruments": [
                _raw_leg(row)
                for row in sorted(
                    active,
                    key=lambda item: (
                        item["expiry"],
                        item["strike"],
                        item["option_type"],
                        item["instrument"],
                    ),
                )
            ],
        },
    }


def _expiry_metrics(
    chain: list[dict[str, Any]],
    snapshot_at: datetime,
) -> Optional[dict[str, Any]]:
    if not chain:
        return None
    expiry = chain[0]["expiry"]
    calls = [row for row in chain if row["option_type"] == "call"]
    puts = [row for row in chain if row["option_type"] == "put"]
    calls_with_ref = [row for row in calls if row.get("underlying_price")]
    puts_with_ref = [row for row in puts if row.get("underlying_price")]
    calls_with_delta = [row for row in calls if row.get("delta") is not None]
    puts_with_delta = [row for row in puts if row.get("delta") is not None]
    if not all((calls_with_ref, puts_with_ref, calls_with_delta, puts_with_delta)):
        return None
    atm_call = min(
        calls_with_ref,
        key=lambda row: (abs(row["strike"] - row["underlying_price"]), row["strike"]),
    )
    atm_put = min(
        puts_with_ref,
        key=lambda row: (abs(row["strike"] - row["underlying_price"]), row["strike"]),
    )
    call25 = min(
        calls_with_delta,
        key=lambda row: (abs(row["delta"] - 0.25), row["strike"]),
    )
    put25 = min(
        puts_with_delta,
        key=lambda row: (abs(row["delta"] + 0.25), row["strike"]),
    )
    selected = (atm_call, atm_put, call25, put25)
    if any(row.get("mark_iv") is None for row in selected):
        return None
    spreads = [
        row["ask_iv"] - row["bid_iv"]
        for row in (atm_call, atm_put)
        if row.get("bid_iv") is not None
        and row.get("ask_iv") is not None
        and row["ask_iv"] >= row["bid_iv"]
    ]
    return {
        "expiry": expiry,
        "dte_years": (expiry - snapshot_at).total_seconds() / (365 * 86400),
        "atm_iv": mean((atm_call["mark_iv"], atm_put["mark_iv"])),
        "call25_iv": call25["mark_iv"],
        "put25_iv": put25["mark_iv"],
        "atm_spread": mean(spreads) if spreads else None,
        "selected_legs": {
            "atm_call": _leg(atm_call),
            "atm_put": _leg(atm_put),
            "call_25d": _leg(call25),
            "put_25d": _leg(put25),
        },
    }


def _bracket_metrics(
    metrics: list[dict[str, Any]],
    target: datetime,
) -> tuple[dict[str, Any], dict[str, Any]]:
    below = [metric for metric in metrics if metric["expiry"] <= target]
    above = [metric for metric in metrics if metric["expiry"] >= target]
    if below and above:
        return max(below, key=lambda row: row["expiry"]), min(
            above,
            key=lambda row: row["expiry"],
        )
    nearest = min(metrics, key=lambda row: abs((row["expiry"] - target).total_seconds()))
    return nearest, nearest


def _constant_maturity_iv(
    lower: dict[str, Any],
    upper: dict[str, Any],
    field: str,
    target_years: float,
) -> float:
    if lower is upper:
        return float(lower[field])
    lower_t = float(lower["dte_years"])
    upper_t = float(upper["dte_years"])
    lower_var = float(lower[field]) ** 2 * lower_t
    upper_var = float(upper[field]) ** 2 * upper_t
    weight = (target_years - lower_t) / (upper_t - lower_t)
    target_var = lower_var + weight * (upper_var - lower_var)
    if target_var <= 0:
        raise ValueError(f"{field}: non-positive interpolated total variance")
    return math.sqrt(target_var / target_years)


def _linear_metric(
    lower: dict[str, Any],
    upper: dict[str, Any],
    field: str,
    target_years: float,
) -> Optional[float]:
    lower_value = lower.get(field)
    upper_value = upper.get(field)
    if lower_value is None or upper_value is None:
        return lower_value if lower is upper else None
    if lower is upper:
        return float(lower_value)
    weight = (target_years - lower["dte_years"]) / (
        upper["dte_years"] - lower["dte_years"]
    )
    return float(lower_value) + weight * (float(upper_value) - float(lower_value))


def _normalize_okx(
    row: dict[str, Any],
    oi: dict[str, Any],
) -> Optional[dict[str, Any]]:
    instrument = str(row.get("instId") or "")
    expiry, option_type, strike = _instrument_parts(instrument, "okx")
    if not expiry:
        return None
    return {
        "instrument": instrument,
        "expiry": expiry,
        "option_type": option_type,
        "strike": strike,
        "delta": _number(row.get("deltaBS")),
        "mark_iv": _positive(row.get("markVol")),
        "bid_iv": _positive(row.get("bidVol")),
        "ask_iv": _positive(row.get("askVol")),
        "open_interest": _number(oi.get("oi")),
        "underlying_price": _positive(row.get("fwdPx")),
        "source": {"summary": row, "open_interest": oi},
    }


def _normalize_bybit(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    instrument = str(row.get("symbol") or "")
    expiry, option_type, strike = _instrument_parts(instrument, "bybit")
    if not expiry:
        return None
    return {
        "instrument": instrument,
        "expiry": expiry,
        "option_type": option_type,
        "strike": strike,
        "delta": _number(row.get("delta")),
        "mark_iv": _positive(row.get("markIv")),
        "bid_iv": _positive(row.get("bid1Iv")),
        "ask_iv": _positive(row.get("ask1Iv")),
        "open_interest": _number(row.get("openInterest")),
        "underlying_price": _positive(row.get("underlyingPrice")),
        "source": row,
    }


def _normalize_deribit_summary(
    row: dict[str, Any],
    snapshot_at: datetime,
) -> Optional[dict[str, Any]]:
    instrument = str(row.get("instrument_name") or "")
    expiry, option_type, strike = _instrument_parts(instrument, "deribit")
    mark_iv = _percent_iv(row.get("mark_iv"))
    underlying = _positive(row.get("underlying_price"))
    if not expiry or mark_iv is None or underlying is None or strike is None:
        return None
    delta = _black_scholes_delta(
        option_type,
        underlying,
        strike,
        mark_iv,
        max((expiry - snapshot_at).total_seconds() / (365 * 86400), 0.0),
        _number(row.get("interest_rate")) or 0.0,
    )
    return {
        "instrument": instrument,
        "expiry": expiry,
        "option_type": option_type,
        "strike": strike,
        "delta": delta,
        "mark_iv": mark_iv,
        "bid_iv": None,
        "ask_iv": None,
        "open_interest": _number(row.get("open_interest")),
        "underlying_price": underlying,
        "source": row,
    }


def _deribit_candidates(
    options: list[dict[str, Any]],
    snapshot_at: datetime,
) -> list[dict[str, Any]]:
    active = [
        row
        for row in options
        if row["expiry"] > snapshot_at and row.get("delta") is not None
    ]
    if not active:
        return []
    target = snapshot_at + timedelta(days=30)
    expiries = sorted({row["expiry"] for row in active})
    below = [expiry for expiry in expiries if expiry <= target]
    above = [expiry for expiry in expiries if expiry >= target]
    selected_expiries = {
        *([max(below)] if below else []),
        *([min(above)] if above else []),
    }
    if not selected_expiries:
        selected_expiries = {
            min(expiries, key=lambda expiry: abs((expiry - target).total_seconds()))
        }
    candidates: dict[str, dict[str, Any]] = {}
    for expiry in selected_expiries:
        chain = [row for row in active if row["expiry"] == expiry]
        for option_type, target_delta in (
            ("call", 0.25),
            ("put", -0.25),
            ("call", 0.50),
            ("put", -0.50),
        ):
            matching = [row for row in chain if row["option_type"] == option_type]
            for row in sorted(
                matching,
                key=lambda item: (
                    abs(item["delta"] - target_delta),
                    item["strike"],
                ),
            )[:2]:
                candidates[row["instrument"]] = row
    return list(candidates.values())


def _leg(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: row.get(key)
        for key in (
            "instrument",
            "strike",
            "delta",
            "mark_iv",
            "bid_iv",
            "ask_iv",
            "open_interest",
        )
    }


def _raw_leg(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **_leg(row),
        "expiry": row["expiry"].isoformat(),
        "option_type": row["option_type"],
        "underlying_price": row.get("underlying_price"),
        "source": row["source"],
    }


def _instrument_parts(
    instrument: str,
    venue: str,
) -> tuple[Optional[datetime], Optional[str], Optional[float]]:
    parts = instrument.split("-")
    option_index = (
        -2
        if venue == "bybit" and len(parts) >= 5 and parts[-2] in {"C", "P"}
        else -1
    )
    if len(parts) < 4 or parts[option_index] not in {"C", "P"}:
        return None, None, None
    date_format = "%y%m%d" if venue == "okx" else "%d%b%y"
    try:
        expiry = datetime.strptime(
            parts[option_index - 2].upper(),
            date_format,
        ).replace(hour=8, tzinfo=timezone.utc)
    except ValueError:
        return None, None, None
    return (
        expiry,
        "call" if parts[option_index] == "C" else "put",
        _positive(parts[option_index - 1]),
    )


def _black_scholes_delta(
    option_type: str,
    underlying: float,
    strike: float,
    volatility: float,
    years: float,
    rate: float,
) -> Optional[float]:
    if underlying <= 0 or strike <= 0 or volatility <= 0 or years <= 0:
        return None
    d1 = (
        math.log(underlying / strike)
        + (rate + 0.5 * volatility * volatility) * years
    ) / (volatility * math.sqrt(years))
    call_delta = 0.5 * (1.0 + math.erf(d1 / math.sqrt(2.0)))
    return call_delta if option_type == "call" else call_delta - 1.0


def _latest_timestamp(values: Any, fallback: datetime) -> datetime:
    timestamps = [_timestamp(value) for value in values]
    return max(
        (value for value in timestamps if value is not None),
        default=_utc(fallback),
    )


def _timestamp(value: Any) -> Optional[datetime]:
    parsed = _number(value)
    if parsed is None:
        return None
    return datetime.fromtimestamp(parsed / 1000, tz=timezone.utc)


def _percent_iv(value: Any) -> Optional[float]:
    parsed = _positive(value)
    return parsed / 100 if parsed is not None else None


def _positive(value: Any) -> Optional[float]:
    parsed = _number(value)
    return parsed if parsed is not None and parsed > 0 else None


def _number(value: Any) -> Optional[float]:
    if value in (None, "", "."):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _check_code(ok: bool, source: str, detail: Any) -> None:
    if not ok:
        raise RuntimeError(f"{source} error: {detail}")
