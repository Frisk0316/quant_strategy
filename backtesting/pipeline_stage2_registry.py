"""Stage 2 probe registry for pipeline orchestration."""
from __future__ import annotations

import argparse
import asyncio
import json
import math
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from typing import Any, Awaitable, Callable, Iterable, Mapping, Sequence

from backtesting.pipeline_checkpoint1 import family_registry_from_text
from backtesting.pipeline_feasibility import FeasibilityCheck, FeasibilityResult, result_to_dict
from backtesting.pipeline_power_screen import min_detectable_sharpe
from backtesting.xvenue_funding_spread_probe import probe_xvenue_funding_spread

BATCH_ID = "idea_batch_20260701_taxonomy_002"
START = "2024-01-01"
END_EXCLUSIVE = "2026-06-17"
DSN = "postgresql://quant:changeme@localhost:5432/quant"
UNIVERSE_PATH = Path("data/universe/universe_membership.parquet")
EXPERIMENT_REGISTRY_PATH = Path("docs/EXPERIMENT_REGISTRY.md")
STATISTICAL_POWER_INPUT_FIELDS = (
    "breadth",
    "n_obs",
    "n_trials",
    "plausible_net_sharpe",
)
FUNDING_SOURCE = "binance"
OI_DATASETS = ("oi_binance_hist_btc", "oi_binance_hist_eth")
VENUES = ("binance", "okx")
XVENUE_SYMBOLS = ("BTC-USDT-SWAP", "ETH-USDT-SWAP")

# ponytail: intentionally small first gate; Claude Stage-1 can tighten it after
# seeing real breadth, but fewer than 10 good names is not a cross-section.
FUNDING_MIN_GOOD_SYMBOLS = 10
FUNDING_MIN_SYMBOL_COVERAGE = 0.80
FUNDING_MIN_REBALANCE_BREADTH = 10
FUNDING_MAX_STALE_RATIO = 0.10
# Breadth min is evaluated from START + this warmup only: universe eligibility
# needs warmup_days of history (config/universe.yaml), so the first month can
# never mathematically reach min_rebalance_breadth. User-approved window change
# 2026-07-03; manifest docs/change_manifests/2026-07-03-stage2-breadth-warmup.md.
FUNDING_BREADTH_WARMUP_DAYS = 30
XVENUE_MIN_COVERAGE = 0.95
XVENUE_MIN_ALIGNMENT = 0.95
OI_MIN_COVERAGE = 0.95
OI_MAX_STALE_RATIO = 0.05
OI_MIN_GOOD_SYMBOLS = 10
OI_5M_ROWS_PER_DAY = 288


@dataclass(frozen=True)
class CandidateSpec:
    key: str
    candidate_id: str
    candidate_dir: str
    hypothesis_id: str
    family_id: str


@dataclass(frozen=True)
class FundingThresholds:
    min_good_symbols: int = FUNDING_MIN_GOOD_SYMBOLS
    min_symbol_coverage: float = FUNDING_MIN_SYMBOL_COVERAGE
    min_rebalance_breadth: int = FUNDING_MIN_REBALANCE_BREADTH
    max_stale_ratio: float = FUNDING_MAX_STALE_RATIO
    breadth_warmup_days: int = FUNDING_BREADTH_WARMUP_DAYS


@dataclass(frozen=True)
class VenueThresholds:
    min_coverage: float = XVENUE_MIN_COVERAGE
    min_alignment: float = XVENUE_MIN_ALIGNMENT


@dataclass(frozen=True)
class OIThresholds:
    min_coverage: float = OI_MIN_COVERAGE
    max_stale_ratio: float = OI_MAX_STALE_RATIO
    min_good_symbols: int = OI_MIN_GOOD_SYMBOLS


@dataclass(frozen=True)
class StatisticalPowerThresholds:
    psr_probability: float = 0.95
    dsr_probability: float = 0.95
    periods_per_year: float = 365.0


Stage2Context = Mapping[str, Any]
Stage2Probe = Callable[[Any, Stage2Context], Awaitable[FeasibilityResult]]


CANDIDATES: dict[str, CandidateSpec] = {
    "funding": CandidateSpec(
        key="funding",
        candidate_id="B-f-funding-xs-dispersion",
        candidate_dir="f_funding_xs_dispersion",
        hypothesis_id="H-009",
        family_id="F-FUNDING-XS-DISPERSION",
    ),
    "xvenue": CandidateSpec(
        key="xvenue",
        candidate_id="B-f-xvenue-leadlag",
        candidate_dir="f_xvenue_leadlag",
        hypothesis_id="H-010",
        family_id="F-XVENUE-LEADLAG",
    ),
    "oi": CandidateSpec(
        key="oi",
        candidate_id="B-f-oi-positioning",
        candidate_dir="f_oi_positioning",
        hypothesis_id="H-012",
        family_id="F-OI-POSITIONING",
    ),
}


