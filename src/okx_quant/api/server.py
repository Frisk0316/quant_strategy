"""
FastAPI application factory and uvicorn launcher.

The server runs as an asyncio.create_task() inside the existing engine event loop.
uvicorn.Config(loop="none") is critical — it reuses the running loop instead of
creating a new one, which would conflict with the engine's asyncio.run().
"""
from __future__ import annotations

import logging
import mimetypes
import os
import secrets
from pathlib import Path

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.websockets import WebSocket, WebSocketDisconnect

from okx_quant.api.routes_backtest import make_backtest_router
from okx_quant.api.routes_config import make_config_router
from okx_quant.api.routes_data import make_data_router
from okx_quant.api.routes_live import make_live_router
from okx_quant.api.state import EngineState
from okx_quant.core.config import load_config

# Python's mimetypes table may not know .js/.jsx on some platforms (Windows,
# minimal Docker images). Browsers reject ES modules served with the wrong
# MIME type and show a blank page. Register all three before StaticFiles mounts.
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("application/javascript", ".jsx")
mimetypes.add_type("application/javascript", ".mjs")

logger = logging.getLogger(__name__)


def _api_key() -> str:
    return os.environ.get("API_KEY", "")


async def verify_api_key(x_api_key: str = Header(default="")) -> None:
    api_key = _api_key()
    if not api_key:
        logger.warning("API_KEY is not set; API authentication is disabled")
        return
    if not secrets.compare_digest(x_api_key, api_key):
        raise HTTPException(status_code=401, detail="Unauthorized")


def _is_valid_ws_api_key(value: str) -> bool:
    api_key = _api_key()
    if not api_key:
        logger.warning("API_KEY is not set; WebSocket authentication is disabled")
        return True
    return secrets.compare_digest(value, api_key)


def _allowed_origins() -> list[str]:
    return [origin.strip() for origin in os.environ.get("ALLOWED_ORIGINS", "").split(",") if origin.strip()]


def _db_dsn() -> str | None:
    try:
        if os.environ.get("DATABASE_URL"):
            return os.environ["DATABASE_URL"]
        cfg = load_config(require_secrets=False)
        dsn = cfg.storage.timescale_dsn
        if dsn:
            os.environ.setdefault("DATABASE_URL", dsn)
        return dsn
    except Exception:
        return None


def create_app(
    state: EngineState,
    results_dir: Path,
    frontend_dir: Path,
) -> FastAPI:
    """
    Build the FastAPI application.

    Route registration order matters: /api routes must come before the
    static file catch-all, otherwise StaticFiles intercepts /api requests.
    """
    app = FastAPI(title="OKX Quant API", docs_url=None, redoc_url=None)

    allowed_origins = _allowed_origins()
    if allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    api_dependencies = [Depends(verify_api_key)]
    app.include_router(
        make_live_router(state),
        prefix="/api/live",
        tags=["live"],
        dependencies=api_dependencies,
    )
    app.include_router(
        make_backtest_router(results_dir),
        prefix="/api/backtest",
        tags=["backtest"],
        dependencies=api_dependencies,
    )
    app.include_router(
        make_config_router(dependencies=api_dependencies),
        prefix="/api",
        tags=["config"],
    )
    app.include_router(
        make_data_router(_db_dsn()),
        prefix="/api/data",
        tags=["data"],
        dependencies=api_dependencies,
    )

    @app.websocket("/api/ws")
    async def ws_endpoint(websocket: WebSocket) -> None:
        if not _is_valid_ws_api_key(websocket.query_params.get("api_key", "")):
            await websocket.accept()
            await websocket.close(code=4001)
            return
        await websocket.accept()
        state.register_ws(websocket)
        try:
            while True:
                # Keep the connection alive; all pushes are driven by engine broadcasts.
                await websocket.receive_text()
        except WebSocketDisconnect:
            state.unregister_ws(websocket)

    # Static files last — html=True serves index.html for unknown paths (SPA routing)
    app.mount(
        "/",
        StaticFiles(directory=str(frontend_dir), html=True),
        name="static",
    )

    return app


async def run_api_server(
    state: EngineState,
    results_dir: Path,
    frontend_dir: Path,
    host: str = "0.0.0.0",
    port: int = 8080,
) -> None:
    """
    Coroutine — await this inside engine.main() as an asyncio.create_task().
    Never call uvicorn.run() here; that would create a new event loop.
    """
    app = create_app(state, results_dir, frontend_dir)
    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        loop="none",         # reuse the running asyncio loop
        log_level="warning",
    )
    server = uvicorn.Server(config)
    await server.serve()
