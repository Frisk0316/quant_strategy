"""One-cycle, public-data-only Deribit shadow execution for H-014.

This module deliberately has no broker, credential, or order-placement surface.
Signal and accounting definitions are imported from the accepted research code
so the shadow path cannot quietly re-derive either one.
"""

from __future__ import annotations

import json
import math
import os
import time
from collections import defaultdict
from datetime import date, datetime, time as dt_time, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import asyncpg
import httpx
import yaml

from research.probes.f_vol_regime_opt_probe import build_series
from research.probes.h014_collect_leg_marks import target_strikes
from research.probes.h014_stage3_backtest import (
    bs_coin,
    settle,
    settlement_fee,
    trade_fee,
)

FROZEN_IVP_MIN = 85.0
FROZEN_Z_MIN = 0.5
FROZEN_TRANCHE_UNITS = 1.0 / 30.0
FROZEN_UNIT_CAP = 1.0
FROZEN_FEES = {
    "trade_coin_cap": 0.0003,
    "settlement_coin_cap": 0.00015,
    "premium_fraction_cap": 0.125,
}
PUBLIC_METHODS = {
    "get_delivery_prices",
    "get_instruments",
    "get_last_trades_by_instrument_and_time",
    "get_order_book",
}
LEG_SPECS = {
    "call_25d": ("call", "sell"),
    "put_25d": ("put", "sell"),
    "put_10d": ("put", "buy"),
}


def _finite(value: Any, *, positive: bool = False) -> float:
    out = float(value)
    if not math.isfinite(out) or (positive and out <= 0):
        raise ValueError(f"expected {'positive ' if positive else ''}finite number, got {value!r}")
    return out


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return _utc(value).isoformat().replace("+00:00", "Z")


def load_config(path: str | Path) -> dict[str, Any]:
    """Load and fail closed if any approved shadow-only constant drifts."""
    config = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if config.get("mode") != "shadow_only":
        raise ValueError("mode must be shadow_only")
    endpoint = urlparse(str(config.get("public_api_url", "")))
    if (
        endpoint.scheme != "https"
        or endpoint.hostname != "www.deribit.com"
        or endpoint.netloc != "www.deribit.com"
        or endpoint.path.rstrip("/") != "/api/v2/public"
        or endpoint.username
        or endpoint.password
        or endpoint.query
        or endpoint.fragment
    ):
        raise ValueError("public_api_url must be the credential-free Deribit public API")
    forbidden = {"api_key", "secret", "passphrase", "private_key", "credential", "token"}

    def keys(value: Any):
        if isinstance(value, dict):
            for key, child in value.items():
                yield str(key).lower()
                yield from keys(child)
        elif isinstance(value, list):
            for child in value:
                yield from keys(child)

    if any(part in key for key in keys(config) for part in forbidden):
        raise ValueError("credentials are forbidden in H-014 shadow config")
    signal = config.get("signal") or {}
    limits = config.get("limits") or {}
    fees = config.get("fees") or {}
    expected = {
        "signal.ivp_min": (signal.get("ivp_min"), FROZEN_IVP_MIN),
        "signal.z_min": (signal.get("z_min"), FROZEN_Z_MIN),
        "limits.tranche_units": (limits.get("tranche_units"), FROZEN_TRANCHE_UNITS),
        "limits.unit_cap_per_symbol": (limits.get("unit_cap_per_symbol"), FROZEN_UNIT_CAP),
        **{f"fees.{key}": (fees.get(key), value) for key, value in FROZEN_FEES.items()},
    }
    for name, (actual, approved) in expected.items():
        if actual is None or not math.isclose(float(actual), approved, rel_tol=0, abs_tol=1e-12):
            raise ValueError(f"{name} is frozen at {approved}; change requires user approval")
    imported_fee_checks = {
        "trade coin cap": (trade_fee(1.0), FROZEN_FEES["trade_coin_cap"]),
        "trade premium cap": (
            trade_fee(0.001),
            FROZEN_FEES["premium_fraction_cap"] * 0.001,
        ),
        "settlement coin cap": (
            settlement_fee(1.0),
            FROZEN_FEES["settlement_coin_cap"],
        ),
    }
    for name, (actual, approved) in imported_fee_checks.items():
        if not math.isclose(actual, approved, rel_tol=0, abs_tol=1e-12):
            raise ValueError(f"imported R8.4 {name} drifted from the approved frozen rule")
    symbols = config.get("symbols") or {}
    if set(symbols) != {"BTC", "ETH"} or not all(str(value) for value in symbols.values()):
        raise ValueError("symbols must map exactly BTC and ETH to canonical DB instruments")
    if not str(config.get("journal_path", "")).strip():
        raise ValueError("journal_path is required")
    return config


