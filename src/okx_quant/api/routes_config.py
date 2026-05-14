"""Configuration inspection endpoints for the frontend."""
from __future__ import annotations

from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def make_config_router(dependencies: list | None = None) -> APIRouter:
    router = APIRouter(dependencies=dependencies or [])

    @router.get("/config/risk")
    def get_risk_config():
        path = PROJECT_ROOT / "config" / "risk.yaml"
        if not path.exists():
            raise HTTPException(status_code=404, detail="risk.yaml not found")
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    return router
