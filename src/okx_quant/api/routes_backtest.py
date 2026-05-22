"""
Backtest results REST endpoints.
Scans results/ directory for run subdirectories containing result.json.
Each result.json matches the artifacts schema produced by backtesting/artifacts.py.
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backtesting.parameter_sweep import (
    ParameterSweepError,
    estimate_sweep_runtime,
    expand_parameter_grid,
    run_parameter_sweep,
)
from backtesting.research_controls import ResearchControlError, sanitize_risk_overrides
from okx_quant.core.symbols import normalize_spot_symbol, normalize_swap_symbol

_run_jobs: dict[str, dict[str, Any]] = {}
_sweep_jobs: dict[str, dict[str, Any]] = {}


def _dsn_reachable(dsn: str, timeout: float = 1.5) -> bool:
    """Best-effort TCP probe that the DSN's host:port accepts connections.

    A full `asyncpg.connect()` would be authoritative but is slow when the DB
    is down (TCP retries can take 5–30s). A simple TCP-level probe is fast and
    catches the common "DB process not running" case which the docs/handoff
    treat as the trigger for parquet fallback.
    """
    import socket
    from urllib.parse import urlparse

    try:
        parsed = urlparse(dsn)
        host = parsed.hostname or "localhost"
        port = parsed.port or 5432
    except Exception:
        return False
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False


def _resolve_candle_backend() -> tuple[str, str | None]:
    """Resolve the candle backend the backtest subprocesses should use.

    Returns (backend, dsn). Prefers `cfg.storage.candle_backend` from
    config/settings.yaml. Falls back to parquet when the DSN is missing OR
    unreachable so backtests don't crash on ConnectionRefusedError when the
    DB process is not running.
    """
    backend = "parquet"
    dsn: str | None = None
    try:
        from okx_quant.core.config import load_config

        cfg = load_config(require_secrets=False)
        backend = (getattr(cfg.storage, "candle_backend", "parquet") or "parquet").lower()
        dsn = getattr(cfg.storage, "timescale_dsn", None)
    except Exception:
        pass
    if not dsn:
        dsn = os.environ.get("DATABASE_URL")
    if backend == "postgres":
        if not dsn or not _dsn_reachable(dsn):
            backend = "parquet"
            dsn = None
    return backend, dsn


_SAFE_DATA_DIR_RE = re.compile(r"^[\w./\-]+$")
_SAFE_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2})?$")
_SAFE_SYMBOL_RE = re.compile(r"^[A-Z0-9\-]+$")
_ALLOWED_EXCHANGES = {"binance", "okx", "bybit", "coinbase", "kraken"}


def _normalize_exchange(value: str | None) -> str:
    """Validate the per-run exchange selection against the allowed set.

    Falls back to cfg.storage.primary_exchange when the input is missing or
    not whitelisted, so a stale frontend can't ask for a non-existent venue.
    """
    candidate = (value or "").strip().lower()
    if candidate in _ALLOWED_EXCHANGES:
        return candidate
    try:
        from okx_quant.core.config import load_config
        cfg = load_config(require_secrets=False)
        cfg_value = (getattr(cfg.storage, "primary_exchange", None) or "binance").lower()
    except Exception:
        cfg_value = "binance"
    return cfg_value if cfg_value in _ALLOWED_EXCHANGES else "binance"
DEFAULT_DAILY_WINNER_UNIVERSE = [
    "BTC-USDT-SWAP",
    "ETH-USDT-SWAP",
    "BNB-USDT-SWAP",
    "SOL-USDT-SWAP",
    "XRP-USDT-SWAP",
    "ADA-USDT-SWAP",
    "DOGE-USDT-SWAP",
    "LINK-USDT-SWAP",
    "AVAX-USDT-SWAP",
    "DOT-USDT-SWAP",
    "LTC-USDT-SWAP",
    "SHIB-USDT-SWAP",
]


class RunBacktestRequest(BaseModel):
    strategy: str
    symbols: list[str] = []
    symbol_x: str | None = None
    symbol_y: str | None = None
    perp_symbol: str | None = None
    spot_symbol: str | None = None
    min_apr_threshold: float | None = None
    bar: str = "1H"
    periods: int | None = None
    start: str | None = None
    end: str | None = None
    run_id: str | None = None
    validation: str | None = Field(default=None, alias="validate")
    # Exchange whose data the backtest should consume. Must match the live-target
    # exchange for deployment promotion (see ai_collaboration.md deployment gates).
    exchange: str | None = None
    universe: list[str] = []
    benchmark: str = "BTC-USDT-SWAP"
    rebalance_minutes: int = 60
    top_k: int = 3
    rank_exit_buffer: int = 6
    initial_equity: float = 5000.0
    data_dir: str = "data/ticks"
    strategy_params: dict[str, Any] = Field(default_factory=dict)
    risk_overrides: dict[str, Any] = Field(default_factory=dict)


class ParameterSweepRequest(BaseModel):
    strategy: str
    symbols: list[str] = []
    bar: str = "1H"
    periods: int | None = None
    start: str | None = None
    end: str | None = None
    sweep_id: str | None = None
    exchange: str | None = None
    initial_equity: float = 5000.0
    data_dir: str = "data/ticks"
    parameter_grid: dict[str, Any] = Field(default_factory=dict)
    max_combinations: int = Field(default=5000, ge=1, le=10000)
    liquidate_on_end: bool | None = None
    risk_overrides: dict[str, Any] = Field(default_factory=dict)
    run_finalists: bool = True
    finalist_top_pct: float = Field(default=0.10, gt=0.0, le=1.0)
    max_finalists: int = Field(default=20, ge=0, le=100)
    finalist_validation: str | None = None


def _run_ohlcv_rotation_job(
    job_id: str,
    req: "RunBacktestRequest",
    run_id: str,
    results_dir: Path,
) -> None:
    try:
        script = PROJECT_ROOT / "scripts" / "backtest_ohlcv_rotation.py"
        out_dir = results_dir / run_id
        out_dir.mkdir(parents=True, exist_ok=True)
        bar = req.bar or "1H"

        backend, dsn = _resolve_candle_backend()
        exchange = _normalize_exchange(req.exchange)
        benchmark = req.benchmark or "BTC-USDT-SWAP"

        if backend == "parquet":
            # Pre-validate parquet availability for benchmark + universe.
            data_dir = _resolve_data_dir(req.data_dir)
            _BAR_RESAMPLE = {"1H", "2H", "4H", "6H", "12H", "1D"}
            missing: list[str] = []
            for inst in list(req.universe or []) + [benchmark]:
                inst_dir = data_dir / inst.replace("-", "_")
                has_bar = (inst_dir / f"candles_{bar}.parquet").exists()
                has_1m = (inst_dir / "candles_1m.parquet").exists()
                can_derive = bar in _BAR_RESAMPLE and has_1m
                if not has_bar and not can_derive:
                    available = sorted(p.name for p in inst_dir.glob("candles_*.parquet")) if inst_dir.exists() else []
                    missing.append(f"{inst}: no candles_{bar}.parquet — available: {available or 'none'}")
            if any(benchmark in m for m in missing):
                _run_jobs[job_id].update({
                    "status": "error",
                    "progress": 100,
                    "message": f"Data not available for benchmark '{benchmark}' at bar='{bar}'",
                    "output": "\n".join(missing),
                })
                return

        cmd = [
            sys.executable,
            str(script),
            "--backend", backend,
            "--data-dir", req.data_dir or "data/ticks",
            "--bar", bar,
            "--benchmark", benchmark,
            "--rebalance-minutes", str(req.rebalance_minutes or 60),
            "--top-k", str(req.top_k or 3),
            "--rank-exit-buffer", str(req.rank_exit_buffer or 6),
            "--initial-equity", str(req.initial_equity or 5000.0),
            "--output-dir", str(out_dir),
            "--universe",
        ] + list(req.universe or [])
        if backend == "postgres" and dsn:
            cmd.extend(["--dsn", dsn])
        cmd.extend(["--exchange", exchange])
        if req.start:
            cmd.extend(["--start", req.start])
        if req.end:
            cmd.extend(["--end", req.end])

        _run_jobs[job_id].update({
            "status": "running",
            "progress": 20,
            "message": "Running OHLCV rotation backtest (loading data…)",
            "command": " ".join(cmd),
        })
        env = os.environ.copy()
        env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
        _run_jobs[job_id]["progress"] = 30
        proc = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            env=env,
            text=True,
            capture_output=True,
        )
        _run_jobs[job_id]["progress"] = 80
        output = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
        if proc.returncode != 0:
            _run_jobs[job_id].update({
                "status": "error",
                "progress": 100,
                "message": f"Backtest failed with exit code {proc.returncode}",
                "output": output[-4000:],
            })
            return
        _run_jobs[job_id].update({"progress": 90, "message": "Post-processing results…"})
        _post_process_ohlcv_rotation(out_dir, run_id, req)
        _run_jobs[job_id].update({
            "status": "done",
            "progress": 100,
            "message": "Backtest complete",
            "output": output[-4000:],
        })
    except Exception as exc:
        _run_jobs[job_id].update({
            "status": "error",
            "progress": 100,
            "message": str(exc),
        })


def _post_process_ohlcv_rotation(
    out_dir: Path,
    run_id: str,
    req: "RunBacktestRequest",
) -> None:
    """Convert ohlcv_rotation script outputs into ADR-0002 result.json + derived CSVs."""
    summary_path = out_dir / "summary.json"
    equity_path = out_dir / "equity_curve.csv"
    if not summary_path.exists():
        return
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    metrics = {k: v for k, v in summary.items() if k != "run_id"}
    trade_count = metrics.get("number_of_trades", 0)
    metrics.setdefault("order_count", trade_count)
    metrics.setdefault("fill_count", trade_count)
    metrics.setdefault("fill_rate", 1.0 if trade_count else 0.0)
    metrics.setdefault("bankrupt", False)

    if equity_path.exists():
        eq_df = pd.read_csv(equity_path, index_col=0, parse_dates=True)
        if "equity" in eq_df.columns:
            eq_df["return"] = eq_df["equity"].pct_change().fillna(0.0)
            returns_df = pd.DataFrame(index=eq_df.index)
            returns_df["datetime"] = eq_df.index.astype(str)
            returns_df["return"] = eq_df["return"]
            returns_df["log_return"] = pd.Series(
                pd.NA,
                index=eq_df.index,
                dtype="Float64",
            )
            positive = returns_df["return"] > -1
            returns_df.loc[positive, "log_return"] = (1 + returns_df.loc[positive, "return"]).map(
                lambda v: pd.NA if pd.isna(v) else math.log(v)
            )
            returns_df.index.name = "ts"
            returns_df.to_csv(out_dir / "returns.csv")

            if "drawdown" not in eq_df.columns:
                running_max = eq_df["equity"].cummax()
                denominator = running_max.where(running_max != 0)
                eq_df["drawdown"] = ((eq_df["equity"] - running_max) / denominator).fillna(0.0)
            else:
                running_max = eq_df["equity"].cummax()

            drawdown_df = pd.DataFrame(index=eq_df.index)
            drawdown_df["datetime"] = eq_df.index.astype(str)
            drawdown_df["equity"] = eq_df["equity"]
            drawdown_df["running_max_equity"] = running_max
            drawdown_df["drawdown"] = eq_df["drawdown"].fillna(0.0)
            drawdown_df["drawdown_pct"] = drawdown_df["drawdown"]
            drawdown_df.index.name = "ts"
            drawdown_df.to_csv(out_dir / "drawdown.csv")

    artifact_refs = {
        key: filename
        for key, filename in {
            "equity": "equity_curve.csv",
            "returns": "returns.csv",
            "drawdown": "drawdown.csv",
            "trades": "trades.csv",
            "positions": "positions.csv",
            "target_weights": "target_weights.csv",
            "summary": "summary.json",
        }.items()
        if (out_dir / filename).exists()
    }

    result = {
        "run_id": run_id,
        "created_at": pd.Timestamp.utcnow().isoformat(),
        "strategies": ["ohlcv_rotation"],
        "symbols": req.universe or [],
        "bar": req.bar or "1H",
        "start": req.start or "",
        "end": req.end or "",
        "metrics": metrics,
        "artifacts": artifact_refs,
    }
    (out_dir / "result.json").write_text(
        json.dumps(result, allow_nan=False, indent=2),
        encoding="utf-8",
    )


def _run_daily_winner_job(
    job_id: str,
    req: "RunBacktestRequest",
    run_id: str,
    results_dir: Path,
) -> None:
    # VALIDATION-ONLY: not a deployable alpha strategy. Intentional deviations from ADR-0002:
    # trades schema omits standard fills columns; fee model is None; Postgres-only (no parquet
    # fallback); no WF/CPCV. Do not "fix" these to conform with production strategy schemas.
    # See docs/ai_collaboration.md § 驗證專用策略.
    try:
        from backtesting.daily_winner_backtest import DailyWinnerParams, run_daily_winner_backtest
        from backtesting.data_loader import load_candles

        out_dir = results_dir / run_id
        out_dir.mkdir(parents=True, exist_ok=True)
        universe = list(dict.fromkeys(req.universe or DEFAULT_DAILY_WINNER_UNIVERSE))
        dsn = os.environ.get("DATABASE_URL") or "postgresql://quant:changeme@127.0.0.1:5432/quant"
        exchange = _normalize_exchange(req.exchange)
        # daily_winner is Postgres-only; if an exchange is selected, switch from
        # the canonical "postgres" view to the per-exchange "market" view.
        load_backend = "market" if exchange else "postgres"

        _run_jobs[job_id].update({
            "status": "running",
            "progress": 10,
            "message": "Loading daily winner 1D candles from DB",
        })
        dfs: dict[str, pd.DataFrame] = {}
        skipped: list[str] = []
        data_sources: list[dict[str, Any]] = []
        for i, inst in enumerate(universe):
            attempts: list[dict[str, Any]] = []
            df = load_candles(
                inst_id=inst,
                bar="1D",
                data_dir=req.data_dir or "data/ticks",
                start=req.start,
                end=req.end,
                backend=load_backend,
                dsn=dsn,
                exchange=exchange if load_backend == "market" else None,
            )
            attempts.append({
                "backend": load_backend,
                "exchange": exchange if load_backend == "market" else None,
                "rows": int(len(df)),
            })
            if df.empty and load_backend == "market":
                df = load_candles(
                    inst_id=inst,
                    bar="1D",
                    data_dir=req.data_dir or "data/ticks",
                    start=req.start,
                    end=req.end,
                    backend="postgres",
                    dsn=dsn,
                    exchange=None,
                )
                attempts.append({
                    "backend": "postgres",
                    "exchange": None,
                    "rows": int(len(df)),
                    "fallback": "canonical_1m_or_1d",
                })
            if df.empty:
                skipped.append(inst)
                data_sources.append({
                    "inst_id": inst,
                    "status": "skipped",
                    "attempts": attempts,
                    "reason": "empty daily OHLCV after market/canonical fallback",
                })
                continue
            dfs[inst] = df
            data_sources.append({
                "inst_id": inst,
                "status": "loaded",
                "rows": int(len(df)),
                "first_ts": str(df.index.min()) if not df.empty else None,
                "last_ts": str(df.index.max()) if not df.empty else None,
                "attempts": attempts,
            })
            _run_jobs[job_id]["progress"] = 10 + int((i + 1) / max(len(universe), 1) * 45)

        if len(dfs) < 2:
            _run_jobs[job_id].update({
                "status": "error",
                "progress": 100,
                "message": "Daily winner needs at least two symbols with daily OHLCV",
                "output": f"Loaded={list(dfs)} skipped={skipped}",
            })
            return

        _run_jobs[job_id].update({"progress": 65, "message": "Running daily winner backtest"})
        result = run_daily_winner_backtest(
            dfs,
            DailyWinnerParams(
                universe=list(dfs.keys()),
                initial_equity=req.initial_equity or 5000.0,
            ),
        )

        _run_jobs[job_id].update({"progress": 85, "message": "Writing frontend result"})
        result_json = _build_daily_winner_result_json(
            run_id=run_id,
            req=req,
            result=result,
            loaded_symbols=list(dfs.keys()),
            skipped_symbols=skipped,
            data_sources=data_sources,
        )
        _attach_daily_winner_validation(result_json, result.daily_returns, req.validation)
        result_json = _json_sanitize(result_json)
        (out_dir / "result.json").write_text(
            json.dumps(result_json, allow_nan=False, indent=2),
            encoding="utf-8",
        )
        _run_jobs[job_id].update({
            "status": "done",
            "progress": 100,
            "message": "Backtest complete",
            "output": (
                f"Daily winner completed: {result_json['metrics']['number_of_trades']} / "
                f"{result_json['metrics']['expected_trade_days']} expected daily trades"
            ),
        })
    except Exception as exc:
        _run_jobs[job_id].update({
            "status": "error",
            "progress": 100,
            "message": str(exc),
        })


def _build_daily_winner_result_json(
    *,
    run_id: str,
    req: "RunBacktestRequest",
    result: Any,
    loaded_symbols: list[str],
    skipped_symbols: list[str],
    data_sources: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the ADR-0002-compatible inline result payload for daily_winner."""
    equity_df = result.equity_curve.to_frame("equity")
    equity_df["datetime"] = equity_df.index.astype(str)
    equity_df["return"] = equity_df["equity"].pct_change().fillna(0.0)
    equity_df["drawdown"] = (
        equity_df["equity"] / equity_df["equity"].cummax() - 1.0
    ).fillna(0.0)
    equity_df.index.name = "ts"
    equity_records = json.loads(
        equity_df.reset_index().to_json(orient="records", date_format="iso", force_ascii=False)
    )

    returns_df = result.daily_returns.to_frame("return")
    returns_df["datetime"] = returns_df.index.astype(str)
    returns_df["log_return"] = returns_df["return"].map(
        lambda value: math.log1p(value) if pd.notna(value) and value > -1 else pd.NA
    )
    returns_df.index.name = "ts"
    returns_records = json.loads(
        returns_df.reset_index().to_json(orient="records", date_format="iso", force_ascii=False)
    )

    trades = result.trades.copy()
    if not trades.empty:
        trades["strategy"] = "daily_winner"
        trades["side"] = "buy"
        trades["status"] = "FILLED"
        trades["type"] = "validation_round_trip"
        trades["datetime"] = trades["entry_ts"]
        trades["ts"] = trades["entry_ts"]
        trades["price"] = trades["entry_price"]
        trades["qty"] = 0.0
        trades["notional"] = 0.0
        trades["fee"] = 0.0
        trades["pnl"] = trades["net_return"]
    trades_records = json.loads(
        trades.to_json(orient="records", date_format="iso", force_ascii=False)
    )
    for i, record in enumerate(trades_records):
        record["id"] = i
        record["pnl_usd"] = None
        record["note"] = "validation-only round trip; quantity/notional are not modeled"

    metrics = dict(result.metrics)
    trade_count = metrics.get("number_of_trades", 0)
    metrics.setdefault("profit_factor", 0.0)
    metrics.setdefault("order_count", trade_count * 2)
    metrics.setdefault("fill_count", trade_count * 2)
    metrics.setdefault("real_fill_count", metrics.get("fill_count", trade_count * 2))
    metrics.setdefault("orders_filled_count", trade_count * 2)
    metrics.setdefault("fill_rate", 1.0 if trade_count else 0.0)
    metrics.setdefault("bankrupt", False)
    metrics.setdefault("total_fees", 0.0)
    metrics.setdefault("fill_notional_usd", 0.0)
    metrics.setdefault("funding_cashflow", 0.0)
    metrics.setdefault("funding_settlement_count", 0)
    metrics["loaded_symbols"] = loaded_symbols
    metrics["skipped_symbols"] = skipped_symbols
    metrics = {key: _json_safe(value) for key, value in metrics.items()}

    return {
        "run_id": run_id,
        "created_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "strategies": ["daily_winner"],
        "symbols": loaded_symbols,
        "bar": "1D",
        "start": req.start or "",
        "end": req.end or "",
        "metrics": metrics,
        "equity": equity_records,
        "returns": returns_records,
        "trades": trades_records,
        "artifacts": {},
        "validation": {
            "validation_only": True,
            "daily_winner_data_sources": data_sources or [],
        },
    }


