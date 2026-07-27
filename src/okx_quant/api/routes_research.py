"""Research-only controls for H-014 shadow and H-009 parameter screening."""

from __future__ import annotations

import asyncio
import json
import math
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator

from okx_quant.execution.deribit_shadow import (
    build_bias_report,
    load_config as load_h014_config,
    run_cycle as run_h014_cycle,
)
from okx_quant.execution.deribit_shadow.runner import resolve_dsn


H009_REGISTERED_BASELINE_N_TRIALS = 4


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class H009SweepRequest(BaseModel):
    lookback_days: list[int] = Field(default_factory=lambda: [7, 14], min_length=1, max_length=10)
    quantiles: list[float] = Field(default_factory=lambda: [0.20, 0.30], min_length=1, max_length=10)

    @field_validator("lookback_days")
    @classmethod
    def validate_lookbacks(cls, values: list[int]) -> list[int]:
        unique = list(dict.fromkeys(values))
        if any(value < 1 or value > 365 for value in unique):
            raise ValueError("lookback_days must be between 1 and 365")
        return unique

    @field_validator("quantiles")
    @classmethod
    def validate_quantiles(cls, values: list[float]) -> list[float]:
        unique = list(dict.fromkeys(values))
        if any(not math.isfinite(value) or value < 0.05 or value > 0.45 for value in unique):
            raise ValueError("quantiles must be between 0.05 and 0.45")
        return unique

    @model_validator(mode="after")
    def validate_grid_size(self) -> "H009SweepRequest":
        if len(self.lookback_days) * len(self.quantiles) > 25:
            raise ValueError("H-009 UI sweeps are limited to 25 combinations")
        return self


def _resolved_h014_config(project_root: Path) -> dict[str, Any]:
    config = load_h014_config(project_root / "config" / "h014_shadow.yaml")
    journal = Path(config["journal_path"])
    if not journal.is_absolute():
        journal = project_root / journal
    journal = journal.resolve()
    if not journal.is_relative_to((project_root / "results").resolve()):
        raise ValueError("H-014 journal_path must stay inside the project results directory")
    config["journal_path"] = str(journal)
    return config


def _known_h009_trials_lower_bound(sweep_root: Path) -> int:
    trials = H009_REGISTERED_BASELINE_N_TRIALS
    if not sweep_root.exists():
        return trials
    for directory in sweep_root.iterdir():
        if not directory.is_dir():
            continue
        path = directory / "request.json"
        if not path.exists():
            path = directory / "summary.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            trials += max(0, int(payload.get("grid_size_this_run") or 0))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            continue
    return trials


def _require_action_header(value: str | None) -> None:
    if value != "1":
        raise HTTPException(status_code=403, detail="Missing local Research Ops action header")


def _run_h014_worker(config: dict[str, Any], dsn: str) -> dict[str, Any]:
    return asyncio.run(run_h014_cycle(config, dsn))


