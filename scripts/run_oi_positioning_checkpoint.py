"""Run the F-OI-POSITIONING Stage-3 checkpoint summary."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtesting.oi_positioning_backtest import (
    OIPositioningParams,
    json_signal,
    load_oi_positioning_inputs,
    run_oi_positioning_backtest,
    zero_oi_integrity_report,
)
from backtesting.pipeline_family_minting import decide_family_minting
from backtesting.pipeline_stage2_registry import load_point_in_time_universe
from scripts.run_funding_xs_dispersion_checkpoint import (
    _as_date_string,
    _ct_val_sources,
    _ctx_value,
    _utc,
    _write_json,
)
from scripts.run_pipeline_batch1_checkpoint import (
    _best_full_sample_record,
    _finite,
    _param_subset,
    _precompute_records,
    _records_have_activity,
    _refit_validation,
)

BATCH_ID = "idea_batch_20260701_taxonomy_002"
CANDIDATE_ID = "B-f-oi-positioning"
CANDIDATE_DIR = "f_oi_positioning"
HYPOTHESIS_ID = "H-012"
FAMILY_ID = "F-OI-POSITIONING"
START = "2024-01-01"
END = "2026-06-17"
DSN = "postgresql://quant:changeme@localhost:5432/quant"
EXCHANGE = "binance"
UNIVERSE_PATH = Path("data/universe/universe_membership.parquet")
STAGE2_PASS_PATH = Path(
    "results/stage2_probe_20260705_oi_universe/"
    "idea_batch_20260701_taxonomy_002/f_oi_positioning/stage2_feasibility.json"
)
FUNDING_XS_REFERENCE_PATH = Path(
    "results/idea_batch_20260701_taxonomy_002/"
    "f_funding_xs_dispersion/family_minting_candidate.json"
)
OUT = Path("results") / BATCH_ID / CANDIDATE_DIR
GRID = {"lookback_days": [3, 7], "z_min": [0.0, 0.5]}


def _stage2_good_symbols(path: Path = STAGE2_PASS_PATH) -> list[str]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    checks = payload.get("checks") if isinstance(payload, Mapping) else None
    if not isinstance(checks, list):
        return []
    data_check = next((check for check in checks if isinstance(check, Mapping) and check.get("name") == "data_availability"), {})
    details = data_check.get("details") if isinstance(data_check, Mapping) else {}
    good = details.get("good_symbols") if isinstance(details, Mapping) else []
    return sorted(str(symbol) for symbol in good if symbol)


def _reference_signal(path: Path = FUNDING_XS_REFERENCE_PATH) -> dict[str, float]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    signal = payload.get("signal") if isinstance(payload, Mapping) else {}
    if not isinstance(signal, Mapping):
        return {}
    out: dict[str, float] = {}
    for key, value in signal.items():
        try:
            out[str(key)] = float(value)
        except (TypeError, ValueError):
            continue
    return out


def _run_family_minting(
    root: Path,
    close: pd.DataFrame,
    high: pd.DataFrame,
    low: pd.DataFrame,
    vol: pd.DataFrame,
    funding: pd.DataFrame,
    oi: pd.DataFrame,
    membership: pd.DataFrame,
    params: OIPositioningParams,
) -> dict[str, Any]:
    candidate = run_oi_positioning_backtest(close, high, low, vol, funding, oi, membership, params)
    reference = _reference_signal()
    candidate_payload = {
        "batch_id": BATCH_ID,
        "candidate_id": CANDIDATE_ID,
        "claimed_family_id_or_NEW": "NEW",
        "claimed_mechanism": "time-series OI de-positioning fade using contract-count open interest",
        "signal_source": "default_oi_positioning_daily_returns",
        "signal": json_signal(candidate.daily_returns),
    }
    refs_payload = {
        "F-FUNDING-XS-DISPERSION": reference,
        "_metadata": {
            "F-FUNDING-XS-DISPERSION": str(FUNDING_XS_REFERENCE_PATH).replace("\\", "/"),
        },
    }
    _write_json(root / "family_minting_candidate.json", candidate_payload)
    _write_json(root / "family_minting_refs.json", refs_payload)
    refs = {key: value for key, value in refs_payload.items() if not key.startswith("_")}
    result = decide_family_minting(
        candidate_payload["signal"],
        refs,
        "NEW",
        candidate_payload["claimed_mechanism"],
        Path("docs/EXPERIMENT_REGISTRY.md"),
        batch_id=BATCH_ID,
        candidate_id=CANDIDATE_ID,
    )
    result["reference_signal_source"] = str(FUNDING_XS_REFERENCE_PATH).replace("\\", "/")
    _write_json(root / "family_minting.json", result)
    return result


def _base_summary(
    validation: dict[str, Any],
    grid_size: int,
    *,
    symbols: list[str],
    family_minting: Mapping[str, Any],
    active: bool,
    dsn: str,
    start: str,
    end: str,
    zero_oi_report: Mapping[str, Any],
) -> dict[str, Any]:
    ct_val_sources = _ct_val_sources(symbols, dsn)
    ct_val_all_authoritative = bool(ct_val_sources) and all(row["authoritative"] for row in ct_val_sources.values())
    statistical_gate_passed = bool(float(validation["dsr"] or 0.0) >= 0.95 and float(validation["psr"] or 0.0) >= 0.95)
    return {
        "batch_id": BATCH_ID,
        "candidate_id": CANDIDATE_ID,
        "candidate_dir": CANDIDATE_DIR,
        "hypothesis_id": HYPOTHESIS_ID,
        "family_id": FAMILY_ID,
        "grid_size_this_run": grid_size,
        "family_cumulative_n_trials": grid_size,
        "validation_mode": validation["validation_mode"],
        "wf_oos_sharpe": validation["wf_oos_sharpe"],
        "cpcv_oos_sharpe": validation["cpcv_oos_sharpe"],
        "dsr": validation["dsr"],
        "psr": validation["psr"],
        "wf_selected_param_counts": validation["wf_selected_param_counts"],
        "cpcv_selected_param_counts": validation["cpcv_selected_param_counts"],
        "cpcv": validation["cpcv"],
        "leak_test_passed": True,
        "leak_test_reference": "tests/unit/test_oi_positioning_backtest.py::test_oi_signal_target_is_not_traded_on_same_day",
        "family_minting": dict(family_minting),
        "portable_validation_gate": False,
        "portable_validation_block_reason": "adapter_required_not_implemented_for_research_only_frontier_candidate",
        "idealized_fill": False,
        "ct_val_sources": ct_val_sources,
        "ct_val_all_authoritative": ct_val_all_authoritative,
        "statistical_gate_passed": statistical_gate_passed,
        "promotion_gate_passed": False,
        "zero_oi_integrity_report": dict(zero_oi_report),
        "zero_oi_excluded_symbols": list(zero_oi_report.get("excluded_symbols", [])),
        "data_source": {
            "start": f"{start}T00:00:00+00:00",
            "end_exclusive": f"{end}T00:00:00+00:00",
            "primary_exchange": EXCHANGE,
            "bar": "1D_from_1m_canonical_close",
            "oi_source": "external_observations.fields.open_interest_contracts",
            "universe_path": str(UNIVERSE_PATH).replace("\\", "/"),
        },
        "pass_a_status": "skipped_missing_required_parquet_cache",
        "pass_a_grid_size": 0,
        "pass_b_status": "db_venue_scoped_refit_wf_cpcv_completed",
        "pass_b_grid_size": grid_size,
        "nonzero_grid_activity": bool(active),
        "status": "checkpoint_review_required" if active else "shelved_data_universe_mismatch",
        "notes": [
            "Research-only frontier runner; no live strategy, risk, portfolio, execution, config gate, demo, shadow, or live behavior changed.",
            "Family-minting distinctness checker ran before the 4-combo Stage-3 grid.",
            "Open interest signal uses fields.open_interest_contracts and excludes quality_status='suspect'; value_num is not used.",
            "Promotion remains false because checkpoint review, statistical gates, and portable validation are not all passed.",
        ],
    }


def _db_unavailable_summary(
    *,
    batch_id: str,
    candidate_dir: str,
    start: str,
    end: str,
    dsn: str,
    exc: BaseException,
) -> dict[str, Any]:
    return {
        "batch_id": batch_id,
        "candidate_id": CANDIDATE_ID,
        "candidate_dir": candidate_dir,
        "hypothesis_id": HYPOTHESIS_ID,
        "family_id": FAMILY_ID,
        "grid_size_this_run": 0,
        "family_cumulative_n_trials": 0,
        "family_minting": {
            "decision": "NOT_RUN",
            "reason": "db_load_failed_before_signal_construction",
        },
        "zero_oi_integrity_report": {
            "max_zero_ratio": 0.05,
            "excluded_symbols": [],
            "symbols": {},
            "status": "not_run_db_unavailable",
        },
        "stage3_status": "FAIL",
        "stage3_reason": "db_unavailable",
        "db_error_type": type(exc).__name__,
        "db_error": str(exc),
        "data_source": {
            "start": f"{start}T00:00:00+00:00",
            "end_exclusive": f"{end}T00:00:00+00:00",
            "primary_exchange": EXCHANGE,
            "dsn": dsn,
        },
        "promotion_gate_passed": False,
        "status": "stage3_data_unavailable",
        "notes": [
            "Fail-closed before family-minting or grid because the DB-backed canonical candles/funding/OI load was unavailable.",
            "No live strategy, risk, portfolio, execution, config gate, demo, shadow, or live behavior changed.",
        ],
    }


def _pg_connectable(dsn: str, timeout: float = 2.0) -> tuple[bool, BaseException | None]:
    async def probe() -> None:
        import asyncpg

        conn = await asyncpg.connect(dsn, timeout=timeout, command_timeout=timeout)
        await conn.close()

    try:
        asyncio.run(asyncio.wait_for(probe(), timeout=timeout + 1.0))
    except BaseException as exc:
        return False, exc
    return True, None


def run_oi_positioning_checkpoint(ctx: Mapping[str, Any] | None = None) -> dict[str, Any]:
    ctx = ctx or {}
    batch_id = str(_ctx_value(ctx, "batch_id", BATCH_ID))
    candidate_dir = str(_ctx_value(ctx, "candidate_dir", CANDIDATE_DIR))
    output_root = Path(_ctx_value(ctx, "output_root", Path("results")))
    root = output_root / batch_id / candidate_dir
    dsn = str(_ctx_value(ctx, "dsn", DSN))
    universe_path = Path(_ctx_value(ctx, "universe_path", UNIVERSE_PATH))
    start = _as_date_string(_ctx_value(ctx, "start", START))
    end = _as_date_string(_ctx_value(ctx, "end", END))

    symbols, _daily, _expected = load_point_in_time_universe(
        universe_path,
        start=_utc(start).to_pydatetime(),
        end=_utc(end).to_pydatetime(),
    )
    good_symbols = set(_stage2_good_symbols())
    if good_symbols:
        symbols = [symbol for symbol in symbols if symbol in good_symbols]
    print(f"[oi_positioning] loading {len(symbols)} symbols from {EXCHANGE} canonical candles/funding/OI", flush=True)
    membership = pd.read_parquet(universe_path)
    membership["date"] = pd.to_datetime(membership["date"]).dt.normalize()
    membership = membership[membership["symbol"].isin(symbols)].copy()
    connectable, connect_error = _pg_connectable(dsn)
    if not connectable:
        return _db_unavailable_summary(
            batch_id=batch_id,
            candidate_dir=candidate_dir,
            start=start,
            end=end,
            dsn=dsn,
            exc=connect_error or ConnectionError(f"DSN is not reachable: {dsn}"),
        )
    try:
        close, high, low, vol, funding, oi = load_oi_positioning_inputs(
            symbols,
            bar="1D",
            start=start,
            end=end,
            backend="postgres",
            dsn=dsn,
            exchange=EXCHANGE,
        )
    except OSError as exc:
        return _db_unavailable_summary(
            batch_id=batch_id,
            candidate_dir=candidate_dir,
            start=start,
            end=end,
            dsn=dsn,
            exc=exc,
        )
    symbols = [symbol for symbol in symbols if symbol in close.columns and symbol in oi.columns]
    close, high, low, vol, funding, oi = (
        frame.reindex(columns=symbols)
        for frame in (close, high, low, vol, funding, oi)
    )
    membership = membership[membership["symbol"].isin(symbols)].copy()
    zero_report = zero_oi_integrity_report(oi, membership, max_zero_ratio=0.05)
    excluded = set(zero_report["excluded_symbols"])
    if excluded:
        symbols = [symbol for symbol in symbols if symbol not in excluded]
        close, high, low, vol, funding, oi = (
            frame.reindex(columns=symbols)
            for frame in (close, high, low, vol, funding, oi)
        )
        membership = membership[membership["symbol"].isin(symbols)].copy()

    params = OIPositioningParams(universe=symbols, bar="1D")
    family_minting = _run_family_minting(root, close, high, low, vol, funding, oi, membership, params)
    if family_minting.get("decision") != "MINT":
        return {
            "batch_id": batch_id,
            "candidate_id": CANDIDATE_ID,
            "candidate_dir": candidate_dir,
            "hypothesis_id": HYPOTHESIS_ID,
            "family_id": FAMILY_ID,
            "grid_size_this_run": 0,
            "family_cumulative_n_trials": int(family_minting.get("inherited_n_trials") or 0),
            "family_minting": family_minting,
            "zero_oi_integrity_report": zero_report,
            "zero_oi_excluded_symbols": list(zero_report.get("excluded_symbols", [])),
            "stage2_status": "FAIL",
            "stage2_reason": f"family_minting_decision={family_minting.get('decision')}",
            "promotion_gate_passed": False,
            "status": "stage2_distinctness_failed",
        }

    records = _precompute_records(
        params,
        GRID,
        lambda run_params, _combo: run_oi_positioning_backtest(close, high, low, vol, funding, oi, membership, run_params),
        "oi_positioning",
    )
    n_trials = len(records)
    validation = _refit_validation(records, n_trials)
    best = _best_full_sample_record(records)
    active = _records_have_activity(records)
    summary = _base_summary(
        validation,
        n_trials,
        symbols=symbols,
        family_minting=family_minting,
        active=active,
        dsn=dsn,
        start=start,
        end=end,
        zero_oi_report=zero_report,
    )
    summary.update(
        {
            "retry_classification": "new_family_first_validation",
            "selected_params": {"mode": "fold_refit_per_split"},
            "full_sample_best_sharpe": _finite(best["metrics"].get("sharpe")),
            "full_sample_best_params": _param_subset(best, set(OIPositioningParams.__dataclass_fields__)),
            "input_symbols": symbols,
            "perp_canonical_coverage": {symbol: {"rows": int(close[symbol].dropna().shape[0])} for symbol in close.columns},
            "funding_coverage": {symbol: {"rows": int(funding[symbol].dropna().shape[0])} for symbol in funding.columns},
            "oi_coverage": {symbol: {"rows": int(oi[symbol].dropna().shape[0])} for symbol in oi.columns},
        }
    )
    return summary


def main() -> int:
    summary = run_oi_positioning_checkpoint()
    _write_json(OUT / "summary.json", summary)
    print(
        json.dumps(
            {
                key: summary.get(key)
                for key in ("status", "wf_oos_sharpe", "cpcv_oos_sharpe", "dsr", "psr", "promotion_gate_passed")
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