def _json_safe(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, np.floating):
        as_float = float(value)
        return as_float if math.isfinite(as_float) else None
    if isinstance(value, np.integer):
        return int(value)
    return value


def _json_sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_sanitize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_sanitize(v) for v in value]
    if isinstance(value, tuple):
        return [_json_sanitize(v) for v in value]
    return _json_safe(value)


def _daily_winner_return_series(records: list[dict[str, Any]]) -> pd.Series:
    rows = []
    for i, record in enumerate(records or []):
        ts = record.get("datetime") or record.get("ts") or i
        value = record.get("return", record.get("simple_return"))
        if value is None or value == "":
            continue
        try:
            rows.append((pd.to_datetime(ts), float(value)))
        except Exception:
            continue
    if not rows:
        return pd.Series(dtype=float)
    index, values = zip(*rows)
    return pd.Series(values, index=pd.DatetimeIndex(index)).sort_index()


def _slice_return_stats(returns: pd.Series, periods: int = 365) -> dict[str, Any]:
    from okx_quant.analytics.performance import max_drawdown, sharpe

    clean = pd.Series(returns, dtype=float).dropna()
    if clean.empty:
        return {"sharpe": 0.0, "return": 0.0, "mdd": 0.0, "n": 0}
    return {
        "sharpe": sharpe(clean, periods=periods),
        "return": float((1.0 + clean).prod() - 1.0),
        "mdd": max_drawdown(clean),
        "n": int(len(clean)),
    }