def resolve_dsn(settings_path: str | Path = "config/settings.yaml") -> str:
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    settings = yaml.safe_load(Path(settings_path).read_text(encoding="utf-8")) or {}
    dsn = (settings.get("storage") or {}).get("timescale_dsn")
    if not dsn:
        raise RuntimeError("DATABASE_URL or storage.timescale_dsn is required")
    return str(dsn)


def compute_signal_rows(dvol: dict[str, float], closes: dict[str, float]) -> list[dict[str, Any]]:
    """Delegate verbatim to the E-039 research series implementation."""
    return build_series(dvol, closes)


async def _signals_from_connection(
    conn: Any,
    config: dict[str, Any],
    as_of: datetime,
) -> dict[str, dict[str, Any]]:
    as_of = _utc(as_of)
    signal_day = as_of.date() - timedelta(days=1)
    out: dict[str, dict[str, Any]] = {}
    for currency, instrument in config["symbols"].items():
        dataset_id = f"dvol_deribit_{currency.lower()}_1h"
        dvol_rows = await conn.fetch(
            """
            WITH ranked AS (
              SELECT (observed_at AT TIME ZONE 'UTC')::date AS day,
                     value_num, published_at,
                     row_number() OVER (
                       PARTITION BY (observed_at AT TIME ZONE 'UTC')::date
                       ORDER BY published_at DESC, observed_at DESC
                     ) AS rank
              FROM external_observations
              WHERE dataset_id = $1
                AND published_at IS NOT NULL
                AND published_at <= $2
                AND value_num IS NOT NULL
                AND quality_status IS DISTINCT FROM 'suspect'
            )
            SELECT day, value_num, published_at
            FROM ranked WHERE rank = 1 ORDER BY day
            """,
            dataset_id,
            as_of,
        )
        close_rows = await conn.fetch(
            """
            SELECT ((ts AT TIME ZONE 'UTC') - INTERVAL '8 hours')::date AS day,
                   (array_agg(close ORDER BY ts DESC))[1] AS close,
                   max(ts) AS source_ts
            FROM canonical_candles
            WHERE inst_id = $1
              AND bar = '1m'
              AND source_primary = $2
              AND ts < $3
              AND quality_status IS DISTINCT FROM 'suspect'
            GROUP BY ((ts AT TIME ZONE 'UTC') - INTERVAL '8 hours')::date
            ORDER BY day
            """,
            instrument,
            str(config.get("price_source", "binance")),
            as_of,
        )
        dvol = {row["day"].isoformat(): _finite(row["value_num"], positive=True) for row in dvol_rows}
        closes = {row["day"].isoformat(): _finite(row["close"], positive=True) for row in close_rows}
        rows = compute_signal_rows(dvol, closes)
        current = next((row for row in reversed(rows) if row["date"] <= signal_day.isoformat()), None)
        if current is None or "ivp" not in current or "z" not in current:
            raise RuntimeError(f"insufficient DB history to classify {currency} as of {signal_day}")
        if current["date"] != signal_day.isoformat():
            raise RuntimeError(
                f"stale DB signal for {currency}: latest common day {current['date']}, "
                f"required {signal_day.isoformat()}"
            )
        published = next(
            (row["published_at"] for row in reversed(dvol_rows) if row["day"] == signal_day),
            None,
        )
        signal = {key: current[key] for key in ("date", "dvol", "px", "rv", "vrp", "z", "ivp")}
        signal.update(
            {
                "currency": currency,
                "instrument": instrument,
                "as_of": _iso(as_of),
                "dvol_published_at": _iso(published) if published else None,
                "ivp_min": FROZEN_IVP_MIN,
                "z_min": FROZEN_Z_MIN,
                "rich": bool(current["ivp"] >= FROZEN_IVP_MIN and current["z"] >= FROZEN_Z_MIN),
                "source": "db_f26_asof",
            }
        )
        out[currency] = signal
    return out