def make_research_router(project_root: Path, *, actions_enabled: bool = False) -> APIRouter:
    """Build the research router; mutations are enabled only on loopback."""
    router = APIRouter()
    project_root = project_root.resolve()
    h009_jobs: dict[str, dict[str, Any]] = {}
    h009_lock = threading.Lock()
    h014_lock = asyncio.Lock()

    @router.get("/h014")
    def h014_status() -> dict[str, Any]:
        config = _resolved_h014_config(project_root)
        return {
            "hypothesis_id": "H-014",
            "mode": "shadow_only",
            "actions_enabled": actions_enabled,
            "frozen_parameters": dict(config["signal"]),
            "report": build_bias_report(config["journal_path"]),
        }

    @router.post("/h014/run")
    async def run_h014(
        research_action: Annotated[str | None, Header(alias="X-Research-Action")] = None,
    ) -> dict[str, Any]:
        if not actions_enabled:
            raise HTTPException(status_code=403, detail="Research actions require the loopback standalone server")
        _require_action_header(research_action)
        if h014_lock.locked():
            raise HTTPException(status_code=409, detail="An H-014 shadow cycle is already running")
        config = _resolved_h014_config(project_root)
        try:
            async with h014_lock:
                summary = await asyncio.to_thread(
                    _run_h014_worker,
                    config,
                    resolve_dsn(project_root / "config" / "settings.yaml"),
                )
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001 - surface bounded public/DB failures to the operator.
            raise HTTPException(status_code=503, detail=f"H-014 shadow cycle failed: {exc}") from exc
        return {**summary, "report": build_bias_report(config["journal_path"])}

    def run_h009_job(job_id: str, sweep_id: str, request: dict[str, Any]) -> None:
        job = h009_jobs[job_id]
        sweep_root = project_root / "results" / "h009_parameter_sweeps"
        output_dir = sweep_root / sweep_id
        with h009_lock:
            job.update(status="running", message="Loading H-009 research inputs", started_at=_utc_now())
            try:
                from scripts.run_funding_xs_dispersion_checkpoint import (
                    run_funding_xs_dispersion_screen,
                )

                known_prior_n_trials = _known_h009_trials_lower_bound(sweep_root)
                output_dir.mkdir(parents=True, exist_ok=False)
                request_record = {
                    "sweep_id": sweep_id,
                    "created_at": _utc_now(),
                    "status": "submitted",
                    "validation_status": "in_sample",
                    "research_only": True,
                    "promotion_gate_passed": False,
                    "grid": {
                        "lookback_days": request["lookback_days"],
                        "quantile": request["quantiles"],
                    },
                    "grid_size_this_run": len(request["lookback_days"]) * len(request["quantiles"]),
                    "registered_baseline_n_trials": H009_REGISTERED_BASELINE_N_TRIALS,
                    "known_prior_n_trials_lower_bound": known_prior_n_trials,
                    "trial_count_scope": "registered_E031_baseline_plus_local_ui_submissions",
                }
                (output_dir / "request.json").write_text(
                    json.dumps(request_record, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                summary = run_funding_xs_dispersion_screen(
                    {
                        "project_root": project_root,
                        "grid": {
                            "lookback_days": request["lookback_days"],
                            "quantile": request["quantiles"],
                        },
                        "prior_family_n_trials": known_prior_n_trials,
                        "dsn": resolve_dsn(project_root / "config" / "settings.yaml"),
                    }
                )
                summary.update(
                    sweep_id=sweep_id,
                    created_at=_utc_now(),
                    artifact=str(output_dir / "summary.json"),
                )
                (output_dir / "summary.json").write_text(
                    json.dumps(summary, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                job.update(
                    status="done",
                    message="H-009 in-sample parameter screen complete",
                    finished_at=_utc_now(),
                    artifact=summary["artifact"],
                    grid_size_this_run=summary["grid_size_this_run"],
                    known_family_n_trials_lower_bound=summary[
                        "known_family_n_trials_lower_bound"
                    ],
                    top_results=summary["results"][:20],
                    warnings=summary["warnings"],
                )
            except Exception as exc:  # noqa: BLE001 - background jobs report errors via status.
                if output_dir.exists():
                    (output_dir / "error.json").write_text(
                        json.dumps({"sweep_id": sweep_id, "status": "error", "error": str(exc)}, indent=2) + "\n",
                        encoding="utf-8",
                    )
                job.update(status="error", message=str(exc), finished_at=_utc_now())

    @router.post("/h009/sweep")
    async def start_h009_sweep(
        request: H009SweepRequest,
        background: BackgroundTasks,
        research_action: Annotated[str | None, Header(alias="X-Research-Action")] = None,
    ) -> dict[str, Any]:
        if not actions_enabled:
            raise HTTPException(status_code=403, detail="Research actions require the loopback standalone server")
        _require_action_header(research_action)
        if any(job["status"] in {"queued", "running"} for job in h009_jobs.values()):
            raise HTTPException(status_code=409, detail="An H-009 parameter screen is already running")
        job_id = uuid.uuid4().hex[:8]
        sweep_id = f"h009_ui_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{job_id}"
        h009_jobs[job_id] = {
            "job_id": job_id,
            "sweep_id": sweep_id,
            "status": "queued",
            "message": "H-009 parameter screen queued",
            "created_at": _utc_now(),
            "research_only": True,
            "promotion_gate_passed": False,
        }
        background.add_task(run_h009_job, job_id, sweep_id, request.model_dump())
        return h009_jobs[job_id]

    @router.get("/h009/sweep/{job_id}")
    def h009_sweep_status(job_id: str) -> dict[str, Any]:
        if job_id not in h009_jobs:
            raise HTTPException(status_code=404, detail="H-009 sweep job not found")
        return h009_jobs[job_id]

    @router.get("/h009/jobs")
    def h009_job_list() -> list[dict[str, Any]]:
        return sorted(h009_jobs.values(), key=lambda job: job["created_at"], reverse=True)

    return router
