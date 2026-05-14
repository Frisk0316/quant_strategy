"""
Backtest results REST endpoints.
Scans results/ directory for run subdirectories containing result.json.
Each result.json matches the artifacts schema produced by backtesting/artifacts.py.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field

from okx_quant.core.symbols import normalize_spot_symbol, normalize_swap_symbol

PROJECT_ROOT = Path(__file__).resolve().parents[3]
_run_jobs: dict[str, dict[str, Any]] = {}


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
    universe: list[str] = []
    benchmark: str = "BTC-USDT-SWAP"
    rebalance_minutes: int = 60
    top_k: int = 3
    rank_exit_buffer: int = 6
    data_dir: str = "data/ticks"


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
        cmd = [
            sys.executable,
            str(script),
            "--backend", "parquet",
            "--data-dir", req.data_dir or "data/ticks",
            "--bar", bar,
            "--benchmark", req.benchmark or "BTC-USDT-SWAP",
            "--rebalance-minutes", str(req.rebalance_minutes or 60),
            "--top-k", str(req.top_k or 3),
            "--rank-exit-buffer", str(req.rank_exit_buffer or 6),
            "--output-dir", str(out_dir),
            "--universe",
        ] + list(req.universe or [])
        if req.start:
            cmd.extend(["--start", req.start])
        if req.end:
            cmd.extend(["--end", req.end])

        _run_jobs[job_id].update({
            "status": "running",
            "progress": 10,
            "message": "Running OHLCV rotation backtest",
            "command": " ".join(cmd),
        })
        env = os.environ.copy()
        env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
        proc = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=60 * 60,
        )
        output = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
        if proc.returncode != 0:
            _run_jobs[job_id].update({
                "status": "error",
                "progress": 100,
                "message": f"Backtest failed with exit code {proc.returncode}",
                "output": output[-4000:],
            })
            return
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
    """Convert ohlcv_rotation script outputs into ADR-0002 result.json + returns.csv."""
    summary_path = out_dir / "summary.json"
    equity_path = out_dir / "equity_curve.csv"
    if not summary_path.exists():
        return
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    metrics = {k: v for k, v in summary.items() if k != "run_id"}
    trade_count = metrics.get("number_of_trades", 0)
    metrics.setdefault("order_count", trade_count)
    metrics.setdefault("fill_count", trade_count)

    if equity_path.exists():
        eq_df = pd.read_csv(equity_path, index_col=0, parse_dates=True)
        if "equity" in eq_df.columns:
            eq_df["return"] = eq_df["equity"].pct_change().fillna(0.0)
            eq_df[["return"]].to_csv(out_dir / "returns.csv")

    result = {
        "run_id": run_id,
        "created_at": pd.Timestamp.utcnow().isoformat(),
        "strategies": ["ohlcv_rotation"],
        "symbols": req.universe or [],
        "bar": req.bar or "1H",
        "start": req.start or "",
        "end": req.end or "",
        "metrics": metrics,
    }
    (out_dir / "result.json").write_text(
        json.dumps(result, allow_nan=False, indent=2),
        encoding="utf-8",
    )


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

        _run_jobs[job_id].update({
            "status": "running",
            "progress": 10,
            "message": "Running replay backtest",
            "command": " ".join(cmd),
        })
        env = os.environ.copy()
        env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
        proc = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=60 * 60,
        )
        output = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
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
                    metrics = data.get("metrics", data.get("mainStats", {}))
                    if not (run_dir / "returns.csv").exists():
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
                            SELECT r.*
                            FROM backtest_runs r
                            WHERE EXISTS (
                                SELECT 1
                                FROM backtest_artifacts a
                                WHERE a.run_id = r.run_id
                                  AND a.artifact_type = 'returns'
                                  AND a.row_count > 0
                            )
                            ORDER BY r.created_at DESC
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
                    item["start"] = item.get("start_date")
                    item["end"] = item.get("end_date")
                    merged[item["run_id"]] = item
        except Exception:
            pass
        return sorted(merged.values(), key=lambda r: str(r.get("created_at") or ""), reverse=True)

    @router.post("/run")
    async def start_backtest(req: RunBacktestRequest, bg: BackgroundTasks):
        allowed = {"obi_market_maker", "as_market_maker", "funding_carry", "pairs_trading", "ohlcv_rotation"}
        validate_allowed = {None, "wf", "cpcv", "both"}
        if req.strategy not in allowed:
            raise HTTPException(status_code=400, detail="Unsupported strategy")
        if req.strategy != "ohlcv_rotation" and req.validation not in validate_allowed:
            raise HTTPException(status_code=400, detail="Unsupported validation mode")
        if req.strategy == "pairs_trading" and req.symbol_x == req.symbol_y:
            raise HTTPException(status_code=400, detail="Pair trading requires two different symbols")
        if req.strategy == "ohlcv_rotation" and not req.universe:
            raise HTTPException(status_code=400, detail="ohlcv_rotation requires at least one symbol in universe")
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
        else:
            bg.add_task(_run_backtest_job, job_id, req, run_id, results_dir)
        return _run_jobs[job_id]

    @router.get("/run/status/{job_id}")
    async def get_backtest_job_status(job_id: str):
        if job_id not in _run_jobs:
            raise HTTPException(status_code=404, detail="Job not found")
        return _run_jobs[job_id]

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
        payload = await _read_db_artifact(run_id, "result")
        if payload is not None:
            return payload
        d = _run_dir(run_id)
        return _read_json(d / "result.json")

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
        result = _read_json(d / "result.json")
        return result.get("metrics", {})

    @router.get("/{run_id}/walk-forward")
    async def get_walk_forward(run_id: str):
        result = await _read_db_artifact(run_id, "result")
        if result is None:
            result = _read_json(_run_dir(run_id) / "result.json")
        return result.get("walk_forward", result.get("walkForward", [])) or []

    @router.get("/{run_id}/cpcv")
    async def get_cpcv(run_id: str):
        result = await _read_db_artifact(run_id, "result")
        if result is None:
            result = _read_json(_run_dir(run_id) / "result.json")
        return result.get("cpcv")

    # ------------------------------------------------------------------
    # Equity curve
    # ------------------------------------------------------------------

    @router.get("/{run_id}/equity")
    async def get_equity(run_id: str, n: int = Query(default=0, ge=0)):
        payload = await _read_db_artifact(run_id, "equity")
        records = payload if payload is not None else _read_csv(_run_dir(run_id) / "equity_curve.csv")
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
        records = payload if payload is not None else _read_csv(_run_dir(run_id) / "trades.csv")
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
        records = payload if payload is not None else _read_csv(_run_dir(run_id) / "returns.csv")
        return _downsample_records(records, n)

    @router.get("/{run_id}/drawdown")
    async def get_drawdown(run_id: str, n: int = Query(default=0, ge=0)):
        payload = await _read_db_artifact(run_id, "drawdown")
        records = payload if payload is not None else _read_csv(_run_dir(run_id) / "drawdown.csv")
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
        payload = await _read_db_artifact(run_id, "execution_markers")
        if payload is not None:
            return payload
        return _read_csv(_run_dir(run_id) / "execution_markers.csv")

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
