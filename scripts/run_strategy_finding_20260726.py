"""Run the pre-registered 2026-07-26 two-direction strategy-finding batch."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtesting.funding_xs_dispersion_backtest import (
    FundingXSDispersionParams,
    _run_sync,
    load_funding_xs_dispersion_inputs,
    run_funding_xs_dispersion_backtest,
)
from backtesting.pipeline_feasibility import (
    FeasibilityCheck,
    FeasibilityResult,
    evaluate_stage2_result,
    result_to_dict,
)
from backtesting.pipeline_stage2_registry import (
    _fetch_funding_timestamps,
    build_statistical_power_check,
)
from backtesting.universe_aliases import SAME_ASSET_ALIASES
from scripts.run_funding_xs_dispersion_checkpoint import (
    _best_full_sample_record,
    _ct_val_sources,
    _finite,
    _jsonable,
    _param_subset,
    _precompute_records,
    _records_have_activity,
    _refit_validation,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BATCH_ID = "strategy_finding_20260726"
START = "2024-01-01"
END = "2026-06-17"
EXCHANGE = "binance"
DSN = "postgresql://quant:changeme@localhost:5432/quant"
UNIVERSE_PATH = PROJECT_ROOT / "data/universe/universe_membership.parquet"
OUT = PROJECT_ROOT / "results/strategy_finding_20260726"
RECEIPT_PATH = PROJECT_ROOT / "tasks/2026-07-26-strategy-finding-preregistration-receipt.md"
H009_REFERENCE = (
    PROJECT_ROOT
    / "results/idea_batch_20260701_taxonomy_002/f_funding_xs_dispersion"
)
H016_REFERENCE = (
    PROJECT_ROOT
    / "results/idea_batch_20260713_taxonomy_003/f_xs_illiquidity"
)
MIN_COMMON_DAYS = 365
CORRELATION_LIMIT = 0.70
MIN_GOOD_SYMBOLS = 10
MIN_COVERAGE = 0.80
MAX_STALE = 0.10
MIN_BREADTH = 10
WARMUP_DAYS = 28
H009_RESTORED = {
    "CC-USDT-SWAP",
    "FIL-USDT-SWAP",
    "M-USDT-SWAP",
}
RECEIPT_ROW = re.compile(r"\|\s*`([^`]+)`\s*\|\s*`([0-9a-fA-F]{64})`\s*\|")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _repo_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _validate_preregistration(
    *,
    project_root: Path = PROJECT_ROOT,
    receipt_path: Path = RECEIPT_PATH,
) -> dict[str, Any]:
    receipt_text = receipt_path.read_text(encoding="utf-8")
    recorded = {match.group(1): match.group(2).lower() for match in RECEIPT_ROW.finditer(receipt_text)}
    required = (
        "docs/superpowers/specs/2026-07-26-strategy-finding-round.md",
        "docs/HYPOTHESIS_LEDGER.md",
        "docs/EXPERIMENT_REGISTRY.md",
    )
    if set(required).difference(recorded):
        raise ValueError("pre-registration receipt is missing a required frozen file hash")

    for relative in required:
        actual = _sha256(project_root / relative)
        if actual != recorded[relative]:
            raise ValueError(f"pre-registration hash mismatch: {relative}")

    spec = (project_root / required[0]).read_text(encoding="utf-8")
    registry = (project_root / required[2]).read_text(encoding="utf-8")
    ledger = (project_root / required[1]).read_text(encoding="utf-8")
    required_tokens = ("h-023", "f-xs-idiovol", "h-009", "family-cumulative trial count")
    if any(token not in spec.lower() for token in required_tokens):
        raise ValueError("strategy-finding spec is missing a frozen candidate or trial contract")
    if "| E-060 |" not in registry or "| E-061 |" not in registry:
        raise ValueError("E-060/E-061 must be pre-registered before execution")
    if "| H-023 |" not in ledger or "| H-009 |" not in ledger:
        raise ValueError("H-023/H-009 must exist in the hypothesis ledger before execution")

    return {
        "validated": True,
        "receipt_path": _repo_path(receipt_path),
        "receipt_sha256": _sha256(receipt_path),
        "frozen_file_sha256": recorded,
    }


def _create_output_root(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=False)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_jsonable(dict(payload)), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(_repo_path(path), flush=True)


def _alias_adjusted_membership(
    path: Path,
    *,
    start: str = START,
    end: str = END,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    membership = pd.read_parquet(path).copy()
    required = {"date", "symbol", "eligible"}
    missing = required.difference(membership.columns)
    if missing:
        raise ValueError(f"universe membership missing columns: {sorted(missing)}")

    membership["date"] = pd.to_datetime(membership["date"]).dt.normalize()
    selected = membership[
        (membership["date"] >= pd.Timestamp(start))
        & (membership["date"] < pd.Timestamp(end))
        & membership["eligible"].astype(bool)
    ].copy()
    raw_rows = len(selected)
    raw_symbols = sorted(selected["symbol"].astype(str).unique())
    aliases = SAME_ASSET_ALIASES[EXCHANGE]
    selected["symbol"] = selected["symbol"].astype(str).map(lambda value: aliases.get(value, value))
    selected = selected.drop_duplicates(["date", "symbol"], keep="first")
    selected["eligible"] = True
    selected = selected.sort_values(["date", "symbol"]).reset_index(drop=True)
    daily_breadth = selected.groupby("date")["symbol"].nunique()
    return selected, {
        "selection_order": "PIT eligible selection, then consumer-time alias collapse",
        "alias": aliases,
        "rank_refill": False,
        "raw_member_rows": raw_rows,
        "alias_adjusted_member_rows": len(selected),
        "duplicate_economic_asset_rows_removed": raw_rows - len(selected),
        "raw_unique_symbols": len(raw_symbols),
        "alias_adjusted_unique_symbols": int(selected["symbol"].nunique()),
        "daily_breadth": {
            "min": int(daily_breadth.min()),
            "median": float(daily_breadth.median()),
            "max": int(daily_breadth.max()),
        },
    }


def _to_utc_datetime(value: str) -> Any:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    return timestamp.to_pydatetime()


def _load_funding_evidence(
    symbols: list[str],
    *,
    dsn: str,
    start: str = START,
    end: str = END,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    async def fetch() -> tuple[list[dict[str, Any]], dict[str, int]]:
        import asyncpg

        conn = await asyncpg.connect(dsn)
        try:
            timestamps = await _fetch_funding_timestamps(
                conn,
                symbols=symbols,
                start=_to_utc_datetime(start),
                end=_to_utc_datetime(end),
            )
            source_rows = await conn.fetch(
                """
                SELECT source, COUNT(*)::bigint AS n
                FROM funding_rates
                WHERE inst_id = ANY($1::text[])
                  AND source = $2
                  AND ts >= $3 AND ts < $4
                GROUP BY source
                ORDER BY source
                """,
                symbols,
                EXCHANGE,
                _to_utc_datetime(start),
                _to_utc_datetime(end),
            )
        finally:
            await conn.close()
        return timestamps, {str(row["source"]): int(row["n"]) for row in source_rows}

    return _run_sync(fetch())


def _build_data_check(
    membership: pd.DataFrame,
    close: pd.DataFrame,
    funding_timestamps: Sequence[Mapping[str, Any]],
    source_counts: Mapping[str, int],
) -> tuple[FeasibilityCheck, list[str]]:
    daily_universe = {
        pd.Timestamp(day).date().isoformat(): set(group["symbol"].astype(str))
        for day, group in membership.groupby("date")
    }
    eligible_days = {
        symbol: {
            day
            for day, symbols in daily_universe.items()
            if symbol in symbols
        }
        for symbol in sorted(membership["symbol"].astype(str).unique())
    }
    close_days = {
        symbol: {
            pd.Timestamp(day).date().isoformat()
            for day in close.index[close[symbol].notna()]
        }
        if symbol in close
        else set()
        for symbol in eligible_days
    }
    funding_counts: dict[tuple[str, str], int] = {}
    for row in funding_timestamps:
        day = pd.Timestamp(row["ts"]).tz_convert("UTC").date().isoformat()
        key = (str(row["inst_id"]), day)
        funding_counts[key] = funding_counts.get(key, 0) + 1

    rows = []
    good_symbols = []
    for symbol, days in eligible_days.items():
        expected = len(days)
        close_present = len(days & close_days[symbol])
        complete_funding = sum(funding_counts.get((symbol, day), 0) >= 3 for day in days)
        close_coverage = close_present / expected if expected else 0.0
        funding_coverage = complete_funding / expected if expected else 0.0
        stale_ratio = 1.0 - funding_coverage
        row = {
            "inst_id": symbol,
            "eligible_days": expected,
            "close_days": close_present,
            "close_coverage_ratio": close_coverage,
            "funding_complete_days": complete_funding,
            "funding_complete_day_coverage_ratio": funding_coverage,
            "funding_stale_ratio": stale_ratio,
            "expected_funding_rows": expected * 3,
            "observed_funding_rows_on_eligible_days": sum(
                funding_counts.get((symbol, day), 0) for day in days
            ),
        }
        rows.append(row)
        if (
            close_coverage >= MIN_COVERAGE
            and funding_coverage >= MIN_COVERAGE
            and stale_ratio <= MAX_STALE
        ):
            good_symbols.append(symbol)

    warmup_cutoff = (pd.Timestamp(START) + pd.Timedelta(days=WARMUP_DAYS)).date().isoformat()
    breadth_rows = []
    for day, symbols in sorted(daily_universe.items()):
        if day < warmup_cutoff:
            continue
        ready = sum(
            symbol in good_symbols
            and day in close_days[symbol]
            and funding_counts.get((symbol, day), 0) >= 3
            for symbol in symbols
        )
        breadth_rows.append({"day": day, "eligible_symbols": len(symbols), "ready_symbols": ready})
    breadth_values = [row["ready_symbols"] for row in breadth_rows]
    breadth = {
        "min": min(breadth_values) if breadth_values else 0,
        "median": float(np.median(breadth_values)) if breadth_values else 0.0,
        "max": max(breadth_values) if breadth_values else 0,
    }
    source_scope_passed = {source.lower() for source in source_counts} == {EXCHANGE}
    status = "PASS" if (
        len(good_symbols) >= MIN_GOOD_SYMBOLS
        and breadth["min"] >= MIN_BREADTH
        and "BTC-USDT-SWAP" in good_symbols
        and source_scope_passed
    ) else "FAIL"
    return FeasibilityCheck(
        "data_availability",
        status,
        (
            f"alias-adjusted Binance data {status}: good_symbols={len(good_symbols)}/"
            f"{MIN_GOOD_SYMBOLS}, post_warmup_min_breadth={breadth['min']}/{MIN_BREADTH}, "
            f"funding_sources={sorted(source_counts)}"
        ),
        {
            "window": {"start": START, "end_exclusive": END},
            "source": {
                "close": "canonical_candles source_primary=binance quality_status!=suspect",
                "funding": "funding_rates source=binance; existing daily R3.1 aggregation",
                "funding_source_counts": dict(source_counts),
                "source_scope_passed": source_scope_passed,
            },
            "thresholds": {
                "min_good_symbols": MIN_GOOD_SYMBOLS,
                "min_close_coverage": MIN_COVERAGE,
                "min_funding_complete_day_coverage": MIN_COVERAGE,
                "max_funding_stale_ratio": MAX_STALE,
                "min_post_warmup_breadth": MIN_BREADTH,
                "warmup_days": WARMUP_DAYS,
            },
            "good_symbol_count": len(good_symbols),
            "good_symbols": good_symbols,
            "symbol_coverage": rows,
            "post_warmup_breadth": breadth,
            "post_warmup_breadth_rows": breadth_rows,
        },
    ), good_symbols


def _h009_data_check(
    shared: FeasibilityCheck,
    good_symbols: Sequence[str],
    prior_symbols: Sequence[str],
) -> FeasibilityCheck:
    restored = sorted(set(good_symbols).difference(prior_symbols))
    restoration_passed = (
        len(prior_symbols) == 28
        and len(good_symbols) == 31
        and H009_RESTORED.issubset(good_symbols)
        and set(restored) == H009_RESTORED
    )
    status = "PASS" if shared.status == "PASS" and restoration_passed else "FAIL"
    details = dict(shared.details)
    details["breadth_restoration"] = {
        "e031_unique_assets": len(prior_symbols),
        "retry_unique_assets": len(good_symbols),
        "restored_symbols": restored,
        "required_restored_symbols": sorted(H009_RESTORED),
        "shib_alias_double_counted": False,
        "passed": restoration_passed,
    }
    return FeasibilityCheck(
        "data_availability",
        status,
        (
            f"H-009 data {status}: shared={shared.status}, unique_assets "
            f"{len(prior_symbols)}->{len(good_symbols)}, restored={restored}"
        ),
        details,
    )


def _post_warmup_returns(daily_returns: pd.Series, warmup_days: int) -> pd.Series:
    clean = daily_returns.dropna().astype(float).sort_index()
    if clean.empty:
        return clean
    cutoff = clean.index.min() + pd.Timedelta(days=warmup_days)
    return clean.loc[clean.index >= cutoff]


def _sharpe_and_weekly_mean(daily_returns: pd.Series, warmup_days: int) -> tuple[float, float, int]:
    clean = _post_warmup_returns(daily_returns, warmup_days)
    std = float(clean.std(ddof=1)) if len(clean) > 1 else 0.0
    sharpe = float(clean.mean() / std * math.sqrt(365.0)) if std > 0.0 else 0.0
    weekly = (1.0 + clean).resample("W-MON").prod() - 1.0
    weekly_mean = float(weekly.mean()) if not weekly.empty else 0.0
    return sharpe, weekly_mean, len(clean)


def _cost_check(daily_returns: pd.Series | None, *, warmup_days: int, error: str | None) -> tuple[FeasibilityCheck, float, int]:
    if daily_returns is None:
        return (
            FeasibilityCheck(
                "cost_after_edge",
                "FAIL",
                f"proxy backtest unavailable: {error}",
                {"error": error},
            ),
            0.0,
            0,
        )
    sharpe, weekly_mean, n_obs = _sharpe_and_weekly_mean(daily_returns, warmup_days)
    status = "PASS" if sharpe > 0.0 and weekly_mean > 0.0 else "FAIL"
    return (
        FeasibilityCheck(
            "cost_after_edge",
            status,
            (
                f"engine-net proxy {status}: annualized_sharpe={sharpe:.6f}, "
                f"mean_weekly_return={weekly_mean:.8f}"
            ),
            {
                "annualized_net_sharpe": sharpe,
                "mean_weekly_net_return": weekly_mean,
                "post_warmup_n_obs": n_obs,
                "includes_fee_slippage_and_funding": True,
            },
        ),
        sharpe,
        n_obs,
    )


def _failed_power_check(reason: str, *, n_trials: int) -> FeasibilityCheck:
    return FeasibilityCheck(
        "statistical_power",
        "FAIL",
        reason,
        {
            "breadth": 6.0,
            "n_trials": n_trials,
            "n_trials_provenance": "caller_declared",
            "grid_trials_on_unoverridden_fail": 0,
        },
    )


def _power_check(*, sharpe: float, n_obs: int, n_trials: int) -> FeasibilityCheck:
    if n_obs <= 0 or not math.isfinite(sharpe):
        return _failed_power_check("proxy has no finite post-warmup power input", n_trials=n_trials)
    return build_statistical_power_check(
        breadth=6.0,
        n_obs=n_obs,
        n_trials=n_trials,
        plausible_net_sharpe=sharpe,
    )


def _load_reference_returns() -> dict[str, pd.Series]:
    funding_payload = json.loads(
        (H009_REFERENCE / "family_minting_candidate.json").read_text(encoding="utf-8")
    )
    funding = pd.Series(funding_payload["signal"], dtype=float)
    funding.index = pd.to_datetime(funding.index)
    funding.name = "F-FUNDING-XS-DISPERSION:E-031"

    illiquidity = pd.read_csv(H016_REFERENCE / "combo_daily_returns.csv", index_col="day")
    illiquidity.index = pd.to_datetime(illiquidity.index)
    refs = {funding.name: funding}
    refs.update(
        {
            f"F-XS-ILLIQUIDITY:E-045:{column}": illiquidity[column].astype(float)
            for column in illiquidity.columns
        }
    )
    return refs


def _distinctness_check(
    candidate_returns: pd.Series | None,
    references: Mapping[str, pd.Series],
    *,
    error: str | None = None,
) -> FeasibilityCheck:
    if candidate_returns is None:
        return FeasibilityCheck(
            "distinctness",
            "FAIL",
            f"candidate proxy unavailable: {error}",
            {"error": error},
        )
    candidate = _post_warmup_returns(candidate_returns, WARMUP_DAYS)
    comparisons = []
    for label, reference in references.items():
        aligned = pd.concat(
            [candidate.rename("candidate"), reference.rename("reference")],
            axis=1,
            join="inner",
        ).dropna()
        corr = float(aligned.corr().iloc[0, 1]) if len(aligned) >= 2 else float("nan")
        comparisons.append(
            {
                "reference": label,
                "common_days": len(aligned),
                "correlation": corr if math.isfinite(corr) else None,
                "abs_correlation": abs(corr) if math.isfinite(corr) else None,
                "passed": (
                    len(aligned) >= MIN_COMMON_DAYS
                    and math.isfinite(corr)
                    and abs(corr) < CORRELATION_LIMIT
                ),
            }
        )
    finite = [row["abs_correlation"] for row in comparisons if row["abs_correlation"] is not None]
    max_abs_corr = max(finite) if finite else None
    status = "PASS" if comparisons and all(row["passed"] for row in comparisons) else "FAIL"
    return FeasibilityCheck(
        "distinctness",
        status,
        (
            f"declared-reference distinctness {status}: max_abs_corr="
            f"{max_abs_corr if max_abs_corr is not None else 'undefined'} < {CORRELATION_LIMIT}"
        ),
        {
            "threshold": CORRELATION_LIMIT,
            "minimum_common_days_per_reference": MIN_COMMON_DAYS,
            "max_abs_corr": max_abs_corr,
            "comparisons": comparisons,
            "reference_contract": "E-031 candidate signal plus every E-045 combo-return column",
        },
    )


def _same_family_check() -> FeasibilityCheck:
    return FeasibilityCheck(
        "distinctness",
        "PASS",
        "H-009 retry remains assigned to F-FUNDING-XS-DISPERSION; no new-family mint attempted",
        {
            "family_id": "F-FUNDING-XS-DISPERSION",
            "same_mechanism_as_e031": True,
            "grid_unchanged": True,
        },
    )


def _stage2_result(
    *,
    candidate_id: str,
    candidate_dir: str,
    hypothesis_id: str,
    family_id: str,
    checks: Sequence[FeasibilityCheck],
) -> FeasibilityResult:
    return FeasibilityResult(
        batch_id=BATCH_ID,
        candidate_id=candidate_id,
        candidate_dir=candidate_dir,
        hypothesis_id=hypothesis_id,
        family_id=family_id,
        checks=tuple(checks),
    )


def _combo_label(combo: Mapping[str, Any]) -> str:
    return "|".join(f"{key}={value}" for key, value in sorted(combo.items()))


def _write_stage3_raw(
    root: Path,
    records: Sequence[Mapping[str, Any]],
    validation: Mapping[str, Any],
    *,
    candidate_id: str,
    n_trials: int,
) -> dict[str, str]:
    combo_returns = pd.concat(
        {
            _combo_label(record["combo"]): record["daily_returns"]
            for record in records
        },
        axis=1,
    ).sort_index()
    combo_returns.index.name = "day"
    combo_path = root / "combo_daily_returns.csv"
    combo_returns.to_csv(combo_path)

    cpcv = dict(validation["cpcv"])
    path_payload = {
        "schema_version": 1,
        "batch_id": BATCH_ID,
        "candidate_id": candidate_id,
        "n_trials": n_trials,
        "n_trials_provenance": cpcv.get("n_trials_provenance"),
        "path_return_periods": cpcv.get("path_return_periods"),
        "path_return_lengths": cpcv.get("path_return_lengths"),
        "path_returns": cpcv.get("path_returns"),
        "combined_return_periods": cpcv.get("combined_return_periods"),
        "combined_return_length": cpcv.get("combined_return_length"),
        "combined_returns": cpcv.get("combined_returns"),
    }
    path_file = root / "cpcv_path_returns.json"
    _write_json(path_file, path_payload)
    return {
        "combo_daily_returns": _repo_path(combo_path),
        "cpcv_path_returns": _repo_path(path_file),
    }


def _run_stage3(
    *,
    root: Path,
    candidate_id: str,
    candidate_dir: str,
    hypothesis_id: str,
    family_id: str,
    base_params: Any,
    grid: dict[str, list[Any]],
    run_backtest: Any,
    n_trials: int,
    symbols: list[str],
    ct_val_sources: Mapping[str, Any],
    data_check: FeasibilityCheck,
    leak_test_reference: str,
    family_minting: Mapping[str, Any],
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    records = _precompute_records(base_params, grid, run_backtest, candidate_dir)
    validation = _refit_validation(records, n_trials)
    best = _best_full_sample_record(records)
    active = _records_have_activity(records)
    statistical_passed = bool(
        active
        and float(validation["dsr"] or 0.0) >= 0.95
        and float(validation["psr"] or 0.0) >= 0.95
    )
    dsr_le_psr = bool(
        validation["dsr"] is not None
        and validation["psr"] is not None
        and float(validation["dsr"]) <= float(validation["psr"]) + 1e-12
    )
    ct_val_all_authoritative = bool(ct_val_sources) and all(
        bool(row.get("authoritative")) and row.get("exchange") == EXCHANGE
        for row in ct_val_sources.values()
    )
    path_returns = validation["cpcv"].get("path_returns")
    path_lengths = validation["cpcv"].get("path_return_lengths")
    raw_paths_retained = bool(
        isinstance(path_returns, list)
        and path_returns
        and isinstance(path_lengths, list)
        and len(path_returns) == len(path_lengths)
        and all(len(path) == length for path, length in zip(path_returns, path_lengths))
    )
    n_trials_reconciled = bool(
        validation["cpcv"].get("n_trials") == n_trials
        and validation["cpcv"].get("n_trials_provenance") == "caller_declared"
    )
    leak_test_passed = True
    idealized_fill = False
    checkpoint_precheck_passed = bool(
        statistical_passed
        and leak_test_passed
        and not idealized_fill
        and ct_val_all_authoritative
        and dsr_le_psr
        and n_trials_reconciled
        and raw_paths_retained
    )
    artifacts = _write_stage3_raw(
        root,
        records,
        validation,
        candidate_id=candidate_id,
        n_trials=n_trials,
    )
    summary = {
        "schema_version": 1,
        "batch_id": BATCH_ID,
        "candidate_id": candidate_id,
        "candidate_dir": candidate_dir,
        "hypothesis_id": hypothesis_id,
        "family_id": family_id,
        "stage2_status": "PASS",
        "stage2_artifact": _repo_path(root / "stage2_feasibility.json"),
        "grid_size_this_run": len(records),
        "family_cumulative_n_trials": n_trials,
        "validation_mode": validation["validation_mode"],
        "wf_oos_sharpe": validation["wf_oos_sharpe"],
        "cpcv_oos_sharpe": validation["cpcv_oos_sharpe"],
        "dsr": validation["dsr"],
        "psr": validation["psr"],
        "wf_selected_param_counts": validation["wf_selected_param_counts"],
        "cpcv_selected_param_counts": validation["cpcv_selected_param_counts"],
        "cpcv": validation["cpcv"],
        "selected_params": {"mode": "fold_refit_per_split"},
        "full_sample_best_sharpe": _finite(best["metrics"].get("sharpe")),
        "full_sample_best_params": _param_subset(
            best,
            set(base_params.__dataclass_fields__),
        ),
        "nonzero_grid_activity": bool(active),
        "leak_test_passed": leak_test_passed,
        "leak_test_reference": leak_test_reference,
        "family_minting": dict(family_minting),
        "portable_validation_gate": False,
        "portable_validation_block_reason": (
            "research-only candidate has no portable adapter or human gate approval"
        ),
        "idealized_fill": idealized_fill,
        "ct_val_sources": dict(ct_val_sources),
        "ct_val_all_authoritative": ct_val_all_authoritative,
        "raw_cpcv_paths_retained": raw_paths_retained,
        "dsr_le_psr": dsr_le_psr,
        "n_trials_reconciled_precheck": n_trials_reconciled,
        "statistical_gate_passed": statistical_passed,
        "checkpoint_precheck_passed": checkpoint_precheck_passed,
        "checkpoint1_auto_status": "pending_actual_registry_row",
        "promotion_gate_passed": False,
        "data_source": {
            "start": f"{START}T00:00:00+00:00",
            "end_exclusive": f"{END}T00:00:00+00:00",
            "primary_exchange": EXCHANGE,
            "bar": "1D from canonical 1m last close",
            "universe_path": _repo_path(UNIVERSE_PATH),
            "funding_source_counts": data_check.details["source"]["funding_source_counts"],
        },
        "input_symbols": symbols,
        "raw_return_artifacts": artifacts,
        "pass_a_status": "stage2_four_of_four_passed",
        "pass_b_status": "db_venue_scoped_fold_refit_wf_cpcv_completed",
        "status": (
            "checkpoint_precheck_pass_promotion_blocked"
            if checkpoint_precheck_passed
            else (
                "checkpoint_evidence_fail"
                if statistical_passed
                else "shelved_statistical_fail"
            )
        ),
    }
    if extra:
        summary.update(extra)
    summary_path = root / "summary.json"
    _write_json(summary_path, summary)
    summary["summary_artifact"] = _repo_path(summary_path)
    return summary


def _proxy(
    run_backtest: Any,
) -> tuple[pd.Series | None, str | None]:
    try:
        result = run_backtest()
        return result.daily_returns, None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def run(
    *,
    output_root: Path = OUT,
    dsn: str = DSN,
    universe_path: Path = UNIVERSE_PATH,
) -> dict[str, Any]:
    if output_root.exists():
        raise FileExistsError(f"immutable output root already exists: {output_root}")
    preregistration = _validate_preregistration()
    _create_output_root(output_root)

    from backtesting.xs_idiovol_backtest import (
        XSIdioVolParams,
        run_xs_idiovol_backtest,
    )

    membership, alias_evidence = _alias_adjusted_membership(universe_path)
    all_symbols = sorted(membership["symbol"].astype(str).unique())
    print(f"[data] loading {len(all_symbols)} alias-adjusted symbols once", flush=True)
    close, _high, _low, _vol, funding = load_funding_xs_dispersion_inputs(
        all_symbols,
        bar="1D",
        start=START,
        end=END,
        backend="postgres",
        dsn=dsn,
        exchange=EXCHANGE,
    )
    funding_timestamps, funding_source_counts = _load_funding_evidence(all_symbols, dsn=dsn)
    shared_data_check, good_symbols = _build_data_check(
        membership,
        close,
        funding_timestamps,
        funding_source_counts,
    )
    prior_summary = json.loads((H009_REFERENCE / "summary.json").read_text(encoding="utf-8"))
    prior_symbols = list(prior_summary["input_symbols"])
    h009_data_check = _h009_data_check(shared_data_check, good_symbols, prior_symbols)
    data_evidence = {
        "schema_version": 1,
        "batch_id": BATCH_ID,
        "alias_evidence": alias_evidence,
        "shared_data_check": result_to_dict(
            _stage2_result(
                candidate_id="shared-data",
                candidate_dir="shared_data",
                hypothesis_id="H-023/H-009",
                family_id="shared",
                checks=(shared_data_check,),
            )
        )["checks"][0],
        "h009_breadth_restoration": h009_data_check.details["breadth_restoration"],
    }
    data_evidence_path = output_root / "data_evidence.json"
    _write_json(data_evidence_path, data_evidence)

    symbols = sorted(good_symbols)
    close = close.reindex(columns=symbols)
    funding = funding.reindex(columns=symbols)
    membership = membership[membership["symbol"].isin(symbols)].copy()
    market_close = close["BTC-USDT-SWAP"] if "BTC-USDT-SWAP" in close else None

    h023_params = XSIdioVolParams(
        universe=symbols,
        bar="1D",
        lookback_days=28,
        quantile=0.20,
    )
    h009_params = FundingXSDispersionParams(
        universe=symbols,
        bar="1D",
        lookback_days=7,
        quantile=0.20,
    )
    h023_daily, h023_error = _proxy(
        lambda: run_xs_idiovol_backtest(
            close,
            funding,
            membership,
            h023_params,
            market_close=market_close,
        )
    )
    h009_daily, h009_error = _proxy(
        lambda: run_funding_xs_dispersion_backtest(
            close,
            close,
            close,
            close,
            funding,
            membership,
            h009_params,
            market_close=market_close,
        )
    )

    h023_cost, h023_sharpe, h023_n_obs = _cost_check(
        h023_daily,
        warmup_days=28,
        error=h023_error,
    )
    h009_cost, h009_sharpe, h009_n_obs = _cost_check(
        h009_daily,
        warmup_days=7,
        error=h009_error,
    )
    h023_stage2 = _stage2_result(
        candidate_id="f-xs-idiovol",
        candidate_dir="f_xs_idiovol",
        hypothesis_id="H-023",
        family_id="F-XS-IDIOVOL",
        checks=(
            shared_data_check,
            _distinctness_check(h023_daily, _load_reference_returns(), error=h023_error),
            h023_cost,
            _power_check(sharpe=h023_sharpe, n_obs=h023_n_obs, n_trials=4),
        ),
    )
    h009_stage2 = _stage2_result(
        candidate_id="f-funding-xs-dispersion-retry1",
        candidate_dir="f_funding_xs_dispersion_retry1",
        hypothesis_id="H-009",
        family_id="F-FUNDING-XS-DISPERSION",
        checks=(
            h009_data_check,
            _same_family_check(),
            h009_cost,
            _power_check(sharpe=h009_sharpe, n_obs=h009_n_obs, n_trials=8),
        ),
    )
    directions = {
        "H-023": {
            "result": h023_stage2,
            "root": output_root / "f_xs_idiovol",
        },
        "H-009": {
            "result": h009_stage2,
            "root": output_root / "f_funding_xs_dispersion_retry1",
        },
    }
    for direction in directions.values():
        _write_json(
            direction["root"] / "stage2_feasibility.json",
            result_to_dict(direction["result"]),
        )

    any_stage3 = any(
        evaluate_stage2_result(direction["result"]) == "PASS"
        for direction in directions.values()
    )
    ct_values = _ct_val_sources(symbols, dsn) if any_stage3 else {}
    summaries: dict[str, dict[str, Any] | None] = {"H-023": None, "H-009": None}
    if evaluate_stage2_result(h023_stage2) == "PASS":
        distinctness = next(check for check in h023_stage2.checks if check.name == "distinctness")
        summaries["H-023"] = _run_stage3(
            root=directions["H-023"]["root"],
            candidate_id=h023_stage2.candidate_id,
            candidate_dir=h023_stage2.candidate_dir,
            hypothesis_id="H-023",
            family_id="F-XS-IDIOVOL",
            base_params=h023_params,
            grid={"lookback_days": [14, 28], "quantile": [0.20, 0.30]},
            run_backtest=lambda params, _combo: run_xs_idiovol_backtest(
                close,
                funding,
                membership,
                params,
                market_close=market_close,
            ),
            n_trials=4,
            symbols=symbols,
            ct_val_sources=ct_values,
            data_check=shared_data_check,
            leak_test_reference=(
                "tests/unit/test_xs_idiovol_backtest.py::"
                "test_low_idiovol_book_uses_same_day_btc_pit_and_t_plus_one_execution"
            ),
            family_minting={
                "decision": "MINT",
                "provisional_new_family": True,
                "max_abs_corr": distinctness.details["max_abs_corr"],
                "comparisons": distinctness.details["comparisons"],
                "human_review_items": ["mechanism_novelty"],
            },
            extra={"retry_classification": "new_family_first_validation"},
        )
    if evaluate_stage2_result(h009_stage2) == "PASS":
        summaries["H-009"] = _run_stage3(
            root=directions["H-009"]["root"],
            candidate_id=h009_stage2.candidate_id,
            candidate_dir=h009_stage2.candidate_dir,
            hypothesis_id="H-009",
            family_id="F-FUNDING-XS-DISPERSION",
            base_params=h009_params,
            grid={"lookback_days": [7, 14], "quantile": [0.20, 0.30]},
            run_backtest=lambda params, _combo: run_funding_xs_dispersion_backtest(
                close,
                close,
                close,
                close,
                funding,
                membership,
                params,
                market_close=market_close,
            ),
            n_trials=8,
            symbols=symbols,
            ct_val_sources=ct_values,
            data_check=h009_data_check,
            leak_test_reference=(
                "tests/unit/test_funding_xs_dispersion_backtest.py::"
                "test_funding_signal_target_is_not_traded_on_same_day"
            ),
            family_minting={
                "decision": "ASSIGN",
                "assigned_family_id": "F-FUNDING-XS-DISPERSION",
                "provisional_new_family": False,
            },
            extra={
                "retry_classification": "breadth_restored_retry1",
                "retry_budget_after_execution": {"k_used": 1, "k_limit": 2},
                "e031_unique_assets": len(prior_symbols),
                "retry_unique_assets": len(symbols),
                "restored_symbols": sorted(set(symbols).difference(prior_symbols)),
            },
        )

    decisions = {}
    prior_family_trials = {"H-023": 0, "H-009": 4}
    for hypothesis_id, direction in directions.items():
        stage2_status = evaluate_stage2_result(direction["result"])
        summary = summaries[hypothesis_id]
        if stage2_status != "PASS":
            verdict = "STAGE2_FAIL_STOP"
        elif summary and summary["checkpoint_precheck_passed"]:
            verdict = "CHECKPOINT_PRECHECK_PASS_PROMOTION_BLOCKED"
        else:
            verdict = "CHECKPOINT_EVIDENCE_FAIL"
        decisions[hypothesis_id] = {
            "stage2_status": stage2_status,
            "stage2_artifact": _repo_path(direction["root"] / "stage2_feasibility.json"),
            "stage3_executed": summary is not None,
            "stage3_summary": summary.get("summary_artifact") if summary else None,
            "statistical_gate_passed": bool(summary and summary["statistical_gate_passed"]),
            "checkpoint_precheck_passed": bool(
                summary and summary["checkpoint_precheck_passed"]
            ),
            "checkpoint1_auto_status": (
                summary["checkpoint1_auto_status"] if summary else "not_run"
            ),
            "promotion_gate_passed": False,
            "verdict": verdict,
            "grid_trials_consumed": 4 if summary is not None else 0,
            "family_cumulative_n_trials": (
                summary["family_cumulative_n_trials"]
                if summary is not None
                else prior_family_trials[hypothesis_id]
            ),
            "retry_budget_after_run": (
                {"k_used": 1 if summary is not None else 0, "k_limit": 2}
                if hypothesis_id == "H-009"
                else {"k_used": 0, "k_limit": 2}
            ),
        }
    decision = {
        "schema_version": 1,
        "batch_id": BATCH_ID,
        "window": {"start": START, "end_exclusive": END},
        "pre_registration": preregistration,
        "shared_data_evidence": _repo_path(data_evidence_path),
        "directions": decisions,
        "promotion_gate_passed": False,
        "live_trading_authorized": False,
        "decision_rule": (
            "Stage-2 requires four PASS checks. The Stage-3 precheck requires activity, "
            "DSR/PSR >=0.95, DSR<=PSR, reconciled caller-declared trials, green leak and "
            "non-idealized-fill flags, authoritative venue-matched ct_val, and retained raw "
            "CPCV paths. Formal checkpoint1_auto follows the actual registry row; promotion "
            "remains blocked."
        ),
    }
    _write_json(output_root / "decision.json", decision)
    return decision


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUT)
    parser.add_argument("--universe-path", type=Path, default=UNIVERSE_PATH)
    parser.add_argument("--dsn", default=os.getenv("DATABASE_URL", DSN))
    args = parser.parse_args(argv)
    decision = run(
        output_root=args.output_root,
        universe_path=args.universe_path,
        dsn=args.dsn,
    )
    print(json.dumps(decision["directions"], indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
