"""
Backtest results REST endpoints.
Scans results/ directory for run subdirectories containing result.json.
Each result.json matches the artifacts schema produced by backtesting/artifacts.py.
"""
from __future__ import annotations

import csv
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import FileResponse
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
from backtesting.turtle_backtest import (
    DEFAULT_TURTLE_SWEEP_MAX_COMBINATIONS,
    HARD_TURTLE_SWEEP_MAX_COMBINATIONS,
)
from backtesting.artifact_rows import (
    read_artifact_rows,
    resolve_artifact_child,
    resolve_artifact_path,
    validate_artifact_id,
    validation_artifact_type,
)
from backtesting.research_controls import ResearchControlError, normalize_execution_profile, sanitize_risk_overrides
from okx_quant.core.symbols import normalize_spot_symbol, normalize_swap_symbol

_run_jobs: dict[str, dict[str, Any]] = {}
_sweep_jobs: dict[str, dict[str, Any]] = {}
_validation_jobs: dict[str, dict[str, Any]] = {}
_price_series_fallback_cache: dict[tuple[str, str], list[dict[str, Any]]] = {}

# Live backtest subprocesses, keyed by job_id, so /run/cancel can terminate them.
_run_procs: dict[str, "subprocess.Popen[str]"] = {}
_RUN_TERMINAL_STATUSES = {"done", "error", "cancelled"}
_SWEEP_TERMINAL_STATUSES = {"done", "error", "cancelled"}
TURTLE_SWEEP_INLINE_ROW_LIMIT = 5_000
TURTLE_SWEEP_INLINE_EQUITY_ROW_LIMIT = 50_000


def _run_cancel_requested(job_id: str) -> bool:
    return bool(_run_jobs.get(job_id, {}).get("cancel_requested"))


def _mark_run_cancelled(job_id: str, output: str | None = None) -> None:
    job = _run_jobs.get(job_id)
    if job is None:
        return
    job.update({
        "status": "cancelled",
        "progress": 100,
        "message": "Backtest cancelled by user",
    })
    if output is not None:
        job["output"] = output[-4000:]


def _sweep_cancel_requested(job_id: str) -> bool:
    return bool(_sweep_jobs.get(job_id, {}).get("cancel_requested"))


def _mark_sweep_cancelled(job_id: str) -> None:
    job = _sweep_jobs.get(job_id)
    if job is None:
        return
    job.update({
        "status": "cancelled",
        "progress": 100,
        "message": "Sweep cancelled by user",
        "updated_at": _utc_now_iso(),
        "finished_at": _utc_now_iso(),
    })


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


IDEALIZED_FILL_WARNING = (
    "fill_all_signals=true: research-only artefact, not admissible as edge / "
    "promotion / live-readiness evidence (see docs/ai_collaboration.md Deployment Gate)."
)


def _contains_idealized_fill_flag(value: Any) -> bool:
    if isinstance(value, dict):
        if bool(value.get("idealized_fill")) or bool(value.get("fill_all_signals")):
            return True
        return any(_contains_idealized_fill_flag(v) for v in value.values())
    if isinstance(value, list):
        return any(_contains_idealized_fill_flag(v) for v in value)
    return False


def _attach_idealized_fill_warning(payload: dict[str, Any], source: Any | None = None) -> dict[str, Any]:
    if not _contains_idealized_fill_flag(source if source is not None else payload):
        return payload
    warnings = list(payload.get("warnings") or [])
    if "idealized_fill" not in warnings:
        warnings.append("idealized_fill")
    payload["warnings"] = warnings
    validation_warnings = list(payload.get("validation_warnings") or [])
    if IDEALIZED_FILL_WARNING not in validation_warnings:
        validation_warnings.append(IDEALIZED_FILL_WARNING)
    payload["validation_warnings"] = validation_warnings
    validation = payload.get("validation")
    if isinstance(validation, dict):
        validation["idealized_fill"] = True
    return payload


_SUMMARY_KEYS = {
    "run_id",
    "display_name",
    "created_at",
    "mode",
    "strategies",
    "strategy",
    "symbols",
    "symbol",
    "bar",
    "start",
    "end",
    "backend",
    "data_source",
    "metrics",
    "parameters",
    "artifacts",
    "validation",
    "warnings",
    "validation_warnings",
}

_VALIDATION_INPUT_ARTIFACT_FILES = {
    "result": "result.json",
    "config": "config.json",
    "price_series": "price_series.csv",
    "indicator_series": "indicator_series.csv",
    "signals": "signals.csv",
    "trades": "trades.csv",
    "fills": "fills.csv",
    "equity": "equity_curve.csv",
    "target_weights": "target_weights.csv",
    "funding_rates": "funding_rates.csv",
    "external_observations": "external_observations.csv",
}

_VALIDATION_JSON_ARTIFACTS = {"result", "config"}

_TURTLE_SWEEP_ARTIFACT_FILES = {
    "summary": "summary.json",
    "summary.json": "summary.json",
    "rows": "rows.csv",
    "rows.csv": "rows.csv",
    "equity_curves": "equity_curves.csv",
    "equity_curves.csv": "equity_curves.csv",
    "surface": "surface.html",
    "surface.html": "surface.html",
}


def _summary_payload(result: dict[str, Any]) -> dict[str, Any]:
    summary = {key: result[key] for key in _SUMMARY_KEYS if key in result}
    artifacts = summary.get("artifacts")
    if isinstance(artifacts, dict):
        summary["artifact_availability"] = {key: bool(value) for key, value in artifacts.items()}
    validation = summary.get("validation")
    if isinstance(validation, dict):
        summary["validation_flags"] = {
            key: value
            for key, value in validation.items()
            if isinstance(value, (bool, int, float, str)) or value is None
        }
    return summary


def _display_slug(value: Any, fallback: str = "unknown") -> str:
    text = str(value or "").strip()
    if not text:
        text = fallback
    text = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")
    return text.lower() or fallback


def _backtest_display_name(row: dict[str, Any]) -> str:
    existing = row.get("display_name")
    if existing:
        return str(existing)
    created = row.get("created_at") or row.get("start") or row.get("start_date")
    try:
        ts = pd.Timestamp(created) if created else pd.Timestamp.now(tz="UTC")
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        day = ts.tz_convert("UTC").strftime("%Y/%m/%d")
    except Exception:
        day = datetime.now(timezone.utc).strftime("%Y/%m/%d")
    strategies = row.get("strategies") or ([row.get("strategy")] if row.get("strategy") else [])
    symbols = row.get("symbols") or ([row.get("symbol")] if row.get("symbol") else [])
    strategy = _display_slug("_".join(str(s) for s in strategies if s) or "strategy")
    symbol_values = [str(s) for s in symbols if s]
    symbol = _display_slug("_".join(symbol_values[:3]) if symbol_values else "multi_symbol")
    if len(symbol_values) > 3:
        symbol = f"{symbol}_plus{len(symbol_values) - 3}"
    return f"{day}_{strategy}_{symbol}"


def _get_price_series_cache(key: tuple[str, str]) -> list[dict[str, Any]] | None:
    rows = _price_series_fallback_cache.get(key)
    return [dict(row) for row in rows] if rows is not None else None


def _set_price_series_cache(key: tuple[str, str], rows: list[dict[str, Any]]) -> None:
    if len(_price_series_fallback_cache) >= 16 and key not in _price_series_fallback_cache:
        _price_series_fallback_cache.clear()
    _price_series_fallback_cache[key] = [dict(row) for row in rows]


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


