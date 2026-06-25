"""
Standalone API + frontend server (no trading engine required).
Serves the React frontend and all /api/backtest/* endpoints.

Usage:
    python scripts/run_server.py
    python scripts/run_server.py --port 8080 --results results
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
import uvicorn

from okx_quant.api.routes_backtest import make_backtest_router
from okx_quant.api.routes_config import make_config_router
from okx_quant.api.routes_data import make_data_router
from okx_quant.api.routes_progress import make_progress_router
from okx_quant.core.config import load_config


def _db_dsn() -> str | None:
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    try:
        cfg = load_config(require_secrets=False)
        dsn = cfg.storage.timescale_dsn
        if dsn:
            os.environ.setdefault("DATABASE_URL", dsn)
            return dsn
    except Exception:
        return None
    return None


def create_app(results_dir: Path, frontend_dir: Path) -> FastAPI:
    app = FastAPI(title="OKX Quant Backtest Viewer", docs_url="/api/docs")
    app.include_router(make_backtest_router(results_dir), prefix="/api/backtest", tags=["backtest"])
    app.include_router(make_config_router(), prefix="/api", tags=["config"])
    app.include_router(make_data_router(_db_dsn()), prefix="/api/data", tags=["data"])
    app.include_router(make_progress_router(PROJECT_ROOT), prefix="/api/progress", tags=["progress"])

    @app.get("/api/live/status")
    def live_status():
        return {"mode": "offline", "running": False}

    @app.websocket("/api/ws")
    async def ws_offline(websocket: WebSocket):
        # Accept then immediately close — prevents StaticFiles AssertionError
        # when the frontend tries to connect in backtest-only mode.
        await websocket.accept()
        await websocket.close(code=1001)

    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="static")
    return app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--results", default=str(PROJECT_ROOT / "results"))
    args = parser.parse_args()

    results_dir = Path(args.results)
    frontend_dir = PROJECT_ROOT / "frontend"

    if not results_dir.exists():
        results_dir.mkdir(parents=True)
        print(f"Created results dir: {results_dir}")

    app = create_app(results_dir, frontend_dir)
    print(f"\n  Frontend: http://{args.host}:{args.port}")
    print(f"  API docs: http://{args.host}:{args.port}/api/docs")
    print(f"  Results:  {results_dir.resolve()}\n")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
