"""H-038 one-off Stage-2 probe for the existing S5 implementation."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from backtesting.data_loader import load_candles
from backtesting.pipeline_checkpoint1 import family_registry_from_text
from backtesting.pipeline_feasibility import FeasibilityCheck, FeasibilityResult, result_to_dict
from backtesting.s5_residual_meanrev_backtest import run_s5_residual_meanrev_backtest
from backtesting.universe_aliases import collapse_same_asset_aliases
from okx_quant.strategies.s5_residual_meanrev import S5ResidualMeanReversionParams

BATCH_ID = "h038_stage2_e095"
START = datetime(2024, 1, 1, tzinfo=timezone.utc)
END = datetime(2026, 6, 17, tzinfo=timezone.utc)
EXCHANGE = "binance"
TOP_N = 20
EXPECTED_MINUTES_PER_DAY = 1_440
MIN_MEMBER_DAY_COVERAGE = 0.95
N_TRIALS = 72
FACTOR_SYMBOLS = ("BTC-USDT-SWAP", "ETH-USDT-SWAP")
OUTPUT_DIR = Path("results/h038_stage2_e095")
UNIVERSE_PATH = Path("data/universe/universe_membership.parquet")
E014_PATH = Path("results/pipeline_batch1_20260625_refit/s5/summary.json")
REGISTRY_PATH = Path("docs/EXPERIMENT_REGISTRY.md")
FROZEN_E014_PARAMS = {
    "factors": "BTC+ETH",
    "fee_bps": 2.0,
    "lookback_days": 14,
    "slippage_bps": 2.0,
    "top_n": 10,
    "z_enter": 1.5,
    "z_exit": 0.0,
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _series_sha256(values: Sequence[str]) -> str:
    return hashlib.sha256(("\n".join(values) + "\n").encode()).hexdigest()


def load_frozen_e014_params(path: Path = E014_PATH) -> tuple[S5ResidualMeanReversionParams, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("family_id") != "F-S5-RESIDUAL-MEANREV":
        raise ValueError(f"unexpected E-014 family_id in {path}")
    raw = payload.get("full_sample_best_params")
    if raw != FROZEN_E014_PARAMS:
        raise ValueError(f"E-014 frozen params changed: expected {FROZEN_E014_PARAMS}, got {raw}")
    params = S5ResidualMeanReversionParams(**raw)
    return params, {
        "source_experiment": "E-014",
        "source_path": path.as_posix(),
        "source_sha256": file_sha256(path),
        "source_field": "full_sample_best_params",
        "validated_frozen_values": dict(FROZEN_E014_PARAMS),
    }


def load_effective_membership(
    path: Path = UNIVERSE_PATH,
    *,
    start: datetime = START,
    end: datetime = END,
    top_n: int = TOP_N,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    frame = pd.read_parquet(path)
    required = {"date", "symbol", "eligible", "adv_usd"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"PIT membership missing columns: {sorted(missing)}")
    frame = frame.loc[frame["eligible"].astype(bool), list(required)].copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame["adv_usd"] = pd.to_numeric(frame["adv_usd"], errors="coerce")
    frame = frame.loc[
        (frame["date"] >= pd.Timestamp(start.date()))
        & (frame["date"] < pd.Timestamp(end.date()))
        & frame["adv_usd"].notna()
    ].sort_values(["date", "adv_usd", "symbol"], ascending=[True, False, True])
    selected = frame.groupby("date", sort=True).head(top_n)
    rows: list[dict[str, Any]] = []
    daily: list[dict[str, Any]] = []
    for day, group in selected.groupby("date", sort=True):
        raw = group["symbol"].astype(str).tolist()
        effective = collapse_same_asset_aliases(raw, exchange=EXCHANGE)
        first_adv: dict[str, float] = {}
        for symbol, adv in zip(raw, group["adv_usd"], strict=True):
            mapped = collapse_same_asset_aliases((symbol,), exchange=EXCHANGE)[0]
            first_adv.setdefault(mapped, float(adv))
        rows.extend(
            {"date": day, "symbol": symbol, "eligible": True, "adv_usd": first_adv[symbol]}
            for symbol in effective
        )
        daily.append(
            {
                "day": day.date().isoformat(),
                "raw_selected_count": len(raw),
                "effective_count": len(effective),
                "aliases_removed": len(raw) - len(effective),
            }
        )
    effective_frame = pd.DataFrame(rows)
    raw_member_days = len(selected)
    effective_member_days = len(effective_frame)
    return effective_frame, {
        "path": path.as_posix(),
        "sha256": file_sha256(path),
        "selection_order": "PIT eligible -> descending adv_usd top-20 -> Binance alias collapse",
        "no_rank_refill_after_alias_collapse": True,
        "raw_member_days": raw_member_days,
        "effective_member_days": effective_member_days,
        "alias_duplicate_member_days_removed": raw_member_days - effective_member_days,
        "universe_days": len(daily),
        "daily_selection_counts": daily,
    }


def load_source_aware_closes(
    symbols: Sequence[str],
    *,
    dsn: str,
    start: datetime = START,
    end: datetime = END,
) -> pd.DataFrame:
    closes: dict[str, pd.Series] = {}
    for symbol in symbols:
        candles = load_candles(
            symbol,
            bar="1m",
            start=start.isoformat(),
            end=end.isoformat(),
            backend="postgres",
            dsn=dsn,
            exchange=EXCHANGE,
        )
        closes[symbol] = candles["close"].astype(float).copy()
    return pd.DataFrame(closes)


async def _fetch_source_scoped_funding(
    dsn: str,
    symbols: Sequence[str],
    start: datetime = START,
    end: datetime = END,
) -> tuple[pd.DataFrame, dict[str, int]]:
    import asyncpg

    conn = await asyncpg.connect(dsn)
    try:
        rows = await conn.fetch(
            """
            SELECT inst_id, ts,
                   COALESCE(realized_rate, funding_rate)::double precision AS rate
            FROM funding_rates
            WHERE source=$1 AND inst_id=ANY($2::text[]) AND ts >= $3 AND ts < $4
            ORDER BY ts, inst_id
            """,
            EXCHANGE,
            list(symbols),
            start,
            end,
        )
    finally:
        await conn.close()
    frame = pd.DataFrame([dict(row) for row in rows])
    counts = {symbol: 0 for symbol in symbols}
    if frame.empty:
        return pd.DataFrame(columns=symbols), counts
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True).dt.tz_localize(None)
    counts.update({str(symbol): int(len(group)) for symbol, group in frame.groupby("inst_id")})
    return frame.pivot_table(index="ts", columns="inst_id", values="rate", aggfunc="last"), counts


def build_data_check(
    close: pd.DataFrame,
    membership: pd.DataFrame,
    membership_audit: Mapping[str, Any],
) -> FeasibilityCheck:
    counts = close.notna().resample("1D").sum()
    expected_keys: list[str] = []
    complete_keys: list[str] = []
    missing_rows: list[dict[str, Any]] = []
    by_symbol: dict[str, dict[str, int]] = {}
    daily_rows: list[dict[str, Any]] = []
    for day, group in membership.groupby("date", sort=True):
        symbols = group["symbol"].astype(str).tolist()
        complete = 0
        for symbol in symbols:
            key = f"{day.date().isoformat()}|{symbol}"
            expected_keys.append(key)
            bars = int(counts.at[day, symbol]) if day in counts.index and symbol in counts else 0
            stats = by_symbol.setdefault(symbol, {"expected_member_days": 0, "complete_member_days": 0})
            stats["expected_member_days"] += 1
            if bars == EXPECTED_MINUTES_PER_DAY:
                complete += 1
                complete_keys.append(key)
                stats["complete_member_days"] += 1
            else:
                missing_rows.append({"day": day.date().isoformat(), "symbol": symbol, "minute_rows": bars})
        daily_rows.append(
            {"day": day.date().isoformat(), "expected_members": len(symbols), "complete_members": complete}
        )
    expected_factor_days = pd.date_range(START.date(), END.date(), inclusive="left", freq="D")
    factor_missing = {
        symbol: (
            len(expected_factor_days)
            if symbol not in counts
            else int(
                counts[symbol]
                .reindex(expected_factor_days, fill_value=0)
                .ne(EXPECTED_MINUTES_PER_DAY)
                .sum()
            )
        )
        for symbol in FACTOR_SYMBOLS
    }
    expected = len(expected_keys)
    complete = len(complete_keys)
    coverage = complete / expected if expected else 0.0
    expected_days = (END.date() - START.date()).days
    passed = (
        expected > 0
        and coverage >= MIN_MEMBER_DAY_COVERAGE
        and int(membership_audit["universe_days"]) == expected_days
        and all(value == 0 for value in factor_missing.values())
    )
    return FeasibilityCheck(
        "data_availability",
        "PASS" if passed else "FAIL",
        f"source-aware PIT member-day completeness={complete}/{expected} ({coverage:.6f})",
        {
            "window": {"start": START.date().isoformat(), "end_exclusive": END.date().isoformat()},
            "candle_table": "canonical_candles_by_source",
            "candle_source_primary": EXCHANGE,
            "bar": "1m",
            "expected_minutes_per_member_day": EXPECTED_MINUTES_PER_DAY,
            "expected_member_days": expected,
            "complete_member_days": complete,
            "member_day_coverage": coverage,
            "required_member_day_coverage": MIN_MEMBER_DAY_COVERAGE,
            "required_member_day_coverage_provenance": {
                "precedent": "backtesting/taker_flow_probe.py::MIN_MEMBER_DAY_COVERAGE = 0.95",
                "invariant": "docs/INVARIANTS.md::I11 requires coverage >= 0.80",
                "authorization": "2026-08-04 user ruling authorizing E-095",
            },
            "missing_member_days": missing_rows,
            "expected_member_keys_sha256": _series_sha256(sorted(expected_keys)),
            "complete_member_keys_sha256": _series_sha256(sorted(complete_keys)),
            "per_symbol_reconciliation": by_symbol,
            "daily_reconciliation": daily_rows,
            "factor_missing_days": factor_missing,
            "required_factor_symbols": list(FACTOR_SYMBOLS),
            "membership": dict(membership_audit),
        },
    )


def derive_breadth(positions: pd.DataFrame, daily_returns: pd.Series) -> dict[str, Any]:
    daily_positions = positions.resample("1D").last()
    observed = daily_returns.dropna().index.intersection(daily_positions.index)
    counts = daily_positions.loc[observed].abs().gt(0.0).sum(axis=1).astype(int)
    measured = float(counts.mean()) if len(counts) else math.nan
    valid = bool(len(counts) and math.isfinite(measured) and measured > 0.0)
    return {
        "formula": "mean_d(count_i(abs(actual_position[d,i]) > 0)), aligned to daily return observations",
        "position_source": "BacktestResult.positions resampled by daily last",
        "n_daily_return_observations": len(observed),
        "input_nonzero_position_count_by_day": [
            {"day": day.date().isoformat(), "count": int(value)} for day, value in counts.items()
        ],
        "measured_mean_simultaneous_names": measured if math.isfinite(measured) else None,
        "breadth_used": measured if valid else 1.0,
        "fail_closed_to_one": not valid,
    }


def _not_evaluated_checks(
    *,
    breadth: float,
    n_obs: int,
    registry_trials: int,
    stop_point: str,
    stop_reason: str,
) -> tuple[FeasibilityCheck, FeasibilityCheck]:
    return (
        FeasibilityCheck(
            "cost_after_edge",
            "FAIL",
            f"NOT_EVALUATED: {stop_reason}",
            {
                "evaluation_status": "NOT_EVALUATED",
                "stop_point": stop_point,
                "roundtrip_cost_bps": 8.0,
                "one_way_fee_bps": 2.0,
                "one_way_slippage_bps": 2.0,
                "funding_source": EXCHANGE,
                "annualized_net_sharpe": None,
                "grid_trials_evaluated": 0,
            },
        ),
        FeasibilityCheck(
            "statistical_power",
            "FAIL",
            f"NOT_EVALUATED: {stop_reason}",
            {
                "evaluation_status": "NOT_EVALUATED",
                "stop_point": stop_point,
                "breadth": breadth,
                "n_obs": n_obs,
                "n_trials": registry_trials,
                "n_trials_provenance": "docs/EXPERIMENT_REGISTRY.md family cumulative",
                "periods_per_year": 365.0,
                "plausible_net_sharpe": None,
                "min_detectable_sharpe": None,
                "grid_trials_evaluated": 0,
            },
        ),
    )


def evaluate_probe(
    close: pd.DataFrame,
    funding: pd.DataFrame,
    membership: pd.DataFrame,
    membership_audit: Mapping[str, Any],
    *,
    e014_path: Path = E014_PATH,
    registry_path: Path = REGISTRY_PATH,
    funding_counts: Mapping[str, int] | None = None,
) -> FeasibilityResult:
    params, frozen_param_provenance = load_frozen_e014_params(e014_path)
    registry = family_registry_from_text(registry_path.read_text(encoding="utf-8"))
    registry_trials = registry["F-S5-RESIDUAL-MEANREV"].cumulative_n_trials
    if registry_trials != N_TRIALS:
        raise ValueError(f"F-S5 registry cumulative n_trials must equal {N_TRIALS}, got {registry_trials}")
    data = build_data_check(close, membership, membership_audit)
    data.details.update(
        {
            "s5_parameters": asdict(params),
            "frozen_parameter_provenance": frozen_param_provenance,
            "funding_source": EXCHANGE,
            "funding_rows_by_symbol": dict(funding_counts or {}),
        }
    )
    if data.status != "PASS":
        checks = (
            data,
            FeasibilityCheck("distinctness", "FAIL", "NOT_EVALUATED: data availability failed", {"evaluation_status": "NOT_EVALUATED", "correlation": None, "common_days": 0}),
            *_not_evaluated_checks(
                breadth=1.0,
                n_obs=0,
                registry_trials=registry_trials,
                stop_point="data_availability",
                stop_reason="data availability failed",
            ),
        )
        return FeasibilityResult(BATCH_ID, "H-038", ".", "H-038", "F-S5-RESIDUAL-MEANREV", checks)

    backtest = run_s5_residual_meanrev_backtest(close, funding, membership, params)
    breadth = derive_breadth(backtest.positions, backtest.daily_returns)
    data.details["breadth_derivation"] = breadth
    e014 = json.loads(e014_path.read_text(encoding="utf-8"))
    candidate_returns = backtest.daily_returns.dropna()
    distinctness = FeasibilityCheck(
        "distinctness",
        "FAIL",
        "UNCONFIRMED: E-014 retains no dated return series, so required correlation is undefined",
        {
            "required_reference": "E-014/F-S5-RESIDUAL-MEANREV",
            "reference_path": e014_path.as_posix(),
            "reference_sha256": file_sha256(e014_path),
            "reference_nonzero_grid_activity": e014.get("nonzero_grid_activity"),
            "reference_dated_return_series_present": False,
            "abs_correlation": None,
            "common_days": 0,
            "undefined_correlation_fails_closed": True,
            "candidate_daily_returns": [
                {"day": day.date().isoformat(), "return": float(value)}
                for day, value in candidate_returns.items()
                if math.isfinite(float(value))
            ],
        },
    )
    cost, power = _not_evaluated_checks(
        breadth=float(breadth["breadth_used"]),
        n_obs=int(breadth["n_daily_return_observations"]),
        registry_trials=registry_trials,
        stop_point="distinctness",
        stop_reason="distinctness failed on the missing dated E-014 family reference",
    )
    return FeasibilityResult(
        BATCH_ID,
        "H-038",
        ".",
        "H-038",
        "F-S5-RESIDUAL-MEANREV",
        (data, distinctness, cost, power),
    )


async def probe_s5_residual_meanrev(_conn: Any, ctx: Mapping[str, Any]) -> FeasibilityResult:
    """Uniform registry adapter; the one-off CLI owns the immutable DB run."""

    return evaluate_probe(
        ctx["close"],
        ctx["funding"],
        ctx["membership"],
        ctx["membership_audit"],
        e014_path=Path(ctx.get("e014_path", E014_PATH)),
        registry_path=Path(ctx.get("registry_path", REGISTRY_PATH)),
        funding_counts=ctx.get("funding_counts"),
    )


def write_artifact(result: FeasibilityResult, output_dir: Path = OUTPUT_DIR) -> tuple[Path, str]:
    path = output_dir / "stage2_feasibility.json"
    hash_path = output_dir / "sha256.json"
    if path.exists() or hash_path.exists():
        raise FileExistsError(f"refusing to overwrite immutable H-038 artifact: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result_to_dict(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    digest = file_sha256(path)
    hash_path.write_text(json.dumps({path.name: digest}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path, digest


def build_breadth_provenance(stage2_path: Path) -> dict[str, Any]:
    payload = json.loads(stage2_path.read_text(encoding="utf-8"))
    checks = {check["name"]: check for check in payload["checks"]}
    data = checks["data_availability"]
    power = checks["statistical_power"]
    missing = data["details"]["missing_member_days"]
    if data["status"] != "FAIL" or power["details"].get("stop_point") != "data_availability":
        raise ValueError("breadth fail-closed provenance requires a data-availability stop")
    if power["details"].get("breadth") != 1.0 or power["details"].get("n_obs") != 0:
        raise ValueError("parent artifact must fail closed to breadth=1 with n_obs=0")
    if len(missing) != 1:
        raise ValueError(f"expected exactly one H-038 data gap, got {len(missing)}")
    return {
        "schema_version": 1,
        "kind": "h038_breadth_fail_closed_provenance",
        "parent_artifact": {
            "path": stage2_path.as_posix(),
            "sha256": file_sha256(stage2_path),
        },
        "stop_point": "data_availability",
        "reason": "strict 100% PIT member-day completeness failed before an admissible backtest",
        "formula": "mean_d(count_i(abs(actual_position[d,i]) > 0)), aligned to daily return observations",
        "position_source": "BacktestResult.positions resampled by daily last",
        "positions_present": False,
        "input_nonzero_position_count_by_day": [],
        "measured_mean_simultaneous_names": None,
        "breadth_used": 1.0,
        "fail_closed_to_one": True,
        "n_obs": 0,
        "data_gap": missing[0],
    }


def write_breadth_provenance(
    stage2_path: Path = OUTPUT_DIR / "stage2_feasibility.json",
    output_dir: Path = OUTPUT_DIR,
) -> tuple[Path, str, Path]:
    path = output_dir / "breadth_provenance.json"
    hash_path = output_dir / "breadth_provenance.sha256.json"
    if path.exists() or hash_path.exists():
        raise FileExistsError(f"refusing to overwrite immutable H-038 breadth provenance: {output_dir}")
    payload = build_breadth_provenance(stage2_path)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    digest = file_sha256(path)
    hash_path.write_text(json.dumps({path.name: digest}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path, digest, hash_path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", default=os.environ.get("DATABASE_URL", ""))
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args(argv)
    if not args.dsn:
        parser.error("--dsn or DATABASE_URL is required")
    membership, audit = load_effective_membership()
    symbols = sorted(set(membership["symbol"].astype(str)) | set(FACTOR_SYMBOLS))
    print(f"loading {len(symbols)} source-aware 1m Binance candle series", flush=True)
    close = load_source_aware_closes(symbols, dsn=args.dsn)
    funding, funding_counts = asyncio.run(_fetch_source_scoped_funding(args.dsn, symbols))
    result = evaluate_probe(close, funding, membership, audit, funding_counts=funding_counts)
    path, digest = write_artifact(result, args.output_dir)
    print(f"{path.as_posix()} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
