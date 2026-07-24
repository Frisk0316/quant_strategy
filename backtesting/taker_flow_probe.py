"""E-058 Stage-2-only taker-flow feasibility probe."""
from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

import numpy as np
import pandas as pd

from backtesting.pipeline_feasibility import FeasibilityCheck, FeasibilityResult
from backtesting.xvenue_leadlag_probe import abs_correlation, load_reference_series
from okx_quant.portfolio.allocation import dollar_neutral_long_short_weights

START = datetime(2024, 1, 1, tzinfo=timezone.utc)
END = datetime(2026, 6, 17, tzinfo=timezone.utc)
FORMAL_WINDOW = {"start": "2024-04-29", "end_exclusive": "2026-06-17"}
ARTIFACT_DIR = Path("e058_taker_flow_stage2_20260724")

MIN_COMMON_DAYS = 365
DISTINCTNESS_THRESHOLD = 0.30
MIN_MEMBER_DAY_COVERAGE = 0.95
EXPECTED_MINUTES_PER_DAY = 1_440
ROUNDTRIP_COST_BPS = 8.0
GATING_REFERENCES = ("F-FUNDING-XS-DISPERSION", "F-VOL-REGIME-OPT")
REFERENCE_RANGES: dict[str, dict[str, str]] = {
    "F-FUNDING-XS-DISPERSION": {
        "start": "2024-01-01",
        "end_exclusive": "2026-06-17",
    },
    "F-VOL-REGIME-OPT": {
        "start": "2022-05-12",
        "end_exclusive": "2026-02-28",
    },
}
REFERENCE_SPECS: dict[str, tuple[Path, str, str]] = {
    "F-FUNDING-XS-DISPERSION": (
        Path(
            "results/idea_batch_20260701_taxonomy_002/"
            "f_funding_xs_dispersion/family_minting_candidate.json"
        ),
        "json",
        "signal",
    ),
    "F-VOL-REGIME-OPT": (
        Path("results/h014_stage3_20260714/combo_daily_returns.csv"),
        "csv",
        "ivp_min=75.0|z_min=0.5",
    ),
}

_NUMBER_RE = r"^[+]?([0-9]+([.][0-9]*)?|[.][0-9]+)([eE][+-]?[0-9]{1,2})?$"
_DAILY_SQL = f"""
WITH parsed AS (
    SELECT
        ts,
        open,
        close,
        volume,
        CASE
            WHEN jsonb_typeof(raw_payload -> 'raw') = 'array'
             AND CASE
                     WHEN jsonb_typeof(raw_payload -> 'raw') = 'array'
                     THEN jsonb_array_length(raw_payload -> 'raw')
                     ELSE 0
                 END > 10
             AND length(COALESCE(raw_payload #>> '{{raw,9}}', '')) <= 64
             AND length(COALESCE(raw_payload #>> '{{raw,10}}', '')) <= 64
             AND raw_payload #>> '{{raw,9}}' ~ '{_NUMBER_RE}'
             AND raw_payload #>> '{{raw,10}}' ~ '{_NUMBER_RE}'
            THEN (raw_payload #>> '{{raw,9}}')::double precision
        END AS taker_buy_base,
        CASE
            WHEN jsonb_typeof(raw_payload -> 'raw') = 'array'
             AND CASE
                     WHEN jsonb_typeof(raw_payload -> 'raw') = 'array'
                     THEN jsonb_array_length(raw_payload -> 'raw')
                     ELSE 0
                 END > 10
             AND length(COALESCE(raw_payload #>> '{{raw,9}}', '')) <= 64
             AND length(COALESCE(raw_payload #>> '{{raw,10}}', '')) <= 64
             AND raw_payload #>> '{{raw,9}}' ~ '{_NUMBER_RE}'
             AND raw_payload #>> '{{raw,10}}' ~ '{_NUMBER_RE}'
            THEN (raw_payload #>> '{{raw,10}}')::double precision
        END AS taker_buy_quote
    FROM market_klines
    WHERE instrument_id = $1
      AND bar = '1m'
      AND ts >= $2
      AND ts < $3
)
SELECT
    (ts AT TIME ZONE 'UTC')::date AS day,
    (array_agg(open ORDER BY ts ASC))[1]::double precision AS open,
    (array_agg(close ORDER BY ts DESC))[1]::double precision AS close,
    SUM(volume)::double precision AS volume,
    SUM(taker_buy_base) FILTER (
        WHERE taker_buy_base >= 0.0 AND taker_buy_quote >= 0.0
    )::double precision AS taker_buy_base,
    SUM(taker_buy_quote) FILTER (
        WHERE taker_buy_base >= 0.0 AND taker_buy_quote >= 0.0
    )::double precision AS taker_buy_quote,
    COUNT(*)::bigint AS row_count,
    COUNT(*) FILTER (
        WHERE taker_buy_base >= 0.0 AND taker_buy_quote >= 0.0
    )::bigint AS valid_count
FROM parsed
GROUP BY (ts AT TIME ZONE 'UTC')::date
ORDER BY day
"""