def _daily_winner_walk_forward(returns: pd.Series, periods: int = 365) -> list[dict[str, Any]]:
    clean = pd.Series(returns, dtype=float).dropna().sort_index()
    n = len(clean)
    if n < 4:
        return []
    is_len = max(2, n // 3)
    oos_len = max(1, min(7, (n - is_len) // 2 or 1))
    rows: list[dict[str, Any]] = []
    cursor = is_len
    i = 0
    while cursor + oos_len <= n:
        is_slice = clean.iloc[cursor - is_len:cursor]
        oos_slice = clean.iloc[cursor:cursor + oos_len]
        is_stats = _slice_return_stats(is_slice, periods)
        oos_stats = _slice_return_stats(oos_slice, periods)
        rows.append({
            "i": i,
            "is_start": is_slice.index[0].isoformat(),
            "is_end": is_slice.index[-1].isoformat(),
            "oos_start": oos_slice.index[0].isoformat(),
            "oos_end": oos_slice.index[-1].isoformat(),
            "is_n": is_stats["n"],
            "oos_n": oos_stats["n"],
            "is_sharpe": is_stats["sharpe"],
            "oos_sharpe": oos_stats["sharpe"],
            "oos_return": oos_stats["return"],
            "oos_mdd": oos_stats["mdd"],
            "validation_only": True,
        })
        cursor += oos_len
        i += 1
    return rows


def _daily_winner_cpcv(returns: pd.Series, periods: int = 365) -> dict[str, Any] | None:
    from itertools import combinations

    from okx_quant.analytics.dsr import deflated_sharpe, psr
    from okx_quant.analytics.performance import sharpe

    clean = pd.Series(returns, dtype=float).dropna().sort_index()
    n = len(clean)
    if n < 4:
        return None
    n_splits = min(6, n)
    k_test = 2 if n_splits >= 3 else 1
    groups = np.array_split(np.arange(n), n_splits)
    combos = []
    combo_returns = []
    for group_ids in combinations(range(n_splits), k_test):
        idx = np.concatenate([groups[group_id] for group_id in group_ids])
        oos = clean.iloc[np.sort(idx)]
        stats = _slice_return_stats(oos, periods)
        combo_returns.append(oos)
        combos.append({
            "test_groups": list(group_ids),
            "sharpe": stats["sharpe"],
            "ret": stats["return"],
            "mdd": stats["mdd"],
            "n": stats["n"],
        })
    if not combos:
        return None
    combo_sharpes = [float(c["sharpe"]) for c in combos]
    combined = pd.concat(combo_returns, ignore_index=True) if combo_returns else clean
    overall = float(np.mean(combo_sharpes)) if combo_sharpes else 0.0
    return {
        "combos": combos,
        "paths": [],
        "dsr": deflated_sharpe(
            returns=np.asarray(combined, dtype=float),
            sr=overall,
            sr_list=combo_sharpes,
            N=max(len(combo_sharpes), 1),
        ),
        "psr": psr(np.asarray(clean, dtype=float)),
        "mean_oos_sharpe": overall,
        "std_oos_sharpe": float(np.std(combo_sharpes, ddof=1)) if len(combo_sharpes) > 1 else 0.0,
        "n_combinations": len(combos),
        "n_paths": 0,
        "validation_only": True,
    }


def _attach_daily_winner_validation(
    payload: dict[str, Any],
    returns: pd.Series,
    mode: str | None,
) -> None:
    if mode in {"wf", "both"}:
        payload["walk_forward"] = _daily_winner_walk_forward(returns)
    cpcv = _daily_winner_cpcv(returns)
    if mode in {"cpcv", "both"} and cpcv:
        payload["cpcv"] = cpcv
    metrics = payload.setdefault("metrics", {})
    metrics.setdefault("psr", cpcv.get("psr") if cpcv else 0.0)
    metrics.setdefault("dsr", cpcv.get("dsr") if cpcv else 0.0)
    metrics["validation_only"] = True


def _normalize_daily_winner_payload(payload: dict[str, Any]) -> dict[str, Any]:
    strategies = payload.get("strategies") or [payload.get("strategy")]
    if "daily_winner" not in strategies:
        return payload

    normalized = dict(payload)
    metrics = dict(normalized.get("metrics") or {})
    equity = [dict(row) for row in normalized.get("equity") or []]
    previous_equity: float | None = None
    for row in equity:
        ts = row.get("datetime") or row.get("ts")
        if ts and not row.get("datetime"):
            row["datetime"] = str(ts)[:10] if "T" in str(ts) else str(ts)
        equity_value = row.get("equity_usd", row.get("equity"))
        try:
            equity_float = float(equity_value)
        except (TypeError, ValueError):
            equity_float = None
        if row.get("return") in {None, ""}:
            row["return"] = 0.0 if previous_equity in {None, 0.0} or equity_float is None else equity_float / previous_equity - 1.0
        if equity_float is not None:
            previous_equity = equity_float
    normalized["equity"] = equity

    returns = normalized.get("returns") or []
    return_series = _daily_winner_return_series(returns)
    if return_series.empty and equity:
        return_series = _daily_winner_return_series(equity)

    if not return_series.empty:
        from okx_quant.analytics.dsr import psr
        from okx_quant.analytics.performance import sharpe

        metrics["sharpe"] = sharpe(return_series, periods=365)
        metrics.setdefault("psr", psr(np.asarray(return_series, dtype=float)))
        metrics.setdefault("dsr", 0.0)
        if "walk_forward" not in normalized:
            normalized["walk_forward"] = _daily_winner_walk_forward(return_series)
        if "cpcv" not in normalized:
            cpcv = _daily_winner_cpcv(return_series)
            if cpcv:
                normalized["cpcv"] = cpcv
                metrics["psr"] = cpcv.get("psr", metrics.get("psr"))
                metrics["dsr"] = cpcv.get("dsr", metrics.get("dsr"))

    trade_count = int(metrics.get("number_of_trades") or len(normalized.get("trades") or []))
    metrics.setdefault("profit_factor", 0.0)
    metrics.setdefault("order_count", trade_count * 2)
    metrics.setdefault("fill_count", trade_count * 2)
    metrics.setdefault("real_fill_count", metrics.get("fill_count", trade_count * 2))
    metrics.setdefault("orders_filled_count", trade_count * 2)
    metrics.setdefault("fill_rate", 1.0 if trade_count else 0.0)
    metrics.setdefault("bankrupt", False)
    metrics.setdefault("total_fees", 0.0)
    metrics.setdefault("fill_notional_usd", 0.0)
    metrics.setdefault("funding_cashflow", 0.0)
    metrics.setdefault("funding_settlement_count", 0)
    metrics["validation_only"] = True
    normalized["metrics"] = {key: _json_safe(value) for key, value in metrics.items()}

    trades = []
    for i, trade in enumerate(normalized.get("trades") or []):
        row = dict(trade)
        entry_ts = row.get("entry_ts") or row.get("datetime") or row.get("ts")
        row.setdefault("id", i)
        row.setdefault("datetime", entry_ts)
        row.setdefault("ts", entry_ts)
        row.setdefault("status", "FILLED")
        row.setdefault("type", "validation_round_trip")
        row.setdefault("price", row.get("entry_price", 0.0))
        row.setdefault("qty", 0.0)
        row.setdefault("notional", 0.0)
        row.setdefault("fee", 0.0)
        row.setdefault("pnl", row.get("net_return", 0.0))
        row.setdefault("pnl_usd", None)
        row.setdefault("note", "validation-only round trip; quantity/notional are not modeled")
        trades.append(row)
    normalized["trades"] = trades
    return normalized


def _as_record_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [dict(row) for row in value if isinstance(row, dict)]
    if isinstance(value, dict):
        rows = value.get("rows") or value.get("records") or value.get("data")
        if isinstance(rows, list):
            return [dict(row) for row in rows if isinstance(row, dict)]
    return []


def _first_present(row: dict[str, Any], keys: list[str], default: Any = None) -> Any:
    for key in keys:
        value = row.get(key)
        if value is not None and value != "":
            return value
    return default


def _visual_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _visual_time_values(value: Any) -> tuple[int | None, str]:
    if value is None or value == "":
        return None, ""
    try:
        if isinstance(value, (int, float, np.integer, np.floating)) and math.isfinite(float(value)):
            raw = float(value)
            unit = "ms" if raw > 1_000_000_000_000 else "s" if raw > 1_000_000_000 else None
            ts = pd.to_datetime(raw, unit=unit, utc=True, errors="coerce") if unit else pd.to_datetime(raw, utc=True, errors="coerce")
        else:
            ts = pd.to_datetime(value, utc=True, errors="coerce")
    except Exception:
        return None, str(value)
    if pd.isna(ts):
        return None, str(value)
    return int(ts.timestamp() * 1000), ts.isoformat()


def _result_visual_symbols(
    result: dict[str, Any] | None,
    fills: list[dict[str, Any]] | None = None,
    trades: list[dict[str, Any]] | None = None,
) -> list[str]:
    symbols: list[str] = []

    def add(value: Any) -> None:
        if isinstance(value, str) and value and _SAFE_SYMBOL_RE.match(value) and value not in symbols:
            symbols.append(value)

    if result:
        for value in result.get("symbols") or []:
            add(value)
        metrics = result.get("metrics") or {}
        for key in ("loaded_symbols", "universe", "skipped_symbols"):
            for value in metrics.get(key) or []:
                add(value)
        for key in ("symbol", "benchmark", "perp_symbol", "spot_symbol"):
            add(result.get(key))
        validation = result.get("validation") or {}
        for source in validation.get("daily_winner_data_sources") or []:
            if isinstance(source, dict):
                add(source.get("inst_id"))
        for row in result.get("trades") or []:
            if isinstance(row, dict):
                add(_first_present(row, ["inst_id", "symbol"]))

    for rows in (fills or [], trades or []):
        for row in rows if isinstance(rows, list) else []:
            if isinstance(row, dict):
                add(_first_present(row, ["inst_id", "symbol"]))

    return symbols


def _downsample_records(records: list[dict[str, Any]], n: int) -> list[dict[str, Any]]:
    """Return at most n evenly-spaced records, always including first and last."""
    if n <= 0 or len(records) <= n:
        return records
    step = len(records) / n
    indices = set(int(i * step) for i in range(n))
    indices.add(len(records) - 1)
    return [records[i] for i in sorted(indices)]


def _downsample_records_by_symbol(records: list[dict[str, Any]], n: int) -> list[dict[str, Any]]:
    """Downsample price records per instrument so multi-symbol charts remain visible."""
    if n <= 0 or len(records) <= n:
        return records
    groups: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for row in records:
        symbol = str(row.get("inst_id") or "")
        if symbol not in groups:
            groups[symbol] = []
            order.append(symbol)
        groups[symbol].append(row)
    if len(groups) <= 1:
        return _downsample_records(records, n)

    per_symbol = max(1, n)
    sampled: list[dict[str, Any]] = []
    for symbol in order:
        sampled.extend(_downsample_records(groups[symbol], per_symbol))
    sampled.sort(key=lambda row: (str(row.get("ts") or row.get("datetime") or ""), row.get("inst_id") or ""))
    return sampled


def _data_source_exchange(result: dict[str, Any] | None) -> str:
    source = (result or {}).get("data_source") or {}
    return _normalize_exchange(source.get("primary_exchange") if isinstance(source, dict) else None)


def _fallback_price_series_from_result(
    result: dict[str, Any],
    *,
    symbol: str | None = None,
    fills: list[dict[str, Any]] | None = None,
    trades: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Rebuild chart OHLCV from the configured candle store when artifacts are absent."""
    from backtesting import data_loader

    selected = [symbol] if symbol else _result_visual_symbols(result, fills=fills, trades=trades)
    if not selected:
        return []

    bar = result.get("bar") or "1H"
    start = result.get("start") or result.get("start_date") or None
    end = result.get("end") or result.get("end_date") or None
    data_dir = str(result.get("data_dir") or "data/ticks")
    backend, dsn = _resolve_candle_backend()
    exchange = _data_source_exchange(result)

    attempts: list[tuple[str, str | None]] = []
    if dsn:
        attempts.append(("market", exchange))
        attempts.append(("postgres", None))
    attempts.append((backend, exchange if backend == "market" else None))
    attempts.append(("parquet", None))

    deduped_attempts: list[tuple[str, str | None]] = []
    for attempt in attempts:
        if attempt not in deduped_attempts:
            deduped_attempts.append(attempt)

    rows: list[dict[str, Any]] = []
    for inst_id in selected:
        df = pd.DataFrame()
        for load_backend, load_exchange in deduped_attempts:
            try:
                df = data_loader.load_candles(
                    inst_id=inst_id,
                    bar=bar,
                    data_dir=data_dir,
                    start=start,
                    end=end,
                    backend=load_backend,  # type: ignore[arg-type]
                    dsn=dsn,
                    exchange=load_exchange,
                )
            except Exception:
                df = pd.DataFrame()
            if not df.empty:
                break
        if df.empty:
            continue
        for ts_value, candle in df.sort_index().iterrows():
            ts_ms, dt = _visual_time_values(ts_value)
            if ts_ms is None:
                continue
            rows.append({
                "ts": ts_ms,
                "datetime": dt,
                "inst_id": inst_id,
                "open": _visual_float(candle.get("open"), float("nan")),
                "high": _visual_float(candle.get("high"), float("nan")),
                "low": _visual_float(candle.get("low"), float("nan")),
                "close": _visual_float(candle.get("close"), float("nan")),
                "vol": _visual_float(candle.get("vol"), 0.0),
            })
    return _json_sanitize(rows)


def _fallback_execution_markers_from_records(
    *,
    fills: list[dict[str, Any]] | None = None,
    trades: list[dict[str, Any]] | None = None,
    result: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build chart markers from fills, or from trade entry/exit rows for non-replay runs."""
    strategies = (result or {}).get("strategies") or [(result or {}).get("strategy") or ""]
    default_strategy = next((strat for strat in strategies if strat), "")

    def marker(
        *,
        source: dict[str, Any],
        ts_value: Any,
        inst_id: str,
        side: str,
        price: Any,
        qty: Any = None,
        pnl: Any = None,
        text_prefix: str | None = None,
    ) -> dict[str, Any] | None:
        ts_ms, dt = _visual_time_values(ts_value)
        if ts_ms is None or not inst_id:
            return None
        side_l = str(side or "buy").lower()
        px = _visual_float(price, 0.0)
        qty_f = _visual_float(qty, 0.0)
        fee = _visual_float(source.get("fee"), 0.0)
        notional = _visual_float(_first_present(source, ["notional_usd", "notional"]), abs(px * qty_f) if qty_f else 0.0)
        pnl_value = _visual_float(pnl, float("nan"))
        marker_position = "belowBar" if side_l == "buy" else "aboveBar"
        marker_shape = "arrowUp" if side_l == "buy" else "arrowDown"
        label = text_prefix or side_l.upper()
        pnl_text = f" | PnL: {pnl_value:.4g}" if math.isfinite(pnl_value) else ""
        marker_text = f"{label} @ {px:,.6g}{pnl_text}"
        return {
            "ts": ts_ms,
            "datetime": dt,
            "inst_id": inst_id,
            "strategy": source.get("strategy") or default_strategy,
            "side": side_l,
            "price": px,
            "qty": qty_f,
            "fee": fee,
            "notional_usd": notional,
            "net_realized_pnl": pnl_value if math.isfinite(pnl_value) else None,
            "day_pnl": None,
            "position_after": source.get("position_after", source.get("size_after")),
            "marker_position": marker_position,
            "marker_shape": marker_shape,
            "marker_text": marker_text,
        }

    markers: list[dict[str, Any]] = []
    for fill in fills or []:
        if not isinstance(fill, dict):
            continue
        state = str(fill.get("state") or fill.get("status") or "filled").lower()
        if state and state not in {"filled", "partially_filled", "fill"}:
            continue
        inst_id = str(_first_present(fill, ["inst_id", "symbol"], ""))
        row = marker(
            source=fill,
            ts_value=_first_present(fill, ["ts", "datetime", "time"]),
            inst_id=inst_id,
            side=str(_first_present(fill, ["side"], "buy")),
            price=_first_present(fill, ["fill_px", "price", "px", "avg_px"]),
            qty=_first_present(fill, ["fill_sz", "qty", "sz"]),
            pnl=_first_present(fill, ["net_realized_pnl", "pnl", "pnl_usd"]),
        )
        if row:
            markers.append(row)
    if markers:
        return _json_sanitize(sorted(markers, key=lambda row: (row.get("ts") or 0, row.get("inst_id") or "")))

    for trade in trades or []:
        if not isinstance(trade, dict):
            continue
        inst_id = str(_first_present(trade, ["inst_id", "symbol"], ""))
        entry_side = str(_first_present(trade, ["side", "entry_side"], "buy")).lower()
        exit_side = "sell" if entry_side == "buy" else "buy"
        entry = marker(
            source=trade,
            ts_value=_first_present(trade, ["entry_ts", "entry_time", "datetime", "ts"]),
            inst_id=inst_id,
            side=entry_side,
            price=_first_present(trade, ["entry_price", "price"]),
            qty=_first_present(trade, ["qty", "size", "entry_qty"]),
            text_prefix="ENTRY",
        )
        if entry:
            markers.append(entry)
        exit_ts = _first_present(trade, ["exit_ts", "exit_time", "close_ts"])
        exit_price = _first_present(trade, ["exit_price", "close_price"])
        if exit_ts is not None and exit_ts != "" and exit_price is not None and exit_price != "":
            exit_row = marker(
                source=trade,
                ts_value=exit_ts,
                inst_id=inst_id,
                side=exit_side,
                price=exit_price,
                qty=_first_present(trade, ["qty", "size", "exit_qty"]),
                pnl=_first_present(trade, ["net_realized_pnl", "net_return", "pnl", "pnl_usd"]),
                text_prefix="EXIT",
            )
            if exit_row:
                markers.append(exit_row)
    return _json_sanitize(sorted(markers, key=lambda row: (row.get("ts") or 0, row.get("inst_id") or "")))


def _run_backtest_job(
    job_id: str,
    req: RunBacktestRequest,
    run_id: str,
    results_dir: Path,
) -> None:
    try:
        req = _normalize_backtest_request(req)
        script = PROJECT_ROOT / "scripts" / "run_replay_backtest.py"
        cmd = [
            sys.executable,
            str(script),
            "--strategy",
            req.strategy,
            "--bar",
            req.bar,
            "--save-artifacts",
            "--output-dir",
            str(results_dir),
            "--run-id",
            run_id,
        ]
        if req.start:
            cmd.extend(["--start", req.start])
        if req.end:
            cmd.extend(["--end", req.end])
        if req.periods:
            cmd.extend(["--periods", str(req.periods)])
        if req.validation:
            cmd.extend(["--validate", req.validation])
        for symbol in req.symbols:
            cmd.extend(["--symbol", symbol])
        if req.symbol_x:
            cmd.extend(["--symbol-x", req.symbol_x])
        if req.symbol_y:
            cmd.extend(["--symbol-y", req.symbol_y])
        if req.perp_symbol:
            cmd.extend(["--perp-symbol", req.perp_symbol])
        if req.spot_symbol:
            cmd.extend(["--spot-symbol", req.spot_symbol])
        if req.min_apr_threshold is not None:
            cmd.extend(["--min-apr-threshold", str(req.min_apr_threshold)])
        if req.strategy_params:
            cmd.extend(["--strategy-params", json.dumps(req.strategy_params)])
        if req.risk_overrides:
            cmd.extend(["--risk-overrides", json.dumps(req.risk_overrides)])
        cmd.extend(["--exchange", _normalize_exchange(req.exchange)])

        _run_jobs[job_id].update({
            "status": "running",
            "progress": 10,
            "message": "Starting replay backtest process",
            "command": " ".join(cmd),
        })
        env = os.environ.copy()
        env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
        import threading
        lines: list[str] = []
        stderr_lines: list[str] = []

        proc = subprocess.Popen(
            cmd,
            cwd=PROJECT_ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        def _drain_stderr():
            for line in (proc.stderr or []):
                stderr_lines.append(line)

        stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
        stderr_thread.start()

        try:
            for line in proc.stdout or []:
                lines.append(line)
                stripped = line.strip()
                if stripped.startswith("PROGRESS:"):
                    try:
                        parts = stripped.split(":", 2)
                        pct = int(parts[1])
                        _run_jobs[job_id]["progress"] = pct
                        if len(parts) > 2 and parts[2].strip():
                            _run_jobs[job_id]["message"] = parts[2].strip()
                    except (ValueError, IndexError):
                        pass
        finally:
            proc.wait()
            stderr_thread.join(timeout=5)

        output = ("".join(lines) + "\n" + "".join(stderr_lines)).strip()
        if proc.returncode != 0:
            _run_jobs[job_id].update({
                "status": "error",
                "progress": 100,
                "message": f"Backtest failed with exit code {proc.returncode}",
                "output": output[-4000:],
            })
            return
        _run_jobs[job_id].update({
            "status": "done",
            "progress": 100,
            "message": "Backtest complete",
            "output": output[-4000:],
        })
    except Exception as exc:
        _run_jobs[job_id].update({
            "status": "error",
            "progress": 100,
            "message": str(exc),
        })


def _run_parameter_sweep_job(
    job_id: str,
    req: ParameterSweepRequest,
    sweep_id: str,
    results_dir: Path,
) -> None:
    try:
        symbols = [normalize_swap_symbol(symbol) for symbol in req.symbols]
        data_dir = str(_resolve_data_dir(req.data_dir))

        def _on_progress(update: dict[str, Any]) -> None:
            _sweep_jobs[job_id].update({
                "status": "running",
                **update,
            })

        summary = run_parameter_sweep(
            strategy=req.strategy,
            parameter_grid=req.parameter_grid,
            symbols=symbols,
            bar=req.bar,
            periods=req.periods,
            start=req.start,
            end=req.end,
            data_dir=data_dir,
            output_dir=results_dir / "parameter_sweeps",
            sweep_id=sweep_id,
            initial_equity=req.initial_equity,
            exchange=_normalize_exchange(req.exchange),
            max_combinations=req.max_combinations,
            liquidate_on_end=req.liquidate_on_end,
            risk_overrides=req.risk_overrides,
            run_finalists=req.run_finalists,
            finalist_top_pct=req.finalist_top_pct,
            max_finalists=req.max_finalists,
            finalist_validation=req.finalist_validation,
            full_output_dir=results_dir,
            progress_callback=_on_progress,
        )
        _sweep_jobs[job_id].update({
            "status": "done",
            "progress": 100,
            "message": "Parameter sweep complete",
            "sweep_id": summary["sweep_id"],
            "artifacts": summary.get("artifacts", {}),
            "top_results": summary.get("top_results", [])[:10],
            "completed_count": summary.get("completed_count", 0),
            "failed_count": summary.get("failed_count", 0),
            "skipped_count": summary.get("skipped_count", 0),
            "finalist_results": summary.get("finalist_results", []),
            "elapsed_seconds": summary.get("elapsed_seconds"),
        })
    except Exception as exc:
        _sweep_jobs[job_id].update({
            "status": "error",
            "progress": 100,
            "message": str(exc),
        })


def make_backtest_router(results_dir: Path) -> APIRouter:
    router = APIRouter()

    def _run_dir(run_id: str) -> Path:
        clean = Path(run_id).name
        d = results_dir / clean
        if not d.is_dir():
            raise HTTPException(status_code=404, detail="Run not found")
        return d

    def _read_json(path: Path) -> dict:
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"{path.name} not found")
        import re
        text = path.read_text(encoding="utf-8")
        # Replace bare Infinity / -Infinity / NaN (not quoted) → null
        text = re.sub(r'(?<!["\w])(-?Infinity|NaN)(?!["\w])', 'null', text)
        return json.loads(text)

    def _read_csv(path: Path) -> list[dict]:
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"{path.name} not found")
        df = pd.read_csv(path)
        return json.loads(df.to_json(orient="records", force_ascii=False))

    def _downsample_records(records: list[dict], n: int) -> list[dict]:
        """Return at most n evenly-spaced records, always including first and last."""
        if n <= 0 or len(records) <= n:
            return records
        step = len(records) / n
        indices = set(int(i * step) for i in range(n))
        indices.add(len(records) - 1)
        return [records[i] for i in sorted(indices)]

    async def _read_db_artifact(run_id: str, artifact_type: str) -> Any | None:
        try:
            import asyncpg

            dsn = os.environ.get("DATABASE_URL")
            if not dsn:
                return None
            conn = await asyncpg.connect(dsn)
            try:
                row = await conn.fetchrow(
                    """
                    SELECT payload
                    FROM backtest_artifacts
                    WHERE run_id = $1 AND artifact_type = $2
                    """,
                    Path(run_id).name,
                    artifact_type,
                )
            finally:
                await conn.close()
            if not row:
                return None
            payload = row["payload"]
            return json.loads(payload) if isinstance(payload, str) else payload
        except Exception:
            return None

    async def _read_result_payload(run_id: str) -> dict[str, Any]:
        payload = await _read_db_artifact(run_id, "result")
        if payload is not None:
            return _normalize_daily_winner_payload(payload)
        return _normalize_daily_winner_payload(_read_json(_run_dir(run_id) / "result.json"))

    async def _read_records_artifact(run_id: str, artifact_type: str, filename: str) -> list[dict[str, Any]]:
        payload = await _read_db_artifact(run_id, artifact_type)
        records = _as_record_list(payload)
        if records:
            return records
        d = results_dir / Path(run_id).name
        if not d.is_dir():
            return []
        path = d / filename
        if not path.exists():
            return []
        return _as_record_list(_read_csv(path))

    # ------------------------------------------------------------------
    # List all runs
    # ------------------------------------------------------------------

    @router.get("/runs")
    async def list_runs():
        """Return a summary list of all saved backtest runs."""
        # Keyed by run_id; DB rows take precedence over filesystem rows.
        merged: dict[str, dict] = {}

        # --- filesystem scan (always) ---
        if results_dir.exists():
            for run_dir in sorted(results_dir.iterdir(), reverse=True):
                result_file = run_dir / "result.json"
                if not (run_dir.is_dir() and result_file.exists()):
                    continue
                try:
                    data = json.loads(result_file.read_text(encoding="utf-8"))
                    data = _normalize_daily_winner_payload(data)
                    metrics = data.get("metrics", data.get("mainStats", {}))
                    if not (run_dir / "returns.csv").exists() and not data.get("returns"):
                        continue
                    run_id = data.get("run_id", run_dir.name)
                    merged[run_id] = {
                        "run_id": run_id,
                        "created_at": data.get("created_at"),
                        "strategies": data.get("strategies", [data.get("strategy", "")]),
                        "symbols": data.get("symbols", [data.get("symbol", "")]),
                        "bar": data.get("bar", ""),
                        "start": data.get("start", data.get("start_date", "")),
                        "end": data.get("end", data.get("end_date", "")),
                        "total_return": metrics.get("total_return"),
                        "sharpe": metrics.get("sharpe"),
                        "max_drawdown": metrics.get("max_drawdown"),
                        "order_count": metrics.get("order_count"),
                        "real_fill_count": metrics.get("real_fill_count", metrics.get("fill_count")),
                    }
                except Exception:
                    pass

        # --- DB scan (overlay; DB data overwrites filesystem entries) ---
        try:
            import asyncpg

            dsn = os.environ.get("DATABASE_URL")
            if dsn:
                conn = await asyncpg.connect(dsn)
                try:
                    try:
                        rows = await conn.fetch(
                            """
                            SELECT
                                r.*,
                                COALESCE((
                                    SELECT MAX(a.created_at)
                                    FROM backtest_artifacts a
                                    WHERE a.run_id = r.run_id
                                ), r.created_at) AS sort_created_at
                            FROM backtest_runs r
                            WHERE EXISTS (
                                SELECT 1
                                FROM backtest_artifacts a
                                WHERE a.run_id = r.run_id
                                  AND a.artifact_type = 'returns'
                                  AND a.row_count > 0
                            )
                            ORDER BY sort_created_at DESC
                            LIMIT 200
                            """
                        )
                    except Exception:
                        rows = await conn.fetch(
                            "SELECT * FROM backtest_runs ORDER BY created_at DESC LIMIT 200"
                        )
                finally:
                    await conn.close()
                for row in rows:
                    item = dict(row)
                    item["created_at"] = item.get("sort_created_at") or item.get("created_at")
                    item.pop("sort_created_at", None)
                    item["start"] = item.get("start_date")
                    item["end"] = item.get("end_date")
                    merged[item["run_id"]] = item
        except Exception:
            pass

        def _created_at_sort_key(row: dict) -> float:
            value = row.get("created_at")
            if not value:
                return 0.0
            try:
                return pd.Timestamp(value).timestamp()
            except Exception:
                return 0.0

        return sorted(merged.values(), key=_created_at_sort_key, reverse=True)

    @router.post("/run")
    async def start_backtest(req: RunBacktestRequest, bg: BackgroundTasks):
        allowed = {
            "obi_market_maker",
            "as_market_maker",
            "funding_carry",
            "pairs_trading",
            "ohlcv_rotation",
            "daily_winner",
            "ma_crossover",
            "ema_crossover",
            "macd_crossover",
            "fear_greed_sentiment",
            "cme_gap_fill",
        }
        validate_allowed = {None, "wf", "cpcv", "both"}
        _validate_backtest_request(req)
        if req.strategy not in allowed:
            raise HTTPException(status_code=400, detail="Unsupported strategy")
        if req.strategy != "ohlcv_rotation" and req.validation not in validate_allowed:
            raise HTTPException(status_code=400, detail="Unsupported validation mode")
        if req.strategy == "pairs_trading" and req.symbol_x == req.symbol_y:
            raise HTTPException(status_code=400, detail="Pair trading requires two different symbols")
        if req.strategy in {"ohlcv_rotation", "daily_winner"} and not req.universe:
            raise HTTPException(status_code=400, detail=f"{req.strategy} requires at least one symbol in universe")
        if req.strategy in {"ma_crossover", "ema_crossover", "macd_crossover"} and not req.symbols:
            raise HTTPException(status_code=400, detail=f"{req.strategy} requires at least one symbol")
        job_id = str(uuid.uuid4())[:8]
        run_id = req.run_id or f"ui_{req.strategy}_{job_id}"
        _run_jobs[job_id] = {
            "job_id": job_id,
            "run_id": run_id,
            "status": "running",
            "progress": 0,
            "message": "Backtest queued",
        }
        if req.strategy == "ohlcv_rotation":
            bg.add_task(_run_ohlcv_rotation_job, job_id, req, run_id, results_dir)
        elif req.strategy == "daily_winner":
            bg.add_task(_run_daily_winner_job, job_id, req, run_id, results_dir)
        else:
            bg.add_task(_run_backtest_job, job_id, req, run_id, results_dir)
        return _run_jobs[job_id]

    @router.get("/run/status/{job_id}")
    async def get_backtest_job_status(job_id: str):
        if job_id not in _run_jobs:
            raise HTTPException(status_code=404, detail="Job not found")
        return _run_jobs[job_id]

    @router.get("/run/jobs")
    async def list_run_jobs():
        """Return all in-memory job states so the frontend can reconnect after page refresh."""
        return list(_run_jobs.values())

    @router.post("/sweep")
    async def start_parameter_sweep(req: ParameterSweepRequest, bg: BackgroundTasks):
        _validate_parameter_sweep_request(req)
        try:
            combinations, skipped = expand_parameter_grid(
                req.strategy,
                req.parameter_grid,
                max_combinations=req.max_combinations,
            )
        except ParameterSweepError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        symbols = [normalize_swap_symbol(symbol) for symbol in req.symbols]
        finalist_count = 0
        if req.run_finalists and req.max_finalists > 0:
            finalist_count = min(req.max_finalists, max(1, math.ceil(len(combinations) * req.finalist_top_pct)))
        estimate = estimate_sweep_runtime(
            strategy=req.strategy,
            bar=req.bar,
            start=req.start,
            end=req.end,
            symbols=symbols,
            combinations=len(combinations),
            finalist_count=finalist_count,
            finalist_validation=req.finalist_validation,
        )
        job_id = str(uuid.uuid4())[:8]
        sweep_id = req.sweep_id or f"ui_sweep_{req.strategy}_{job_id}"
        _sweep_jobs[job_id] = {
            "job_id": job_id,
            "sweep_id": sweep_id,
            "status": "running",
            "progress": 0,
            "message": "Parameter sweep queued",
            "combination_count": len(combinations),
            "skipped_count": len(skipped),
            "finalist_count": finalist_count,
            "estimate": estimate,
        }
        bg.add_task(_run_parameter_sweep_job, job_id, req, sweep_id, results_dir)
        return _sweep_jobs[job_id]

    @router.get("/sweep/status/{job_id}")
    async def get_parameter_sweep_status(job_id: str):
        if job_id not in _sweep_jobs:
            raise HTTPException(status_code=404, detail="Sweep job not found")
        return _sweep_jobs[job_id]

    @router.get("/sweep/jobs")
    async def list_parameter_sweep_jobs():
        return list(_sweep_jobs.values())

    @router.delete("/{run_id}")
    async def delete_run(run_id: str):
        d = results_dir / Path(run_id).name
        shutil.rmtree(d, ignore_errors=True)
        try:
            import asyncpg

            dsn = os.environ.get("DATABASE_URL")
            if dsn:
                conn = await asyncpg.connect(dsn)
                try:
                    await conn.execute("DELETE FROM backtest_runs WHERE run_id = $1", run_id)
                finally:
                    await conn.close()
        except Exception:
            pass
        return {"deleted": run_id}

    # ------------------------------------------------------------------
    # Single run — full result.json
    # ------------------------------------------------------------------

    @router.get("/{run_id}")
    async def get_run(run_id: str):
        """Return the full result.json for a run."""
        return await _read_result_payload(run_id)

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    @router.get("/{run_id}/metrics")
    async def get_metrics(run_id: str):
        payload = await _read_db_artifact(run_id, "metrics")
        if payload is not None:
            return payload
        d = _run_dir(run_id)
        path = d / "metrics.json"
        if path.exists():
            return _read_json(path)
        result = _normalize_daily_winner_payload(_read_json(d / "result.json"))
        return result.get("metrics", {})

    @router.get("/{run_id}/walk-forward")
    async def get_walk_forward(run_id: str):
        result = await _read_db_artifact(run_id, "result")
        if result is None:
            result = _read_json(_run_dir(run_id) / "result.json")
        result = _normalize_daily_winner_payload(result)
        return result.get("walk_forward", result.get("walkForward", [])) or []

    @router.get("/{run_id}/cpcv")
    async def get_cpcv(run_id: str):
        result = await _read_db_artifact(run_id, "result")
        if result is None:
            result = _read_json(_run_dir(run_id) / "result.json")
        result = _normalize_daily_winner_payload(result)
        return result.get("cpcv")

    # ------------------------------------------------------------------
    # Equity curve
    # ------------------------------------------------------------------

    @router.get("/{run_id}/equity")
    async def get_equity(run_id: str, n: int = Query(default=0, ge=0)):
        payload = await _read_db_artifact(run_id, "equity")
        if payload is not None:
            records = payload
        else:
            d = _run_dir(run_id)
            path = d / "equity_curve.csv"
            if path.exists():
                records = _read_csv(path)
            else:
                records = _normalize_daily_winner_payload(_read_json(d / "result.json")).get("equity", [])
        return _downsample_records(records, n)

    # ------------------------------------------------------------------
    # Orders / Fills / Trades / Positions
    # ------------------------------------------------------------------

    @router.get("/{run_id}/orders")
    async def get_orders(run_id: str):
        payload = await _read_db_artifact(run_id, "orders")
        if payload is not None:
            return payload
        return _read_csv(_run_dir(run_id) / "orders.csv")

    @router.get("/{run_id}/fills")
    async def get_fills(
        run_id: str,
        limit: int = Query(default=0, ge=0),
        offset: int = Query(default=0, ge=0),
    ):
        payload = await _read_db_artifact(run_id, "fills")
        records = payload if payload is not None else _read_csv(_run_dir(run_id) / "fills.csv")
        if offset:
            records = records[offset:]
        if limit:
            records = records[:limit]
        return records

    @router.get("/{run_id}/trades")
    async def get_trades(
        run_id: str,
        limit: int = Query(default=0, ge=0),
        offset: int = Query(default=0, ge=0),
    ):
        payload = await _read_db_artifact(run_id, "trades")
        if payload is not None:
            records = payload
        else:
            d = _run_dir(run_id)
            path = d / "trades.csv"
            records = _read_csv(path) if path.exists() else _normalize_daily_winner_payload(_read_json(d / "result.json")).get("trades", [])
        if offset:
            records = records[offset:]
        if limit:
            records = records[:limit]
        return records

    @router.get("/{run_id}/positions")
    async def get_positions(run_id: str):
        payload = await _read_db_artifact(run_id, "positions")
        if payload is not None:
            return payload
        return _read_csv(_run_dir(run_id) / "positions.csv")

    # ------------------------------------------------------------------
    # Returns / Drawdown
    # ------------------------------------------------------------------

    @router.get("/{run_id}/returns")
    async def get_returns(run_id: str, n: int = Query(default=0, ge=0)):
        payload = await _read_db_artifact(run_id, "returns")
        if payload is not None:
            records = payload
        else:
            d = _run_dir(run_id)
            path = d / "returns.csv"
            records = _read_csv(path) if path.exists() else _normalize_daily_winner_payload(_read_json(d / "result.json")).get("returns", [])
        return _downsample_records(records, n)

    @router.get("/{run_id}/drawdown")
    async def get_drawdown(run_id: str, n: int = Query(default=0, ge=0)):
        payload = await _read_db_artifact(run_id, "drawdown")
        if payload is not None:
            records = payload
        else:
            d = _run_dir(run_id)
            drawdown_path = d / "drawdown.csv"
            if drawdown_path.exists():
                records = _read_csv(drawdown_path)
            else:
                equity_path = d / "equity_curve.csv"
                if not equity_path.exists():
                    raise HTTPException(status_code=404, detail="drawdown.csv not found")
                eq_df = pd.read_csv(equity_path)
                if "equity" not in eq_df.columns:
                    raise HTTPException(status_code=404, detail="drawdown data not found")
                running_max = eq_df["equity"].cummax()
                denominator = running_max.where(running_max != 0)
                if "drawdown" not in eq_df.columns:
                    eq_df["drawdown"] = ((eq_df["equity"] - running_max) / denominator).fillna(0.0)
                eq_df["running_max_equity"] = running_max
                eq_df["drawdown_pct"] = eq_df["drawdown"]
                records = json.loads(eq_df.to_json(orient="records", force_ascii=False))
        return _downsample_records(records, n)

    # ------------------------------------------------------------------
    # Funding / Signals / Risk events
    # ------------------------------------------------------------------

    @router.get("/{run_id}/funding")
    async def get_funding(run_id: str):
        payload = await _read_db_artifact(run_id, "funding")
        if payload is not None:
            return payload
        return _read_csv(_run_dir(run_id) / "funding.csv")

    @router.get("/{run_id}/signals")
    async def get_signals(run_id: str):
        payload = await _read_db_artifact(run_id, "signals")
        if payload is not None:
            return payload
        return _read_csv(_run_dir(run_id) / "signals.csv")

    @router.get("/{run_id}/risk-events")
    async def get_risk_events(run_id: str):
        payload = await _read_db_artifact(run_id, "risk_events")
        if payload is not None:
            return payload
        return _read_csv(_run_dir(run_id) / "risk_events.csv")

    # ------------------------------------------------------------------
    # Execution detail
    # ------------------------------------------------------------------

    @router.get("/{run_id}/rejected-orders")
    async def get_rejected_orders(run_id: str):
        payload = await _read_db_artifact(run_id, "rejected_orders")
        if payload is not None:
            return payload
        return _read_csv(_run_dir(run_id) / "rejected_orders.csv")

    @router.get("/{run_id}/cancel-log")
    async def get_cancel_log(run_id: str):
        payload = await _read_db_artifact(run_id, "cancel_log")
        if payload is not None:
            return payload
        return _read_csv(_run_dir(run_id) / "cancel_log.csv")

    @router.get("/{run_id}/execution-markers")
    async def get_execution_markers(run_id: str):
        records = await _read_records_artifact(run_id, "execution_markers", "execution_markers.csv")
        if records:
            return records
        result = await _read_result_payload(run_id)
        fills = await _read_records_artifact(run_id, "fills", "fills.csv")
        trades = await _read_records_artifact(run_id, "trades", "trades.csv")
        if not trades:
            trades = _as_record_list(result.get("trades"))
        return _fallback_execution_markers_from_records(
            fills=fills,
            trades=trades,
            result=result,
        )

    @router.get("/{run_id}/price-series")
    async def get_price_series(
        run_id: str,
        symbol: str | None = Query(default=None),
        n: int = Query(default=0, ge=0),
    ):
        if symbol:
            if not _SAFE_SYMBOL_RE.match(symbol):
                raise HTTPException(status_code=400, detail=f"Invalid symbol: {symbol}")
        records = await _read_records_artifact(run_id, "price_series", "price_series.csv")
        result: dict[str, Any] | None = None
        fills: list[dict[str, Any]] = []
        trades: list[dict[str, Any]] = []

        async def _load_visual_context() -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
            nonlocal result, fills, trades
            if result is None:
                result = await _read_result_payload(run_id)
            if not fills:
                fills = await _read_records_artifact(run_id, "fills", "fills.csv")
            if not trades:
                trades = await _read_records_artifact(run_id, "trades", "trades.csv")
                if not trades:
                    trades = _as_record_list(result.get("trades"))
            return result, fills, trades

        if symbol:
            records = [row for row in records if row.get("inst_id") == symbol]
            if not records:
                result_ctx, fills_ctx, trades_ctx = await _load_visual_context()
                records = _fallback_price_series_from_result(
                    result_ctx,
                    symbol=symbol,
                    fills=fills_ctx,
                    trades=trades_ctx,
                )
            return _downsample_records(records, n)

        if records:
            result_ctx, fills_ctx, trades_ctx = await _load_visual_context()
            expected_symbols = _result_visual_symbols(result_ctx, fills=fills_ctx, trades=trades_ctx)
            available_symbols = {str(row.get("inst_id") or "") for row in records}
            missing_symbols = [inst_id for inst_id in expected_symbols if inst_id not in available_symbols]
            if missing_symbols:
                fallback_rows = _fallback_price_series_from_result(
                    result_ctx,
                    fills=fills_ctx,
                    trades=trades_ctx,
                )
                records.extend(row for row in fallback_rows if row.get("inst_id") in missing_symbols)
        else:
            result_ctx, fills_ctx, trades_ctx = await _load_visual_context()
            records = _fallback_price_series_from_result(
                result_ctx,
                fills=fills_ctx,
                trades=trades_ctx,
            )
        return _downsample_records_by_symbol(records, n)

    @router.get("/{run_id}/indicators")
    async def get_indicators(
        run_id: str,
        symbol: str | None = Query(default=None),
        n: int = Query(default=0, ge=0),
    ):
        payload = await _read_db_artifact(run_id, "indicator_series")
        if payload is not None:
            records = payload
        else:
            indicator_path = _run_dir(run_id) / "indicator_series.csv"
            if not indicator_path.exists():
                return []
            records = _read_csv(indicator_path)
        if symbol:
            if not _SAFE_SYMBOL_RE.match(symbol):
                raise HTTPException(status_code=400, detail=f"Invalid symbol: {symbol}")
            records = [row for row in records if row.get("inst_id") == symbol]
        return _downsample_records(records, n)

    # ------------------------------------------------------------------
    # Data coverage
    # ------------------------------------------------------------------

    @router.get("/{run_id}/data-coverage")
    async def get_data_coverage(run_id: str):
        payload = await _read_db_artifact(run_id, "data_coverage")
        if payload is not None:
            return payload
        return _read_json(_run_dir(run_id) / "data_coverage.json")

    return router


def _normalize_backtest_request(req: RunBacktestRequest) -> RunBacktestRequest:
    normalized = req.model_copy(deep=True)
    normalized.symbols = [
        normalize_swap_symbol(symbol)
        for symbol in normalized.symbols
        if symbol
    ]
    if normalized.symbol_x:
        normalized.symbol_x = normalize_swap_symbol(normalized.symbol_x)
    if normalized.symbol_y:
        normalized.symbol_y = normalize_swap_symbol(normalized.symbol_y)
    if normalized.perp_symbol:
        normalized.perp_symbol = normalize_swap_symbol(normalized.perp_symbol)
    if normalized.spot_symbol:
        normalized.spot_symbol = normalize_spot_symbol(normalized.spot_symbol)
    return normalized


def _resolve_data_dir(data_dir: str | None) -> Path:
    raw = data_dir or "data/ticks"
    if not _SAFE_DATA_DIR_RE.match(raw):
        raise HTTPException(status_code=400, detail="Invalid data_dir")
    resolved = (PROJECT_ROOT / raw).resolve()
    try:
        resolved.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="data_dir path traversal not allowed") from exc
    return resolved


def _validate_backtest_request(req: RunBacktestRequest) -> None:
    _resolve_data_dir(req.data_dir)
    if req.start and not _SAFE_DATE_RE.match(req.start):
        raise HTTPException(status_code=400, detail="Invalid start date format")
    if req.end and not _SAFE_DATE_RE.match(req.end):
        raise HTTPException(status_code=400, detail="Invalid end date format")
    if len(req.universe) > 50:
        raise HTTPException(status_code=400, detail="Universe too large (max 50 symbols)")
    if len(req.symbols) > 50:
        raise HTTPException(status_code=400, detail="Symbol list too large (max 50 symbols)")
    if req.benchmark and not _SAFE_SYMBOL_RE.match(req.benchmark):
        raise HTTPException(status_code=400, detail=f"Invalid symbol: {req.benchmark}")
    for sym in req.universe:
        if not _SAFE_SYMBOL_RE.match(sym):
            raise HTTPException(status_code=400, detail=f"Invalid symbol: {sym}")
    for sym in req.symbols:
        if not _SAFE_SYMBOL_RE.match(sym):
            raise HTTPException(status_code=400, detail=f"Invalid symbol: {sym}")
    for key, value in req.strategy_params.items():
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", str(key)):
            raise HTTPException(status_code=400, detail=f"Invalid strategy param: {key}")
        if not isinstance(value, (int, float, str, bool)) and value is not None:
            raise HTTPException(status_code=400, detail=f"Invalid strategy param value for: {key}")
    try:
        req.risk_overrides = sanitize_risk_overrides(req.risk_overrides)
    except ResearchControlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _validate_parameter_sweep_request(req: ParameterSweepRequest) -> None:
    _resolve_data_dir(req.data_dir)
    if req.strategy not in {"ma_crossover", "ema_crossover", "macd_crossover"}:
        raise HTTPException(status_code=400, detail="Parameter sweep supports MA, EMA, and MACD only")
    if req.finalist_validation not in {None, "none", "wf", "cpcv", "both"}:
        raise HTTPException(status_code=400, detail="Unsupported finalist validation mode")
    if req.start and not _SAFE_DATE_RE.match(req.start):
        raise HTTPException(status_code=400, detail="Invalid start date format")
    if req.end and not _SAFE_DATE_RE.match(req.end):
        raise HTTPException(status_code=400, detail="Invalid end date format")
    if not req.symbols:
        raise HTTPException(status_code=400, detail="Parameter sweep requires at least one symbol")
    if len(req.symbols) > 50:
        raise HTTPException(status_code=400, detail="Symbol list too large (max 50 symbols)")
    for sym in req.symbols:
        if not _SAFE_SYMBOL_RE.match(sym):
            raise HTTPException(status_code=400, detail=f"Invalid symbol: {sym}")
    for key, value in req.parameter_grid.items():
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", str(key)):
            raise HTTPException(status_code=400, detail=f"Invalid parameter: {key}")
        if not isinstance(value, (int, float, str, list, tuple)):
            raise HTTPException(status_code=400, detail=f"Invalid parameter value for: {key}")
    try:
        req.risk_overrides = sanitize_risk_overrides(req.risk_overrides)
    except ResearchControlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