async def load_signals(
    dsn: str,
    config: dict[str, Any],
    as_of: datetime,
) -> dict[str, dict[str, Any]]:
    """DB-only signal path; public market data is intentionally unavailable here."""
    conn = await asyncpg.connect(dsn, timeout=15, command_timeout=60)
    try:
        return await _signals_from_connection(conn, config, as_of)
    finally:
        await conn.close()


class DeribitPublicClient:
    """Small allow-listed client: public market data only, never orders."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 20.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url.rstrip("/") + "/",
            timeout=timeout,
            transport=transport,
            headers={"User-Agent": "quant-strategy-h014-shadow/1"},
        )

    def close(self) -> None:
        self._client.close()

    def _get(self, method: str, **params: Any) -> Any:
        if method not in PUBLIC_METHODS:
            raise ValueError(f"Deribit public method not allowed: {method}")
        for attempt in range(3):
            response = self._client.get(method, params=params)
            if response.status_code == 429 and attempt < 2:
                time.sleep(0.5 * (attempt + 1))
                continue
            response.raise_for_status()
            payload = response.json()
            if payload.get("error"):
                raise RuntimeError(f"Deribit public API error: {payload['error']}")
            return payload.get("result")
        raise RuntimeError("Deribit public API retry exhausted")

    def instruments(self, currency: str) -> list[dict[str, Any]]:
        return list(self._get("get_instruments", currency=currency, kind="option", expired="false") or [])

    def order_book(self, instrument: str) -> dict[str, Any]:
        return dict(self._get("get_order_book", instrument_name=instrument, depth=1) or {})

    def delivery_price(self, currency: str, expiry: date) -> float | None:
        result = self._get("get_delivery_prices", index_name=f"{currency.lower()}_usd", count=100)
        for row in (result or {}).get("data", []):
            if _delivery_date(row.get("date")) == expiry:
                return _finite(row["delivery_price"], positive=True)
        return None

    def day_vwap(self, instrument: str, day: date) -> dict[str, Any] | None:
        start = datetime.combine(day, dt_time.min, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        cursor = int(start.timestamp() * 1000)
        end_ms = int(end.timestamp() * 1000)
        trades: list[dict[str, Any]] = []
        while True:
            result = self._get(
                "get_last_trades_by_instrument_and_time",
                instrument_name=instrument,
                start_timestamp=cursor,
                end_timestamp=end_ms,
                count=1000,
                sorting="asc",
                include_old="true",
            ) or {}
            batch = list(result.get("trades") or [])
            trades.extend(batch)
            if not result.get("has_more") or not batch:
                break
            cursor = int(batch[-1]["timestamp"]) + 1
        usable = [
            (_finite(row["price"], positive=True), _finite(row["amount"], positive=True))
            for row in trades
            if row.get("price") is not None and row.get("amount") is not None
        ]
        if not usable:
            return None
        amount = sum(size for _, size in usable)
        return {
            "vwap_coin": sum(price * size for price, size in usable) / amount,
            "amount": amount,
            "trade_count": len(usable),
        }


def _delivery_date(value: Any) -> date | None:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value) / 1000, tz=timezone.utc).date()
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%d%b%y"):
        try:
            return datetime.strptime(text.upper(), fmt).date()
        except ValueError:
            pass
    return None


def build_intent_legs(
    currency: str,
    signal: dict[str, Any],
    instruments: list[dict[str, Any]],
    now: datetime,
) -> list[dict[str, Any]]:
    """Select today's chain with the same target-strike helper as research."""
    now = _utc(now)
    now_ms = int(now.timestamp() * 1000)
    expiries = sorted(
        {
            int(row["expiration_timestamp"])
            for row in instruments
            if int(row.get("expiration_timestamp", 0)) > now_ms + 5 * 86_400_000
        }
    )
    if not expiries:
        raise ValueError(f"no listed option expiry available for {currency}")
    target_expiry = now_ms + 30 * 86_400_000
    expiry_ms = min(expiries, key=lambda value: abs(value - target_expiry))
    chain = [row for row in instruments if int(row.get("expiration_timestamp", 0)) == expiry_ms]
    targets = target_strikes(_finite(signal["px"], positive=True), _finite(signal["dvol"], positive=True))
    legs: list[dict[str, Any]] = []
    for leg, (kind, side) in LEG_SPECS.items():
        strike_target, _ = targets[leg]
        candidates = [row for row in chain if str(row.get("option_type", "")).lower() == kind]
        if not candidates:
            raise ValueError(f"no {kind} instruments available for {currency} {leg}")
        selected = min(candidates, key=lambda row: abs(_finite(row["strike"]) - strike_target))
        legs.append(
            {
                "leg": leg,
                "currency": currency,
                "instrument": str(selected["instrument_name"]),
                "kind": kind,
                "side": side,
                "strike": _finite(selected["strike"], positive=True),
                "target_strike": strike_target,
                "expiry": datetime.fromtimestamp(expiry_ms / 1000, tz=timezone.utc).date().isoformat(),
                "expiry_timestamp": expiry_ms,
                "units": FROZEN_TRANCHE_UNITS,
            }
        )
    return legs


