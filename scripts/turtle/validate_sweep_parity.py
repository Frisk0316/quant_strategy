from __future__ import annotations

import argparse
import asyncio
import contextlib
import importlib.util
import io
import math
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from backtesting.turtle_backtest import SWEEP_COLUMNS, TurtleParams, run_turtle_sweep

REF_PARAMS = TurtleParams(
    enter_term_sys1=20,
    enter_term_sys2=55,
    leave_term_sys1=10,
    leave_term_sys2=20,
    own_capital=10_000.0,
    invest_pct=0.25,
    min_position=0.0001,
    fee=0.003,
    atr_period=20,
    single_sys_unit_limit=4,
    both_sys_unit_limit=4,
)
REF_GRID = {
    "enter_term_sys1": "6~30",
    "enter_term_sys2": 55,
    "leave_term_sys1": "5~19",
    "leave_term_sys2": 20,
}
KEY_COLUMNS = ("enter_term_sys1", "enter_term_sys2", "leave_term_sys1", "leave_term_sys2")
INT_COLUMNS = {
    *KEY_COLUMNS,
    "s1_max_consec_win",
    "s1_max_consec_loss",
    "s2_max_consec_win",
    "s2_max_consec_loss",
    "overall_max_consec_win",
    "overall_max_consec_loss",
    "final_win_count",
    "final_loss_count",
}