_INSTRUMENT_SQL = """
SELECT instrument_id, inst_id
FROM market_instruments
WHERE exchange = 'binance'
  AND market_type = 'linear_perpetual'
  AND contract_type = 'perpetual'
  AND inst_id = ANY($1::text[])
ORDER BY inst_id, listing_time NULLS FIRST
"""

_FUNDING_SQL = """
SELECT
    inst_id AS symbol,
    (ts AT TIME ZONE 'UTC')::date AS day,
    SUM(COALESCE(realized_rate, funding_rate))::double precision AS funding_rate,
    COUNT(*)::bigint AS funding_count
FROM funding_rates
WHERE source = 'binance'
  AND inst_id = ANY($1::text[])
  AND ts >= $2
  AND ts < $3
GROUP BY inst_id, (ts AT TIME ZONE 'UTC')::date
ORDER BY symbol, day
"""


def _utc(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _declared_window(value: Any, label: str) -> tuple[datetime, datetime]:
    if not isinstance(value, Mapping):
        raise ValueError(f"H-022 distinctness contract defect: {label} must be a date range")
    if value.get("start") is None or value.get("end_exclusive") is None:
        raise ValueError(
            f"H-022 distinctness contract defect: {label} requires start and end_exclusive"
        )
    start, end = _utc(value["start"]), _utc(value["end_exclusive"])
    if end <= start:
        raise ValueError(f"H-022 distinctness contract defect: {label} end must follow start")
    return start, end


def parse_taker_fields(raw_payload: Any) -> tuple[float, float] | None:
    """Strictly parse Binance kline raw slots 9/10; malformed values are missing."""

    if not isinstance(raw_payload, Mapping):
        return None
    raw = raw_payload.get("raw")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)) or len(raw) <= 10:
        return None
    if isinstance(raw[9], bool) or isinstance(raw[10], bool):
        return None
    try:
        base, quote = float(raw[9]), float(raw[10])
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(base) and math.isfinite(quote) and base >= 0.0 and quote >= 0.0):
        return None
    return base, quote


def check_distinctness_feasibility(
    formal_window: Mapping[str, Any],
    reference_ranges: Mapping[str, Mapping[str, Any]] | None,
    min_common_days: int = MIN_COMMON_DAYS,
) -> dict[str, Any]:
    """Fail before DB access when the declared R6.6 ranges cannot support the gate."""

    if type(min_common_days) is not int or min_common_days <= 0:
        raise ValueError("H-022 distinctness contract defect: min_common_days must be positive")
    if not isinstance(reference_ranges, Mapping):
        raise ValueError("H-022 distinctness contract defect: declared reference_ranges are required")
    missing = [name for name in GATING_REFERENCES if name not in reference_ranges]
    if missing:
        raise ValueError(
            "H-022 distinctness contract defect: missing declared reference ranges for "
            + ", ".join(missing)
        )

    candidate_start, candidate_end = _declared_window(formal_window, "formal_window")
    details: dict[str, Any] = {
        "formal_window": {
            "start": candidate_start.date().isoformat(),
            "end_exclusive": candidate_end.date().isoformat(),
        },
        "required_minimum": min_common_days,
        "references": {},
    }
    joint_start, joint_end = candidate_start, candidate_end
    for family in GATING_REFERENCES:
        ref_start, ref_end = _declared_window(reference_ranges[family], family)
        common_start, common_end = max(candidate_start, ref_start), min(candidate_end, ref_end)
        common_days = max(0, (common_end.date() - common_start.date()).days)
        details["references"][family] = {
            "start": ref_start.date().isoformat(),
            "end_exclusive": ref_end.date().isoformat(),
            "achievable_common_days": common_days,
        }
        joint_start, joint_end = max(joint_start, ref_start), min(joint_end, ref_end)
    details["joint_achievable_common_days"] = max(
        0, (joint_end.date() - joint_start.date()).days
    )
    failures = {
        family: row["achievable_common_days"]
        for family, row in details["references"].items()
        if row["achievable_common_days"] < min_common_days
    }
    if failures:
        raise ValueError(
            "H-022 distinctness contract defect: insufficient achievable common days: "
            + ", ".join(f"{family}={days}" for family, days in failures.items())
        )
    return details


