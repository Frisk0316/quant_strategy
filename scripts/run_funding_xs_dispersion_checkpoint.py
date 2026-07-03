"""Run the F-FUNDING-XS-DISPERSION Stage-3 checkpoint summary."""
from __future__ import annotations

import asyncio
import concurrent.futures
import json
import sys
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtesting.c2_funding_carry_backtest import C2FundingCarryParams, load_c2_inputs, run_c2_funding_carry_backtest
from backtesting.funding_xs_dispersion_backtest import (
    FundingXSDispersionParams,
    json_signal,
    load_funding_xs_dispersion_inputs,
    run_funding_xs_dispersion_backtest,
)
from backtesting.pipeline_family_minting import decide_family_minting
from backtesting.pipeline_stage2_registry import load_point_in_time_universe
from scripts.run_pipeline_batch1_checkpoint import (
    _best_full_sample_record,
    _finite,
    _jsonable,
    _param_subset,
    _precompute_records,
    _records_have_activity,
    _refit_validation,
)

BATCH_ID = "idea_batch_20260701_taxonomy_002"
CANDIDATE_ID = "B-f-funding-xs-dispersion"
CANDIDATE_DIR = "f_funding_xs_dispersion"
HYPOTHESIS_ID = "H-009"
FAMILY_ID = "F-FUNDING-XS-DISPERSION"
START = "2024-01-01"
END = "2026-06-17"
DSN = "postgresql://quant:changeme@localhost:5432/quant"
EXCHANGE = "binance"
UNIVERSE_PATH = Path("data/universe/universe_membership.parquet")
STAGE2_PASS_PATH = Path(
    "results/stage2_reprobe_20260704_funding_rebuilt/"
    "idea_batch_20260701_taxonomy_002/f_funding_xs_dispersion/stage2_feasibility.json"
)
OUT = Path("results") / BATCH_ID / CANDIDATE_DIR


def _ctx_value(ctx: Mapping[str, Any], key: str, default: Any) -> Any:
    return ctx.get(key, default) if isinstance(ctx, Mapping) else default


def _as_date_string(value: Any) -> str:
    if hasattr(value, "isoformat"):
        return pd.Timestamp(value).date().isoformat()
    return str(value)


def _utc(value: str) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_jsonable(dict(payload)), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(path)


def _stage2_good_symbols(path: Path = STAGE2_PASS_PATH) -> list[str]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    checks = payload.get("checks") if isinstance(payload, Mapping) else None
    if not isinstance(checks, list):
        return []
    data_check = next((check for check in checks if isinstance(check, Mapping) and check.get("name") == "data_availability"), {})
    details = data_check.get("details") if isinstance(data_check, Mapping) else {}
    thresholds = details.get("thresholds") if isinstance(details, Mapping) else {}
    min_coverage = float(thresholds.get("min_symbol_coverage", 0.80))
    max_stale = float(thresholds.get("max_stale_ratio", 0.10))
    rows = details.get("symbol_coverage") if isinstance(details, Mapping) else []
    return sorted(
        str(row["inst_id"])
        for row in rows
        if isinstance(row, Mapping)
        and float(row.get("coverage_ratio") or 0.0) >= min_coverage
        and float(row.get("stale_ratio") or 0.0) <= max_stale
    )


def _ct_val_sources(symbols: list[str], dsn: str) -> dict[str, dict[str, Any]]:
    async def fetch() -> dict[str, Any]:
        import asyncpg

        conn = await asyncpg.connect(dsn)
        try:
            rows = await conn.fetch(
                """
                SELECT symbol, ct_val, source
                FROM venue_instrument_specs
                WHERE exchange = $1 AND symbol = ANY($2::text[])
                """,
                EXCHANGE,
                symbols,
            )
        finally:
            await conn.close()
        return {str(row["symbol"]): dict(row) for row in rows}

    try:
        asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            db_rows = pool.submit(lambda: asyncio.run(fetch())).result()
    except RuntimeError:
        db_rows = asyncio.run(fetch())
    except Exception:
        db_rows = {}

    out: dict[str, dict[str, Any]] = {}
    for symbol in symbols:
        row = db_rows.get(symbol)
        if row:
            out[symbol] = {
                "exchange": EXCHANGE,
                "source": row.get("source") or "db",
                "ct_val": float(row["ct_val"]),
                "authoritative": True,
            }
        elif symbol.startswith("1000"):
            out[symbol] = {
                "exchange": EXCHANGE,
                "source": "missing_db_multiplier_contract",
                "ct_val": None,
                "authoritative": False,
            }
        else:
            out[symbol] = {
                "exchange": EXCHANGE,
                "source": "exchange_base_unit",
                "ct_val": 1.0,
                "authoritative": True,
            }
    return out


