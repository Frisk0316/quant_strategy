"""
Backtest results REST endpoints.
Scans results/ directory for run subdirectories containing result.json.
Each result.json matches the window.MOCK schema so the frontend can load it directly.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException


def make_backtest_router(results_dir: Path) -> APIRouter:
    router = APIRouter()

    @router.get("/runs")
    def list_runs():
        """Return a summary list of all saved backtest runs."""
        runs = []
        if not results_dir.exists():
            return runs
        for run_dir in sorted(results_dir.iterdir(), reverse=True):
            result_file = run_dir / "result.json"
            if not (run_dir.is_dir() and result_file.exists()):
                continue
            try:
                data = json.loads(result_file.read_text())
                stats = data.get("mainStats", {})
                runs.append({
                    "run_id": data.get("run_id", run_dir.name),
                    "created_at": data.get("created_at"),
                    "strategy": data.get("strategy", ""),
                    "symbol": data.get("symbol", ""),
                    "start_date": data.get("start_date", ""),
                    "end_date": data.get("end_date", ""),
                    "sharpe": stats.get("sharpe"),
                    "total_return": stats.get("total_return"),
                    "max_drawdown": stats.get("max_drawdown"),
                })
            except Exception:
                pass
        return runs

    @router.get("/{run_id}")
    def get_run(run_id: str):
        """Return the full result.json for a run — same shape as window.MOCK."""
        # Prevent path traversal
        run_id_clean = Path(run_id).name
        result_file = results_dir / run_id_clean / "result.json"
        if not result_file.exists():
            raise HTTPException(status_code=404, detail="Run not found")
        return json.loads(result_file.read_text())

    return router