def validate_power_declaration(value: Any) -> dict[str, float | int]:
    """Validate ex-ante inputs; discard generic-caller estimates measured here."""

    if not isinstance(value, Mapping):
        raise ValueError("H-022 statistical_power must declare breadth=6 and n_trials=4")
    extras = sorted(
        set(value) - {"breadth", "n_trials", "n_obs", "plausible_net_sharpe"}
    )
    if extras:
        raise ValueError(
            "H-022 statistical_power has unexpected fields: "
            + ", ".join(extras)
        )
    breadth, n_trials = value.get("breadth"), value.get("n_trials")
    if isinstance(breadth, bool) or not isinstance(breadth, (int, float)) or float(breadth) != 6.0:
        raise ValueError("H-022 ex-ante breadth must equal 6")
    if type(n_trials) is not int or n_trials != 4:
        raise ValueError("H-022 prospective n_trials must equal 4")
    if value.get("n_obs") is not None and (
        type(value["n_obs"]) is not int or value["n_obs"] <= 0
    ):
        raise ValueError("H-022 caller n_obs estimate must be a positive integer")
    if value.get("plausible_net_sharpe") is not None:
        plausible = value["plausible_net_sharpe"]
        if isinstance(plausible, bool) or not math.isfinite(float(plausible)):
            raise ValueError("H-022 caller plausible_net_sharpe estimate must be finite")
    return {"breadth": 6.0, "n_trials": 4}


def _ordered_members(value: Any, *, top_n: int) -> list[str]:
    if isinstance(value, (str, bytes, set, frozenset)) or not isinstance(value, Sequence):
        raise ValueError("daily_universe members must preserve descending adv_usd order")
    return list(dict.fromkeys(str(symbol) for symbol in value))[:top_n]


def _membership(
    index: pd.DatetimeIndex,
    columns: pd.Index,
    daily_universe: Mapping[str, Sequence[str]],
    *,
    top_n: int,
) -> pd.DataFrame:
    eligible = pd.DataFrame(False, index=index, columns=columns)
    for ts in index:
        for symbol in _ordered_members(daily_universe.get(ts.date().isoformat(), ()), top_n=top_n):
            if symbol in eligible.columns:
                eligible.at[ts, symbol] = True
    return eligible


def _weekly_weights(
    scores: pd.DataFrame,
    daily_universe: Mapping[str, Sequence[str]],
    *,
    fraction: float,
    top_n: int,
) -> pd.DataFrame:
    eligible = _membership(scores.index, scores.columns, daily_universe, top_n=top_n)
    output = pd.DataFrame(0.0, index=scores.index, columns=scores.columns)
    current = pd.Series(0.0, index=scores.columns)
    for ts in scores.index:
        if ts.weekday() == 0:
            ranked = scores.loc[ts].where(eligible.loc[ts]).dropna()
            current = dollar_neutral_long_short_weights(ranked, q=fraction).reindex(
                scores.columns, fill_value=0.0
            )
        output.loc[ts] = current
    return output


def _pivot(frame: pd.DataFrame, column: str, index: pd.DatetimeIndex, symbols: list[str]) -> pd.DataFrame:
    if column not in frame:
        return pd.DataFrame(np.nan, index=index, columns=symbols)
    return (
        frame.pivot_table(index="day", columns="symbol", values=column, aggfunc="last")
        .reindex(index=index, columns=symbols)
        .astype(float)
    )


