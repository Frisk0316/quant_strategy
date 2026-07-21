"""Frozen H-010 calibration helpers and Stage-2 checks.

The calibration is deliberately separate from the registered Stage-2 caller:
it freezes the sample-derived power input before the active probe opens a DB
connection.  It never evaluates the four-cell Stage-3 grid.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import math
from bisect import bisect_left
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import median, stdev
from typing import Any, Mapping, Sequence

from backtesting.pipeline_feasibility import FeasibilityCheck
from backtesting.pipeline_power_screen import min_detectable_sharpe

SYMBOLS = ("BTC-USDT-SWAP", "ETH-USDT-SWAP")
CALIBRATION_START = datetime(2020, 1, 1, tzinfo=timezone.utc)
CALIBRATION_END = datetime(2020, 4, 1, tzinfo=timezone.utc)
FORMAL_START = datetime(2020, 4, 1, tzinfo=timezone.utc)
FORMAL_END = datetime(2026, 6, 17, tzinfo=timezone.utc)
BREADTH = 1.5
N_OBS = 2268
N_TRIALS = 4
POWER_FLOOR = min_detectable_sharpe(breadth=BREADTH, n_obs=N_OBS, n_trials=N_TRIALS)
MIN_COMMON_DAYS = 365
DISTINCTNESS_THRESHOLD = 0.30

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
    "F-XVENUE-FUNDING-SPREAD": (
        Path("results/h021_stage3_20260715/combo_daily_returns.csv"),
        "csv",
        "L3_H1__base",
    ),
}
GATING_REFERENCES = ("F-FUNDING-XS-DISPERSION", "F-VOL-REGIME-OPT")
ADVISORY_REFERENCES = ("F-XVENUE-FUNDING-SPREAD",)


@dataclass(frozen=True)
class AnchorParams:
    lookback_min: int = 240
    z_entry: float = 2.0
    z_exit: float = 0.5
    max_hold_min: int = 60
    maker_fee_bps: float = 2.0
    maker_slippage_bps: float = 2.0
    taker_fee_bps: float = 5.0
    taker_slippage_bps: float = 2.0


PARAMS = AnchorParams()
SCHEMA_VERSION = 1


def _utc(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _float(value: Any) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("non-finite numeric input")
    return result


def _canonical_json(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def payload_sha256(payload: Mapping[str, Any]) -> str:
    body = {key: value for key, value in payload.items() if key != "payload_sha256"}
    return hashlib.sha256(_canonical_json(body)).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _reference_metadata(specs: Mapping[str, tuple[Path, str, str]]) -> dict[str, dict[str, str]]:
    return {
        family: {
            "path": str(path).replace("\\", "/"),
            "format": kind,
            "field": field,
            "sha256": file_sha256(path),
        }
        for family, (path, kind, field) in specs.items()
    }


def load_reference_series(path: Path, kind: str, field: str) -> dict[str, float]:
    if kind == "json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        values = payload.get(field)
        if not isinstance(values, Mapping):
            raise ValueError(f"{path} field {field!r} must be an object")
        return {str(key)[:10]: _float(value) for key, value in values.items()}
    if kind == "csv":
        output: dict[str, float] = {}
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if field not in (reader.fieldnames or []):
                raise ValueError(f"{path} missing column {field!r}")
            day_field = "day_utc" if "day_utc" in (reader.fieldnames or []) else "day"
            if day_field not in (reader.fieldnames or []):
                day_field = (reader.fieldnames or [""])[0]
            for row in reader:
                if row.get(day_field) and row.get(field) not in (None, ""):
                    output[str(row[day_field])[:10]] = _float(row[field])
        return output
    raise ValueError(f"unsupported reference format {kind!r}")


def abs_correlation(left: Mapping[str, float], right: Mapping[str, float]) -> tuple[float | None, int]:
    keys = sorted(set(left) & set(right))
    if len(keys) < 2:
        return None, len(keys)
    xs = [float(left[key]) for key in keys]
    ys = [float(right[key]) for key in keys]
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    dx = [value - mean_x for value in xs]
    dy = [value - mean_y for value in ys]
    denominator = math.sqrt(sum(value * value for value in dx) * sum(value * value for value in dy))
    if denominator == 0.0:
        return None, len(keys)
    return abs(sum(x * y for x, y in zip(dx, dy)) / denominator), len(keys)


def build_distinctness_check(
    candidate_daily: Mapping[str, float],
    references: Mapping[str, Mapping[str, float]],
) -> FeasibilityCheck:
    correlations: dict[str, float | None] = {}
    common_days: dict[str, int] = {}
    for family in (*GATING_REFERENCES, *ADVISORY_REFERENCES):
        correlation, count = abs_correlation(candidate_daily, references.get(family, {}))
        correlations[family] = correlation
        common_days[family] = count
    gating_defined = all(
        correlations[family] is not None and common_days[family] >= MIN_COMMON_DAYS
        for family in GATING_REFERENCES
    )
    maximum = max(
        (float(correlations[family]) for family in GATING_REFERENCES if correlations[family] is not None),
        default=1.0,
    )
    passed = gating_defined and maximum < DISTINCTNESS_THRESHOLD
    return FeasibilityCheck(
        name="distinctness",
        status="PASS" if passed else "FAIL",
        reason=(
            f"daily-return max abs correlation {maximum:.6f} < {DISTINCTNESS_THRESHOLD:.2f}"
            if gating_defined
            else "daily-return correlation unavailable or has fewer than 365 common dates"
        ),
        details={
            "candidate_kind": "fixed_anchor_daily_net_strategy_returns",
            "reference_kind": "daily_strategy_returns",
            "correlations": correlations,
            "common_days": common_days,
            "gating_references": list(GATING_REFERENCES),
            "advisory_references": list(ADVISORY_REFERENCES),
            "threshold": DISTINCTNESS_THRESHOLD,
            "undefined_fails_closed": True,
        },
    )


def _expected_funding_times(start: datetime, end: datetime) -> list[datetime]:
    cursor = start.replace(minute=0, second=0, microsecond=0)
    while cursor < start or cursor.hour % 8:
        cursor += timedelta(hours=1)
    output: list[datetime] = []
    while cursor < end:
        output.append(cursor)
        cursor += timedelta(hours=8)
    return output


def _funding_index(
    funding_rows: Sequence[Mapping[str, Any]],
    *,
    start: datetime,
    end: datetime,
) -> tuple[dict[str, tuple[list[datetime], list[float]]], dict[str, Any]]:
    by_symbol: dict[str, dict[datetime, float]] = {symbol: {} for symbol in SYMBOLS}
    wrong_sources: set[str] = set()
    for raw in funding_rows:
        row = dict(raw)
        source = str(row.get("source") or "")
        if source != "okx":
            wrong_sources.add(source or "missing")
            continue
        symbol = str(row.get("inst_id") or "")
        if symbol in by_symbol:
            ts = _utc(row.get("ts"))
            if start <= ts < end:
                by_symbol[symbol][ts] = _float(
                    row.get("realized_rate") if row.get("realized_rate") is not None else row.get("funding_rate")
                )
    expected = _expected_funding_times(start, end)
    indexes: dict[str, tuple[list[datetime], list[float]]] = {}
    details: dict[str, Any] = {"source": "okx", "wrong_sources_ignored": sorted(wrong_sources), "symbols": {}}
    complete = True
    for symbol in SYMBOLS:
        values = by_symbol[symbol]
        missing = [ts for ts in expected if ts not in values]
        complete = complete and not missing
        times = sorted(values)
        indexes[symbol] = (times, [values[ts] for ts in times])
        details["symbols"][symbol] = {
            "expected_settlements": len(expected),
            "observed_settlements": len(times),
            "missing_settlements": len(missing),
            "first_missing": missing[0].isoformat() if missing else None,
        }
    details["complete"] = complete
    return indexes, details


def _funding_cashflow(
    index: tuple[list[datetime], list[float]],
    *,
    entry: datetime,
    exit: datetime,
    side: int,
) -> tuple[float, int]:
    times, rates = index
    lo = bisect_left(times, entry)
    hi = bisect_left(times, exit)
    selected = rates[lo:hi]
    return -float(side) * sum(selected), len(selected)


def _calendar_days(start: datetime, end: datetime) -> list[str]:
    output: list[str] = []
    cursor = start.date()
    last = (end - timedelta(microseconds=1)).date()
    while cursor <= last:
        output.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return output


def simulate_fixed_anchor(
    aligned_rows: Sequence[Mapping[str, Any]],
    funding_rows: Sequence[Mapping[str, Any]],
    *,
    start: datetime = CALIBRATION_START,
    end: datetime = CALIBRATION_END,
    params: AnchorParams = PARAMS,
) -> dict[str, Any]:
    """Run the one frozen calibration anchor; this is not a Stage-3 grid."""

    start, end = _utc(start), _utc(end)
    funding, funding_details = _funding_index(funding_rows, start=start, end=end)
    rows_by_symbol: dict[str, list[dict[str, Any]]] = {symbol: [] for symbol in SYMBOLS}
    for raw in aligned_rows:
        row = dict(raw)
        symbol = str(row.get("inst_id") or "")
        if symbol in rows_by_symbol:
            rows_by_symbol[symbol].append(row)

    daily = {day: 0.0 for day in _calendar_days(start, end)}
    trades: list[dict[str, Any]] = []
    errors: list[str] = []
    discarded_terminal_positions = 0
    expected_rows = int((end - start).total_seconds() // 60)
    for symbol, rows in rows_by_symbol.items():
        rows.sort(key=lambda row: _utc(row["ts"]))
        timestamps = [_utc(row["ts"]) for row in rows]
        if len(rows) != expected_rows or not rows or timestamps[0] != start or timestamps[-1] != end - timedelta(minutes=1):
            errors.append(f"{symbol}: aligned candle count/bounds mismatch")
            continue
        if any(current - previous != timedelta(minutes=1) for previous, current in zip(timestamps, timestamps[1:])):
            errors.append(f"{symbol}: non-consecutive aligned minute")
            continue

        window: deque[float] = deque()
        rolling_sum = 0.0
        rolling_sumsq = 0.0
        position = 0
        entry_ts: datetime | None = None
        entry_price = 0.0
        held_minutes = 0
        pending: tuple[str, int | str] | None = None
        for row, ts in zip(rows, timestamps):
            okx_open = _float(row["okx_open"])
            okx_close = _float(row["okx_close"])
            binance_close = _float(row["binance_close"])
            if min(okx_open, okx_close, binance_close) <= 0.0:
                errors.append(f"{symbol}: non-positive price at {ts.isoformat()}")
                break

            if pending and pending[0] == "exit" and position:
                reason = str(pending[1])
                gross = float(position) * (okx_open / entry_price - 1.0)
                exit_cost = (
                    params.taker_fee_bps + params.taker_slippage_bps
                    if reason == "max_hold"
                    else params.maker_fee_bps + params.maker_slippage_bps
                )
                cost_bps = params.maker_fee_bps + params.maker_slippage_bps + exit_cost
                funding_pnl, settlements = _funding_cashflow(
                    funding[symbol], entry=entry_ts or ts, exit=ts, side=position
                )
                net = gross - cost_bps / 10_000.0 + funding_pnl
                daily[ts.date().isoformat()] += 0.5 * net
                trades.append(
                    {
                        "symbol": symbol,
                        "entry_ts": (entry_ts or ts).isoformat(),
                        "exit_ts": ts.isoformat(),
                        "side": position,
                        "exit_reason": reason,
                        "gross_capture": gross,
                        "gross_capture_bps": gross * 10_000.0,
                        "roundtrip_cost_bps": cost_bps,
                        "funding_cashflow": funding_pnl,
                        "funding_settlement_count": settlements,
                        "net_return": net,
                    }
                )
                position = 0
                entry_ts = None
                entry_price = 0.0
                held_minutes = 0
                pending = None
            if pending and pending[0] == "entry" and not position:
                position = int(pending[1])
                entry_ts = ts
                entry_price = okx_open
                held_minutes = 0
                pending = None

            gap = math.log(binance_close) - math.log(okx_close)
            window.append(gap)
            rolling_sum += gap
            rolling_sumsq += gap * gap
            if len(window) > params.lookback_min:
                old = window.popleft()
                rolling_sum -= old
                rolling_sumsq -= old * old
            z_score: float | None = None
            if len(window) == params.lookback_min:
                mean = rolling_sum / params.lookback_min
                variance = max(
                    0.0,
                    (rolling_sumsq - params.lookback_min * mean * mean) / (params.lookback_min - 1),
                )
                if variance > 0.0:
                    z_score = (gap - mean) / math.sqrt(variance)

            if position:
                held_minutes += 1
                if z_score is not None and abs(z_score) <= params.z_exit:
                    pending = ("exit", "mean_reversion")
                elif held_minutes >= params.max_hold_min:
                    pending = ("exit", "max_hold")
            elif z_score is not None and abs(z_score) >= params.z_entry:
                pending = ("entry", 1 if z_score > 0.0 else -1)
        if position or (pending and pending[0] == "entry"):
            discarded_terminal_positions += 1

    gross_values = [float(row["gross_capture_bps"]) for row in trades]
    cost_values = [float(row["roundtrip_cost_bps"]) for row in trades]
    daily_values = [daily[day] for day in sorted(daily)]
    provisional_sharpe: float | None = None
    if len(daily_values) >= 2 and stdev(daily_values) > 0.0:
        provisional_sharpe = sum(daily_values) / len(daily_values) / stdev(daily_values) * math.sqrt(365.0)
    input_valid = not errors and bool(trades)
    measured = input_valid and bool(funding_details["complete"]) and provisional_sharpe is not None
    return {
        "input_valid": input_valid,
        "funding_complete": bool(funding_details["complete"]),
        "measured": measured,
        "errors": errors,
        "aligned_rows": {symbol: len(rows_by_symbol[symbol]) for symbol in SYMBOLS},
        "expected_rows_per_symbol": expected_rows,
        "funding": funding_details,
        "trade_count": len(trades),
        "discarded_terminal_positions": discarded_terminal_positions,
        "median_gross_capture_bps": median(gross_values) if gross_values else None,
        "median_roundtrip_cost_bps": median(cost_values) if cost_values else None,
        "cost_gate_passed": bool(gross_values and median(gross_values) > median(cost_values)),
        "provisional_net_sharpe": provisional_sharpe,
        "daily_net_returns": daily,
        "trades": trades,
    }


def build_calibration_evidence(
    aligned_rows: Sequence[Mapping[str, Any]],
    funding_rows: Sequence[Mapping[str, Any]],
    *,
    reference_specs: Mapping[str, tuple[Path, str, str]] = REFERENCE_SPECS,
) -> dict[str, Any]:
    metrics = simulate_fixed_anchor(aligned_rows, funding_rows)
    references = _reference_metadata(reference_specs)
    reference_series = {
        family: load_reference_series(path, kind, field)
        for family, (path, kind, field) in reference_specs.items()
    }
    distinctness = build_distinctness_check(metrics["daily_net_returns"], reference_series)
    measured = bool(metrics["measured"])
    plausible = float(metrics["provisional_net_sharpe"] or 0.0) if measured else 0.0
    reasons = list(metrics["errors"])
    if not metrics["funding_complete"]:
        reasons.append("venue-matched OKX funding is incomplete; no cross-venue substitution")
    if not metrics["trade_count"]:
        reasons.append("fixed anchor produced no completed trades")
    if not metrics["cost_gate_passed"]:
        reasons.append("median gross capture does not exceed median exact round-trip cost")
    if distinctness.status != "PASS":
        reasons.append("required daily-return distinctness correlations are unavailable or fail")
    if measured and plausible < POWER_FLOOR:
        reasons.append("measured calibration Sharpe is below the frozen power floor")
    valid = measured and distinctness.status == "PASS"
    status = "PASS" if valid and metrics["cost_gate_passed"] and plausible >= POWER_FLOOR else "FAIL"
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": "h010_pre_stage2_calibration",
        "status": status,
        "valid": valid,
        "measured": measured,
        "failure_reasons": reasons,
        "hypothesis_id": "H-010",
        "family_id": "F-XVENUE-LEADLAG",
        "calibration_window": {
            "start": CALIBRATION_START.isoformat(),
            "end_exclusive": CALIBRATION_END.isoformat(),
            "excluded_from_formal_validation": True,
        },
        "formal_window": {
            "start": FORMAL_START.isoformat(),
            "end_exclusive": FORMAL_END.isoformat(),
            "daily_observations": N_OBS,
        },
        "anchor": asdict(PARAMS),
        "execution": {
            "signal_time": "close_t",
            "fill_time": "exact_aligned_open_t_plus_1",
            "maker_proxy_idealized": True,
            "signal_venue": "binance",
            "execution_venue": "okx",
        },
        "statistical_power": {
            "breadth": BREADTH,
            "n_obs": N_OBS,
            "n_trials": N_TRIALS,
            "plausible_net_sharpe": plausible,
            "min_detectable_sharpe": POWER_FLOOR,
            "plausible_net_sharpe_measured": measured,
        },
        "calibration": {key: value for key, value in metrics.items() if key != "trades"},
        "distinctness": {
            "name": distinctness.name,
            "status": distinctness.status,
            "reason": distinctness.reason,
            "details": distinctness.details,
        },
        "references": references,
        "grid_trials_evaluated": 0,
        "idealized_fill": True,
        "promotion_evidence": False,
    }
    payload["payload_sha256"] = payload_sha256(payload)
    return payload


def validate_calibration_evidence(
    payload: Mapping[str, Any],
    *,
    reference_specs: Mapping[str, tuple[Path, str, str]] = REFERENCE_SPECS,
) -> dict[str, Any]:
    result = dict(payload)
    if result.get("schema_version") != SCHEMA_VERSION or result.get("kind") != "h010_pre_stage2_calibration":
        raise ValueError("unsupported H-010 calibration evidence")
    if result.get("payload_sha256") != payload_sha256(result):
        raise ValueError("H-010 calibration evidence hash mismatch")
    expected_anchor = asdict(PARAMS)
    if result.get("anchor") != expected_anchor:
        raise ValueError("H-010 calibration anchor does not match the frozen contract")
    power = result.get("statistical_power")
    if not isinstance(power, Mapping):
        raise ValueError("H-010 calibration evidence has no statistical_power object")
    for key, expected in (("breadth", BREADTH), ("n_obs", N_OBS), ("n_trials", N_TRIALS)):
        if power.get(key) != expected:
            raise ValueError(f"H-010 calibration {key} does not match the frozen contract")
    if not math.isfinite(float(power.get("plausible_net_sharpe"))):
        raise ValueError("H-010 plausible_net_sharpe must be finite")
    expected_references = _reference_metadata(reference_specs)
    if result.get("references") != expected_references:
        raise ValueError("H-010 reference artifact hash mismatch")
    return result


def checks_from_evidence(base_data_check: FeasibilityCheck, evidence: Mapping[str, Any]) -> tuple[FeasibilityCheck, ...]:
    calibration = evidence.get("calibration") if isinstance(evidence.get("calibration"), Mapping) else {}
    funding = calibration.get("funding") if isinstance(calibration.get("funding"), Mapping) else {}
    data_passed = base_data_check.status == "PASS" and bool(calibration.get("input_valid")) and bool(
        funding.get("complete")
    )
    data_details = dict(base_data_check.details)
    data_details.update(
        {
            "okx_funding": funding,
            "calibration_input_valid": bool(calibration.get("input_valid")),
            "execution_venue_funding_required": "okx",
            "cross_venue_funding_substitution": False,
        }
    )
    data_check = FeasibilityCheck(
        name="data_availability",
        status="PASS" if data_passed else "FAIL",
        reason=(
            "source-aware candles and venue-matched OKX funding are complete"
            if data_passed
            else "H-010 data prerequisite failed: venue candles and exact OKX funding must both be complete"
        ),
        details=data_details,
    )
    distinctness_payload = evidence.get("distinctness")
    if isinstance(distinctness_payload, Mapping):
        distinctness = FeasibilityCheck(
            name="distinctness",
            status=str(distinctness_payload.get("status") or "FAIL"),
            reason=str(distinctness_payload.get("reason") or "distinctness unavailable"),
            details=dict(distinctness_payload.get("details") or {}),
        )
    else:
        distinctness = FeasibilityCheck("distinctness", "FAIL", "distinctness evidence unavailable")
    median_gross = calibration.get("median_gross_capture_bps")
    median_cost = calibration.get("median_roundtrip_cost_bps")
    cost_passed = bool(evidence.get("measured")) and bool(calibration.get("cost_gate_passed"))
    cost = FeasibilityCheck(
        name="cost_after_edge",
        status="PASS" if cost_passed else "FAIL",
        reason=(
            f"median gross capture {median_gross} bps exceeds median exact cost {median_cost} bps"
            if cost_passed
            else "cost-after-edge unavailable or failed under the frozen calibration"
        ),
        details={
            "calibration_window": evidence.get("calibration_window"),
            "trade_count": calibration.get("trade_count"),
            "median_gross_capture_bps": median_gross,
            "median_roundtrip_cost_bps": median_cost,
            "plausible_net_sharpe": (evidence.get("statistical_power") or {}).get(
                "plausible_net_sharpe"
            ),
            "plausible_net_sharpe_measured": evidence.get("measured"),
            "grid_trials_evaluated": 0,
        },
    )
    return data_check, distinctness, cost


async def fetch_calibration_inputs(conn: Any) -> tuple[list[Any], list[Any]]:
    aligned = await conn.fetch(
        """
        SELECT inst_id, ts,
               MAX(open) FILTER (WHERE source_primary = 'okx') AS okx_open,
               MAX(close) FILTER (WHERE source_primary = 'okx') AS okx_close,
               MAX(close) FILTER (WHERE source_primary = 'binance') AS binance_close
        FROM canonical_candles_by_source
        WHERE inst_id = ANY($1::text[])
          AND source_primary = ANY($2::text[])
          AND bar = '1m'
          AND quality_status != 'suspect'
          AND ts >= $3 AND ts < $4
        GROUP BY inst_id, ts
        HAVING COUNT(DISTINCT source_primary) = 2
        ORDER BY inst_id, ts
        """,
        list(SYMBOLS),
        ["binance", "okx"],
        CALIBRATION_START,
        CALIBRATION_END,
    )
    funding = await conn.fetch(
        """
        SELECT source, inst_id, ts, funding_rate, realized_rate
        FROM funding_rates
        WHERE source = 'okx'
          AND inst_id = ANY($1::text[])
          AND ts >= $2 AND ts < $3
        ORDER BY inst_id, ts
        """,
        list(SYMBOLS),
        CALIBRATION_START,
        CALIBRATION_END,
    )
    return list(aligned), list(funding)


async def calibrate_from_db(dsn: str) -> dict[str, Any]:
    import asyncpg

    conn = await asyncpg.connect(dsn)
    try:
        aligned, funding = await fetch_calibration_inputs(conn)
    finally:
        await conn.close()
    return build_calibration_evidence(aligned, funding)


def write_evidence(path: Path, payload: Mapping[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite immutable calibration evidence: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", default="postgresql://quant:changeme@localhost:5432/quant")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    payload = asyncio.run(calibrate_from_db(args.dsn))
    write_evidence(args.output, payload)
    print(
        f"{args.output}: status={payload['status']} valid={payload['valid']} "
        f"measured={payload['measured']} trials={payload['grid_trials_evaluated']}"
    )
    for reason in payload.get("failure_reasons", []):
        print(f"  - {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