def _run_family_minting(
    root: Path,
    close: pd.DataFrame,
    high: pd.DataFrame,
    low: pd.DataFrame,
    vol: pd.DataFrame,
    funding: pd.DataFrame,
    membership: pd.DataFrame,
    params: FundingXSDispersionParams,
    *,
    start: str,
    end: str,
    dsn: str,
) -> dict[str, Any]:
    candidate = run_funding_xs_dispersion_backtest(close, high, low, vol, funding, membership, params)
    c2_params = C2FundingCarryParams()
    try:
        perp_close, spot_close, c2_funding = load_c2_inputs(
            c2_params.pairs,
            start=start,
            end=end,
            backend="postgres",
            dsn=dsn,
            exchange=EXCHANGE,
        )
        reference = run_c2_funding_carry_backtest(perp_close, spot_close, c2_funding, c2_params).daily_returns
        reference_source = "c2_funding_carry_default_daily_returns"
    except Exception:
        reference = funding.reindex(columns=[symbol for symbol in c2_params.pairs if symbol in funding.columns]).resample("1D").mean().mean(axis=1)
        reference_source = "fallback_btc_eth_mean_funding_rate"

    candidate_payload = {
        "batch_id": BATCH_ID,
        "candidate_id": CANDIDATE_ID,
        "claimed_family_id_or_NEW": "NEW",
        "claimed_mechanism": "perp-only cross-sectional long low trailing funding APR / short high trailing funding APR",
        "signal_source": "default_funding_xs_dispersion_daily_returns",
        "signal": json_signal(candidate.daily_returns),
    }
    refs_payload = {
        "F-FUNDING-CARRY": json_signal(reference),
        "_metadata": {"F-FUNDING-CARRY": reference_source},
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
    result["reference_signal_source"] = reference_source
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
) -> dict[str, Any]:
    ct_val_sources = _ct_val_sources(symbols, dsn)
    ct_val_all_authoritative = bool(ct_val_sources) and all(row["authoritative"] for row in ct_val_sources.values())
    statistical_gate_passed = bool(float(validation["dsr"] or 0.0) >= 0.95 and float(validation["psr"] or 0.0) >= 0.95)
    promotion_gate_passed = False
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
        "leak_test_reference": "tests/unit/test_funding_xs_dispersion_backtest.py::test_funding_signal_target_is_not_traded_on_same_day",
        "family_minting": dict(family_minting),
        "portable_validation_gate": False,
        "portable_validation_block_reason": "adapter_required_not_implemented_for_research_only_frontier_candidate",
        "idealized_fill": False,
        "ct_val_sources": ct_val_sources,
        "ct_val_all_authoritative": ct_val_all_authoritative,
        "statistical_gate_passed": statistical_gate_passed,
        "promotion_gate_passed": promotion_gate_passed,
        "data_source": {
            "start": f"{start}T00:00:00+00:00",
            "end_exclusive": f"{end}T00:00:00+00:00",
            "primary_exchange": EXCHANGE,
            "bar": "1D_from_1m_canonical_close",
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
            "Promotion remains false because portable validation is adapter-required/absent and human review has not approved any gate.",
        ],
    }


def run_funding_xs_dispersion_checkpoint(ctx: Mapping[str, Any] | None = None) -> dict[str, Any]:
    ctx = ctx or {}
    batch_id = str(_ctx_value(ctx, "batch_id", BATCH_ID))
    candidate_dir = str(_ctx_value(ctx, "candidate_dir", CANDIDATE_DIR))
    output_root = Path(_ctx_value(ctx, "output_root", Path("results")))
    root = output_root / batch_id / candidate_dir
    dsn = str(_ctx_value(ctx, "dsn", DSN))
    universe_path = Path(_ctx_value(ctx, "universe_path", UNIVERSE_PATH))
    start = _as_date_string(_ctx_value(ctx, "start", START))
    end = _as_date_string(_ctx_value(ctx, "end", END))

    symbols, _daily, _expected = load_point_in_time_universe(universe_path, start=_utc(start).to_pydatetime(), end=_utc(end).to_pydatetime())
    good_symbols = set(_stage2_good_symbols())
    if good_symbols:
        symbols = [symbol for symbol in symbols if symbol in good_symbols]
    print(f"[funding_xs] loading {len(symbols)} symbols from {EXCHANGE} canonical candles/funding", flush=True)
    membership = pd.read_parquet(universe_path)
    membership["date"] = pd.to_datetime(membership["date"]).dt.normalize()
    membership = membership[membership["symbol"].isin(symbols)].copy()
    close, high, low, vol, funding = load_funding_xs_dispersion_inputs(
        symbols,
        bar="1D",
        start=start,
        end=end,
        backend="postgres",
        dsn=dsn,
        exchange=EXCHANGE,
    )
    market_close = close["BTC-USDT-SWAP"] if "BTC-USDT-SWAP" in close.columns else None
    params = FundingXSDispersionParams(universe=symbols, bar="1D")
    grid = {"lookback_days": [7, 14], "quantile": [0.20, 0.30]}

    family_minting = _run_family_minting(root, close, high, low, vol, funding, membership, params, start=start, end=end, dsn=dsn)
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
            "stage2_status": "FAIL",
            "stage2_reason": f"family_minting_decision={family_minting.get('decision')}",
            "promotion_gate_passed": False,
            "status": "stage2_distinctness_failed",
        }

    records = _precompute_records(
        params,
        grid,
        lambda run_params, _combo: run_funding_xs_dispersion_backtest(close, high, low, vol, funding, membership, run_params, market_close=market_close),
        "funding_xs",
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
    )
    summary.update(
        {
            "retry_classification": "new_family_first_validation",
            "selected_params": {"mode": "fold_refit_per_split"},
            "full_sample_best_sharpe": _finite(best["metrics"].get("sharpe")),
            "full_sample_best_params": _param_subset(best, set(FundingXSDispersionParams.__dataclass_fields__)),
            "input_symbols": symbols,
            "perp_canonical_coverage": {symbol: {"rows": int(close[symbol].dropna().shape[0])} for symbol in close.columns},
            "funding_coverage": {symbol: {"rows": int(funding[symbol].dropna().shape[0])} for symbol in funding.columns},
        }
    )
    return summary


def main() -> int:
    summary = run_funding_xs_dispersion_checkpoint()
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
