"""Stage-2 probe for same-symbol Deribit/Binance funding divergence."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import sqrt
from typing import Any, Mapping, Sequence

from backtesting.pipeline_feasibility import FeasibilityCheck, FeasibilityResult
from backtesting.pipeline_family_minting import BORDERLINE_CORR


SYMBOL_DATASETS = {
    "BTC-USDT-SWAP": "funding_deribit_btc",
    "ETH-USDT-SWAP": "funding_deribit_eth",
}
DERIBIT_PRICE_IDS = {
    "BTC-USDT-SWAP": ("BTC-PERPETUAL", "BTC-USDT-SWAP"),
    "ETH-USDT-SWAP": ("ETH-PERPETUAL", "ETH-USDT-SWAP"),
}


@dataclass(frozen=True)
class ProbeThresholds:
    min_common_days: int = 730
    min_funding_coverage: float = 0.99
    min_alignment_coverage: float = 0.99
    min_price_coverage: float = 0.95


@dataclass(frozen=True)
class FundingProxyParams:
    lookback_events: int
    entry_bps: float


@dataclass(frozen=True)
class AlignedEvent:
    ts: datetime
    deribit_rate: float
    binance_rate: float

    @property
    def spread(self) -> float:
        return self.deribit_rate - self.binance_rate


FROZEN_GRID = tuple(
    FundingProxyParams(lookback_events=lookback, entry_bps=entry_bps)
    for lookback in (3, 9)
    for entry_bps in (1.0, 2.0)
)
BASE_COST_BPS = 4.0  # repo research defaults: fee 2 + slippage 2
STRESS_COST_BPS = 7.0  # conservative taker stress: fee 5 + slippage 2


def _utc(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _fields(row: Mapping[str, Any]) -> Mapping[str, Any]:
    value = row.get("fields")
    return value if isinstance(value, Mapping) else {}


def _expected_times(start: datetime, end: datetime) -> list[datetime]:
    count = int((end - start).total_seconds() // (8 * 60 * 60))
    return [start + timedelta(hours=8 * offset) for offset in range(count)]


def _canonical_hour(value: Any) -> datetime | None:
    """Accept source jitter up to one second around an hourly boundary."""

    parsed = _utc(value)
    rounded = (parsed + timedelta(minutes=30)).replace(minute=0, second=0, microsecond=0)
    return rounded if abs((parsed - rounded).total_seconds()) <= 1.0 else None


def align_funding_events(
    binance_rows: Sequence[Mapping[str, Any]],
    deribit_rows: Sequence[Mapping[str, Any]],
    *,
    start: datetime,
    end: datetime,
) -> tuple[dict[str, list[AlignedEvent]], dict[str, dict[str, Any]]]:
    """Align each Binance settlement with eight completed Deribit hourly rates."""

    binance: dict[tuple[str, datetime], float] = {}
    for row in binance_rows:
        symbol = str(row.get("inst_id") or "")
        rate = _float(row.get("rate"))
        observed_at = _canonical_hour(row["observed_at"])
        if symbol in SYMBOL_DATASETS and rate is not None and observed_at is not None:
            binance[(symbol, observed_at)] = rate

    by_dataset: dict[tuple[str, datetime], float] = {}
    invalid_deribit_rows = 0
    for row in deribit_rows:
        dataset = str(row.get("dataset_id") or "")
        fields = _fields(row)
        rate = _float(row.get("rate"))
        raw_observed_at = _utc(row["observed_at"])
        observed_at = _canonical_hour(raw_observed_at)
        published_at = _utc(row.get("published_at") or raw_observed_at)
        valid = (
            dataset in SYMBOL_DATASETS.values()
            and rate is not None
            and observed_at is not None
            and str(row.get("quality_status") or "") != "suspect"
            and str(row.get("unit") or fields.get("unit") or "") == "rate_1h_decimal"
            and published_at <= raw_observed_at
        )
        if valid:
            by_dataset[(dataset, observed_at)] = rate
        else:
            invalid_deribit_rows += 1

    expected = _expected_times(start, end)
    aligned: dict[str, list[AlignedEvent]] = {}
    coverage: dict[str, dict[str, Any]] = {}
    for symbol, dataset in SYMBOL_DATASETS.items():
        symbol_events: list[AlignedEvent] = []
        binance_count = 0
        for ts in expected:
            binance_rate = binance.get((symbol, ts))
            if binance_rate is None:
                continue
            binance_count += 1
            hours = [ts - timedelta(hours=offset) for offset in range(7, -1, -1)]
            hourly = [by_dataset.get((dataset, hour)) for hour in hours]
            if any(rate is None for rate in hourly):
                continue
            symbol_events.append(
                AlignedEvent(
                    ts=ts,
                    deribit_rate=sum(float(rate) for rate in hourly),
                    binance_rate=binance_rate,
                )
            )
        expected_count = len(expected)
        common_days = (
            (symbol_events[-1].ts - symbol_events[0].ts).total_seconds() / 86_400
            if len(symbol_events) >= 2
            else 0.0
        )
        aligned[symbol] = symbol_events
        coverage[symbol] = {
            "expected_binance_events": expected_count,
            "binance_events": binance_count,
            "binance_coverage": binance_count / expected_count if expected_count else 0.0,
            "aligned_events": len(symbol_events),
            "alignment_coverage": len(symbol_events) / expected_count if expected_count else 0.0,
            "common_days": common_days,
            "first_ts": symbol_events[0].ts.isoformat() if symbol_events else None,
            "last_ts": symbol_events[-1].ts.isoformat() if symbol_events else None,
            "invalid_deribit_rows_seen": invalid_deribit_rows,
        }
    return aligned, coverage


def _price_coverage(
    price_rows: Sequence[Mapping[str, Any]],
    *,
    start: datetime,
    end: datetime,
) -> dict[str, dict[str, Any]]:
    expected = int((end - start).total_seconds() // 60)
    by_id = {str(row.get("inst_id") or ""): row for row in price_rows}
    result: dict[str, dict[str, Any]] = {}
    for symbol, identifiers in DERIBIT_PRICE_IDS.items():
        best = max(
            (by_id.get(identifier, {}) for identifier in identifiers),
            key=lambda row: int(row.get("row_count") or 0),
        )
        count = int(best.get("row_count") or 0)
        result[symbol] = {
            "accepted_inst_ids": list(identifiers),
            "row_count": count,
            "expected_1m_rows": expected,
            "coverage": count / expected if expected else 0.0,
            "first_ts": str(best.get("first_ts")) if best.get("first_ts") else None,
            "last_ts": str(best.get("last_ts")) if best.get("last_ts") else None,
        }
    return result


def _abs_corr(left: Mapping[str, float], right: Mapping[str, float]) -> float | None:
    keys = sorted(set(left) & set(right))
    if len(keys) < 2:
        return None
    xs = [left[key] for key in keys]
    ys = [right[key] for key in keys]
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    dx = [value - mean_x for value in xs]
    dy = [value - mean_y for value in ys]
    denominator = sqrt(sum(value * value for value in dx) * sum(value * value for value in dy))
    return abs(sum(x * y for x, y in zip(dx, dy)) / denominator) if denominator else None


def build_distinctness_check(aligned: Mapping[str, Sequence[AlignedEvent]]) -> FeasibilityCheck:
    daily: dict[str, dict[str, dict[str, float]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(float))
    )
    for symbol, events in aligned.items():
        for event in events:
            day = event.ts.date().isoformat()
            daily[day][symbol]["spread"] += event.spread
            daily[day][symbol]["binance"] += event.binance_rate

    candidate: dict[str, float] = {}
    carry: dict[str, float] = {}
    xs: dict[str, float] = {}
    for day, symbols in daily.items():
        if set(symbols) != set(SYMBOL_DATASETS):
            continue
        mean_binance = sum(row["binance"] for row in symbols.values()) / len(symbols)
        for symbol, row in symbols.items():
            key = f"{day}:{symbol}"
            candidate[key] = row["spread"]
            carry[key] = row["binance"]
            xs[key] = row["binance"] - mean_binance

    correlations = {
        "F-FUNDING-CARRY": _abs_corr(candidate, carry),
        "F-FUNDING-XS-DISPERSION": _abs_corr(candidate, xs),
    }
    available = [value for value in correlations.values() if value is not None]
    complete = len(available) == len(correlations)
    maximum = max(available, default=1.0)
    status = "PASS" if candidate and complete and maximum < BORDERLINE_CORR else "FAIL"
    return FeasibilityCheck(
        name="distinctness",
        status=status,
        reason=(
            f"feature-proxy max abs correlation {maximum:.6f} vs {BORDERLINE_CORR:.2f} threshold"
            if complete
            else "feature-proxy correlation unavailable; insufficient or zero-variance observations"
        ),
        details={
            "proxy_only": True,
            "observations": len(candidate),
            "correlations": correlations,
            "threshold": BORDERLINE_CORR,
            "all_correlations_defined": complete,
            "human_mechanism_review_required": True,
        },
    )


def evaluate_funding_proxy(
    events: Sequence[AlignedEvent],
    params: FundingProxyParams,
    *,
    one_way_cost_bps: float,
) -> dict[str, Any]:
    """Evaluate lagged funding capture; no price, basis, or collateral PnL."""

    state = 0
    history: list[float] = []
    targets: list[int] = []
    threshold = params.entry_bps / 10_000
    for event in events:
        history.append(event.spread)
        forecast = (
            sum(history[-params.lookback_events :]) / params.lookback_events
            if len(history) >= params.lookback_events
            else None
        )
        if forecast is not None:
            sign = 1 if forecast > 0 else -1 if forecast < 0 else 0
            if state == 0 and abs(forecast) >= threshold:
                state = sign
            elif state != 0 and sign != state:
                state = sign if abs(forecast) >= threshold else 0
        targets.append(state)

    positions = [0, *targets[:-1]] if targets else []
    gross_capture = sum(0.5 * position * event.spread for position, event in zip(positions, events))
    turnover = 0.0
    episodes = 0
    previous = 0
    for position in positions:
        turnover += abs(position - previous)
        if position and position != previous:
            episodes += 1
        previous = position
    turnover += abs(previous)  # forced final exit
    cost = turnover * one_way_cost_bps / 10_000
    return {
        "lookback_events": params.lookback_events,
        "entry_bps": params.entry_bps,
        "gross_capture": gross_capture,
        "gross_capture_bps": gross_capture * 10_000,
        "turnover": turnover,
        "cost": cost,
        "cost_bps": cost * 10_000,
        "net_capture": gross_capture - cost,
        "net_capture_bps": (gross_capture - cost) * 10_000,
        "episodes": episodes,
        "active_events": sum(position != 0 for position in positions),
        "passed": gross_capture > cost,
    }


def event_gap_count(events: Sequence[AlignedEvent]) -> int:
    return sum(
        current.ts - previous.ts != timedelta(hours=8)
        for previous, current in zip(events, events[1:])
    )


def build_cost_check(aligned: Mapping[str, Sequence[AlignedEvent]]) -> FeasibilityCheck:
    event_gaps = {symbol: event_gap_count(events) for symbol, events in aligned.items()}
    scenarios: dict[str, dict[str, Any]] = {}
    common_cells: dict[str, set[str]] = {}
    for name, cost_bps in (("base", BASE_COST_BPS), ("conservative", STRESS_COST_BPS)):
        by_symbol: dict[str, list[dict[str, Any]]] = {}
        passed_by_symbol: dict[str, set[str]] = {}
        for symbol, events in aligned.items():
            rows = [evaluate_funding_proxy(events, params, one_way_cost_bps=cost_bps) for params in FROZEN_GRID]
            by_symbol[symbol] = rows
            passed_by_symbol[symbol] = {
                f"L{row['lookback_events']}_H{row['entry_bps']:g}" for row in rows if row["passed"]
            }
        common = set.intersection(*passed_by_symbol.values()) if passed_by_symbol else set()
        common_cells[name] = common
        scenarios[name] = {
            "one_way_cost_bps": cost_bps,
            "symbols": by_symbol,
            "common_passing_cells": sorted(common),
        }

    robust = common_cells.get("base", set()) & common_cells.get("conservative", set())
    status = "PASS" if robust and not any(event_gaps.values()) else "FAIL"
    return FeasibilityCheck(
        name="cost_after_edge",
        status=status,
        reason=(
            f"robust common passing cells={sorted(robust)} under base and conservative two-leg costs; "
            f"event_gaps={event_gaps}"
        ),
        details={
            "n_trials": len(FROZEN_GRID),
            "result_kind": "lagged_funding_proxy_not_full_price_pnl",
            "pair_leg_weight": 0.5,
            "gross_formula": "0.5 * lagged_position * (deribit_8h - binance_8h)",
            "scenarios": scenarios,
            "robust_common_passing_cells": sorted(robust),
            "event_gaps": event_gaps,
        },
    )


def evaluate_xvenue_funding_spread_rows(
    *,
    binance_rows: Sequence[Mapping[str, Any]],
    deribit_rows: Sequence[Mapping[str, Any]],
    price_rows: Sequence[Mapping[str, Any]],
    ctx: Mapping[str, Any],
    thresholds: ProbeThresholds = ProbeThresholds(),
) -> FeasibilityResult:
    start = _utc(ctx["start"])
    end = _utc(ctx["end"])
    aligned, funding_coverage = align_funding_events(binance_rows, deribit_rows, start=start, end=end)
    price_coverage = _price_coverage(price_rows, start=start, end=end)
    funding_ready = all(
        row["common_days"] >= thresholds.min_common_days
        and row["binance_coverage"] >= thresholds.min_funding_coverage
        and row["alignment_coverage"] >= thresholds.min_alignment_coverage
        and row["invalid_deribit_rows_seen"] == 0
        for row in funding_coverage.values()
    )
    price_ready = all(row["coverage"] >= thresholds.min_price_coverage for row in price_coverage.values())
    data_check = FeasibilityCheck(
        name="data_availability",
        status="PASS" if funding_ready and price_ready else "FAIL",
        reason=f"funding_signal_ready={funding_ready}; deribit_stage3_price_ready={price_ready}",
        details={
            "window": {"start": start.isoformat(), "end_exclusive": end.isoformat()},
            "thresholds": {
                "min_common_days": thresholds.min_common_days,
                "min_funding_coverage": thresholds.min_funding_coverage,
                "min_alignment_coverage": thresholds.min_alignment_coverage,
                "min_price_coverage": thresholds.min_price_coverage,
            },
            "funding_signal_ready": funding_ready,
            "stage3_price_ready": price_ready,
            "funding": funding_coverage,
            "deribit_1m_prices": price_coverage,
            "policy": "fail_closed_no_index_price_substitution",
        },
    )
    return FeasibilityResult(
        batch_id=str(ctx["batch_id"]),
        candidate_id=str(ctx["candidate_id"]),
        candidate_dir=str(ctx["candidate_dir"]),
        hypothesis_id=str(ctx["hypothesis_id"]),
        family_id=str(ctx["family_id"]),
        checks=(data_check, build_distinctness_check(aligned), build_cost_check(aligned)),
    )


async def probe_xvenue_funding_spread(conn: Any, ctx: Mapping[str, Any]) -> FeasibilityResult:
    start = _utc(ctx["start"])
    end = _utc(ctx["end"])
    symbols = list(SYMBOL_DATASETS)
    datasets = list(SYMBOL_DATASETS.values())
    price_ids = sorted({item for values in DERIBIT_PRICE_IDS.values() for item in values})
    try:
        binance_rows = await conn.fetch(
            """
            SELECT inst_id, ts AS observed_at,
                   COALESCE(realized_rate, funding_rate) AS rate
            FROM funding_rates
            WHERE source = 'binance'
              AND inst_id = ANY($1::text[])
              AND ts >= $2 AND ts < $3
            ORDER BY inst_id, ts
            """,
            symbols,
            start - timedelta(seconds=1),
            end + timedelta(seconds=1),
        )
        deribit_rows = await conn.fetch(
            """
            SELECT dataset_id, observed_at, published_at, value_num AS rate,
                   quality_status, fields, fields->>'unit' AS unit
            FROM external_observations
            WHERE dataset_id = ANY($1::text[])
              AND observed_at >= $2 AND observed_at < $3
            ORDER BY dataset_id, observed_at
            """,
            datasets,
            start - timedelta(hours=7),
            end,
        )
        price_rows = await conn.fetch(
            """
            SELECT inst_id, COUNT(*)::bigint AS row_count,
                   MIN(ts) AS first_ts, MAX(ts) AS last_ts
            FROM canonical_candles
            WHERE source_primary = 'deribit'
              AND inst_id = ANY($1::text[])
              AND bar = '1m'
              AND quality_status != 'suspect'
              AND ts >= $2 AND ts < $3
            GROUP BY inst_id
            """,
            price_ids,
            start,
            end,
        )
        return evaluate_xvenue_funding_spread_rows(
            binance_rows=binance_rows,
            deribit_rows=deribit_rows,
            price_rows=price_rows,
            ctx=ctx,
        )
    except Exception as exc:
        checks = tuple(
            FeasibilityCheck(
                name=name,
                status="FAIL",
                reason="xvenue funding-spread probe unavailable",
                details={"error_type": type(exc).__name__, "error": str(exc), "policy": "fail_closed"},
            )
            for name in ("data_availability", "distinctness", "cost_after_edge")
        )
        return FeasibilityResult(
            batch_id=str(ctx["batch_id"]),
            candidate_id=str(ctx["candidate_id"]),
            candidate_dir=str(ctx["candidate_dir"]),
            hypothesis_id=str(ctx["hypothesis_id"]),
            family_id=str(ctx["family_id"]),
            checks=checks,
        )