def _utc(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def _iso_dt(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


def _jsonable(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _expected_1m_rows(start: datetime, end: datetime) -> int:
    return int((end - start).total_seconds() // 60)


def _expected_5m_rows(start: datetime, end: datetime) -> int:
    return int((end - start).total_seconds() // (5 * 60))


def _expected_8h_rows(start: datetime, end: datetime) -> int:
    return int((end - start).total_seconds() // (8 * 60 * 60))


def _safe_ratio(numerator: float, denominator: float) -> float:
    return float(numerator) / float(denominator) if denominator else 0.0


def _quantiles(values: Sequence[int]) -> dict[str, int | float]:
    if not values:
        return {"min": 0, "median": 0, "max": 0}
    return {"min": int(min(values)), "median": float(median(values)), "max": int(max(values))}


def _spec(candidate_key: str) -> CandidateSpec:
    try:
        return CANDIDATES[candidate_key]
    except KeyError as exc:
        raise ValueError(f"unknown candidate key {candidate_key!r}") from exc


def build_stage2_result(candidate_key: str, check: FeasibilityCheck) -> FeasibilityResult:
    spec = _spec(candidate_key)
    return FeasibilityResult(
        batch_id=BATCH_ID,
        candidate_id=spec.candidate_id,
        candidate_dir=spec.candidate_dir,
        hypothesis_id=spec.hypothesis_id,
        family_id=spec.family_id,
        checks=(check,),
    )


def build_fail_closed_result(candidate_key: str, exc: BaseException) -> FeasibilityResult:
    check = FeasibilityCheck(
        name="data_availability",
        status="FAIL",
        reason="data_probe_unavailable",
        details={
            "error_type": type(exc).__name__,
            "error": str(exc),
            "policy": "fail_closed_no_proxy_no_fabrication",
        },
    )
    return build_stage2_result(candidate_key, check)


def build_statistical_power_check(
    *,
    breadth: float,
    n_obs: int,
    n_trials: int,
    plausible_net_sharpe: float,
    thresholds: StatisticalPowerThresholds = StatisticalPowerThresholds(),
    skew: float = 0.0,
    kurtosis: float = 3.0,
    override_rationale: str | None = None,
) -> FeasibilityCheck:
    if not math.isfinite(float(plausible_net_sharpe)):
        raise ValueError("plausible_net_sharpe must be finite")
    if thresholds.psr_probability < 0.95 or thresholds.dsr_probability < 0.95:
        raise ValueError("Stage 2 PSR/DSR probabilities cannot be below 0.95")
    if override_rationale is not None and not isinstance(override_rationale, str):
        raise ValueError("override_rationale must be written text")

    minimum = min_detectable_sharpe(
        breadth=breadth,
        n_obs=n_obs,
        n_trials=n_trials,
        psr_probability=thresholds.psr_probability,
        dsr_probability=thresholds.dsr_probability,
        skew=skew,
        kurtosis=kurtosis,
        periods_per_year=thresholds.periods_per_year,
    )
    plausible = float(plausible_net_sharpe)
    measured_pass = plausible >= minimum
    rationale = (override_rationale or "").strip()
    overridden = not measured_pass and bool(rationale)
    status = "PASS" if measured_pass or overridden else "FAIL"
    comparison = ">=" if measured_pass else "<"
    reason = (
        f"plausible_net_sharpe={plausible:.4f} {comparison} "
        f"min_detectable_sharpe={minimum:.4f}"
    )
    if overridden:
        reason = f"{reason}; overridden by written ex-ante rationale: {rationale}"
    return FeasibilityCheck(
        name="statistical_power",
        status=status,
        reason=reason,
        details={
            "breadth": float(breadth),
            "n_obs": n_obs,
            "effective_n_obs": float(breadth) * n_obs,
            "n_trials": n_trials,
            "n_trials_provenance": "caller_declared",
            "plausible_net_sharpe": plausible,
            "min_detectable_sharpe": minimum,
            "psr_probability": thresholds.psr_probability,
            "dsr_probability": thresholds.dsr_probability,
            "periods_per_year": thresholds.periods_per_year,
            "skew": float(skew),
            "kurtosis": float(kurtosis),
            "measured_status": "PASS" if measured_pass else "FAIL",
            "overridden": overridden,
            "override_rationale": rationale or None,
            "grid_trials_on_unoverridden_fail": 0,
        },
    )


def add_statistical_power_check(
    result: FeasibilityResult,
    **inputs: Any,
) -> FeasibilityResult:
    check = build_statistical_power_check(**inputs)
    checks = tuple(existing for existing in result.checks if existing.name != check.name)
    return replace(result, checks=(*checks, check))


def _missing_statistical_power_check() -> FeasibilityCheck:
    return FeasibilityCheck(
        name="statistical_power",
        status="FAIL",
        reason="statistical power inputs missing; breadth, n_obs, n_trials, and plausible_net_sharpe are required",
        details={"grid_trials_on_unoverridden_fail": 0},
    )


def require_statistical_power_inputs(
    value: Any,
    *,
    label: str = "statistical power inputs",
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object containing {', '.join(STATISTICAL_POWER_INPUT_FIELDS)}")
    missing = [field for field in STATISTICAL_POWER_INPUT_FIELDS if value.get(field) is None]
    if missing:
        raise ValueError(f"{label} missing required fields: {', '.join(missing)}")
    return dict(value)


def _ensure_statistical_power_check(result: FeasibilityResult) -> FeasibilityResult:
    if any(check.name == "statistical_power" for check in result.checks):
        return result
    return replace(result, checks=(*result.checks, _missing_statistical_power_check()))


def _failed_statistical_power_result(
    result: FeasibilityResult,
    reason: str,
    *,
    error_type: str | None = None,
) -> FeasibilityResult:
    checks = tuple(check for check in result.checks if check.name != "statistical_power")
    details: dict[str, Any] = {"grid_trials_on_unoverridden_fail": 0}
    if error_type:
        details["error_type"] = error_type
    return replace(
        result,
        checks=(*checks, FeasibilityCheck(
            name="statistical_power",
            status="FAIL",
            reason=reason,
            details=details,
        )),
    )


def _with_context_power_screen(result: FeasibilityResult, ctx: Stage2Context) -> FeasibilityResult:
    payload = ctx.get("statistical_power")
    if payload is None:
        return _ensure_statistical_power_check(result)
    try:
        if not isinstance(payload, Mapping):
            raise ValueError("statistical_power context must be an object")
        values = dict(payload)
        thresholds = StatisticalPowerThresholds(
            psr_probability=float(values.pop("psr_probability", 0.95)),
            dsr_probability=float(values.pop("dsr_probability", 0.95)),
            periods_per_year=float(values.pop("periods_per_year", 365.0)),
        )
        declared_n_trials = values.pop("n_trials", None)
        if declared_n_trials is not None and (
            type(declared_n_trials) is not int or declared_n_trials <= 0
        ):
            raise ValueError("ex-ante family cumulative n_trials must be a positive integer")
        registry_path = Path(ctx.get("experiment_registry_path", EXPERIMENT_REGISTRY_PATH))
        registry = family_registry_from_text(registry_path.read_text(encoding="utf-8"))
        family = registry.get(result.family_id)
        if family is None:
            raise ValueError(f"family missing from {registry_path}")
        effective_n_trials = max(family.cumulative_n_trials, int(declared_n_trials or 0))
        if effective_n_trials <= 0:
            raise ValueError("family cumulative n_trials must be pre-registered and positive")
        check = build_statistical_power_check(
            thresholds=thresholds,
            n_trials=effective_n_trials,
            **values,
        )
        check.details.update(
            {
                "n_trials_provenance": "max_registry_actual_and_ex_ante_declared_cumulative",
                "n_trials_registry_path": str(registry_path).replace("\\", "/"),
                "registry_cumulative_n_trials": family.cumulative_n_trials,
                "caller_declared_n_trials": declared_n_trials,
            }
        )
        checks = tuple(existing for existing in result.checks if existing.name != check.name)
        return replace(result, checks=(*checks, check))
    except Exception as exc:
        return _failed_statistical_power_result(
            result,
            f"statistical power screen failed closed: {exc}",
            error_type=type(exc).__name__,
        )


def build_funding_data_check(
    *,
    symbol_coverage: Sequence[Mapping[str, Any]],
    rebalance_breadth: Sequence[Mapping[str, Any]],
    thresholds: FundingThresholds,
    universe_symbol_count: int,
    expected_8h_rows: int,
) -> FeasibilityCheck:
    normalized_symbols = sorted((dict(row) for row in symbol_coverage), key=lambda row: str(row.get("inst_id", "")))
    good_symbols = [
        row
        for row in normalized_symbols
        if float(row.get("coverage_ratio") or 0.0) >= thresholds.min_symbol_coverage
        and float(row.get("stale_ratio") or 0.0) <= thresholds.max_stale_ratio
    ]
    breadth_warmup_cutoff = (
        date.fromisoformat(START) + timedelta(days=thresholds.breadth_warmup_days)
    ).isoformat()
    evaluated_breadth = [
        row for row in rebalance_breadth if str(row.get("day") or "") >= breadth_warmup_cutoff
    ]
    breadth_values = [int(row.get("ready_symbols") or 0) for row in evaluated_breadth]
    breadth_stats = _quantiles(breadth_values)
    min_breadth = int(breadth_stats["min"])
    status = "PASS" if (
        len(good_symbols) >= thresholds.min_good_symbols
        and min_breadth >= thresholds.min_rebalance_breadth
    ) else "FAIL"
    reason = (
        f"funding breadth {status}: "
        f"good_symbols={len(good_symbols)}/{thresholds.min_good_symbols}, "
        f"min_rebalance_breadth={min_breadth}/{thresholds.min_rebalance_breadth}"
    )
    return FeasibilityCheck(
        name="data_availability",
        status=status,
        reason=reason,
        details={
            "window": {
                "start": f"{START}T00:00:00+00:00",
                "end_exclusive": f"{END_EXCLUSIVE}T00:00:00+00:00",
                "expected_8h_rows_full_window": expected_8h_rows,
                "breadth_warmup_cutoff": breadth_warmup_cutoff,
                "breadth_days_evaluated": len(evaluated_breadth),
                "breadth_days_total": len(rebalance_breadth),
            },
            "source": FUNDING_SOURCE,
            "thresholds": asdict(thresholds),
            "universe_symbol_count": int(universe_symbol_count),
            "good_symbol_count": len(good_symbols),
            "rebalance_breadth_stats": breadth_stats,
            "symbol_coverage": normalized_symbols,
            "rebalance_breadth": [dict(row) for row in rebalance_breadth],
        },
    )


def build_xvenue_data_check(
    *,
    venue_coverage: Mapping[str, Mapping[str, Any]],
    thresholds: VenueThresholds,
    expected_1m_rows: int,
) -> FeasibilityCheck:
    normalized: dict[str, dict[str, Any]] = {}
    missing_venues: list[dict[str, Any]] = []
    alignment_failures: list[dict[str, Any]] = []
    for inst_id in sorted(venue_coverage):
        row = dict(venue_coverage[inst_id])
        normalized[inst_id] = row
        for venue in VENUES:
            venue_row = dict(row.get(venue) or {"row_count": 0, "coverage_ratio": 0.0})
            row[venue] = venue_row
            coverage_ratio = float(venue_row.get("coverage_ratio") or 0.0)
            if coverage_ratio < thresholds.min_coverage:
                missing_venues.append(
                    {
                        "inst_id": inst_id,
                        "venue": venue,
                        "coverage_ratio": coverage_ratio,
                    }
                )
        alignment_ratio = float(row.get("alignment_ratio") or 0.0)
        if alignment_ratio < thresholds.min_alignment:
            alignment_failures.append(
                {
                    "inst_id": inst_id,
                    "aligned_rows": int(row.get("aligned_rows") or 0),
                    "alignment_ratio": alignment_ratio,
                }
            )
    if missing_venues:
        missing_text = "; ".join(
            f"{row['venue']} {row['inst_id']} coverage={row['coverage_ratio']:.4f}"
            for row in missing_venues
        )
        status = "FAIL"
        reason = (
            "venue-scoped canonical 1m coverage failed: "
            f"{missing_text}; no Binance substitution allowed by I19"
        )
    elif alignment_failures:
        fail_text = "; ".join(
            f"{row['inst_id']} aligned={row['alignment_ratio']:.4f}"
            for row in alignment_failures
        )
        status = "FAIL"
        reason = f"venue-scoped canonical 1m alignment failed: {fail_text}"
    else:
        status = "PASS"
        reason = "venue-scoped Binance and OKX canonical 1m coverage and alignment passed"
    return FeasibilityCheck(
        name="data_availability",
        status=status,
        reason=reason,
        details={
            "window": {
                "start": f"{START}T00:00:00+00:00",
                "end_exclusive": f"{END_EXCLUSIVE}T00:00:00+00:00",
                "expected_1m_rows": expected_1m_rows,
            },
            "thresholds": asdict(thresholds),
            "invariant": "I19: no cross-venue substitution for missing venue-tagged candles",
            "venue_coverage": normalized,
            "missing_venues": missing_venues,
            "alignment_failures": alignment_failures,
        },
    )


def build_oi_data_check(
    *,
    dataset_coverage: Mapping[str, Mapping[str, Any]],
    thresholds: OIThresholds,
    expected_5m_rows: int,
    expected_days: int,
) -> FeasibilityCheck:
    normalized: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, Any]] = []
    for dataset_id in sorted(dataset_coverage):
        row = dict(dataset_coverage[dataset_id])
        daily_rows = [dict(day_row) for day_row in row.get("daily_rows") or []]
        row_count = int(row.get("row_count") or 0)
        complete_days = sum(1 for day_row in daily_rows if int(day_row.get("row_count") or 0) >= OI_5M_ROWS_PER_DAY)
        missing_ratio = _safe_ratio(max(0, expected_5m_rows - row_count), expected_5m_rows)
        stale_ratio = _safe_ratio(max(0, expected_days - complete_days), expected_days)
        coverage_ratio = _safe_ratio(row_count, expected_5m_rows)
        row.update(
            {
                "row_count": row_count,
                "expected_5m_rows": expected_5m_rows,
                "coverage_ratio": coverage_ratio,
                "missing_ratio": missing_ratio,
                "stale_ratio": stale_ratio,
                "complete_days": complete_days,
                "expected_days": expected_days,
                "daily_rows": daily_rows,
            }
        )
        normalized[dataset_id] = row
        if coverage_ratio < thresholds.min_coverage or stale_ratio > thresholds.max_stale_ratio:
            failures.append(
                {
                    "dataset_id": dataset_id,
                    "coverage_ratio": coverage_ratio,
                    "missing_ratio": missing_ratio,
                    "stale_ratio": stale_ratio,
                }
            )

    if failures:
        status = "FAIL"
        fail_text = "; ".join(
            f"{row['dataset_id']} coverage={row['coverage_ratio']:.4f} stale={row['stale_ratio']:.4f}"
            for row in failures
        )
        reason = f"Binance Vision 5m OI coverage failed: {fail_text}"
    else:
        status = "PASS"
        reason = "Binance Vision 5m BTC/ETH OI coverage passed"
    return FeasibilityCheck(
        name="data_availability",
        status=status,
        reason=reason,
        details={
            "window": {
                "start": f"{START}T00:00:00+00:00",
                "end_exclusive": f"{END_EXCLUSIVE}T00:00:00+00:00",
                "expected_5m_rows": expected_5m_rows,
                "expected_days": expected_days,
            },
            "source": "binance_vision_metrics",
            "thresholds": asdict(thresholds),
            "dataset_coverage": normalized,
            "failures": failures,
        },
    )


def _oi_dataset_id_for_symbol(inst_id: str) -> str:
    base = str(inst_id).upper().split("-")[0]
    return f"oi_binance_hist_{base.lower()}"


def build_oi_universe_data_check(
    *,
    symbols: Sequence[str],
    daily_universe: Mapping[str, set[str]],
    dataset_daily_rows: Mapping[str, Sequence[Mapping[str, Any]]],
    thresholds: OIThresholds,
) -> FeasibilityCheck:
    by_dataset_day: dict[str, dict[str, dict[str, Any]]] = {
        dataset_id: {str(row.get("day")): dict(row) for row in rows}
        for dataset_id, rows in dataset_daily_rows.items()
    }
    symbol_coverage: list[dict[str, Any]] = []
    good_symbols: list[str] = []
    failures: list[dict[str, Any]] = []
    for symbol in sorted(symbols):
        dataset_id = _oi_dataset_id_for_symbol(symbol)
        eligible_days = sorted(day for day, day_symbols in daily_universe.items() if symbol in day_symbols)
        daily_rows: list[dict[str, Any]] = []
        first_ts = None
        last_ts = None
        row_count = 0
        complete_days = 0
        for day in eligible_days:
            source_row = dict(by_dataset_day.get(dataset_id, {}).get(day) or {})
            day_count = int(source_row.get("row_count") or 0)
            row_count += day_count
            if day_count >= OI_5M_ROWS_PER_DAY:
                complete_days += 1
            if source_row.get("first_ts") is not None and first_ts is None:
                first_ts = source_row.get("first_ts")
            if source_row.get("last_ts") is not None:
                last_ts = source_row.get("last_ts")
            daily_rows.append({"day": day, "row_count": day_count})

        expected_days = len(eligible_days)
        expected_5m_rows = expected_days * OI_5M_ROWS_PER_DAY
        coverage_ratio = _safe_ratio(row_count, expected_5m_rows)
        missing_ratio = _safe_ratio(max(0, expected_5m_rows - row_count), expected_5m_rows)
        stale_ratio = _safe_ratio(max(0, expected_days - complete_days), expected_days)
        row = {
            "inst_id": symbol,
            "dataset_id": dataset_id,
            "row_count": row_count,
            "expected_5m_rows": expected_5m_rows,
            "coverage_ratio": coverage_ratio,
            "missing_ratio": missing_ratio,
            "stale_ratio": stale_ratio,
            "complete_days": complete_days,
            "expected_days": expected_days,
            "first_ts": _iso_dt(first_ts),
            "last_ts": _iso_dt(last_ts),
            "daily_rows": daily_rows,
        }
        symbol_coverage.append(row)
        if coverage_ratio >= thresholds.min_coverage and stale_ratio <= thresholds.max_stale_ratio:
            good_symbols.append(symbol)
        else:
            failures.append(
                {
                    "inst_id": symbol,
                    "dataset_id": dataset_id,
                    "coverage_ratio": coverage_ratio,
                    "missing_ratio": missing_ratio,
                    "stale_ratio": stale_ratio,
                }
            )

    status = "PASS" if len(good_symbols) >= thresholds.min_good_symbols else "FAIL"
    reason = (
        f"Binance Vision PIT OI universe coverage {status}: "
        f"good_symbols={len(good_symbols)}/{thresholds.min_good_symbols}"
    )
    return FeasibilityCheck(
        name="data_availability",
        status=status,
        reason=reason,
        details={
            "window": {
                "start": f"{START}T00:00:00+00:00",
                "end_exclusive": f"{END_EXCLUSIVE}T00:00:00+00:00",
                "rows_per_day": OI_5M_ROWS_PER_DAY,
            },
            "source": "binance_vision_metrics",
            "thresholds": asdict(thresholds),
            "universe_symbol_count": len(symbol_coverage),
            "good_symbol_count": len(good_symbols),
            "good_symbols": good_symbols,
            "symbol_coverage": symbol_coverage,
            "failures": failures,
        },
    )


def load_point_in_time_universe(
    path: Path,
    *,
    start: datetime,
    end: datetime,
) -> tuple[list[str], dict[str, set[str]], dict[str, int]]:
    import pandas as pd

    df = pd.read_parquet(path)
    required = {"date", "symbol", "eligible"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"universe membership missing columns: {sorted(missing)}")
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], utc=False).dt.date
    mask = (df["date"] >= start.date()) & (df["date"] < end.date()) & df["eligible"].astype(bool)
    eligible = df.loc[mask, ["date", "symbol"]]
    daily: dict[str, set[str]] = {}
    symbol_days: dict[str, int] = {}
    for day_value, group in eligible.groupby("date"):
        symbols = {str(symbol) for symbol in group["symbol"].dropna().unique()}
        daily[day_value.isoformat()] = symbols
        for symbol in symbols:
            symbol_days[symbol] = symbol_days.get(symbol, 0) + 1
    return sorted(symbol_days), daily, {symbol: days * 3 for symbol, days in symbol_days.items()}


async def _connect(dsn: str) -> Any:
    import asyncpg

    return await asyncpg.connect(dsn)


async def _fetch_funding_timestamps(
    conn: Any,
    *,
    symbols: Sequence[str],
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    if not symbols:
        return []
    rows = await conn.fetch(
        """
        SELECT inst_id, ts
        FROM funding_rates
        WHERE source = $1
          AND inst_id = ANY($2::text[])
          AND ts >= $3 AND ts < $4
        ORDER BY inst_id, ts
        """,
        FUNDING_SOURCE,
        list(symbols),
        start,
        end,
    )
    return [{"inst_id": str(row["inst_id"]), "ts": row["ts"]} for row in rows]


def _summarize_funding(
    rows: Iterable[Mapping[str, Any]],
    *,
    daily_universe: Mapping[str, set[str]],
    expected_by_symbol: Mapping[str, int],
    expected_full_window: int,
    thresholds: FundingThresholds,
) -> FeasibilityCheck:
    counts_by_symbol_day: dict[tuple[str, str], int] = {}
    timestamps_by_symbol: dict[str, list[datetime]] = {symbol: [] for symbol in expected_by_symbol}
    for row in rows:
        inst_id = str(row["inst_id"])
        ts = row["ts"]
        if not isinstance(ts, datetime):
            ts = datetime.fromisoformat(str(ts))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        day = ts.astimezone(timezone.utc).date().isoformat()
        if inst_id not in daily_universe.get(day, set()):
            continue
        counts_by_symbol_day[(inst_id, day)] = counts_by_symbol_day.get((inst_id, day), 0) + 1
        timestamps_by_symbol.setdefault(inst_id, []).append(ts)

    symbol_coverage: list[dict[str, Any]] = []
    for symbol in sorted(expected_by_symbol):
        expected = int(expected_by_symbol[symbol])
        timestamps = sorted(timestamps_by_symbol.get(symbol, []))
        row_count = len(timestamps)
        eligible_days = max(1, expected // 3)
        incomplete_days = sum(
            1
            for day, symbols in daily_universe.items()
            if symbol in symbols and counts_by_symbol_day.get((symbol, day), 0) < 3
        )
        missing_ratio = _safe_ratio(max(0, expected - row_count), expected)
        stale_ratio = _safe_ratio(incomplete_days, eligible_days)
        symbol_coverage.append(
            {
                "inst_id": symbol,
                "row_count": row_count,
                "expected_8h_rows": expected,
                "coverage_ratio": _safe_ratio(row_count, expected),
                "missing_ratio": missing_ratio,
                "stale_ratio": stale_ratio,
                "first_ts": _iso_dt(timestamps[0]) if timestamps else None,
                "last_ts": _iso_dt(timestamps[-1]) if timestamps else None,
            }
        )

    rebalance_breadth = []
    for day in sorted(daily_universe):
        eligible_symbols = sorted(daily_universe[day])
        ready_symbols = sum(1 for symbol in eligible_symbols if counts_by_symbol_day.get((symbol, day), 0) >= 3)
        rebalance_breadth.append(
            {
                "day": day,
                "eligible_symbols": len(eligible_symbols),
                "ready_symbols": ready_symbols,
            }
        )

    return build_funding_data_check(
        symbol_coverage=symbol_coverage,
        rebalance_breadth=rebalance_breadth,
        thresholds=thresholds,
        universe_symbol_count=len(expected_by_symbol),
        expected_8h_rows=expected_full_window,
    )


async def probe_funding(
    conn: Any,
    *,
    universe_path: Path,
    start: datetime,
    end: datetime,
    thresholds: FundingThresholds,
) -> FeasibilityResult:
    symbols, daily_universe, expected_by_symbol = load_point_in_time_universe(universe_path, start=start, end=end)
    rows = await _fetch_funding_timestamps(conn, symbols=symbols, start=start, end=end)
    check = _summarize_funding(
        rows,
        daily_universe=daily_universe,
        expected_by_symbol=expected_by_symbol,
        expected_full_window=_expected_8h_rows(start, end),
        thresholds=thresholds,
    )
    check.details["universe"] = {
        "path": str(universe_path),
        "eligible_symbols": symbols,
        "daily_rebalance_count": len(daily_universe),
    }
    return build_stage2_result("funding", check)


async def _fetch_venue_coverage(
    conn: Any,
    *,
    symbols: Sequence[str],
    start: datetime,
    end: datetime,
) -> dict[str, dict[str, Any]]:
    expected_rows = _expected_1m_rows(start, end)
    coverage: dict[str, dict[str, Any]] = {
        symbol: {
            venue: {
                "row_count": 0,
                "expected_1m_rows": expected_rows,
                "coverage_ratio": 0.0,
                "missing_rows": expected_rows,
                "first_ts": None,
                "last_ts": None,
                "daily_rows": [],
            }
            for venue in VENUES
        }
        for symbol in symbols
    }
    total_rows = await conn.fetch(
        """
        SELECT
            inst_id,
            source_primary AS venue,
            COUNT(*)::bigint AS row_count,
            MIN(ts) AS first_ts,
            MAX(ts) AS last_ts
        FROM canonical_candles
        WHERE inst_id = ANY($1::text[])
          AND source_primary = ANY($2::text[])
          AND bar = '1m'
          AND quality_status != 'suspect'
          AND ts >= $3 AND ts < $4
        GROUP BY inst_id, source_primary
        """,
        list(symbols),
        list(VENUES),
        start,
        end,
    )
    for row in total_rows:
        inst_id = str(row["inst_id"])
        venue = str(row["venue"])
        row_count = int(row["row_count"] or 0)
        coverage[inst_id][venue].update(
            {
                "row_count": row_count,
                "coverage_ratio": _safe_ratio(row_count, expected_rows),
                "missing_rows": max(0, expected_rows - row_count),
                "first_ts": _iso_dt(row["first_ts"]),
                "last_ts": _iso_dt(row["last_ts"]),
            }
        )

    daily_rows = await conn.fetch(
        """
        SELECT
            inst_id,
            source_primary AS venue,
            date_trunc('day', ts)::date AS day,
            COUNT(*)::bigint AS row_count
        FROM canonical_candles
        WHERE inst_id = ANY($1::text[])
          AND source_primary = ANY($2::text[])
          AND bar = '1m'
          AND quality_status != 'suspect'
          AND ts >= $3 AND ts < $4
        GROUP BY inst_id, source_primary, date_trunc('day', ts)::date
        ORDER BY inst_id, source_primary, day
        """,
        list(symbols),
        list(VENUES),
        start,
        end,
    )
    for row in daily_rows:
        inst_id = str(row["inst_id"])
        venue = str(row["venue"])
        coverage[inst_id][venue]["daily_rows"].append(
            {"day": row["day"].isoformat(), "row_count": int(row["row_count"] or 0)}
        )

    aligned = await conn.fetch(
        """
        SELECT b.inst_id, COUNT(*)::bigint AS aligned_rows
        FROM canonical_candles b
        JOIN canonical_candles o
          ON b.inst_id = o.inst_id
         AND b.bar = o.bar
         AND b.ts = o.ts
        WHERE b.inst_id = ANY($1::text[])
          AND b.bar = '1m'
          AND b.source_primary = 'binance'
          AND o.source_primary = 'okx'
          AND b.quality_status != 'suspect'
          AND o.quality_status != 'suspect'
          AND b.ts >= $2 AND b.ts < $3
        GROUP BY b.inst_id
        """,
        list(symbols),
        start,
        end,
    )
    aligned_by_symbol = {str(row["inst_id"]): int(row["aligned_rows"] or 0) for row in aligned}
    for symbol in symbols:
        aligned_rows = aligned_by_symbol.get(symbol, 0)
        coverage[symbol]["aligned_rows"] = aligned_rows
        coverage[symbol]["alignment_ratio"] = _safe_ratio(aligned_rows, expected_rows)
    return coverage


async def _fetch_oi_coverage(
    conn: Any,
    *,
    datasets: Sequence[str],
    start: datetime,
    end: datetime,
) -> dict[str, dict[str, Any]]:
    expected_rows = _expected_5m_rows(start, end)
    coverage: dict[str, dict[str, Any]] = {
        dataset_id: {
            "row_count": 0,
            "expected_5m_rows": expected_rows,
            "coverage_ratio": 0.0,
            "missing_ratio": 1.0,
            "first_ts": None,
            "last_ts": None,
            "daily_rows": [],
        }
        for dataset_id in datasets
    }
    total_rows = await conn.fetch(
        """
        SELECT
            dataset_id,
            COUNT(*)::bigint AS row_count,
            MIN(observed_at) AS first_ts,
            MAX(observed_at) AS last_ts
        FROM external_observations
        WHERE dataset_id = ANY($1::text[])
          AND observed_at >= $2 AND observed_at < $3
          AND value_num IS NOT NULL
          AND quality_status != 'suspect'
        GROUP BY dataset_id
        """,
        list(datasets),
        start,
        end,
    )
    for row in total_rows:
        dataset_id = str(row["dataset_id"])
        row_count = int(row["row_count"] or 0)
        coverage[dataset_id].update(
            {
                "row_count": row_count,
                "coverage_ratio": _safe_ratio(row_count, expected_rows),
                "missing_ratio": _safe_ratio(max(0, expected_rows - row_count), expected_rows),
                "first_ts": _iso_dt(row["first_ts"]),
                "last_ts": _iso_dt(row["last_ts"]),
            }
        )

    daily_rows = await conn.fetch(
        """
        SELECT
            dataset_id,
            date_trunc('day', observed_at)::date AS day,
            COUNT(*)::bigint AS row_count
        FROM external_observations
        WHERE dataset_id = ANY($1::text[])
          AND observed_at >= $2 AND observed_at < $3
          AND value_num IS NOT NULL
          AND quality_status != 'suspect'
        GROUP BY dataset_id, date_trunc('day', observed_at)::date
        ORDER BY dataset_id, day
        """,
        list(datasets),
        start,
        end,
    )
    for row in daily_rows:
        dataset_id = str(row["dataset_id"])
        coverage[dataset_id]["daily_rows"].append(
            {"day": row["day"].isoformat(), "row_count": int(row["row_count"] or 0)}
        )
    return coverage


async def _fetch_oi_daily_rows(
    conn: Any,
    *,
    datasets: Sequence[str],
    start: datetime,
    end: datetime,
) -> dict[str, list[dict[str, Any]]]:
    coverage: dict[str, list[dict[str, Any]]] = {dataset_id: [] for dataset_id in datasets}
    rows = await conn.fetch(
        """
        SELECT
            dataset_id,
            date_trunc('day', observed_at)::date AS day,
            COUNT(*)::bigint AS row_count,
            MIN(observed_at) AS first_ts,
            MAX(observed_at) AS last_ts
        FROM external_observations
        WHERE dataset_id = ANY($1::text[])
          AND observed_at >= $2 AND observed_at < $3
          AND value_num IS NOT NULL
          AND quality_status != 'suspect'
        GROUP BY dataset_id, date_trunc('day', observed_at)::date
        ORDER BY dataset_id, day
        """,
        list(datasets),
        start,
        end,
    )
    for row in rows:
        dataset_id = str(row["dataset_id"])
        coverage.setdefault(dataset_id, []).append(
            {
                "day": row["day"].isoformat(),
                "row_count": int(row["row_count"] or 0),
                "first_ts": _iso_dt(row["first_ts"]),
                "last_ts": _iso_dt(row["last_ts"]),
            }
        )
    return coverage


async def probe_xvenue(
    conn: Any,
    *,
    start: datetime,
    end: datetime,
    thresholds: VenueThresholds,
) -> FeasibilityResult:
    coverage = await _fetch_venue_coverage(conn, symbols=XVENUE_SYMBOLS, start=start, end=end)
    check = build_xvenue_data_check(
        venue_coverage=coverage,
        thresholds=thresholds,
        expected_1m_rows=_expected_1m_rows(start, end),
    )
    return build_stage2_result("xvenue", check)


async def probe_oi(
    conn: Any,
    *,
    start: datetime,
    end: datetime,
    thresholds: OIThresholds,
) -> FeasibilityResult:
    coverage = await _fetch_oi_coverage(conn, datasets=OI_DATASETS, start=start, end=end)
    check = build_oi_data_check(
        dataset_coverage=coverage,
        thresholds=thresholds,
        expected_5m_rows=_expected_5m_rows(start, end),
        expected_days=(end.date() - start.date()).days,
    )
    return build_stage2_result("oi", check)


async def probe_oi_universe(
    conn: Any,
    *,
    universe_path: Path,
    start: datetime,
    end: datetime,
    thresholds: OIThresholds,
) -> FeasibilityResult:
    symbols, daily_universe, _expected_by_symbol = load_point_in_time_universe(
        universe_path,
        start=start,
        end=end,
    )
    datasets = [_oi_dataset_id_for_symbol(symbol) for symbol in symbols]
    daily_rows = await _fetch_oi_daily_rows(conn, datasets=datasets, start=start, end=end)
    check = build_oi_universe_data_check(
        symbols=symbols,
        daily_universe=daily_universe,
        dataset_daily_rows=daily_rows,
        thresholds=thresholds,
    )
    check.details["universe"] = {
        "path": str(universe_path),
        "eligible_symbols": symbols,
        "daily_rebalance_count": len(daily_universe),
    }
    return build_stage2_result("oi", check)


async def _run_funding_probe(conn: Any, ctx: Stage2Context) -> FeasibilityResult:
    return _with_context_power_screen(
        await probe_funding(
            conn,
            universe_path=Path(ctx["universe_path"]),
            start=ctx["start"],
            end=ctx["end"],
            thresholds=FundingThresholds(),
        ),
        ctx,
    )


async def _run_xvenue_probe(conn: Any, ctx: Stage2Context) -> FeasibilityResult:
    return _with_context_power_screen(
        await probe_xvenue(conn, start=ctx["start"], end=ctx["end"], thresholds=VenueThresholds()),
        ctx,
    )


async def _run_oi_probe(conn: Any, ctx: Stage2Context) -> FeasibilityResult:
    return _with_context_power_screen(
        await probe_oi_universe(
            conn,
            universe_path=Path(ctx["universe_path"]),
            start=ctx["start"],
            end=ctx["end"],
            thresholds=OIThresholds(),
        ),
        ctx,
    )


async def _run_xvenue_funding_spread_probe(conn: Any, ctx: Stage2Context) -> FeasibilityResult:
    return _with_context_power_screen(await probe_xvenue_funding_spread(conn, ctx), ctx)


STAGE2_PROBES: dict[str, Stage2Probe] = {
    "F-FUNDING-XS-DISPERSION": _run_funding_probe,
    "F-OI-POSITIONING": _run_oi_probe,
    "F-XVENUE-LEADLAG": _run_xvenue_probe,
    "F-XVENUE-FUNDING-SPREAD": _run_xvenue_funding_spread_probe,
}


def _write_result(output_root: Path, result: FeasibilityResult) -> Path:
    result = _ensure_statistical_power_check(result)
    path = output_root / result.batch_id / result.candidate_dir / "stage2_feasibility.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _jsonable(result_to_dict(result))
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


async def run_data_probe(
    *,
    dsn: str,
    output_root: Path,
    universe_path: Path,
    candidates: Sequence[str],
    statistical_power: Mapping[str, Any],
    experiment_registry_path: Path = EXPERIMENT_REGISTRY_PATH,
) -> list[tuple[FeasibilityResult, Path]]:
    statistical_power = require_statistical_power_inputs(statistical_power)
    start = _utc(START)
    end = _utc(END_EXCLUSIVE)
    try:
        conn = await _connect(dsn)
    except Exception as exc:
        failed = [build_fail_closed_result(candidate_key, exc) for candidate_key in candidates]
        failed = [
            _with_context_power_screen(
                result,
                {
                    "statistical_power": statistical_power,
                    "experiment_registry_path": experiment_registry_path,
                },
            )
            for result in failed
        ]
        return [(result, _write_result(output_root, result)) for result in failed]

    results: list[tuple[FeasibilityResult, Path]] = []
    try:
        for candidate_key in candidates:
            try:
                if candidate_key == "funding":
                    result = await probe_funding(
                        conn,
                        universe_path=universe_path,
                        start=start,
                        end=end,
                        thresholds=FundingThresholds(),
                    )
                elif candidate_key == "oi":
                    result = await probe_oi_universe(
                        conn,
                        universe_path=universe_path,
                        start=start,
                        end=end,
                        thresholds=OIThresholds(),
                    )
                elif candidate_key == "xvenue":
                    result = await probe_xvenue(conn, start=start, end=end, thresholds=VenueThresholds())
                else:
                    raise ValueError(f"unknown candidate key {candidate_key!r}")
            except Exception as exc:
                result = build_fail_closed_result(candidate_key, exc)
            result = _with_context_power_screen(
                result,
                {
                    "statistical_power": statistical_power,
                    "experiment_registry_path": experiment_registry_path,
                },
            )
            results.append((result, _write_result(output_root, result)))
    finally:
        await conn.close()
    return results


def _candidate_list(value: str) -> list[str]:
    if value == "all":
        return ["funding", "xvenue"]
    return [value]


def _print_summary(result: FeasibilityResult, path: Path) -> None:
    payload = result_to_dict(result)
    check = result.checks[0]
    print(f"{path}: data_availability={check.status}; stage2_status={payload['stage2_status']}; {check.reason}")
    details = check.details
    if result.family_id == "F-FUNDING-XS-DISPERSION" and details:
        stats = details.get("rebalance_breadth_stats", {})
        print(
            "  funding breadth: "
            f"universe={details.get('universe_symbol_count')}, "
            f"good_symbols={details.get('good_symbol_count')}, "
            f"min_daily_ready={stats.get('min')}, median_daily_ready={stats.get('median')}"
        )
    if result.family_id == "F-XVENUE-LEADLAG" and details:
        for inst_id, row in (details.get("venue_coverage") or {}).items():
            venue_bits = []
            for venue in VENUES:
                venue_row = row.get(venue) or {}
                venue_bits.append(
                    f"{venue} rows={venue_row.get('row_count')} coverage={venue_row.get('coverage_ratio')}"
                )
            venue_bits.append(f"aligned_rows={row.get('aligned_rows')} alignment={row.get('alignment_ratio')}")
            print(f"  {inst_id}: " + "; ".join(venue_bits))
    if result.family_id == "F-OI-POSITIONING" and details:
        if details.get("symbol_coverage"):
            print(
                "  OI universe: "
                f"good_symbols={details.get('good_symbol_count')}/"
                f"{(details.get('thresholds') or {}).get('min_good_symbols')}"
            )
            for row in details.get("symbol_coverage") or []:
                print(
                    f"  {row.get('inst_id')}: dataset={row.get('dataset_id')} rows={row.get('row_count')} "
                    f"coverage={row.get('coverage_ratio')} "
                    f"missing={row.get('missing_ratio')} stale={row.get('stale_ratio')}"
                )
            return
        for dataset_id, row in (details.get("dataset_coverage") or {}).items():
            print(
                f"  {dataset_id}: rows={row.get('row_count')} "
                f"coverage={row.get('coverage_ratio')} "
                f"missing={row.get('missing_ratio')} stale={row.get('stale_ratio')}"
            )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", default=DSN)
    parser.add_argument("--output-root", type=Path, default=Path("results"))
    parser.add_argument("--universe-path", type=Path, default=UNIVERSE_PATH)
    parser.add_argument("--candidate", choices=CANDIDATES, required=True)
    parser.add_argument("--breadth", type=float, required=True)
    parser.add_argument("--n-obs", type=int, required=True)
    parser.add_argument("--n-trials", type=int, required=True)
    parser.add_argument("--plausible-net-sharpe", type=float, required=True)
    parser.add_argument("--power-override-rationale")
    parser.add_argument("--experiment-registry", type=Path, default=EXPERIMENT_REGISTRY_PATH)
    args = parser.parse_args(argv)

    statistical_power = {
        "breadth": args.breadth,
        "n_obs": args.n_obs,
        "n_trials": args.n_trials,
        "plausible_net_sharpe": args.plausible_net_sharpe,
        "override_rationale": args.power_override_rationale,
    }

    outputs = asyncio.run(
        run_data_probe(
            dsn=args.dsn,
            output_root=args.output_root,
            universe_path=args.universe_path,
            candidates=_candidate_list(args.candidate),
            statistical_power=statistical_power,
            experiment_registry_path=args.experiment_registry,
        )
    )
    for result, path in outputs:
        _print_summary(result, path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