def _resolve_candle_backend(exchange: str | None = None) -> tuple[str, str | None]:
    """Resolve the candle backend the backtest subprocesses should use.

    Returns (backend, dsn). Prefers `cfg.storage.candle_backend` from
    config/settings.yaml. Falls back to parquet when the DSN is missing OR
    unreachable unless an exchange was declared; venue-scoped candles require
    canonical source provenance.
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
            if exchange:
                raise ValueError(
                    f"Venue-scoped candle backend for exchange='{exchange}' requires "
                    "a reachable postgres DSN; parquet candles have no source provenance."
                )
            backend = "parquet"
            dsn = None
    return backend, dsn


_SAFE_DATA_DIR_RE = re.compile(r"^[\w./\-]+$")
_SAFE_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2})?$")
_SAFE_SYMBOL_RE = re.compile(r"^[A-Z0-9\-]+$")
_ALLOWED_EXCHANGES = {"binance", "okx", "bybit", "coinbase", "kraken"}


def _normalize_exchange(value: str | None) -> str:
    """Use the configured default when omitted and reject unknown venues."""
    candidate = (value or "").strip().lower()
    if candidate:
        if candidate not in _ALLOWED_EXCHANGES:
            allowed = ", ".join(sorted(_ALLOWED_EXCHANGES))
            raise HTTPException(status_code=400, detail=f"exchange must be one of: {allowed}")
        return candidate
    from okx_quant.core.config import load_config

    cfg = load_config(require_secrets=False)
    return str(cfg.storage.primary_exchange).lower()


def _artifact_id_or_400(value: str, field: str) -> str:
    try:
        return validate_artifact_id(value, field)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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
    fill_all_signals: bool = False
    execution_profile: str = "strategy_fill"


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
    max_combinations: int = Field(default=5000, ge=1, le=HARD_TURTLE_SWEEP_MAX_COMBINATIONS)
    liquidate_on_end: bool | None = None
    risk_overrides: dict[str, Any] = Field(default_factory=dict)
    fill_all_signals: bool = False
    run_finalists: bool = True
    finalist_top_pct: float = Field(default=0.10, gt=0.0, le=1.0)
    max_finalists: int = Field(default=20, ge=0, le=100)
    finalist_validation: str | None = None


class DifferentialValidationRequest(BaseModel):
    engines: list[str] = Field(default_factory=lambda: ["vectorbt", "backtrader", "nautilus"])
    validation_id: str | None = None


class StrategyDifferentialValidationRequest(BaseModel):
    strategy: str
    engines: list[str] = Field(default_factory=lambda: ["vectorbt", "backtrader", "nautilus"])
    validation_id: str | None = None
    fixture_run_id: str | None = None


def _request_field_was_set(req: BaseModel, name: str) -> bool:
    fields = getattr(req, "model_fields_set", None)
    if fields is None:
        fields = getattr(req, "__fields_set__", set())
    return name in fields


def _run_ohlcv_rotation_job(
    job_id: str,
    req: "RunBacktestRequest",
    run_id: str,
    results_dir: Path,
) -> None:
    try:
        script = PROJECT_ROOT / "scripts" / "backtest_ohlcv_rotation.py"
        out_dir = resolve_artifact_child(results_dir, run_id, "run_id")
        out_dir.mkdir(parents=True, exist_ok=True)
        bar = req.bar or "1H"

        exchange = _normalize_exchange(req.exchange)
        backend, dsn = _resolve_candle_backend(exchange)
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
        if req.fill_all_signals:
            cmd.append("--fill-all-signals")
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
        # Popen + communicate (not subprocess.run) so /run/cancel can terminate it.
        proc = subprocess.Popen(
            cmd,
            cwd=PROJECT_ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        _run_procs[job_id] = proc
        try:
            stdout, stderr = proc.communicate()
        finally:
            _run_procs.pop(job_id, None)
        _run_jobs[job_id]["progress"] = 80
        output = ((stdout or "") + "\n" + (stderr or "")).strip()
        if _run_cancel_requested(job_id):
            _mark_run_cancelled(job_id, output)
            return
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
        warning_fields: dict[str, Any] = {}
        result_path = out_dir / "result.json"
        if result_path.exists():
            try:
                warning_fields = _attach_idealized_fill_warning(
                    {},
                    json.loads(result_path.read_text(encoding="utf-8")),
                )
            except Exception:
                warning_fields = {}
        _run_jobs[job_id].update({
            "status": "done",
            "progress": 100,
            "message": "Backtest complete",
            "output": output[-4000:],
            **warning_fields,
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
    validation = {}
    if req.fill_all_signals:
        validation = {
            "fill_all_signals": True,
            "idealized_fill": True,
        }

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
            "price_series": "price_series.csv",
            "signals": "signals.csv",
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
    parameters = _request_parameters(req)
    rotation_params = parameters.setdefault("strategies", {}).setdefault("ohlcv_rotation", {})
    rotation_params.update({
        "benchmark_inst_id": req.benchmark or "BTC-USDT-SWAP",
        "bar": req.bar or "1H",
        "rebalance_minutes": req.rebalance_minutes or 60,
        "top_k": req.top_k or 3,
        "rank_exit_buffer": req.rank_exit_buffer or 6,
        "fill_all_signals": bool(req.fill_all_signals),
    })

    result = {
        "run_id": run_id,
        "created_at": pd.Timestamp.utcnow().isoformat(),
        "strategies": ["ohlcv_rotation"],
        "symbols": req.universe or [],
        "bar": req.bar or "1H",
        "benchmark": req.benchmark or "BTC-USDT-SWAP",
        "start": req.start or "",
        "end": req.end or "",
        "metrics": metrics,
        "parameters": parameters,
        "artifacts": artifact_refs,
    }
    if validation:
        result["validation"] = validation
    _attach_idealized_fill_warning(result)
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

        out_dir = resolve_artifact_child(results_dir, run_id, "run_id")
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
            if _run_cancel_requested(job_id):
                _mark_run_cancelled(job_id)
                return
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

        if _run_cancel_requested(job_id):
            _mark_run_cancelled(job_id)
            return
        # ponytail: the compute itself isn't interruptible; cancel is honored at
        # the load-loop and pre-compute checkpoints, which covers the slow part.
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
        _write_daily_winner_artifacts(out_dir, dfs, result_json)
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

    round_trips = result.trades.copy()
    round_trip_records = json.loads(
        round_trips.to_json(orient="records", date_format="iso", force_ascii=False)
    )
    for i, record in enumerate(round_trip_records):
        record["id"] = record.get("id", i)
        record["round_trip_id"] = record.get("round_trip_id", i)
        record["strategy"] = "daily_winner"
        record["type"] = "validation_round_trip"
    trades_records = _daily_winner_execution_rows(
        round_trip_records,
        equity_records=equity_records,
        initial_equity=req.initial_equity or 5000.0,
    )

    metrics = dict(result.metrics)
    _daily_winner_apply_execution_metrics(metrics, round_trip_records, trades_records)
    metrics.setdefault("bankrupt", False)
    metrics.setdefault("funding_cashflow", 0.0)
    metrics.setdefault("funding_settlement_count", 0)
    metrics.setdefault("funding_mode", "not_modeled")
    metrics["loaded_symbols"] = loaded_symbols
    metrics["skipped_symbols"] = skipped_symbols
    metrics = {key: _json_safe(value) for key, value in metrics.items()}
    validation_mode = _daily_winner_validation_mode(req.validation)

    return {
        "run_id": run_id,
        "created_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "strategies": ["daily_winner"],
        "symbols": loaded_symbols,
        "bar": "1D",
        "start": req.start or "",
        "end": req.end or "",
        "metrics": metrics,
        "parameters": _request_parameters(req),
        "equity": equity_records,
        "returns": returns_records,
        "round_trips": round_trip_records,
        "trades": trades_records,
        "artifacts": {},
        "validation": {
            "validation_only": True,
            "validation_mode": validation_mode,
            "validation_requested": validation_mode,
            "daily_winner_data_sources": data_sources or [],
        },
    }


def _daily_winner_validation_mode(mode: str | None) -> str:
    return mode if mode in {"wf", "cpcv", "both"} else "none"


def _daily_winner_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _write_daily_winner_artifacts(
    out_dir: Path,
    dfs: dict[str, pd.DataFrame],
    payload: dict[str, Any],
) -> None:
    artifact_refs = payload.setdefault("artifacts", {})

    price_series = _daily_winner_price_series_frame(dfs)
    if not price_series.empty:
        price_series.to_csv(out_dir / "price_series.csv", index=False)
        artifact_refs["price_series"] = "price_series.csv"

    signals = _daily_winner_signal_rows(payload)
    pd.DataFrame(
        signals,
        columns=["ts", "datetime", "strategy", "inst_id", "side", "fair_value"],
    ).to_csv(out_dir / "signals.csv", index=False)
    artifact_refs["signals"] = "signals.csv"

    for key, filename in {
        "trades": "trades.csv",
        "round_trips": "round_trips.csv",
        "equity": "equity_curve.csv",
        "returns": "returns.csv",
    }.items():
        rows = payload.get(key) or []
        if isinstance(rows, list):
            pd.DataFrame(rows).to_csv(out_dir / filename, index=False)
            artifact_refs[key] = filename

    pd.DataFrame(columns=["ts", "datetime", "strategy", "inst_id"]).to_csv(
        out_dir / "indicator_series.csv",
        index=False,
    )
    pd.DataFrame().to_csv(out_dir / "fills.csv", index=False)


def _turtle_symbol(req: "RunBacktestRequest | ParameterSweepRequest") -> str:
    symbols = [symbol for symbol in (req.symbols or []) if symbol]
    if not symbols and isinstance(req, RunBacktestRequest) and req.benchmark:
        symbols = [req.benchmark]
    if len(symbols) != 1:
        raise ValueError("turtle requires exactly one symbol")
    return normalize_swap_symbol(symbols[0])


def _turtle_fixed_grid_scalar(grid: dict[str, Any], name: str) -> Any | None:
    value = grid.get(name)
    if isinstance(value, dict):
        if "fixed" not in value:
            return None
        value = value.get("fixed")
    if isinstance(value, (list, tuple)):
        return value[0] if len(value) == 1 else None
    if isinstance(value, str) and ("~" in value or "," in value or ".." in value):
        return None
    return value


def _turtle_sweep_base_params(grid: dict[str, Any]) -> dict[str, Any]:
    param_keys = {
        "enter_term_sys1",
        "enter_term_sys2",
        "leave_term_sys1",
        "leave_term_sys2",
        "single_sys_unit_limit",
        "both_sys_unit_limit",
        "own_capital",
        "invest_pct",
        "min_position",
        "fee",
        "atr_period",
    }
    return {
        name: value
        for name in param_keys
        if (value := _turtle_fixed_grid_scalar(grid, name)) is not None
    }


def _coerce_turtle_invest_pct(value: Any) -> float:
    text = str(value).strip()
    has_percent_suffix = text.endswith("%")
    if has_percent_suffix:
        text = text[:-1].strip()
    number = float(text)
    if has_percent_suffix or number > 1:
        return number / 100.0
    return number


def _turtle_params_from_request(req: "RunBacktestRequest | ParameterSweepRequest") -> Any:
    from backtesting.turtle_backtest import TurtleParams

    raw = dict(getattr(req, "strategy_params", {}) or {})
    if isinstance(req, ParameterSweepRequest):
        raw.update(_turtle_sweep_base_params(req.parameter_grid or {}))
    raw.setdefault("own_capital", req.initial_equity or TurtleParams().own_capital)
    int_fields = {
        "enter_term_sys1",
        "enter_term_sys2",
        "leave_term_sys1",
        "leave_term_sys2",
        "single_sys_unit_limit",
        "both_sys_unit_limit",
        "atr_period",
    }
    float_fields = {"own_capital", "invest_pct", "min_position", "fee"}
    cleaned: dict[str, Any] = {}
    for key, value in raw.items():
        if key in int_fields and value is not None and value != "":
            cleaned[key] = int(value)
        elif key == "invest_pct" and value is not None and value != "":
            cleaned[key] = _coerce_turtle_invest_pct(value)
        elif key in float_fields and value is not None and value != "":
            cleaned[key] = float(value)
        else:
            cleaned[key] = value
    params = TurtleParams(**cleaned)
    params.validate()
    return params


def _turtle_load_daily_candles(req: "RunBacktestRequest | ParameterSweepRequest", symbol: str) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    from backtesting.data_loader import load_candles

    dsn = os.environ.get("DATABASE_URL") or "postgresql://quant:changeme@127.0.0.1:5432/quant"
    exchange = _normalize_exchange(req.exchange)
    load_backend = "market" if exchange else "postgres"
    attempts: list[dict[str, Any]] = []
    df = pd.DataFrame()
    try:
        df = load_candles(
            inst_id=symbol,
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
    except Exception as exc:
        attempts.append({
            "backend": load_backend,
            "exchange": exchange if load_backend == "market" else None,
            "rows": 0,
            "error": str(exc),
        })
    if df.empty and load_backend == "market":
        df = load_candles(
            inst_id=symbol,
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
            "fallback": "canonical_1d",
        })
    if df.empty:
        raise ValueError(f"No 1D OHLCV loaded for turtle symbol {symbol}")
    return df, attempts


def _run_turtle_job(
    job_id: str,
    req: "RunBacktestRequest",
    run_id: str,
    results_dir: Path,
) -> None:
    try:
        from backtesting.turtle_backtest import run_turtle_backtest

        if (req.bar or "1D") != "1D":
            raise ValueError("turtle supports 1D bars only")
        out_dir = resolve_artifact_child(results_dir, run_id, "run_id")
        out_dir.mkdir(parents=True, exist_ok=True)
        symbol = _turtle_symbol(req)
        params = _turtle_params_from_request(req)
        _run_jobs[job_id].update({
            "status": "running",
            "progress": 10,
            "message": "Loading turtle 1D candles from DB",
        })
        daily_df, attempts = _turtle_load_daily_candles(req, symbol)
        if _run_cancel_requested(job_id):
            _mark_run_cancelled(job_id)
            return
        _run_jobs[job_id].update({"progress": 65, "message": "Running turtle reference-port backtest"})
        result = run_turtle_backtest(daily_df, params)
        payload = _build_turtle_result_json(
            run_id=run_id,
            req=req,
            result=result,
            symbol=symbol,
            data_sources=[{
                "inst_id": symbol,
                "status": "loaded",
                "rows": int(len(daily_df)),
                "first_ts": str(daily_df.index.min()) if not daily_df.empty else None,
                "last_ts": str(daily_df.index.max()) if not daily_df.empty else None,
                "attempts": attempts,
            }],
        )
        _run_jobs[job_id].update({"progress": 85, "message": "Writing turtle frontend artifacts"})
        _write_turtle_artifacts(out_dir, symbol, daily_df, result, payload)
        payload = _json_sanitize(payload)
        (out_dir / "result.json").write_text(
            json.dumps(payload, allow_nan=False, indent=2),
            encoding="utf-8",
        )
        _run_jobs[job_id].update({
            "status": "done",
            "progress": 100,
            "message": "Backtest complete",
            "output": f"Turtle completed for {symbol}: {payload['metrics'].get('order_count', 0)} orders",
        })
    except Exception as exc:
        _run_jobs[job_id].update({
            "status": "error",
            "progress": 100,
            "message": str(exc),
        })


def _build_turtle_result_json(
    *,
    run_id: str,
    req: "RunBacktestRequest",
    result: Any,
    symbol: str,
    data_sources: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    params = _turtle_params_from_request(req)
    equity_records = _turtle_equity_records(result.equity_curve)
    returns_records = [
        {
            "ts": row["ts"],
            "datetime": row["datetime"],
            "return": row["return"],
            "log_return": math.log1p(row["return"]) if row["return"] > -1 else None,
        }
        for row in equity_records
    ]
    trades_records = _turtle_trade_records(result.trades, symbol)
    parameters = _request_parameters(req)
    parameters.setdefault("strategies", {})["turtle"] = {
        **asdict(params),
        "symbol": symbol,
        "bar": "1D",
        "research_only_reference_port": True,
    }
    metrics = dict(result.metrics)
    metrics["validation_only"] = True
    metrics["research_only"] = True
    return {
        "run_id": run_id,
        "created_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "strategies": ["turtle"],
        "symbols": [symbol],
        "bar": "1D",
        "start": req.start or "",
        "end": req.end or "",
        "metrics": _json_sanitize(metrics),
        "parameters": _json_sanitize(parameters),
        "equity": equity_records,
        "returns": returns_records,
        "trades": trades_records,
        "artifacts": {},
        "validation": {
            "validation_only": True,
            "validation_mode": "none",
            "research_only": True,
            "controls_ignored": ["risk_overrides", "execution_profile", "fill_all_signals"],
            "turtle_data_sources": data_sources or [],
            "reference_semantics": "new_startegy turtle_trading_system_full port",
        },
        "data_source": {
            "primary_exchange": _normalize_exchange(req.exchange),
            "backend": "market_or_postgres_1d",
        },
    }


def _turtle_equity_records(equity_curve: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for _, row in equity_curve.iterrows():
        ts_ms, dt = _visual_time_values(row.get("date"))
        if ts_ms is None:
            continue
        rows.append({
            "ts": ts_ms,
            "datetime": dt,
            "equity": _daily_winner_float(row.get("equity"), 0.0),
            "return": _daily_winner_float(row.get("return"), 0.0),
            "drawdown": _daily_winner_float(row.get("drawdown"), 0.0),
        })
    return rows


def _turtle_trade_records(trades: pd.DataFrame, symbol: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if trades is None or trades.empty:
        return records
    for i, row in trades.reset_index(drop=True).iterrows():
        ts_ms, dt = _visual_time_values(_first_present(row, ["ts", "datetime"]))
        if ts_ms is None:
            continue
        action = str(row.get("action") or "")
        side = "sell" if action == "exit" else "buy"
        price = _daily_winner_float(row.get("price"), 0.0)
        qty = _daily_winner_float(row.get("size"), 0.0)
        records.append({
            "id": i,
            "ts": ts_ms,
            "datetime": dt,
            "strategy": "turtle",
            "inst_id": symbol,
            "symbol": symbol,
            "system": row.get("system"),
            "side": side,
            "execution_phase": "exit" if side == "sell" else "entry",
            "action": action,
            "reason": row.get("reason"),
            "price": price,
            "fill_px": price,
            "qty": qty,
            "fill_sz": qty,
            "fee": _daily_winner_float(row.get("fee_paid"), 0.0),
            "notional_usd": abs(price * qty),
            "pnl": row.get("pnl"),
            "net_realized_pnl": row.get("pnl"),
            "cash_after": row.get("cash_after"),
            "position_after": row.get("units_after"),
        })
    return _json_sanitize(records)


def _turtle_price_series_frame(symbol: str, daily_df: pd.DataFrame) -> pd.DataFrame:
    data = daily_df.sort_index().copy()
    if not isinstance(data.index, pd.DatetimeIndex):
        if "date" in data.columns:
            data.index = pd.to_datetime(data["date"], utc=True, errors="coerce")
        elif "ts" in data.columns:
            data.index = pd.to_datetime(data["ts"], utc=True, errors="coerce")
    rows: list[dict[str, Any]] = []
    for ts_value, row in data.iterrows():
        ts_ms, dt = _visual_time_values(ts_value)
        if ts_ms is None:
            continue
        rows.append({
            "ts": ts_ms,
            "datetime": dt,
            "inst_id": symbol,
            "open": _daily_winner_float(row.get("open"), float("nan")),
            "high": _daily_winner_float(row.get("high"), float("nan")),
            "low": _daily_winner_float(row.get("low"), float("nan")),
            "close": _daily_winner_float(row.get("close"), float("nan")),
            "vol": _daily_winner_float(row.get("vol", row.get("volume")), 0.0),
        })
    return pd.DataFrame(rows, columns=["ts", "datetime", "inst_id", "open", "high", "low", "close", "vol"])


def _turtle_indicator_series_frame(symbol: str, frame: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "ATR",
        "last_enter_max_sys1",
        "last_enter_max_sys2",
        "last_leave_min_sys1",
        "last_leave_min_sys2",
        "s1_stop_loss",
        "s2_stop_loss",
        "s1_units",
        "s2_units",
        "total_units",
        "equity",
    ]
    rows: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        ts_ms, dt = _visual_time_values(row.get("date"))
        if ts_ms is None:
            continue
        item = {"ts": ts_ms, "datetime": dt, "strategy": "turtle", "inst_id": symbol}
        for col in columns:
            item[col] = row.get(col)
        rows.append(item)
    return pd.DataFrame(rows, columns=["ts", "datetime", "strategy", "inst_id", *columns])


def _write_turtle_artifacts(
    out_dir: Path,
    symbol: str,
    daily_df: pd.DataFrame,
    result: Any,
    payload: dict[str, Any],
) -> None:
    artifact_refs = payload.setdefault("artifacts", {})
    price_series = _turtle_price_series_frame(symbol, daily_df)
    price_series.to_csv(out_dir / "price_series.csv", index=False)
    artifact_refs["price_series"] = "price_series.csv"

    indicator_series = _turtle_indicator_series_frame(symbol, result.frame)
    indicator_series.to_csv(out_dir / "indicator_series.csv", index=False)
    artifact_refs["indicator_series"] = "indicator_series.csv"

    trades = pd.DataFrame(payload.get("trades") or [])
    trades.to_csv(out_dir / "trades.csv", index=False)
    artifact_refs["trades"] = "trades.csv"

    signals = trades[["ts", "datetime", "strategy", "inst_id", "side", "price"]].rename(
        columns={"price": "fair_value"}
    ) if not trades.empty else pd.DataFrame(columns=["ts", "datetime", "strategy", "inst_id", "side", "fair_value"])
    signals.to_csv(out_dir / "signals.csv", index=False)
    artifact_refs["signals"] = "signals.csv"

    fills = trades.copy() if not trades.empty else pd.DataFrame(columns=["ts", "datetime", "strategy", "inst_id", "side", "fill_px", "fill_sz", "state"])
    if not fills.empty:
        fills["state"] = "filled"
    fills.to_csv(out_dir / "fills.csv", index=False)
    artifact_refs["fills"] = "fills.csv"

    equity = pd.DataFrame(payload.get("equity") or [])
    equity.to_csv(out_dir / "equity_curve.csv", index=False)
    artifact_refs["equity"] = "equity_curve.csv"

    returns = pd.DataFrame(payload.get("returns") or [])
    returns.to_csv(out_dir / "returns.csv", index=False)
    artifact_refs["returns"] = "returns.csv"

    drawdown = equity[["ts", "datetime", "equity", "drawdown"]].copy() if not equity.empty else pd.DataFrame()
    if not drawdown.empty:
        drawdown["running_max_equity"] = equity["equity"].cummax()
        drawdown["drawdown_pct"] = drawdown["drawdown"]
    drawdown.to_csv(out_dir / "drawdown.csv", index=False)
    artifact_refs["drawdown"] = "drawdown.csv"

    (out_dir / "metrics.json").write_text(
        json.dumps(_json_sanitize(payload.get("metrics") or {}), indent=2, allow_nan=False),
        encoding="utf-8",
    )
    artifact_refs["metrics"] = "metrics.json"


def _daily_winner_price_series_frame(dfs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for inst_id, df in dfs.items():
        if df is None or df.empty:
            continue
        data = df.sort_index().copy()
        for ts_value, row in data.iterrows():
            ts_ms, dt = _visual_time_values(ts_value)
            if ts_ms is None:
                continue
            rows.append({
                "ts": ts_ms,
                "datetime": dt,
                "inst_id": inst_id,
                "open": _daily_winner_float(row.get("open"), float("nan")),
                "high": _daily_winner_float(row.get("high"), float("nan")),
                "low": _daily_winner_float(row.get("low"), float("nan")),
                "close": _daily_winner_float(row.get("close"), float("nan")),
                "vol": _daily_winner_float(row.get("vol", row.get("volume")), 0.0),
            })
    return pd.DataFrame(rows, columns=["ts", "datetime", "inst_id", "open", "high", "low", "close", "vol"])


def _daily_winner_signal_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    round_trips = [row for row in payload.get("round_trips") or [] if isinstance(row, dict)]
    trades = [row for row in payload.get("trades") or [] if isinstance(row, dict)]
    source_rows = round_trips or trades
    for row in source_rows:
        phase = str(row.get("execution_phase") or "").lower()
        is_execution = phase in {"entry", "exit"} or str(row.get("type") or "") == "validation_synthetic_fill"
        if is_execution:
            signal = _daily_winner_signal_row(
                inst_id=str(row.get("inst_id") or row.get("symbol") or ""),
                side=str(row.get("side") or "").lower(),
                ts_value=row.get("datetime") or row.get("ts"),
                fair_value=row.get("price", row.get("fill_px")),
            )
            if signal:
                rows.append(signal)
            continue
        entry = _daily_winner_signal_row(
            inst_id=str(row.get("inst_id") or row.get("symbol") or ""),
            side="buy",
            ts_value=row.get("entry_ts") or row.get("datetime") or row.get("ts"),
            fair_value=row.get("entry_price", row.get("price")),
        )
        if entry:
            rows.append(entry)
        exit_row = _daily_winner_signal_row(
            inst_id=str(row.get("inst_id") or row.get("symbol") or ""),
            side="sell",
            ts_value=row.get("exit_ts") or row.get("close_ts"),
            fair_value=row.get("exit_price", row.get("close_price")),
        )
        if exit_row:
            rows.append(exit_row)
    return rows


def _daily_winner_signal_row(
    *,
    inst_id: str,
    side: str,
    ts_value: Any,
    fair_value: Any,
) -> dict[str, Any] | None:
    if not inst_id or side not in {"buy", "sell"}:
        return None
    ts_ms, dt = _visual_time_values(ts_value)
    if ts_ms is None:
        return None
    return {
        "ts": ts_ms,
        "datetime": dt,
        "strategy": "daily_winner",
        "inst_id": inst_id,
        "side": side,
        "fair_value": _daily_winner_float(fair_value, float("nan")),
    }


def _daily_winner_equity_seed(
    equity_records: list[dict[str, Any]] | None,
    initial_equity: float | None,
) -> float:
    for row in equity_records or []:
        value = row.get("equity_usd", row.get("equity"))
        equity = _daily_winner_float(value, float("nan"))
        if math.isfinite(equity) and equity > 0:
            return equity
    return _daily_winner_float(initial_equity, 5000.0)


def _daily_winner_sort_key(row: dict[str, Any]) -> pd.Timestamp:
    value = row.get("entry_ts") or row.get("datetime") or row.get("ts") or row.get("exit_ts")
    ts = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(ts):
        return pd.Timestamp("2262-01-01", tz="UTC")
    return ts


def _daily_winner_execution_rows(
    round_trips: list[dict[str, Any]],
    *,
    equity_records: list[dict[str, Any]] | None = None,
    initial_equity: float | None = None,
) -> list[dict[str, Any]]:
    """Expand daily_winner round trips into synthetic buy/sell execution rows."""
    rows: list[dict[str, Any]] = []
    current_equity = _daily_winner_equity_seed(equity_records, initial_equity)
    ordered = sorted((dict(row) for row in round_trips or []), key=_daily_winner_sort_key)
    for i, trade in enumerate(ordered):
        inst_id = str(trade.get("inst_id") or trade.get("symbol") or "")
        entry_ts = trade.get("entry_ts") or trade.get("datetime") or trade.get("ts")
        exit_ts = trade.get("exit_ts") or trade.get("close_ts")
        entry_price = _daily_winner_float(trade.get("entry_price", trade.get("price")), 0.0)
        exit_price = _daily_winner_float(trade.get("exit_price", trade.get("close_price", entry_price)), 0.0)
        if not inst_id or entry_price <= 0 or exit_price <= 0:
            continue

        entry_equity = _daily_winner_float(trade.get("entry_equity"), current_equity)
        if entry_equity <= 0:
            entry_equity = current_equity
        cost_rate = abs(_daily_winner_float(trade.get("cost_rate"), 0.0))
        gross_return = _daily_winner_float(trade.get("gross_return"), exit_price / entry_price - 1.0)
        net_return = _daily_winner_float(trade.get("net_return"), gross_return - cost_rate)
        qty = entry_equity / entry_price if entry_price > 0 else 0.0
        entry_notional = abs(qty * entry_price)
        exit_notional = abs(qty * exit_price)
        total_cost = abs(entry_equity * cost_rate)
        entry_fee = total_cost / 2.0
        exit_fee = total_cost / 2.0
        pnl_usd = entry_equity * net_return
        exit_equity = entry_equity + pnl_usd
        round_trip_id = int(_daily_winner_float(trade.get("round_trip_id", trade.get("id", i)), i))

        base = {
            "inst_id": inst_id,
            "symbol": inst_id,
            "strategy": "daily_winner",
            "status": "FILLED",
            "type": "validation_synthetic_fill",
            "round_trip_id": round_trip_id,
            "entry_ts": entry_ts,
            "exit_ts": exit_ts,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "qty": qty,
            "fill_sz": qty,
            "gross_return": gross_return,
            "net_return": net_return,
            "cost_rate": cost_rate,
            "holding_minutes": trade.get("holding_minutes", 1440),
        }
        rows.append({
            **base,
            "id": round_trip_id * 2,
            "execution_phase": "entry",
            "side": "buy",
            "datetime": entry_ts,
            "ts": entry_ts,
            "price": entry_price,
            "fill_px": entry_price,
            "notional": entry_notional,
            "notional_usd": entry_notional,
            "fee": entry_fee,
            "pnl": None,
            "pnl_usd": None,
            "net_realized_pnl": None,
            "position_after": qty,
            "entry_equity": entry_equity,
            "exit_equity": None,
            "note": "validation-only synthetic BUY leg; quantity/notional inferred from full-equity daily allocation",
        })
        rows.append({
            **base,
            "id": round_trip_id * 2 + 1,
            "execution_phase": "exit",
            "side": "sell",
            "datetime": exit_ts,
            "ts": exit_ts,
            "price": exit_price,
            "fill_px": exit_price,
            "notional": exit_notional,
            "notional_usd": exit_notional,
            "fee": exit_fee,
            "pnl": pnl_usd,
            "pnl_usd": pnl_usd,
            "net_realized_pnl": pnl_usd,
            "position_after": 0.0,
            "entry_equity": entry_equity,
            "exit_equity": exit_equity,
            "note": "validation-only synthetic SELL leg; PnL shown on exit; funding is not modeled",
        })
        current_equity = exit_equity
    return _json_sanitize(rows)


def _daily_winner_is_execution_row(row: dict[str, Any]) -> bool:
    if row.get("execution_phase") in {"entry", "exit"}:
        return True
    return str(row.get("type") or "") == "validation_synthetic_fill"


def _daily_winner_apply_execution_metrics(
    metrics: dict[str, Any],
    round_trips: list[dict[str, Any]],
    execution_rows: list[dict[str, Any]],
) -> None:
    trade_count = int(metrics.get("number_of_trades") or len(round_trips) or len(execution_rows) // 2)
    fill_count = len(execution_rows) if execution_rows else trade_count * 2
    metrics.setdefault("profit_factor", 0.0)
    metrics["number_of_trades"] = trade_count
    metrics["order_count"] = fill_count
    metrics["fill_count"] = fill_count
    metrics["real_fill_count"] = fill_count
    metrics["orders_filled_count"] = fill_count
    metrics["fill_rate"] = 1.0 if fill_count else 0.0
    metrics["total_fees"] = float(sum(_daily_winner_float(row.get("fee"), 0.0) for row in execution_rows))
    metrics["fill_notional_usd"] = float(sum(_daily_winner_float(row.get("notional_usd", row.get("notional")), 0.0) for row in execution_rows))


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


def _request_parameters(req: "RunBacktestRequest") -> dict[str, Any]:
    turtle = req.strategy == "turtle"
    risk = {} if turtle else req.risk_overrides or {}
    fill_all_signals = False if turtle else bool(req.fill_all_signals)
    return _json_sanitize({
        "strategies": {
            req.strategy: req.strategy_params or {},
        },
        "risk": risk,
        "backtest": {
            "execution_profile": "strategy_fill" if turtle else req.execution_profile,
            "fill_all_signals": fill_all_signals,
        },
        "overrides": {
            "strategy_params": req.strategy_params or {},
            "risk_overrides": risk,
        },
    })


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
    validation_mode = _daily_winner_validation_mode(mode)
    validation = payload.setdefault("validation", {})
    validation["validation_only"] = True
    validation["validation_mode"] = validation_mode
    validation["validation_requested"] = validation_mode
    metrics = payload.setdefault("metrics", {})
    metrics["validation_only"] = True
    metrics["validation_requested"] = validation_mode
    if validation_mode in {"wf", "both"}:
        payload["walk_forward"] = _daily_winner_walk_forward(returns)
    cpcv = _daily_winner_cpcv(returns) if validation_mode in {"cpcv", "both"} else None
    if cpcv:
        payload["cpcv"] = cpcv
        metrics["psr"] = cpcv.get("psr")
        metrics["dsr"] = cpcv.get("dsr")


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
        from okx_quant.analytics.performance import sharpe

        metrics["sharpe"] = sharpe(return_series, periods=365)

    validation = dict(normalized.get("validation") or {})
    inferred_validation = "none"
    has_wf = bool(normalized.get("walk_forward") or normalized.get("walkForward"))
    has_cpcv = bool(normalized.get("cpcv"))
    if has_wf and has_cpcv:
        inferred_validation = "both"
    elif has_wf:
        inferred_validation = "wf"
    elif has_cpcv:
        inferred_validation = "cpcv"
    validation_mode = _daily_winner_validation_mode(
        validation.get("validation_mode")
        or validation.get("validation_requested")
        or metrics.get("validation_requested")
        or inferred_validation
    )
    validation["validation_only"] = True
    validation["validation_mode"] = validation_mode
    validation["validation_requested"] = validation_mode
    normalized["validation"] = validation

    cpcv = normalized.get("cpcv") if isinstance(normalized.get("cpcv"), dict) else None
    if cpcv:
        metrics["psr"] = cpcv.get("psr", metrics.get("psr"))
        metrics["dsr"] = cpcv.get("dsr", metrics.get("dsr"))
    elif validation_mode == "none":
        metrics.pop("psr", None)
        metrics.pop("dsr", None)

    raw_trades = [dict(row) for row in normalized.get("trades") or [] if isinstance(row, dict)]
    round_trips = [dict(row) for row in normalized.get("round_trips") or [] if isinstance(row, dict)]
    if not round_trips and raw_trades and not any(_daily_winner_is_execution_row(row) for row in raw_trades):
        round_trips = raw_trades
    execution_rows = (
        _daily_winner_execution_rows(round_trips, equity_records=equity)
        if round_trips
        else raw_trades
    )
    if round_trips:
        for i, row in enumerate(round_trips):
            row.setdefault("id", i)
            row.setdefault("round_trip_id", i)
            row.setdefault("strategy", "daily_winner")
            row.setdefault("type", "validation_round_trip")
    normalized["round_trips"] = round_trips
    normalized["trades"] = execution_rows
    _daily_winner_apply_execution_metrics(metrics, round_trips, execution_rows)
    metrics.setdefault("bankrupt", False)
    metrics.setdefault("funding_cashflow", 0.0)
    metrics.setdefault("funding_settlement_count", 0)
    metrics.setdefault("funding_mode", "not_modeled")
    metrics["validation_only"] = True
    metrics["validation_requested"] = validation_mode
    normalized["metrics"] = {key: _json_safe(value) for key, value in metrics.items()}
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
        if isinstance(value, str) and re.fullmatch(r"[+-]?\d+(?:\.\d+)?", value.strip()):
            raw = float(value)
            unit = "ms" if raw > 1_000_000_000_000 else "s" if raw > 1_000_000_000 else None
            ts = pd.to_datetime(raw, unit=unit, utc=True, errors="coerce") if unit else pd.to_datetime(raw, utc=True, errors="coerce")
        elif isinstance(value, (int, float, np.integer, np.floating)) and math.isfinite(float(value)):
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


def _record_symbol(row: dict[str, Any]) -> str:
    return str(row.get("inst_id") or row.get("symbol") or "")


def _filter_records_by_symbol(records: list[dict[str, Any]], symbol: str | None) -> list[dict[str, Any]]:
    if not symbol:
        return records
    return [row for row in records if _record_symbol(row) == symbol]


def _limit_records(records: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    if limit <= 0 or len(records) <= limit:
        return records
    return _downsample_records(records, limit)


def _data_source_exchange(result: dict[str, Any] | None) -> str:
    source = (result or {}).get("data_source") or {}
    return _normalize_exchange(source.get("primary_exchange") if isinstance(source, dict) else None)


def _dedupe_price_attempts(attempts: list[tuple[str, str | None]]) -> list[tuple[str, str | None]]:
    deduped: list[tuple[str, str | None]] = []
    for attempt in attempts:
        if attempt not in deduped:
            deduped.append(attempt)
    return deduped


def _preferred_price_series_attempts(
    result: dict[str, Any],
    inst_id: str,
    default_attempts: list[tuple[str, str | None]],
) -> list[tuple[str, str | None]]:
    """Prefer candle backends that are known to have loaded this daily_winner run."""
    validation = result.get("validation") or {}
    sources = validation.get("daily_winner_data_sources") or []
    preferred: list[tuple[str, str | None]] = []
    for source in sources:
        if not isinstance(source, dict) or source.get("inst_id") != inst_id:
            continue
        for attempt in source.get("attempts") or []:
            if not isinstance(attempt, dict) or _visual_float(attempt.get("rows"), 0.0) <= 0:
                continue
            backend = str(attempt.get("backend") or "").lower()
            if backend not in {"market", "postgres", "parquet"}:
                continue
            exchange = attempt.get("exchange") if backend == "market" else None
            preferred.append((backend, str(exchange) if exchange else None))
        break
    return _dedupe_price_attempts(preferred + default_attempts) if preferred else default_attempts


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
    deduped_attempts = _dedupe_price_attempts(attempts)

    def load_symbol_rows(inst_id: str) -> list[dict[str, Any]]:
        df = pd.DataFrame()
        for load_backend, load_exchange in _preferred_price_series_attempts(result, inst_id, deduped_attempts):
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
            return []
        symbol_rows: list[dict[str, Any]] = []
        for ts_value, candle in df.sort_index().iterrows():
            ts_ms, dt = _visual_time_values(ts_value)
            if ts_ms is None:
                continue
            symbol_rows.append({
                "ts": ts_ms,
                "datetime": dt,
                "inst_id": inst_id,
                "open": _visual_float(candle.get("open"), float("nan")),
                "high": _visual_float(candle.get("high"), float("nan")),
                "low": _visual_float(candle.get("low"), float("nan")),
                "close": _visual_float(candle.get("close"), float("nan")),
                "vol": _visual_float(candle.get("vol"), 0.0),
            })
        return symbol_rows

    rows: list[dict[str, Any]] = []
    for inst_id in selected:
        rows.extend(load_symbol_rows(inst_id))
    rows.sort(key=lambda row: (row.get("ts") or 0, row.get("inst_id") or ""))
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
        phase = str(trade.get("execution_phase") or "").lower()
        if phase in {"entry", "exit"} or str(trade.get("type") or "") == "validation_synthetic_fill":
            side = str(_first_present(trade, ["side"], "buy")).lower()
            row = marker(
                source=trade,
                ts_value=_first_present(trade, ["ts", "datetime", "time"]),
                inst_id=inst_id,
                side=side,
                price=_first_present(trade, ["fill_px", "price", "px", "avg_px"]),
                qty=_first_present(trade, ["fill_sz", "qty", "sz"]),
                pnl=_first_present(trade, ["net_realized_pnl", "pnl_usd", "pnl"]),
                text_prefix="EXIT" if phase == "exit" or side == "sell" else "ENTRY",
            )
            if row:
                markers.append(row)
            continue
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
            "--execution-profile",
            req.execution_profile,
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
        if req.fill_all_signals:
            cmd.append("--fill-all-signals")
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
        _run_procs[job_id] = proc

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
            _run_procs.pop(job_id, None)

        output = ("".join(lines) + "\n" + "".join(stderr_lines)).strip()
        if _run_cancel_requested(job_id):
            _mark_run_cancelled(job_id, output)
            return
        if proc.returncode != 0:
            _run_jobs[job_id].update({
                "status": "error",
                "progress": 100,
                "message": f"Backtest failed with exit code {proc.returncode}",
                "output": output[-4000:],
            })
            return
        warning_fields: dict[str, Any] = {}
        effective_run_id = validate_artifact_id(run_id, "run_id")
        comparison_path = resolve_artifact_child(
            results_dir,
            f"{effective_run_id}_execution_comparison.json",
            "artifact_name",
        )
        comparison_payload: dict[str, Any] = {}
        if req.execution_profile == "dual_output" and comparison_path.exists():
            try:
                comparison_payload = json.loads(comparison_path.read_text(encoding="utf-8"))
                effective_run_id = validate_artifact_id(
                    str(comparison_payload.get("strategy_fill_run_id") or f"{run_id}_strategy_fill"),
                    "run_id",
                )
            except Exception:
                effective_run_id = validate_artifact_id(f"{run_id}_strategy_fill", "run_id")
        result_path = resolve_artifact_path(
            results_dir,
            (effective_run_id, "run_id"),
            ("result.json", "artifact_name"),
        )
        if result_path.exists():
            try:
                warning_fields = _attach_idealized_fill_warning(
                    {},
                    json.loads(result_path.read_text(encoding="utf-8")),
                )
            except Exception:
                warning_fields = {}
        _run_jobs[job_id].update({
            "status": "done",
            "progress": 100,
            "message": "Backtest complete",
            "run_id": effective_run_id,
            "base_run_id": run_id if req.execution_profile == "dual_output" else None,
            "execution_profile": req.execution_profile,
            "execution_comparison": str(comparison_path) if comparison_payload else None,
            "comparison_run_ids": {
                "strategy_fill": comparison_payload.get("strategy_fill_run_id"),
                "realistic_execution": comparison_payload.get("realistic_execution_run_id"),
            } if comparison_payload else None,
            "output": output[-4000:],
            **warning_fields,
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
                "updated_at": _utc_now_iso(),
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
            fill_all_signals=req.fill_all_signals,
            run_finalists=req.run_finalists,
            finalist_top_pct=req.finalist_top_pct,
            max_finalists=req.max_finalists,
            finalist_validation=req.finalist_validation,
            full_output_dir=results_dir,
            progress_callback=_on_progress,
        )
        warning_fields = _attach_idealized_fill_warning({}, summary)
        if req.fill_all_signals and not warning_fields:
            warning_fields = _attach_idealized_fill_warning({}, {"idealized_fill": True})
        _sweep_jobs[job_id].update({
            "status": "done",
            "progress": 100,
            "message": "Parameter sweep complete",
            "updated_at": _utc_now_iso(),
            "finished_at": _utc_now_iso(),
            "sweep_id": summary["sweep_id"],
            "artifacts": summary.get("artifacts", {}),
            "top_results": summary.get("top_results", [])[:10],
            "completed_count": summary.get("completed_count", 0),
            "failed_count": summary.get("failed_count", 0),
            "skipped_count": summary.get("skipped_count", 0),
            "finalist_results": summary.get("finalist_results", []),
            "elapsed_seconds": summary.get("elapsed_seconds"),
            **warning_fields,
        })
    except Exception as exc:
        _sweep_jobs[job_id].update({
            "status": "error",
            "progress": 100,
            "message": str(exc),
            "updated_at": _utc_now_iso(),
            "finished_at": _utc_now_iso(),
        })


def _run_turtle_sweep_job(
    job_id: str,
    req: ParameterSweepRequest,
    sweep_id: str,
    results_dir: Path,
) -> None:
    try:
        from backtesting.turtle_backtest import run_turtle_sweep

        symbol = _turtle_symbol(req)
        params = _turtle_params_from_request(req)

        def _on_progress(update: dict[str, Any]) -> None:
            _sweep_jobs[job_id].update({
                "status": "running",
                "updated_at": _utc_now_iso(),
                **update,
            })

        _sweep_jobs[job_id].update({
            "status": "running",
            "progress": 10,
            "message": "Loading turtle 1D candles from DB",
            "updated_at": _utc_now_iso(),
        })
        daily_df, attempts = _turtle_load_daily_candles(req, symbol)
        _sweep_jobs[job_id].update({
            "progress": 35,
            "message": "Running turtle parameter sweep",
            "updated_at": _utc_now_iso(),
        })
        output_dir = resolve_artifact_path(
            results_dir,
            ("turtle_sweeps", "artifact_namespace"),
            (sweep_id, "sweep_id"),
        )
        summary = run_turtle_sweep(
            daily_df,
            req.parameter_grid,
            params,
            output_dir=output_dir,
            sweep_id=sweep_id,
            progress_callback=_on_progress,
            cancel_callback=lambda: _sweep_cancel_requested(job_id),
            max_combinations=req.max_combinations,
        )
        summary["symbol"] = symbol
        summary["bar"] = "1D"
        summary["validation"] = {
            "validation_only": True,
            "research_only": True,
            "turtle_data_sources": [{
                "inst_id": symbol,
                "status": "loaded",
                "rows": int(len(daily_df)),
                "first_ts": str(daily_df.index.min()) if not daily_df.empty else None,
                "last_ts": str(daily_df.index.max()) if not daily_df.empty else None,
                "attempts": attempts,
            }],
        }
        (output_dir / "summary.json").write_text(
            json.dumps(_json_sanitize(summary), indent=2, allow_nan=False),
            encoding="utf-8",
        )
        if summary.get("status") == "cancelled":
            _mark_sweep_cancelled(job_id)
            _sweep_jobs[job_id].update({
                "sweep_id": summary["sweep_id"],
                "artifacts": summary.get("artifacts", {}),
                "top_results": summary.get("top_results", [])[:10],
                "completed_count": summary.get("completed_count", 0),
                "failed_count": summary.get("failed_count", 0),
                "skipped_count": summary.get("skipped_count", 0),
                "elapsed_seconds": summary.get("elapsed_seconds"),
                "symbol": symbol,
                "bar": "1D",
            })
            return
        _sweep_jobs[job_id].update({
            "status": "done",
            "progress": 100,
            "message": "Turtle parameter sweep complete",
            "updated_at": _utc_now_iso(),
            "finished_at": _utc_now_iso(),
            "sweep_id": summary["sweep_id"],
            "artifacts": summary.get("artifacts", {}),
            "top_results": summary.get("top_results", [])[:10],
            "completed_count": summary.get("completed_count", 0),
            "failed_count": summary.get("failed_count", 0),
            "skipped_count": summary.get("skipped_count", 0),
            "elapsed_seconds": summary.get("elapsed_seconds"),
            "symbol": symbol,
            "bar": "1D",
        })
    except Exception as exc:
        _sweep_jobs[job_id].update({
            "status": "error",
            "progress": 100,
            "message": str(exc),
            "updated_at": _utc_now_iso(),
            "finished_at": _utc_now_iso(),
        })


def _run_differential_validation_job(
    job_id: str,
    run_id: str,
    run_dir: Path,
    engines: list[str],
    validation_id: str | None,
    output_dir: Path | None = None,
    cleanup_dir: Path | None = None,
) -> None:
    try:
        from backtesting.differential_validation import run_differential_validation

        _validation_jobs[job_id].update({
            "status": "running",
            "progress": 20,
            "message": "Running differential validation",
            "updated_at": _utc_now_iso(),
        })
        summary = run_differential_validation(
            run_dir=run_dir,
            engines=engines,
            output_dir=output_dir,
            validation_id=validation_id,
        )
        _validation_jobs[job_id].update({
            "status": "done",
            "progress": 100,
            "message": f"Differential validation {summary.get('status', 'complete')}",
            "validation_id": summary.get("validation_id"),
            "summary": summary,
            "updated_at": _utc_now_iso(),
            "finished_at": _utc_now_iso(),
        })
    except Exception as exc:
        _validation_jobs[job_id].update({
            "status": "error",
            "progress": 100,
            "message": str(exc),
            "updated_at": _utc_now_iso(),
            "finished_at": _utc_now_iso(),
        })
    finally:
        if cleanup_dir is not None:
            shutil.rmtree(cleanup_dir, ignore_errors=True)


def _run_strategy_differential_validation_job(
    job_id: str,
    results_dir: Path,
    strategy: str,
    fixture_run_id: str | None,
    engines: list[str],
    validation_id: str | None,
) -> None:
    try:
        from backtesting.differential_validation import run_strategy_differential_validation

        _validation_jobs[job_id].update({
            "status": "running",
            "progress": 20,
            "message": "Running strategy validation",
            "updated_at": _utc_now_iso(),
        })
        summary = run_strategy_differential_validation(
            results_dir=results_dir,
            strategy=strategy,
            engines=engines,
            fixture_run_id=fixture_run_id,
            validation_id=validation_id,
        )
        _validation_jobs[job_id].update({
            "status": "done",
            "progress": 100,
            "message": f"Strategy validation {summary.get('status', 'complete')}",
            "validation_id": summary.get("validation_id"),
            "strategy": summary.get("strategy"),
            "fixture_run_id": summary.get("fixture_run_id"),
            "summary": summary,
            "updated_at": _utc_now_iso(),
            "finished_at": _utc_now_iso(),
        })
    except Exception as exc:
        _validation_jobs[job_id].update({
            "status": "error",
            "progress": 100,
            "message": str(exc),
            "updated_at": _utc_now_iso(),
            "finished_at": _utc_now_iso(),
        })


def make_backtest_router(results_dir: Path) -> APIRouter:
    router = APIRouter()

    def _artifact_id(value: str, field: str) -> str:
        return _artifact_id_or_400(value, field)

    def _artifact_child(root: Path, value: str, field: str) -> Path:
        try:
            return resolve_artifact_child(root, value, field)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    def _artifact_path(root: Path, *components: tuple[str, str]) -> Path:
        try:
            return resolve_artifact_path(root, *components)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    def _run_dir(run_id: str) -> Path:
        d = _artifact_child(results_dir, run_id, "run_id")
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

    def _csv_row_count(path: Path) -> int:
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"{path.name} not found")
        with path.open("r", encoding="utf-8", newline="") as fh:
            return max(0, sum(1 for _ in fh) - 1)

    def _metadata_dict(value: Any) -> dict:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}
        return {}

    def _parameters_from_config(run_dir: Path, data: dict) -> dict:
        params = data.get("parameters")
        if isinstance(params, dict) and params:
            return params
        config_path = run_dir / "config.json"
        if not config_path.exists():
            return {}
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        strategy_names = (data.get("strategies") or [data.get("strategy") or ""])
        strategies_cfg = config.get("strategies") or {}
        risk_cfg = config.get("risk") or {}
        backtest_cfg = config.get("backtest") if isinstance(config.get("backtest"), dict) else {}
        cli_args = config.get("cli_args") or {}
        return {
            "strategies": {
                name: strategies_cfg.get(name)
                for name in strategy_names
                if name and isinstance(strategies_cfg.get(name), dict)
            },
            "risk": {
                key: risk_cfg.get(key)
                for key in ("max_order_notional_usd", "max_pos_pct_equity", "max_leverage")
                if key in risk_cfg
            },
            "backtest": {
                key: backtest_cfg.get(key)
                for key in (
                    "order_latency_ms",
                    "cancel_latency_ms",
                    "queue_fill_fraction",
                    "liquidate_on_end",
                    "fill_all_signals",
                )
                if key in backtest_cfg
            },
            "overrides": {
                "strategy_params": cli_args.get("strategy_params") or {},
                "risk_overrides": cli_args.get("risk_overrides") or {},
            },
        }

    def _downsample_records(records: list[dict], n: int) -> list[dict]:
        """Return at most n evenly-spaced records, always including first and last."""
        if n <= 0 or len(records) <= n:
            return records
        step = len(records) / n
        indices = set(int(i * step) for i in range(n))
        indices.add(len(records) - 1)
        return [records[i] for i in sorted(indices)]

    async def _read_db_artifact(run_id: str, artifact_type: str) -> Any | None:
        clean_run_id = _artifact_id(run_id, "run_id")
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
                    clean_run_id,
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

    async def _read_db_artifacts(run_id: str) -> dict[str, Any]:
        clean_run_id = _artifact_id(run_id, "run_id")
        try:
            import asyncpg

            dsn = os.environ.get("DATABASE_URL")
            if not dsn:
                return {}
            conn = await asyncpg.connect(dsn)
            try:
                rows = await conn.fetch(
                    """
                    SELECT artifact_type, payload
                    FROM backtest_artifacts
                    WHERE run_id = $1
                    """,
                    clean_run_id,
                )
            finally:
                await conn.close()
            artifacts: dict[str, Any] = {}
            for row in rows:
                payload = row["payload"]
                artifacts[row["artifact_type"]] = json.loads(payload) if isinstance(payload, str) else payload
            return artifacts
        except Exception:
            return {}

    def _write_materialized_artifact(path: Path, artifact_type: str, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if artifact_type in _VALIDATION_JSON_ARTIFACTS:
            path.write_text(json.dumps(_json_sanitize(payload), indent=2, ensure_ascii=False), encoding="utf-8")
            return
        pd.DataFrame(_as_record_list(payload)).to_csv(path, index=False)

    async def _materialize_db_validation_input(run_id: str) -> Path | None:
        clean = _artifact_id(run_id, "run_id")
        artifacts = await _read_db_artifacts(run_id)
        if "result" not in artifacts:
            return None
        materialized = Path(tempfile.mkdtemp(prefix=f"diffval_{clean}_"))
        try:
            for artifact_type, filename in _VALIDATION_INPUT_ARTIFACT_FILES.items():
                if artifact_type in artifacts:
                    _write_materialized_artifact(materialized / filename, artifact_type, artifacts[artifact_type])
        except Exception:
            shutil.rmtree(materialized, ignore_errors=True)
            raise
        return materialized

    async def _read_row_artifact(
        run_id: str,
        artifact_type: str,
        symbol: str | None = None,
        limit: int = 0,
        offset: int = 0,
        n: int = 0,
    ) -> list[dict[str, Any]]:
        clean_run_id = _artifact_id(run_id, "run_id")
        dsn = os.environ.get("DATABASE_URL")
        if not dsn:
            return []
        return await read_artifact_rows(
            dsn=dsn,
            run_id=clean_run_id,
            artifact_type=artifact_type,
            symbol=symbol,
            limit=limit,
            offset=offset,
            n=n,
        )

    async def _read_result_payload(run_id: str) -> dict[str, Any]:
        clean_run_id = _artifact_id(run_id, "run_id")
        payload = await _read_db_artifact(run_id, "result")
        if payload is not None:
            result_payload = _normalize_daily_winner_payload(payload)
        else:
            result_payload = _normalize_daily_winner_payload(_read_json(_run_dir(run_id) / "result.json"))
        if not result_payload.get("parameters"):
            run_dir = _artifact_child(results_dir, clean_run_id, "run_id")
            if run_dir.is_dir():
                result_payload["parameters"] = _parameters_from_config(run_dir, result_payload)
        if not result_payload.get("display_name"):
            result_payload["display_name"] = _backtest_display_name(result_payload)
        return _attach_idealized_fill_warning(result_payload)

    async def _read_records_artifact(
        run_id: str,
        artifact_type: str,
        filename: str,
        symbol: str | None = None,
        limit: int = 0,
        offset: int = 0,
        n: int = 0,
        downsample: bool = False,
    ) -> list[dict[str, Any]]:
        clean_run_id = _artifact_id(run_id, "run_id")
        row_records = await _read_row_artifact(
            run_id,
            artifact_type,
            symbol=symbol,
            limit=limit,
            offset=offset,
            n=n if downsample else 0,
        )
        if row_records:
            return row_records

        payload = await _read_db_artifact(run_id, artifact_type)
        records = _as_record_list(payload)
        if records:
            records = _filter_records_by_symbol(records, symbol)
            if offset:
                records = records[offset:]
            if limit:
                records = records[:limit]
            return _downsample_records(records, n) if downsample else records
        d = _artifact_child(results_dir, clean_run_id, "run_id")
        if not d.is_dir():
            return []
        path = d / filename
        if not path.exists():
            return []
        if symbol:
            rows: list[dict[str, Any]] = []
            with path.open("r", encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    if _record_symbol(row) == symbol:
                        rows.append(row)
            records = rows
        else:
            records = _as_record_list(_read_csv(path))
        if offset:
            records = records[offset:]
        if limit:
            records = records[:limit]
        return _downsample_records(records, n) if downsample else records

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
                    item = {
                        "run_id": run_id,
                        "display_name": data.get("display_name"),
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
                        "parameters": _parameters_from_config(run_dir, data),
                    }
                    item["display_name"] = _backtest_display_name(item)
                    merged[run_id] = _attach_idealized_fill_warning(item, data)
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
                    metadata = _metadata_dict(item.get("metadata"))
                    existing = merged.get(item["run_id"], {})
                    item["display_name"] = item.get("display_name") or existing.get("display_name")
                    item["display_name"] = _backtest_display_name(item)
                    item["parameters"] = metadata.get("parameters") or existing.get("parameters") or {}
                    merged[item["run_id"]] = _attach_idealized_fill_warning(item, metadata)
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
            "funding_carry",
            "pairs_trading",
            "ohlcv_rotation",
            "daily_winner",
            "turtle",
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
        if req.strategy == "turtle":
            if (req.bar or "1D") != "1D":
                raise HTTPException(status_code=400, detail="turtle supports 1D bars only")
            try:
                _turtle_symbol(req)
                _turtle_params_from_request(req)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        if req.strategy in {"ma_crossover", "ema_crossover", "macd_crossover"} and not req.symbols:
            raise HTTPException(status_code=400, detail=f"{req.strategy} requires at least one symbol")
        job_id = str(uuid.uuid4())[:8]
        run_id = _artifact_id(req.run_id or f"ui_{req.strategy}_{job_id}", "run_id")
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
        elif req.strategy == "turtle":
            bg.add_task(_run_turtle_job, job_id, req, run_id, results_dir)
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

    @router.post("/run/cancel/{job_id}")
    async def cancel_backtest_job(job_id: str):
        job = _run_jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        if job.get("status") in _RUN_TERMINAL_STATUSES:
            return job
        job["cancel_requested"] = True
        proc = _run_procs.get(job_id)
        if proc is not None and proc.poll() is None:
            proc.terminate()  # worker sees the dead process and marks "cancelled"
        job.update({"status": "cancelling", "message": "Cancelling backtest..."})
        return job

    @router.post("/sweep")
    async def start_parameter_sweep(req: ParameterSweepRequest, bg: BackgroundTasks):
        if req.strategy == "turtle":
            if not _request_field_was_set(req, "max_combinations"):
                req.max_combinations = DEFAULT_TURTLE_SWEEP_MAX_COMBINATIONS
            _validate_turtle_sweep_request(req)
            try:
                from backtesting.turtle_backtest import expand_turtle_grid

                combinations, skipped = expand_turtle_grid(
                    req.parameter_grid,
                    max_combinations=req.max_combinations,
                )
                _turtle_params_from_request(req)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            job_id = str(uuid.uuid4())[:8]
            sweep_id = _artifact_id(req.sweep_id or f"ui_sweep_turtle_{job_id}", "sweep_id")
            _sweep_jobs[job_id] = {
                "job_id": job_id,
                "sweep_id": sweep_id,
                "status": "running",
                "progress": 0,
                "message": "Turtle parameter sweep queued",
                "created_at": _utc_now_iso(),
                "updated_at": _utc_now_iso(),
                "combination_count": len(combinations),
                "skipped_count": len(skipped),
                "finalist_count": 0,
                "estimate": {
                    "strategy": "turtle",
                    "valid_combinations": len(combinations),
                    "skipped_combinations": len(skipped),
                    "run_finalists": False,
                },
                "symbol": _turtle_symbol(req),
                "bar": "1D",
            }
            bg.add_task(_run_turtle_sweep_job, job_id, req, sweep_id, results_dir)
            return _sweep_jobs[job_id]

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
        sweep_id = _artifact_id(req.sweep_id or f"ui_sweep_{req.strategy}_{job_id}", "sweep_id")
        if finalist_count:
            _artifact_id(f"{sweep_id}_rank_{finalist_count:03d}", "finalist_run_id")
        _artifact_id(f"{sweep_id}.json", "artifact_name")
        _artifact_id(f"{sweep_id}.csv", "artifact_name")
        _sweep_jobs[job_id] = {
            "job_id": job_id,
            "sweep_id": sweep_id,
            "status": "running",
            "progress": 0,
            "message": "Parameter sweep queued",
            "created_at": _utc_now_iso(),
            "updated_at": _utc_now_iso(),
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

    @router.post("/sweep/cancel/{job_id}")
    async def cancel_parameter_sweep_job(job_id: str):
        job = _sweep_jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Sweep job not found")
        if job.get("status") in _SWEEP_TERMINAL_STATUSES:
            return job
        job["cancel_requested"] = True
        job.update({"status": "cancelling", "message": "Cancelling sweep...", "updated_at": _utc_now_iso()})
        return job

    @router.get("/sweep/jobs")
    async def list_parameter_sweep_jobs():
        return list(_sweep_jobs.values())

    @router.get("/sweep/result/{sweep_id}")
    async def get_turtle_sweep_result(sweep_id: str):
        path = _artifact_path(
            results_dir,
            ("turtle_sweeps", "artifact_namespace"),
            (sweep_id, "sweep_id"),
            ("summary.json", "artifact_name"),
        )
        if not path.exists():
            raise HTTPException(status_code=404, detail="Turtle sweep result not found")
        payload = _read_json(path)
        artifacts = payload.get("artifacts") or {}
        sweep_dir = path.parent
        artifact_row_counts: dict[str, int] = {}
        inline_omitted: dict[str, str] = {}
        if artifacts.get("rows") and len(payload.get("free_params") or []) <= 2:
            rows_path = sweep_dir / artifacts["rows"]
            if rows_path.exists():
                row_count = _csv_row_count(rows_path)
                artifact_row_counts["rows"] = row_count
                if row_count <= TURTLE_SWEEP_INLINE_ROW_LIMIT:
                    payload["rows"] = _read_csv(rows_path)
                else:
                    inline_omitted["rows"] = f"rows.csv has {row_count} rows; use artifact endpoint"
        if artifacts.get("equity_curves"):
            equity_path = sweep_dir / artifacts["equity_curves"]
            if equity_path.exists():
                equity_count = _csv_row_count(equity_path)
                artifact_row_counts["equity_curves"] = equity_count
                if equity_count <= TURTLE_SWEEP_INLINE_EQUITY_ROW_LIMIT:
                    payload["equity_curves"] = _read_csv(equity_path)
                else:
                    inline_omitted["equity_curves"] = (
                        f"equity_curves.csv has {equity_count} rows; use artifact endpoint"
                    )
        if artifact_row_counts:
            payload["artifact_row_counts"] = artifact_row_counts
        if inline_omitted:
            payload["inline_omitted"] = inline_omitted
        return payload

    @router.get("/sweep/artifact/{sweep_id}/{name}")
    async def get_turtle_sweep_artifact(sweep_id: str, name: str):
        filename = _TURTLE_SWEEP_ARTIFACT_FILES.get(_artifact_id(name, "artifact_name"))
        if filename is None:
            raise HTTPException(status_code=404, detail="Turtle sweep artifact not found")
        path = _artifact_path(
            results_dir,
            ("turtle_sweeps", "artifact_namespace"),
            (sweep_id, "sweep_id"),
            (filename, "artifact_name"),
        )
        if not path.exists():
            raise HTTPException(status_code=404, detail="Turtle sweep artifact not found")
        if filename.endswith(".json"):
            return _read_json(path)
        if filename.endswith(".csv"):
            return _read_csv(path)
        return FileResponse(path, media_type="text/html")

    @router.delete("/{run_id}")
    async def delete_run(run_id: str):
        clean_run_id = _artifact_id(run_id, "run_id")
        d = _artifact_child(results_dir, clean_run_id, "run_id")
        shutil.rmtree(d, ignore_errors=True)
        try:
            import asyncpg

            dsn = os.environ.get("DATABASE_URL")
            if dsn:
                conn = await asyncpg.connect(dsn)
                try:
                    await conn.execute("DELETE FROM backtest_runs WHERE run_id = $1", clean_run_id)
                finally:
                    await conn.close()
        except Exception:
            pass
        return {"deleted": clean_run_id}

    # ------------------------------------------------------------------
    # Differential validation
    # ------------------------------------------------------------------

    @router.get("/strategy-validation/fixtures")
    async def list_strategy_validation_fixtures(strategy: str | None = None):
        from backtesting.differential_validation import list_strategy_validation_fixtures

        clean_strategy = _artifact_id(strategy, "strategy") if strategy else None
        return list_strategy_validation_fixtures(results_dir, clean_strategy)

    @router.post("/strategy-validation/run")
    async def run_strategy_differential_validation_endpoint(
        req: StrategyDifferentialValidationRequest,
        bg: BackgroundTasks,
    ):
        from backtesting.differential_validation import ENGINE_NAMES

        strategy = _artifact_id(req.strategy, "strategy")
        fixture_run_id = (
            _artifact_id(req.fixture_run_id, "fixture_run_id")
            if req.fixture_run_id is not None
            else None
        )
        validation_id = (
            _artifact_id(req.validation_id, "validation_id")
            if req.validation_id is not None
            else None
        )
        engines = [str(engine).strip().lower() for engine in (req.engines or []) if str(engine).strip()]
        if not engines:
            engines = ["vectorbt", "backtrader", "nautilus"]
        unknown = sorted(set(engines) - ENGINE_NAMES)
        if unknown:
            raise HTTPException(status_code=400, detail=f"Unsupported engine(s): {', '.join(unknown)}")
        job_id = f"stratval_{uuid.uuid4().hex[:10]}"
        _validation_jobs[job_id] = {
            "job_id": job_id,
            "strategy": strategy,
            "fixture_run_id": fixture_run_id,
            "validation_id": validation_id,
            "engines": engines,
            "status": "queued",
            "progress": 0,
            "message": "Queued strategy validation",
            "created_at": _utc_now_iso(),
            "updated_at": _utc_now_iso(),
        }
        bg.add_task(
            _run_strategy_differential_validation_job,
            job_id,
            results_dir,
            strategy,
            fixture_run_id,
            engines,
            validation_id,
        )
        return _validation_jobs[job_id]

    @router.get("/strategy-validation")
    async def list_strategy_validations(strategy: str | None = None):
        from backtesting.differential_validation import list_strategy_validation_results

        clean_strategy = _artifact_id(strategy, "strategy") if strategy else None
        return list_strategy_validation_results(results_dir, clean_strategy)

    @router.get("/strategy-validation/contracts")
    async def get_strategy_validation_contracts(strategy: str | None = None):
        from backtesting.differential_validation import (
            REFERENCE_VALIDATION_CONTRACTS,
            strategy_reference_validation_contract,
        )

        if strategy:
            return strategy_reference_validation_contract(_artifact_id(strategy, "strategy"))
        return [
            strategy_reference_validation_contract(name)
            for name in sorted(REFERENCE_VALIDATION_CONTRACTS)
        ]

    @router.get("/strategy-validation/{strategy}")
    async def list_strategy_validations_for_strategy(strategy: str):
        from backtesting.differential_validation import list_strategy_validation_results

        return list_strategy_validation_results(results_dir, _artifact_id(strategy, "strategy"))

    @router.get("/strategy-validation/{strategy}/{validation_id}")
    async def get_strategy_validation(strategy: str, validation_id: str):
        from backtesting.differential_validation import read_strategy_validation_result

        try:
            return read_strategy_validation_result(
                results_dir,
                _artifact_id(strategy, "strategy"),
                _artifact_id(validation_id, "validation_id"),
            )
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Strategy validation result not found")

    @router.get("/strategy-validation/{strategy}/{validation_id}/artifact/{artifact_name}")
    async def get_strategy_validation_artifact(
        strategy: str,
        validation_id: str,
        artifact_name: str,
    ):
        from backtesting.differential_validation import read_strategy_validation_artifact

        try:
            return read_strategy_validation_artifact(
                results_dir,
                _artifact_id(strategy, "strategy"),
                _artifact_id(validation_id, "validation_id"),
                _artifact_id(artifact_name, "artifact_name"),
            )
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Strategy validation artifact not found")

    @router.post("/{run_id}/differential-validation/run")
    async def run_differential_validation_endpoint(
        run_id: str,
        req: DifferentialValidationRequest,
        bg: BackgroundTasks,
    ):
        from backtesting.differential_validation import ENGINE_NAMES

        clean_run_id = _artifact_id(run_id, "run_id")
        run_artifact_dir = _artifact_child(results_dir, clean_run_id, "run_id")
        d = run_artifact_dir
        output_dir: Path | None = None
        cleanup_dir: Path | None = None
        validation_id = (
            _artifact_id(req.validation_id, "validation_id")
            if req.validation_id is not None
            else None
        )
        if not d.is_dir():
            materialized = await _materialize_db_validation_input(clean_run_id)
            if materialized is None:
                raise HTTPException(status_code=404, detail="Run not found")
            d = materialized
            cleanup_dir = materialized
            validation_id = validation_id or f"db_{uuid.uuid4().hex[:10]}"
            output_dir = _artifact_path(
                results_dir,
                (clean_run_id, "run_id"),
                ("validation", "artifact_namespace"),
                (validation_id, "validation_id"),
            )
        engines = [str(engine).strip().lower() for engine in (req.engines or []) if str(engine).strip()]
        if not engines:
            engines = ["vectorbt", "backtrader", "nautilus"]
        unknown = sorted(set(engines) - ENGINE_NAMES)
        if unknown:
            raise HTTPException(status_code=400, detail=f"Unsupported engine(s): {', '.join(unknown)}")
        job_id = f"diffval_{uuid.uuid4().hex[:10]}"
        _validation_jobs[job_id] = {
            "job_id": job_id,
            "run_id": clean_run_id,
            "validation_id": validation_id,
            "engines": engines,
            "status": "queued",
            "progress": 0,
            "message": "Queued differential validation",
            "created_at": _utc_now_iso(),
            "updated_at": _utc_now_iso(),
        }
        bg.add_task(
            _run_differential_validation_job,
            job_id,
            clean_run_id,
            d,
            engines,
            validation_id,
            output_dir,
            cleanup_dir,
        )
        return _validation_jobs[job_id]

    @router.get("/differential-validation/jobs")
    async def list_differential_validation_jobs():
        return list(_validation_jobs.values())

    @router.get("/differential-validation/status/{job_id}")
    async def get_differential_validation_status(job_id: str):
        if job_id not in _validation_jobs:
            raise HTTPException(status_code=404, detail="Differential validation job not found")
        return _validation_jobs[job_id]

    @router.get("/{run_id}/differential-validation")
    async def list_differential_validations(run_id: str):
        from backtesting.differential_validation import list_validation_results

        return list_validation_results(_run_dir(run_id))

    @router.get("/{run_id}/differential-validation/{validation_id}")
    async def get_differential_validation(run_id: str, validation_id: str):
        from backtesting.differential_validation import read_validation_result

        try:
            return read_validation_result(
                _run_dir(run_id),
                _artifact_id(validation_id, "validation_id"),
            )
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Differential validation result not found")

    @router.get("/{run_id}/differential-validation/{validation_id}/artifact/{artifact_name}")
    async def get_differential_validation_artifact(
        run_id: str,
        validation_id: str,
        artifact_name: str,
    ):
        from backtesting.differential_validation import read_validation_artifact

        try:
            clean_validation_id = _artifact_id(validation_id, "validation_id")
            clean_artifact_name = _artifact_id(artifact_name, "artifact_name")
            if clean_artifact_name.lower().endswith(".csv"):
                rows = await _read_row_artifact(
                    run_id,
                    validation_artifact_type(clean_validation_id, clean_artifact_name),
                )
                if rows:
                    return rows
            return read_validation_artifact(_run_dir(run_id), clean_validation_id, clean_artifact_name)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Differential validation artifact not found")

    # ------------------------------------------------------------------
    # Single run — full result.json
    # ------------------------------------------------------------------

    @router.get("/{run_id}")
    async def get_run(run_id: str):
        """Return the full result.json for a run."""
        return await _read_result_payload(run_id)

    @router.get("/{run_id}/summary")
    async def get_run_summary(run_id: str):
        """Return lightweight run metadata for immediate UI selection."""
        return _summary_payload(await _read_result_payload(run_id))

    @router.get("/{run_id}/execution-comparison")
    async def get_execution_comparison(run_id: str):
        """Return the paired Strategy Fill vs realistic execution comparison."""
        await _read_result_payload(run_id)
        clean_run_id = _artifact_id(run_id, "run_id")
        candidates: list[Path] = []
        for suffix in ("_strategy_fill", "_realistic_execution"):
            if clean_run_id.endswith(suffix):
                candidates.append(_artifact_child(
                    results_dir,
                    f"{clean_run_id[:-len(suffix)]}_execution_comparison.json",
                    "artifact_name",
                ))
        candidates.append(_artifact_child(
            results_dir,
            f"{clean_run_id}_execution_comparison.json",
            "artifact_name",
        ))
        for path in candidates:
            if path.name.endswith("_execution_comparison.json") and path.exists():
                return _read_json(path)
        raise HTTPException(status_code=404, detail="Execution comparison artifact not found")

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
        records = await _read_records_artifact(
            run_id,
            "equity",
            "equity_curve.csv",
            n=n,
            downsample=True,
        )
        if records:
            return records
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
        records = await _read_records_artifact(run_id, "orders", "orders.csv")
        if records:
            return records
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
        row_records = await _read_row_artifact(run_id, "fills", limit=limit, offset=offset)
        if row_records:
            return row_records
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
        row_records = await _read_row_artifact(run_id, "trades", limit=limit, offset=offset)
        if row_records:
            return row_records
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
        records = await _read_records_artifact(
            run_id,
            "returns",
            "returns.csv",
            n=n,
            downsample=True,
        )
        if records:
            return records
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
        records = await _read_records_artifact(
            run_id,
            "drawdown",
            "drawdown.csv",
            n=n,
            downsample=True,
        )
        if records:
            return records
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
    async def get_execution_markers(
        run_id: str,
        symbol: str | None = Query(default=None),
        limit: int = Query(default=0, ge=0),
    ):
        if symbol and not _SAFE_SYMBOL_RE.match(symbol):
            raise HTTPException(status_code=400, detail=f"Invalid symbol: {symbol}")
        records = await _read_records_artifact(
            run_id,
            "execution_markers",
            "execution_markers.csv",
        )
        if records:
            return _limit_records(_filter_records_by_symbol(records, symbol), limit)
        result = await _read_result_payload(run_id)
        fills = await _read_records_artifact(run_id, "fills", "fills.csv")
        trades = await _read_records_artifact(run_id, "trades", "trades.csv")
        if not trades:
            trades = _as_record_list(result.get("trades"))
        markers = _fallback_execution_markers_from_records(
            fills=fills,
            trades=trades,
            result=result,
        )
        return _limit_records(_filter_records_by_symbol(markers, symbol), limit)

    @router.get("/{run_id}/price-series")
    async def get_price_series(
        run_id: str,
        symbol: str | None = Query(default=None),
        n: int = Query(default=0, ge=0),
    ):
        if symbol:
            if not _SAFE_SYMBOL_RE.match(symbol):
                raise HTTPException(status_code=400, detail=f"Invalid symbol: {symbol}")
        clean_run_id = _artifact_id(run_id, "run_id")
        records = await _read_records_artifact(
            run_id,
            "price_series",
            "price_series.csv",
            symbol=symbol,
            n=n if symbol else 0,
            downsample=bool(n and symbol),
        )
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
            if not records:
                cache_key = (clean_run_id, symbol)
                cached = _get_price_series_cache(cache_key)
                if cached is not None:
                    records = cached
                else:
                    result_ctx, fills_ctx, trades_ctx = await _load_visual_context()
                    records = _fallback_price_series_from_result(
                        result_ctx,
                        symbol=symbol,
                        fills=fills_ctx,
                        trades=trades_ctx,
                    )
                    _set_price_series_cache(cache_key, records)
            return records

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
            cache_key = (clean_run_id, "*")
            cached = _get_price_series_cache(cache_key)
            if cached is not None:
                records = cached
            else:
                result_ctx, fills_ctx, trades_ctx = await _load_visual_context()
                records = _fallback_price_series_from_result(
                    result_ctx,
                    fills=fills_ctx,
                    trades=trades_ctx,
                )
                _set_price_series_cache(cache_key, records)
        return _downsample_records_by_symbol(records, n)

    @router.get("/{run_id}/indicators")
    async def get_indicators(
        run_id: str,
        symbol: str | None = Query(default=None),
        n: int = Query(default=0, ge=0),
    ):
        if symbol:
            if not _SAFE_SYMBOL_RE.match(symbol):
                raise HTTPException(status_code=400, detail=f"Invalid symbol: {symbol}")
        return await _read_records_artifact(
            run_id,
            "indicator_series",
            "indicator_series.csv",
            symbol=symbol,
            n=n,
            downsample=bool(n),
        )

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
    if normalized.fill_all_signals:
        normalized.execution_profile = "strategy_fill"
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
    req.exchange = _normalize_exchange(req.exchange)
    if req.run_id is not None:
        req.run_id = _artifact_id_or_400(req.run_id, "run_id")
    try:
        req.execution_profile = normalize_execution_profile(req.execution_profile)
    except ResearchControlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if req.run_id is not None and req.execution_profile == "dual_output":
        _artifact_id_or_400(f"{req.run_id}_strategy_fill", "run_id")
        _artifact_id_or_400(f"{req.run_id}_realistic_execution", "run_id")
        _artifact_id_or_400(f"{req.run_id}_execution_comparison.json", "artifact_name")
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


def _validate_turtle_sweep_request(req: ParameterSweepRequest) -> None:
    _resolve_data_dir(req.data_dir)
    req.exchange = _normalize_exchange(req.exchange)
    if req.sweep_id is not None:
        req.sweep_id = _artifact_id_or_400(req.sweep_id, "sweep_id")
    if (req.bar or "1D") != "1D":
        raise HTTPException(status_code=400, detail="turtle sweep supports 1D bars only")
    if req.max_combinations > HARD_TURTLE_SWEEP_MAX_COMBINATIONS:
        raise HTTPException(
            status_code=400,
            detail=f"turtle sweep max_combinations is capped at {HARD_TURTLE_SWEEP_MAX_COMBINATIONS}",
        )
    if req.finalist_validation not in {None, "none"}:
        raise HTTPException(status_code=400, detail="turtle sweep does not run finalist validation")
    if req.start and not _SAFE_DATE_RE.match(req.start):
        raise HTTPException(status_code=400, detail="Invalid start date format")
    if req.end and not _SAFE_DATE_RE.match(req.end):
        raise HTTPException(status_code=400, detail="Invalid end date format")
    try:
        _turtle_symbol(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    for key, value in req.parameter_grid.items():
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", str(key)):
            raise HTTPException(status_code=400, detail=f"Invalid parameter: {key}")
        if not isinstance(value, (int, float, str, list, tuple, dict)):
            raise HTTPException(status_code=400, detail=f"Invalid parameter value for: {key}")
    try:
        req.risk_overrides = sanitize_risk_overrides(req.risk_overrides)
    except ResearchControlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _validate_parameter_sweep_request(req: ParameterSweepRequest) -> None:
    _resolve_data_dir(req.data_dir)
    req.exchange = _normalize_exchange(req.exchange)
    if req.sweep_id is not None:
        req.sweep_id = _artifact_id_or_400(req.sweep_id, "sweep_id")
    if req.strategy not in {"ma_crossover", "ema_crossover", "macd_crossover"}:
        raise HTTPException(status_code=400, detail="Parameter sweep supports MA, EMA, and MACD only")
    if req.max_combinations > 10000:
        if _request_field_was_set(req, "max_combinations"):
            raise HTTPException(status_code=400, detail="parameter sweep max_combinations is capped at 10000")
        req.max_combinations = 5000
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