def _reference_module() -> Any:
    ref_dir = next(PROJECT_ROOT.glob("new_startegy_*"), None)
    if ref_dir is None:
        raise SystemExit("BLOCKED: reference directory new_startegy_* not found")
    path = ref_dir / "trading_target_func.py"
    try:
        spec = importlib.util.spec_from_file_location("turtle_reference", path)
        if spec is None or spec.loader is None:
            raise SystemExit(f"BLOCKED: cannot load reference module from {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except ModuleNotFoundError as exc:
        raise SystemExit(f"BLOCKED: reference dependency missing: {exc.name}") from exc


def _read_daily_csv(path: Path, start: str | None = None, end: str | None = None) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "date" not in df.columns:
        raise SystemExit(f"{path} must contain a date column")
    df = df.loc[:, ["date", "open", "high", "low", "close"]].copy()
    df["date"] = pd.to_datetime(df["date"], utc=True).dt.tz_localize(None)
    if start:
        df = df[df["date"] >= pd.Timestamp(start)]
    if end:
        df = df[df["date"] < pd.Timestamp(end)]
    return df.reset_index(drop=True)


def _to_polars_daily(daily: pd.DataFrame) -> Any:
    try:
        import polars as pl
    except ModuleNotFoundError as exc:
        raise SystemExit("BLOCKED: reference dependency missing: polars") from exc
    return pl.DataFrame({col: daily[col].to_list() for col in ["date", "open", "high", "low", "close"]})


def _reference_rows(daily: pd.DataFrame) -> list[dict[str, Any]]:
    ref = _reference_module()
    daily_pl = _to_polars_daily(daily)
    rows: list[dict[str, Any]] = []
    for enter1 in range(6, 31):
        for leave1 in range(5, 20):
            combo = {
                "enter_term_sys1": enter1,
                "enter_term_sys2": 55,
                "leave_term_sys1": leave1,
                "leave_term_sys2": 20,
            }
            if not (enter1 > leave1):
                continue
            with contextlib.redirect_stdout(io.StringIO()):
                result_df = ref.turtle_trading_system_full(daily_pl, **{**asdict(REF_PARAMS), **combo})
            whole_asset = result_df["whole_asset"]
            all_asset = REF_PARAMS.own_capital + whole_asset
            s1_outcomes = ref.get_outcomes_single(result_df, "s1")
            s2_outcomes = ref.get_outcomes_single(result_df, "s2")
            overall_outcomes = ref.get_outcomes_overall_v2(result_df)
            rows.append(
                {
                    **combo,
                    "win_rate": ref.calc_win_rate_full(result_df),
                    "profit_loss_ratio": ref.calc_profit_loss_ratio_full(result_df),
                    "expectancy": ref.calc_expectancy_full(result_df),
                    "mdd": ref.calc_mdd(all_asset, filter_zero=True),
                    "final_whole_asset": float(whole_asset[-1]),
                    "positive_rate": ref.calc_whole_asset_stats(whole_asset)[0],
                    "median_asset": ref.calc_whole_asset_stats(whole_asset)[1],
                    "mean_asset": ref.calc_whole_asset_stats(whole_asset)[2],
                    "s1_return_median": result_df["s1_trade_return"].median(),
                    "s1_return_mean": result_df["s1_trade_return"].mean(),
                    "s2_return_median": result_df["s2_trade_return"].median(),
                    "s2_return_mean": result_df["s2_trade_return"].mean(),
                    "s1_max_consec_win": ref.max_consecutive(s1_outcomes, 1),
                    "s1_max_consec_loss": ref.max_consecutive(s1_outcomes, 0),
                    "s2_max_consec_win": ref.max_consecutive(s2_outcomes, 1),
                    "s2_max_consec_loss": ref.max_consecutive(s2_outcomes, 0),
                    "overall_max_consec_win": ref.max_consecutive(overall_outcomes, 1),
                    "overall_max_consec_loss": ref.max_consecutive(overall_outcomes, 0),
                    "final_win_count": int(result_df["cumulative_win_count"][-1]),
                    "final_loss_count": int(result_df["cumulative_loss_count"][-1]),
                    "min_equity": float(result_df["equity"].min()),
                    "min_realized_pnl": float(result_df["realized_pnl"].min()),
                    "final_equity": result_df["equity"][-1],
                }
            )
    return rows


def _port_rows(daily: pd.DataFrame) -> list[dict[str, Any]]:
    summary = run_turtle_sweep(daily, REF_GRID, REF_PARAMS)
    return [{col: row.get(col) for col in SWEEP_COLUMNS} for row in summary["rows"]]


def _key(row: dict[str, Any]) -> tuple[int, int, int, int]:
    return tuple(int(float(row[col])) for col in KEY_COLUMNS)  # type: ignore[return-value]


def _float(value: Any) -> float:
    if value is None or value == "":
        return float("nan")
    return float(value)


def _compare_rows(
    left: list[dict[str, Any]],
    right: list[dict[str, Any]],
    *,
    left_name: str,
    right_name: str,
) -> list[str]:
    right_by_key = {_key(row): row for row in right}
    mismatches: list[str] = []
    for left_row in left:
        key = _key(left_row)
        right_row = right_by_key.get(key)
        if right_row is None:
            mismatches.append(f"{key}: missing in {right_name}")
            continue
        for col in SWEEP_COLUMNS:
            lv = left_row.get(col)
            rv = right_row.get(col)
            if col in INT_COLUMNS:
                if int(float(lv)) != int(float(rv)):
                    mismatches.append(f"{key} {col}: {left_name}={lv} {right_name}={rv}")
                continue
            lf = _float(lv)
            rf = _float(rv)
            if math.isnan(lf) and math.isnan(rf):
                continue
            if not math.isclose(lf, rf, rel_tol=1e-9, abs_tol=1e-9):
                mismatches.append(f"{key} {col}: {left_name}={lf:.12g} {right_name}={rf:.12g}")
    return mismatches


def _print_result(label: str, mismatches: list[str]) -> bool:
    if not mismatches:
        print(f"PASS {label}: all {len(SWEEP_COLUMNS)} columns match")
        return True
    print(f"FAIL {label}: {len(mismatches)} mismatches")
    for item in mismatches[:5]:
        print(f"  {item}")
    return False


def _read_result_csv(path: Path) -> list[dict[str, Any]]:
    return pd.read_csv(path).loc[:, list(SWEEP_COLUMNS)].to_dict("records")


def _dsn_from_config() -> str | None:
    if os.getenv("DATABASE_URL"):
        return os.getenv("DATABASE_URL")
    try:
        import yaml

        cfg = yaml.safe_load((PROJECT_ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))
        return ((cfg or {}).get("storage") or {}).get("timescale_dsn")
    except Exception:
        return None


async def _db_daily(args: argparse.Namespace) -> pd.DataFrame:
    import asyncpg

    dsn = args.dsn or _dsn_from_config()
    if not dsn:
        raise SystemExit("BLOCKED: --dsn or DATABASE_URL/config storage.timescale_dsn is required")
    conn = await asyncpg.connect(dsn)
    try:
        for bar in ("1m", "1D"):
            row = await conn.fetchrow(
                """
                SELECT MIN(ts) AS first_ts, MAX(ts) AS last_ts, COUNT(*) AS rows
                FROM canonical_candles
                WHERE inst_id=$1 AND bar=$2 AND source_primary=$3
                  AND quality_status != 'suspect'
                """,
                args.symbol,
                bar,
                args.source_primary,
            )
            print(f"DB coverage {bar}: first={row['first_ts']} last={row['last_ts']} rows={row['rows']}")
        rows_1m = await _fetch_candles(conn, args, "1m")
        rows_1d = await _fetch_candles(conn, args, "1D")
    finally:
        await conn.close()
    daily_1m = _resample_1m(rows_1m)
    daily_1d = _rows_to_daily(rows_1d)
    if not daily_1m.empty and not daily_1d.empty:
        _report_daily_overlap(daily_1m, daily_1d)
    if daily_1m.empty and not daily_1d.empty:
        print("Using DB 1D because no DB 1m rows were returned for this range.")
        return daily_1d
    return daily_1m


async def _fetch_candles(conn: Any, args: argparse.Namespace, bar: str) -> list[dict[str, Any]]:
    clauses = [
        "inst_id=$1",
        "bar=$2",
        "source_primary=$3",
        "quality_status != 'suspect'",
    ]
    params: list[Any] = [args.symbol, bar, args.source_primary]
    if args.start:
        params.append(pd.Timestamp(args.start).to_pydatetime())
        clauses.append(f"ts >= ${len(params)}")
    if args.end:
        params.append(pd.Timestamp(args.end).to_pydatetime())
        clauses.append(f"ts < ${len(params)}")
    rows = await conn.fetch(
        f"""
        SELECT ts, open, high, low, close, COALESCE(vol_quote, vol_base, vol_contract, 0) AS vol
        FROM canonical_candles
        WHERE {" AND ".join(clauses)}
        ORDER BY ts
        """,
        *params,
    )
    return [dict(row) for row in rows]


def _rows_to_daily(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close"])
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["ts"], utc=True).dt.tz_localize(None)
    return df.loc[:, ["date", "open", "high", "low", "close"]]


def _resample_1m(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close"])
    df = pd.DataFrame(rows)
    df["ts"] = pd.to_datetime(df["ts"], utc=True).dt.tz_localize(None)
    resampled = df.set_index("ts").resample("1D", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "vol": "sum"}
    )
    resampled = resampled.dropna(subset=["open", "close"]).reset_index().rename(columns={"ts": "date"})
    return resampled.loc[:, ["date", "open", "high", "low", "close"]]


def _report_daily_overlap(left: pd.DataFrame, right: pd.DataFrame) -> None:
    merged = left.merge(right, on="date", suffixes=("_1m", "_1d"))
    if merged.empty:
        print("DB 1m-vs-1D overlap: none")
        return
    diffs = []
    for col in ("open", "high", "low", "close"):
        mism = ~np.isclose(merged[f"{col}_1m"], merged[f"{col}_1d"], rtol=1e-9, atol=1e-9)
        diffs.append(int(mism.sum()))
    print(f"DB 1m-vs-1D overlap days={len(merged)} OHLC mismatches={dict(zip(('open','high','low','close'), diffs))}")
    if any(diffs):
        row = merged.loc[
            ~np.isclose(merged["close_1m"], merged["close_1d"], rtol=1e-9, atol=1e-9)
        ].head(1)
        if not row.empty:
            print(f"Sample OHLC mismatch: {row.iloc[0].to_dict()}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-csv")
    parser.add_argument("--input-csv")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--dsn")
    parser.add_argument("--symbol", default="BTC-USDT-SWAP")
    parser.add_argument("--source-primary", default="binance")
    parser.add_argument("--fixture", default=str(PROJECT_ROOT / "tests" / "fixtures" / "turtle" / "daily_ohlc.csv"))
    args = parser.parse_args()

    daily = (
        _read_daily_csv(Path(args.input_csv), args.start, args.end)
        if args.input_csv
        else asyncio.run(_db_daily(args))
        if args.reference_csv
        else _read_daily_csv(Path(args.fixture), args.start, args.end)
    )
    print(f"Daily input: rows={len(daily)} first={daily['date'].min()} last={daily['date'].max()}")
    reference = _reference_rows(daily)
    port = _port_rows(daily)

    if args.reference_csv:
        user_rows = _read_result_csv(Path(args.reference_csv))
        fingerprint_ok = _print_result(
            "Tier B fingerprint reference-vs-user-csv",
            _compare_rows(reference, user_rows, left_name="reference", right_name="user_csv"),
        )
        if not fingerprint_ok:
            if not daily.empty:
                print(f"Sample synthesized first day OHLC: {daily.head(1).to_dict('records')[0]}")
                print(f"Sample synthesized last day OHLC: {daily.tail(1).to_dict('records')[0]}")
            print("STOP: user CSV input was not reproduced; mismatch is data, not the pandas port.")
            return 1
        return 0 if _print_result(
            "Tier B port-vs-user-csv",
            _compare_rows(port, user_rows, left_name="port", right_name="user_csv"),
        ) else 1

    return 0 if _print_result(
        "Tier A reference-vs-port",
        _compare_rows(reference, port, left_name="reference", right_name="port"),
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
