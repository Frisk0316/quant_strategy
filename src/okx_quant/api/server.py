"""
FastAPI application factory and uvicorn launcher.

The server runs as an asyncio.create_task() inside the existing engine event loop.
uvicorn.Config(loop="none") is critical — it reuses the running loop instead of
creating a new one, which would conflict with the engine's asyncio.run().
"""
from __future__ import annotations

from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.websockets import WebSocket, WebSocketDisconnect

from okx_quant.api.routes_backtest import make_backtest_router
from okx_quant.api.routes_live import make_live_router
from okx_quant.api.state import EngineState


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
    app = FastAPI(title="OKX Quant API", docs_url="/api/docs", redoc_url=None)

    app.include_router(make_live_router(state), prefix="/api/live", tags=["live"])
    app.include_router(make_backtest_router(results_dir), prefix="/api/backtest", tags=["backtest"])

    @app.websocket("/api/ws")
    async def ws_endpoint(websocket: WebSocket) -> None:
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