def validate_intent_set(
    legs: list[dict[str, Any]],
    *,
    tranche_units: float,
    open_units: float,
    unit_cap: float = FROZEN_UNIT_CAP,
) -> None:
    """Enforce R8.3 before a multi-leg intent reaches market-data filling."""
    tranche_units = _finite(tranche_units, positive=True)
    if open_units < 0 or open_units + tranche_units > unit_cap + 1e-12:
        raise ValueError(f"R8.3 unit cap exceeded: {open_units + tranche_units} > {unit_cap}")
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for leg in legs:
        _finite(leg["units"], positive=True)
        groups[(str(leg["currency"]), str(leg["expiry"]))].append(leg)
    for key, group in groups.items():
        short_puts = [leg for leg in group if leg["kind"] == "put" and leg["side"] == "sell"]
        if not short_puts:
            continue
        min_short_strike = min(_finite(leg["strike"], positive=True) for leg in short_puts)
        long_puts = [
            leg
            for leg in group
            if leg["kind"] == "put"
            and leg["side"] == "buy"
            and _finite(leg["strike"], positive=True) < min_short_strike
        ]
        short_units = sum(_finite(leg["units"], positive=True) for leg in short_puts)
        long_units = sum(_finite(leg["units"], positive=True) for leg in long_puts)
        if long_units + 1e-12 < short_units:
            raise ValueError(f"R8.3 naked short put rejected for {key[0]} expiry {key[1]}")


def _book_snapshot(result: dict[str, Any], *, fillable: bool) -> dict[str, Any]:
    def top(rows: Any) -> tuple[float | None, float | None]:
        if not rows:
            return None, None
        return _finite(rows[0][0], positive=True), _finite(rows[0][1], positive=True)

    bid, bid_size = top(result.get("bids"))
    ask, ask_size = top(result.get("asks"))
    if fillable and (bid is None or ask is None or not bid_size or not ask_size):
        raise ValueError("order book has no fillable top-of-book")
    if bid is not None and ask is not None and bid > ask:
        raise ValueError("crossed order book")
    mid = (bid + ask) / 2 if bid is not None and ask is not None else None
    spread = ask - bid if bid is not None and ask is not None else None
    return {
        "timestamp": (
            _iso(datetime.fromtimestamp(int(result["timestamp"]) / 1000, tz=timezone.utc))
            if result.get("timestamp")
            else None
        ),
        "bid": bid,
        "bid_size": bid_size,
        "ask": ask,
        "ask_size": ask_size,
        "mid": mid,
        "spread": spread,
        "spread_bps": spread / mid * 10_000 if spread is not None and mid else None,
        "mark_price": _optional_finite(result.get("mark_price"), positive=True),
        "mark_iv": _optional_finite(result.get("mark_iv"), positive=True),
        "underlying_price": _optional_finite(result.get("underlying_price"), positive=True),
    }