def build_taker_flow_proxy(
    daily_panel: pd.DataFrame,
    daily_universe: Mapping[str, Sequence[str]],
    *,
    lookback_days: int = 30,
    own_z_days: int = 90,
    fraction: float = 0.20,
) -> dict[str, Any]:
    """Build the frozen 30d/weekly/0.2 proxy and advisory H-002 factor."""

    required = {"day", "symbol", "open", "close", "volume", "taker_buy_base"}
    missing = required.difference(daily_panel.columns)
    if missing:
        raise ValueError(f"daily taker panel missing columns: {sorted(missing)}")
    if (lookback_days, own_z_days, fraction) != (30, 90, 0.20):
        raise ValueError("E-058 permits only the frozen 30d/90d/0.2 Stage-2 proxy")

    frame = daily_panel.copy()
    frame["day"] = pd.to_datetime(frame["day"]).dt.normalize()
    if "parseable" in frame:
        invalid = ~frame["parseable"].fillna(False).astype(bool)
        frame.loc[invalid, ["volume", "taker_buy_base"]] = np.nan
    index = pd.DatetimeIndex(sorted(pd.to_datetime(list(daily_universe)))).normalize()
    symbols = sorted(
        {
            symbol
            for members in daily_universe.values()
            for symbol in _ordered_members(members, top_n=30)
        }
    )
    open_price = _pivot(frame, "open", index, symbols)
    close = _pivot(frame, "close", index, symbols)
    volume = _pivot(frame, "volume", index, symbols)
    taker = _pivot(frame, "taker_buy_base", index, symbols)
    eligible = _membership(index, close.columns, daily_universe, top_n=30)

    rolling_volume = volume.where(eligible).rolling(lookback_days, min_periods=lookback_days).sum()
    rolling_taker = taker.where(eligible).rolling(lookback_days, min_periods=lookback_days).sum()
    net_flow_ratio = (2.0 * rolling_taker - rolling_volume) / rolling_volume.replace(0.0, np.nan)
    own_mean = net_flow_ratio.rolling(own_z_days, min_periods=own_z_days).mean()
    own_std = net_flow_ratio.rolling(own_z_days, min_periods=own_z_days).std()
    own_z = (net_flow_ratio - own_mean) / own_std.replace(0.0, np.nan)
    own_z = own_z.where(eligible)
    xs_z = own_z.sub(own_z.mean(axis=1), axis=0).div(
        own_z.std(axis=1).replace(0.0, np.nan), axis=0
    )

    weights = _weekly_weights(xs_z, daily_universe, fraction=fraction, top_n=30)
    positions = weights.shift(1).fillna(0.0)
    # Signal is known at t close, positions begin at t+1 open, and this
    # forward open-to-open return begins only after that executable fill.
    asset_returns = open_price.shift(-1).div(open_price).sub(1.0)
    active = positions.ne(0.0)
    return_complete = (~active | asset_returns.notna()).all(axis=1)
    gross = (positions * asset_returns).sum(axis=1).where(active.any(axis=1) & return_complete)

    if "funding_rate" in frame:
        funding_rate = _pivot(frame, "funding_rate", index, symbols)
        funding_count = _pivot(frame, "funding_count", index, symbols)
        short_active = positions.lt(0.0)
        funding_complete_by_day = (~short_active | funding_count.ge(3.0)).all(axis=1)
    else:
        funding_rate = pd.DataFrame(0.0, index=index, columns=symbols)
        funding_complete_by_day = pd.Series(True, index=index)
    short_payment = (positions.clip(upper=0.0) * funding_rate.fillna(0.0)).clip(
        lower=0.0
    ).sum(axis=1)
    weekly_execution = pd.Series(index.weekday == 0, index=index).shift(
        1, fill_value=False
    ) & active.any(axis=1)
    net = (
        gross
        - short_payment
        - weekly_execution.astype(float) * ROUNDTRIP_COST_BPS / 10_000.0
    )

    momentum = (close / close.shift(21) - 1.0) / np.log(
        close / close.shift(1)
    ).rolling(21, min_periods=2).std().replace(0.0, np.nan)
    momentum_weights = _weekly_weights(momentum, daily_universe, fraction=0.30, top_n=25)
    momentum_positions = momentum_weights.shift(1).fillna(0.0)
    momentum_active = momentum_positions.ne(0.0)
    momentum_complete = (~momentum_active | asset_returns.notna()).all(axis=1)
    momentum_returns = (momentum_positions * asset_returns).sum(axis=1).where(
        momentum_active.any(axis=1) & momentum_complete
    )

    formal_mask = (index >= pd.Timestamp(FORMAL_WINDOW["start"])) & (
        index < pd.Timestamp(FORMAL_WINDOW["end_exclusive"])
    )
    weekly_gross = (1.0 + gross.loc[formal_mask].dropna()).groupby(
        gross.loc[formal_mask].dropna().index.to_period("W-SUN")
    ).prod() - 1.0
    weekly_short_payment = short_payment.loc[formal_mask].groupby(
        short_payment.loc[formal_mask].index.to_period("W-SUN")
    ).sum()
    return {
        "net_flow_ratio": net_flow_ratio,
        "own_z": own_z,
        "xs_z": xs_z,
        "weights": weights,
        "positions": positions,
        "gross_returns": gross.loc[formal_mask],
        "net_returns": net.loc[formal_mask],
        "weekly_gross_returns": weekly_gross,
        "weekly_short_funding_payment": weekly_short_payment,
        "funding_complete": bool(funding_complete_by_day.loc[formal_mask & active.any(axis=1)].all()),
        "momentum_returns": momentum_returns.loc[formal_mask],
    }


