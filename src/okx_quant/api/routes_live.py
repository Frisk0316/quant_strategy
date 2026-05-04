"""
Live trading REST endpoints.
All data is sourced from EngineState which reads directly from engine components.
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from okx_quant.api.state import EngineState


def make_live_router(state: EngineState) -> APIRouter:
    router = APIRouter()

    @router.get("/status")
    def get_status():
        return state.get_status()

    @router.get("/risk")
    def get_risk():
        return state.get_live_risk()

    @router.get("/positions")
    def get_positions():
        return state.get_positions()

    @router.get("/trades")
    def get_trades(limit: int = Query(200, ge=1, le=1000)):
        return state.get_trades(limit)

    return router