def _optional_finite(value: Any, *, positive: bool = False) -> float | None:
    if value is None:
        return None
    return _finite(value, positive=positive)


def validate_record(record: dict[str, Any]) -> None:
    for key in ("schema_version", "event_id", "event_type", "ts"):
        if key not in record:
            raise ValueError(f"journal record missing {key}")
    if record["event_type"] not in {"intent", "mark", "settlement", "vwap"}:
        raise ValueError(f"unsupported journal event_type {record['event_type']!r}")
    if record["event_type"] == "intent":
        for key in ("signal", "status", "legs"):
            if key not in record:
                raise ValueError(f"intent record missing {key}")


class Journal:
    """Append-only JSONL with deterministic event-id dedupe."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.records: list[dict[str, Any]] = []
        if self.path.exists():
            for line_number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), 1):
                try:
                    record = json.loads(line)
                    validate_record(record)
                except Exception as exc:
                    raise ValueError(f"invalid JSONL record at line {line_number}") from exc
                self.records.append(record)
        self._event_ids = {record["event_id"] for record in self.records}

    def has(self, event_id: str) -> bool:
        return event_id in self._event_ids

    def append(self, record: dict[str, Any]) -> bool:
        validate_record(record)
        if record["event_id"] in self._event_ids:
            return False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # ponytail: v1 is a single manual process; add a file lock only if scheduling is approved.
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self.records.append(record)
        self._event_ids.add(record["event_id"])
        return True


def _settled_positions(journal: Journal) -> set[str]:
    return {
        str(record["position_id"])
        for record in journal.records
        if record["event_type"] == "settlement"
    }


def _open_positions(journal: Journal) -> list[dict[str, Any]]:
    settled = _settled_positions(journal)
    positions: dict[str, dict[str, Any]] = {}
    for record in journal.records:
        if record["event_type"] == "intent" and record.get("status") == "filled":
            for leg in record["legs"]:
                position = dict(leg)
                position.update(
                    {
                        "intent_id": record["intent_id"],
                        "currency": record["currency"],
                        "entry_date": record["intent"]["entry_date"],
                        "signal": record["signal"],
                        "previous_mark": leg["fill"]["price_coin"],
                    }
                )
                positions[position["position_id"]] = position
        elif record["event_type"] == "mark" and record["position_id"] in positions:
            positions[record["position_id"]]["previous_mark"] = record["mark_coin"]
    return [position for key, position in positions.items() if key not in settled]


def _open_units(journal: Journal, currency: str, on_date: date) -> float:
    settled = _settled_positions(journal)
    total = 0.0
    for record in journal.records:
        if (
            record["event_type"] == "intent"
            and record.get("status") == "filled"
            and record.get("currency") == currency
            and date.fromisoformat(record["intent"]["expiry"]) > on_date
            and any(leg["position_id"] not in settled for leg in record["legs"])
        ):
            total += _finite(record["intent"]["units"], positive=True)
    return total


def _record_prior_vwaps(client: DeribitPublicClient, journal: Journal, today: date, now: datetime) -> int:
    written = 0
    for intent in list(journal.records):
        if intent["event_type"] != "intent" or intent.get("status") != "filled":
            continue
        entry_day = date.fromisoformat(intent["intent"]["entry_date"])
        if entry_day >= today:
            continue
        for leg in intent["legs"]:
            event_id = f"vwap:{leg['position_id']}"
            if journal.has(event_id):
                continue
            value = client.day_vwap(leg["instrument"], entry_day)
            record = {
                "schema_version": 1,
                "event_id": event_id,
                "event_type": "vwap",
                "ts": _iso(now),
                "event_date": today.isoformat(),
                "currency": intent["currency"],
                "position_id": leg["position_id"],
                "leg": leg["leg"],
                "side": leg["side"],
                "instrument": leg["instrument"],
                "fill_price_coin": leg["fill"]["price_coin"],
                "status": "ok" if value else "no_trades",
                "vwap_coin": value["vwap_coin"] if value else None,
                "trade_count": value["trade_count"] if value else 0,
                "amount": value["amount"] if value else 0.0,
            }
            written += int(journal.append(record))
    return written


def _mark_or_settle(
    client: DeribitPublicClient,
    journal: Journal,
    signals: dict[str, dict[str, Any]],
    now: datetime,
) -> dict[str, int]:
    counts = {"marks": 0, "settlements": 0, "pending_settlements": 0}
    today = now.date()
    for position in _open_positions(journal):
        if date.fromisoformat(position["entry_date"]) >= today:
            continue
        position_id = position["position_id"]
        expiry_at = datetime.fromtimestamp(position["expiry_timestamp"] / 1000, tz=timezone.utc)
        sign = 1.0 if position["side"] == "sell" else -1.0
        units = _finite(position["units"], positive=True)
        previous = _finite(position["previous_mark"])
        if now >= expiry_at:
            event_id = f"settlement:{position_id}"
            if journal.has(event_id):
                continue
            delivery = client.delivery_price(position["currency"], expiry_at.date())
            if delivery is None:
                counts["pending_settlements"] += 1
                continue
            payoff = settle(position["kind"], delivery, _finite(position["strike"], positive=True))
            fee = settlement_fee(payoff) * units
            record = {
                "schema_version": 1,
                "event_id": event_id,
                "event_type": "settlement",
                "ts": _iso(now),
                "event_date": today.isoformat(),
                "currency": position["currency"],
                "position_id": position_id,
                "leg": position["leg"],
                "instrument": position["instrument"],
                "delivery_price": delivery,
                "payoff_coin": payoff,
                "previous_mark_coin": previous,
                "settlement_fee_coin": fee,
                "pnl_coin": sign * (previous - payoff) * units - fee,
                "accounting": "R8.2/R8.4/R8.5 imported",
            }
            counts["settlements"] += int(journal.append(record))
            continue
        event_id = f"mark:{today.isoformat()}:{position_id}"
        if journal.has(event_id):
            continue
        snapshot = _book_snapshot(client.order_book(position["instrument"]), fillable=False)
        mark = snapshot["mid"] if snapshot["mid"] is not None else snapshot["mark_price"]
        if mark is None:
            continue
        signal = signals[position["currency"]]
        entry_iv = position["book"].get("mark_iv")
        iv_offset = entry_iv - position["signal"]["dvol"] if entry_iv is not None else 0.0
        fallback = bs_coin(
            snapshot["underlying_price"] or signal["px"],
            position["strike"],
            signal["dvol"] + iv_offset,
            max((expiry_at - now).total_seconds() / (365 * 86_400), 1e-9),
            position["kind"],
        )
        record = {
            "schema_version": 1,
            "event_id": event_id,
            "event_type": "mark",
            "ts": _iso(now),
            "event_date": today.isoformat(),
            "currency": position["currency"],
            "position_id": position_id,
            "leg": position["leg"],
            "instrument": position["instrument"],
            "source": "book_mid" if snapshot["mid"] is not None else "deribit_mark",
            "book": snapshot,
            "mark_coin": mark,
            "previous_mark_coin": previous,
            "research_fallback_mark_coin": fallback,
            "tracking_error_coin": mark - fallback,
            "pnl_coin": sign * (previous - mark) * units,
            "accounting": "R8.5 imported",
        }
        counts["marks"] += int(journal.append(record))
    return counts


def _intent_record(
    client: DeribitPublicClient,
    journal: Journal,
    signal: dict[str, Any],
    now: datetime,
) -> dict[str, Any] | None:
    currency = signal["currency"]
    intent_id = f"h014:{now.date().isoformat()}:{signal['date']}:{currency}"
    event_id = f"intent:{intent_id}"
    if journal.has(event_id):
        return None
    common = {
        "schema_version": 1,
        "event_id": event_id,
        "event_type": "intent",
        "intent_id": intent_id,
        "ts": _iso(now),
        "event_date": now.date().isoformat(),
        "currency": currency,
        "signal": signal,
        "legs": [],
    }
    if not signal["rich"]:
        return {**common, "status": "not_rich", "intent": None}
    open_units = _open_units(journal, currency, now.date())
    if open_units + FROZEN_TRANCHE_UNITS > FROZEN_UNIT_CAP + 1e-12:
        return {
            **common,
            "status": "cap_rejected",
            "intent": {"units": FROZEN_TRANCHE_UNITS, "open_units": open_units},
        }
    legs = build_intent_legs(currency, signal, client.instruments(currency), now)
    validate_intent_set(
        legs,
        tranche_units=FROZEN_TRANCHE_UNITS,
        open_units=open_units,
        unit_cap=FROZEN_UNIT_CAP,
    )
    filled: list[dict[str, Any]] = []
    fill_error = None
    for leg in legs:
        try:
            snapshot = _book_snapshot(client.order_book(leg["instrument"]), fillable=True)
        except (KeyError, TypeError, ValueError) as exc:
            fill_error = str(exc)
            filled.append({**leg, "book_error": fill_error})
            continue
        price = snapshot["bid"] if leg["side"] == "sell" else snapshot["ask"]
        fee = trade_fee(price) * leg["units"]
        filled.append(
            {
                **leg,
                "position_id": f"{intent_id}:{leg['leg']}",
                "book": snapshot,
                "fill": {
                    "model": "sell_bid_buy_ask",
                    "price_coin": price,
                    "units": leg["units"],
                },
                "fees": {"trade_fee_coin": fee, "rule": "R8.4 imported"},
            }
        )
    expiry = legs[0]["expiry"]
    intent = {
        "entry_date": now.date().isoformat(),
        "expiry": expiry,
        "units": FROZEN_TRANCHE_UNITS,
        "open_units_before": open_units,
        "unit_cap": FROZEN_UNIT_CAP,
    }
    if fill_error or any("fill" not in leg for leg in filled):
        return {**common, "status": "missed_entry", "intent": intent, "legs": filled, "error": fill_error}
    return {
        **common,
        "status": "filled",
        "intent": intent,
        "legs": filled,
        "pnl_coin": -sum(leg["fees"]["trade_fee_coin"] for leg in filled),
    }


async def run_cycle(
    config: dict[str, Any],
    dsn: str,
    *,
    now: datetime | None = None,
    client: DeribitPublicClient | None = None,
) -> dict[str, Any]:
    """Run exactly one daily shadow cycle and exit."""
    now = _utc(now or datetime.now(timezone.utc))
    as_of = datetime.combine(now.date(), dt_time(hour=8), tzinfo=timezone.utc)
    if now < as_of:
        raise RuntimeError("H-014 daily cycle must run at or after 08:00 UTC")
    signals = await load_signals(dsn, config, as_of)
    journal = Journal(config["journal_path"])
    own_client = client is None
    client = client or DeribitPublicClient(str(config["public_api_url"]))
    try:
        vwap_count = _record_prior_vwaps(client, journal, now.date(), now)
        accounting = _mark_or_settle(client, journal, signals, now)
        intents = []
        for signal in signals.values():
            record = _intent_record(client, journal, signal, now)
            if record is not None:
                journal.append(record)
                intents.append({"currency": signal["currency"], "status": record["status"]})
        return {
            "ts": _iso(now),
            "journal_path": str(journal.path),
            "intents": intents,
            "vwap_records": vwap_count,
            **accounting,
            "order_capability": False,
            "credentials_used": False,
        }
    finally:
        if own_client:
            client.close()


def _metric(values: list[float]) -> dict[str, Any]:
    return {
        "samples": len(values),
        "mean": sum(values) / len(values) if values else None,
        "mean_abs": sum(abs(value) for value in values) / len(values) if values else None,
        "max_abs": max((abs(value) for value in values), default=None),
    }


def build_bias_report(path: str | Path) -> dict[str, Any]:
    """Build the ADR-0011 exit metrics from an existing JSONL journal."""
    records = Journal(path).records
    intent_days: list[date] = []
    ignored_stale_signal_records = 0
    rich = {"filled": 0, "missed_entry": 0, "cap_rejected": 0}
    pnl_by_currency_day: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    valid_intent_events: set[str] = set()
    valid_positions: set[str] = set()
    for record in records:
        if record["event_type"] != "intent":
            continue
        event_day = date.fromisoformat(record["event_date"])
        signal_day = date.fromisoformat(record["signal"]["date"])
        if signal_day != event_day - timedelta(days=1):
            ignored_stale_signal_records += 1
            continue
        valid_intent_events.add(record["event_id"])
        intent_days.append(event_day)
        if record.get("status") in rich:
            rich[record["status"]] += 1
        if record.get("status") == "filled":
            valid_positions.update(leg["position_id"] for leg in record["legs"])

    for record in records:
        if record["event_type"] == "intent" and record["event_id"] not in valid_intent_events:
            continue
        if record["event_type"] != "intent" and record.get("position_id") not in valid_positions:
            continue
        pnl = record.get("pnl_coin")
        if pnl is not None and record.get("currency") and record.get("event_date"):
            pnl_by_currency_day[record["currency"]][record["event_date"]] += _finite(pnl)

    bias_by_leg: dict[str, list[float]] = defaultdict(list)
    bias_bps_by_leg: dict[str, list[float]] = defaultdict(list)
    for record in records:
        if (
            record["event_type"] != "vwap"
            or record.get("position_id") not in valid_positions
            or record.get("vwap_coin") is None
        ):
            continue
        vwap = _finite(record["vwap_coin"], positive=True)
        fill = _finite(record["fill_price_coin"], positive=True)
        adverse = vwap - fill if record["side"] == "sell" else fill - vwap
        bias_by_leg[record["leg"]].append(adverse)
        bias_bps_by_leg[record["leg"]].append(adverse / vwap * 10_000)

    tracking = [
        _finite(record["tracking_error_coin"])
        for record in records
        if record["event_type"] == "mark"
        and record.get("position_id") in valid_positions
        and record.get("tracking_error_coin") is not None
    ]
    curves: dict[str, list[dict[str, Any]]] = {}
    for currency, by_day in pnl_by_currency_day.items():
        cumulative = 0.0
        curve = []
        for day in sorted(by_day):
            cumulative += by_day[day]
            curve.append({"date": day, "daily_pnl_coin": by_day[day], "cumulative_pnl_coin": cumulative})
        curves[currency] = curve

    first = min(intent_days) if intent_days else None
    last = max(intent_days) if intent_days else None
    weeks = ((last - first).days + 1) / 7 if first and last else 0.0
    distinct_weeks = len({day.isocalendar()[:2] for day in intent_days})
    fillable_denominator = rich["filled"] + rich["missed_entry"]
    missed_rate = rich["missed_entry"] / fillable_denominator if fillable_denominator else None
    fill_bias = {
        leg: {"coin": _metric(values), "bps": _metric(bias_bps_by_leg[leg])}
        for leg, values in sorted(bias_by_leg.items())
    }
    metrics_complete = bool(
        set(fill_bias) == set(LEG_SPECS) and missed_rate is not None and tracking
    )
    exit_criteria = {
        "journal_weeks": weeks,
        "minimum_weeks": 8,
        "distinct_journal_weeks": distinct_weeks,
        "minimum_distinct_weeks": 8,
        "eight_week_journal_met": weeks >= 8 and distinct_weeks >= 8,
        "fill_bias_per_leg": fill_bias,
        "missed_entry_rate": missed_rate,
        "rich_opportunities_with_book_test": fillable_denominator,
        "cap_rejections_excluded_from_missed_rate": rich["cap_rejected"],
        "ignored_stale_signal_records": ignored_stale_signal_records,
        "mark_tracking_error_coin": _metric(tracking),
        "bias_metrics_complete": metrics_complete,
    }
    exit_criteria["live_adr_discussion_unlocked"] = bool(
        exit_criteria["eight_week_journal_met"] and metrics_complete
    )
    exit_criteria["live_trading_approved"] = False
    return {
        "schema_version": 1,
        "generated_at": _iso(datetime.now(timezone.utc)),
        "journal_path": str(path),
        "exit_criteria": exit_criteria,
        "shadow_equity_curve_coin": curves,
        "note": "Meeting exit criteria unlocks only a live ADR discussion; R7.2 and explicit user approval remain required.",
    }