def _native_symbol(symbol: str) -> str:
    normalized = symbol.upper()
    if normalized.endswith("-USDT-SWAP"):
        return normalized.removesuffix("-USDT-SWAP").replace("-", "") + "USDT"
    return normalized.replace("-", "")


def _year_windows(start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    windows: list[tuple[datetime, datetime]] = []
    cursor = start
    while cursor < end:
        next_year = datetime(cursor.year + 1, 1, 1, tzinfo=timezone.utc)
        boundary = min(end, next_year)
        windows.append((cursor, boundary))
        cursor = boundary
    return windows


def _load_universe(path: Path, start: datetime, end: datetime) -> dict[str, tuple[str, ...]]:
    frame = pd.read_parquet(path)
    required = {"date", "symbol", "eligible", "adv_usd"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"PIT universe missing columns: {sorted(missing)}")
    frame = frame.loc[frame["eligible"].astype(bool), list(required)].copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    frame["adv_usd"] = pd.to_numeric(frame["adv_usd"], errors="coerce")
    frame = frame.loc[
        (frame["date"] >= start.date())
        & (frame["date"] < end.date())
        & frame["adv_usd"].notna()
    ].sort_values(["date", "adv_usd", "symbol"], ascending=[True, False, True])
    frame = frame.groupby("date", sort=True).head(30)
    return {
        day.isoformat(): tuple(group["symbol"].astype(str))
        for day, group in frame.groupby("date", sort=True)
    }


async def _fetch_daily_panel(
    conn: Any,
    symbols: Sequence[str],
    start: datetime,
    end: datetime,
) -> tuple[list[dict[str, Any]], list[str]]:
    requested = sorted({_native_symbol(symbol) for symbol in symbols})
    instrument_rows = await conn.fetch(_INSTRUMENT_SQL, requested)
    by_native: dict[str, Any] = {}
    for row in instrument_rows:
        native = str(row["inst_id"])
        if native in by_native:
            raise ValueError(f"ambiguous Binance linear-perpetual instrument for {native}")
        by_native[native] = row["instrument_id"]

    instruments: dict[str, Any] = {}
    for symbol in symbols:
        instrument_id = by_native.get(_native_symbol(symbol))
        if instrument_id is not None:
            instruments[symbol] = instrument_id
    rows: list[dict[str, Any]] = []
    for symbol, instrument_id in instruments.items():
        for chunk_start, chunk_end in _year_windows(start, end):
            for raw in await conn.fetch(_DAILY_SQL, instrument_id, chunk_start, chunk_end):
                row = dict(raw)
                row["symbol"] = symbol
                row["parseable"] = (
                    int(row["row_count"]) == EXPECTED_MINUTES_PER_DAY
                    and int(row["valid_count"]) == EXPECTED_MINUTES_PER_DAY
                )
                rows.append(row)
    unresolved = sorted(set(symbols) - set(instruments))
    return rows, unresolved


async def _fetch_funding(
    conn: Any,
    symbols: Sequence[str],
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in await conn.fetch(_FUNDING_SQL, list(symbols), start, end)
    ]


def _data_check(
    rows: Sequence[Mapping[str, Any]],
    daily_universe: Mapping[str, Sequence[str]],
    unresolved: Sequence[str],
    start: datetime,
    end: datetime,
) -> FeasibilityCheck:
    by_key = {(str(row["day"])[:10], str(row["symbol"])): row for row in rows}
    expected_days = (end.date() - start.date()).days
    expected_member_days = parseable_member_days = 0
    missing_minute_rows = malformed_rows = 0
    flow_values: list[float] = []
    by_symbol: dict[str, dict[str, int]] = {}
    daily_breadth = [
        len(_ordered_members(members, top_n=30)) for members in daily_universe.values()
    ]
    for day, members in daily_universe.items():
        for symbol in _ordered_members(members, top_n=30):
            expected_member_days += 1
            stats = by_symbol.setdefault(symbol, {"expected_member_days": 0, "parseable_member_days": 0})
            stats["expected_member_days"] += 1
            row = by_key.get((day, symbol))
            if row is None:
                missing_minute_rows += EXPECTED_MINUTES_PER_DAY
                continue
            row_count, valid_count = int(row["row_count"]), int(row["valid_count"])
            missing_minute_rows += max(0, EXPECTED_MINUTES_PER_DAY - row_count)
            malformed_rows += max(0, row_count - valid_count)
            volume, taker = row.get("volume"), row.get("taker_buy_base")
            complete = (
                row_count == valid_count == EXPECTED_MINUTES_PER_DAY
                and volume is not None
                and taker is not None
                and math.isfinite(float(volume))
                and math.isfinite(float(taker))
                and float(volume) > 0.0
            )
            if complete:
                parseable_member_days += 1
                stats["parseable_member_days"] += 1
                flow_values.append((2.0 * float(taker) - float(volume)) / float(volume))
    coverage = (
        parseable_member_days / expected_member_days if expected_member_days else 0.0
    )
    universe_day_coverage = len(daily_universe) / expected_days if expected_days else 0.0
    nondegenerate = len(flow_values) >= 2 and float(np.std(flow_values)) > 0.0
    passed = (
        coverage >= MIN_MEMBER_DAY_COVERAGE
        and universe_day_coverage == 1.0
        and nondegenerate
    )
    return FeasibilityCheck(
        name="data_availability",
        status="PASS" if passed else "FAIL",
        reason=(
            f"parseable PIT member-day coverage={coverage:.6f} "
            f"{'>=' if coverage >= MIN_MEMBER_DAY_COVERAGE else '<'} "
            f"{MIN_MEMBER_DAY_COVERAGE:.2f}"
        ),
        details={
            "window": {"start": start.date().isoformat(), "end_exclusive": end.date().isoformat()},
            "source": "market_klines.raw_payload.raw[9]/[10]",
            "query_shape": "Binance instrument resolution then symbol-year UTC ts bounds",
            "top_n_by_adv_usd": 30,
            "expected_member_days": expected_member_days,
            "parseable_member_days": parseable_member_days,
            "member_day_coverage": coverage,
            "minimum_coverage": MIN_MEMBER_DAY_COVERAGE,
            "universe_days": len(daily_universe),
            "expected_universe_days": expected_days,
            "universe_day_coverage": universe_day_coverage,
            "minimum_daily_breadth": min(daily_breadth, default=0),
            "maximum_daily_breadth": max(daily_breadth, default=0),
            "malformed_taker_rows": malformed_rows,
            "missing_minute_rows": missing_minute_rows,
            "unresolved_symbols": list(unresolved),
            "flow_non_degenerate": nondegenerate,
            "symbols": by_symbol,
        },
    )


def _as_daily_dict(series: pd.Series) -> dict[str, float]:
    return {
        pd.Timestamp(day).date().isoformat(): float(value)
        for day, value in series.dropna().items()
        if math.isfinite(float(value))
    }


def _reference_series(ctx: Mapping[str, Any]) -> tuple[dict[str, Mapping[str, float]], dict[str, Any]]:
    injected = ctx.get("reference_series")
    if isinstance(injected, Mapping):
        return {name: dict(values) for name, values in injected.items()}, {"injected": True}
    references: dict[str, Mapping[str, float]] = {}
    metadata: dict[str, Any] = {}
    for family, (path, kind, field) in REFERENCE_SPECS.items():
        references[family] = load_reference_series(path, kind, field)
        metadata[family] = {
            "path": str(path).replace("\\", "/"),
            "field": field,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    return references, metadata


def _distinctness_check(
    proxy: Mapping[str, Any],
    references: Mapping[str, Mapping[str, float]],
    reference_metadata: Mapping[str, Any],
) -> FeasibilityCheck:
    candidate = _as_daily_dict(proxy["gross_returns"])
    correlations: dict[str, float | None] = {}
    common_days: dict[str, int] = {}
    for family in GATING_REFERENCES:
        correlations[family], common_days[family] = abs_correlation(
            candidate, references.get(family, {})
        )
    h002 = _as_daily_dict(proxy["momentum_returns"])
    correlations["H-002/F-XS-MOMENTUM"], common_days[
        "H-002/F-XS-MOMENTUM"
    ] = abs_correlation(candidate, h002)
    passed = all(
        correlations[family] is not None
        and common_days[family] >= MIN_COMMON_DAYS
        and float(correlations[family]) < DISTINCTNESS_THRESHOLD
        for family in GATING_REFERENCES
    )
    return FeasibilityCheck(
        name="distinctness",
        status="PASS" if passed else "FAIL",
        reason=(
            "all gating absolute correlations are below 0.30"
            if passed
            else "a gating correlation is unavailable, under-covered, or at least 0.30"
        ),
        details={
            "candidate_kind": "frozen_30d_weekly_taker_flow_daily_gross_returns",
            "abs_correlations": correlations,
            "common_days": common_days,
            "gating_references": list(GATING_REFERENCES),
            "advisory_references": ["H-002/F-XS-MOMENTUM"],
            "advisory_h002_proxy": "21d_skip0_vol_normalized_top25_adv_q0.30_equal_weight_weekly_t_plus_1",
            "advisory_h002_exact_e005_reproduction": False,
            "advisory_h002_omissions": [
                "inverse_vol_weighting",
                "book_vol_target",
                "per_name_cap",
                "market_regime_multiplier",
            ],
            "threshold": DISTINCTNESS_THRESHOLD,
            "required_common_days": MIN_COMMON_DAYS,
            "reference_artifacts": dict(reference_metadata),
            "undefined_fails_closed": True,
        },
    )


def _annualized_sharpe(series: pd.Series) -> float:
    clean = series.dropna().astype(float)
    if len(clean) < 2:
        return 0.0
    std = float(clean.std(ddof=1))
    if not math.isfinite(std) or std <= 0.0:
        return 0.0
    value = float(clean.mean()) / std * math.sqrt(365.0)
    return value if math.isfinite(value) else 0.0


def _cost_check(proxy: Mapping[str, Any], power: Mapping[str, float | int]) -> FeasibilityCheck:
    weekly_gross = proxy["weekly_gross_returns"].dropna().astype(float)
    weekly_funding = proxy["weekly_short_funding_payment"].reindex(
        weekly_gross.index, fill_value=0.0
    )
    gross_bps = float(median(weekly_gross) * 10_000.0) if len(weekly_gross) else 0.0
    funding_bps = (
        max(0.0, float(median(weekly_funding) * 10_000.0))
        if len(weekly_funding)
        else 0.0
    )
    hurdle_bps = ROUNDTRIP_COST_BPS + funding_bps
    net = proxy["net_returns"].dropna().astype(float)
    n_obs = int(len(net))
    funding_complete = bool(proxy["funding_complete"])
    measured_sharpe = _annualized_sharpe(net)
    plausible = measured_sharpe if funding_complete else 0.0
    passed = funding_complete and gross_bps > hurdle_bps and plausible > 0.0
    return FeasibilityCheck(
        name="cost_after_edge",
        status="PASS" if passed else "FAIL",
        reason=(
            f"median weekly gross={gross_bps:.4f} bps "
            f"{'>' if gross_bps > hurdle_bps else '<='} hurdle={hurdle_bps:.4f} bps"
        ),
        details={
            "variant": "lookback30_weekly_fraction0.2_own_z90_xs_z_t_plus_1",
            "weekly_episode_count": int(len(weekly_gross)),
            "median_weekly_gross_capture_bps": gross_bps,
            "roundtrip_cost_bps": ROUNDTRIP_COST_BPS,
            "median_short_leg_funding_payment_bps": funding_bps,
            "cost_hurdle_bps": hurdle_bps,
            "positive_short_funding_receipts_credited": False,
            "funding_complete": funding_complete,
            "n_obs": n_obs,
            "plausible_net_sharpe": float(plausible),
            "statistical_power_inputs": {
                "breadth": float(power["breadth"]),
                "n_obs": n_obs,
                "n_trials": int(power["n_trials"]),
                "plausible_net_sharpe": float(plausible),
            },
            "grid_trials_evaluated": 0,
        },
    )


def _unavailable_proxy_checks(
    *,
    feasibility: Mapping[str, Any],
    reference_metadata: Mapping[str, Any],
    power: Mapping[str, float | int],
) -> tuple[FeasibilityCheck, FeasibilityCheck]:
    reason = "no daily taker panel is available for the frozen E-058 proxy"
    distinctness = FeasibilityCheck(
        name="distinctness",
        status="FAIL",
        reason=reason,
        details={
            "gating_references": list(GATING_REFERENCES),
            "advisory_references": ["H-002/F-XS-MOMENTUM"],
            "reference_artifacts": dict(reference_metadata),
            "ex_ante_range_feasibility": dict(feasibility),
            "undefined_fails_closed": True,
        },
    )
    cost = FeasibilityCheck(
        name="cost_after_edge",
        status="FAIL",
        reason=reason,
        details={
            "n_obs": 0,
            "plausible_net_sharpe": 0.0,
            "statistical_power_inputs": {
                "breadth": float(power["breadth"]),
                "n_obs": 0,
                "n_trials": int(power["n_trials"]),
                "plausible_net_sharpe": 0.0,
            },
            "grid_trials_evaluated": 0,
        },
    )
    return distinctness, cost


async def probe_taker_flow(conn: Any, ctx: Mapping[str, Any]) -> FeasibilityResult:
    """Run the fixed three-check E-058 probe; the registry appends power."""

    power = validate_power_declaration(ctx.get("statistical_power"))
    feasibility = check_distinctness_feasibility(
        FORMAL_WINDOW,
        ctx.get("reference_ranges"),
    )
    start, end = _utc(ctx.get("start", START)), _utc(ctx.get("end", END))
    if start != START or end != END:
        raise ValueError("E-058 data window is frozen at [2024-01-01, 2026-06-17)")
    universe_path = Path(ctx["universe_path"])
    daily_universe = _load_universe(universe_path, start, end)
    references, reference_metadata = _reference_series(ctx)

    async with conn.transaction(readonly=True):
        await conn.execute("SET LOCAL statement_timeout = '120s'")
        symbols = sorted({symbol for members in daily_universe.values() for symbol in members})
        rows, unresolved = await _fetch_daily_panel(conn, symbols, start, end)
        funding_rows = await _fetch_funding(conn, symbols, start, end)

    funding = {
        (str(row["day"])[:10], str(row["symbol"])): row for row in funding_rows
    }
    for row in rows:
        matched = funding.get((str(row["day"])[:10], str(row["symbol"])))
        row["funding_rate"] = matched.get("funding_rate") if matched else np.nan
        row["funding_count"] = matched.get("funding_count") if matched else 0
    panel = pd.DataFrame(rows)
    data = _data_check(rows, daily_universe, unresolved, start, end)
    if panel.empty:
        distinctness, cost = _unavailable_proxy_checks(
            feasibility=feasibility,
            reference_metadata=reference_metadata,
            power=power,
        )
        return FeasibilityResult(
            batch_id=ARTIFACT_DIR.name,
            candidate_id="B-f-taker-flow",
            candidate_dir="f_taker_flow",
            hypothesis_id="H-022",
            family_id="F-TAKER-FLOW",
            checks=(data, distinctness, cost),
        )
    proxy = build_taker_flow_proxy(panel, daily_universe)
    distinctness = _distinctness_check(proxy, references, reference_metadata)
    distinctness.details["ex_ante_range_feasibility"] = feasibility
    cost = _cost_check(proxy, power)
    return FeasibilityResult(
        batch_id=ARTIFACT_DIR.name,
        candidate_id="B-f-taker-flow",
        candidate_dir="f_taker_flow",
        hypothesis_id="H-022",
        family_id="F-TAKER-FLOW",
        checks=(data, distinctness, cost),
    )
