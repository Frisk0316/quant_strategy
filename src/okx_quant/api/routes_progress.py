"""Read-only workstream progress dashboard API.

Reads config/workstreams.yaml and reports each workstream's milestone progress.
No VCS, DB, or network access; the endpoint never starts child processes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

_VALID_STATUS = {"active", "blocked", "done", "shelved"}


def _milestone_states(milestones: list[str], current: str, status: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen_current = False
    for name in milestones:
        if status == "done":
            state = "done"
        elif name == current:
            state = "current"
            seen_current = True
        elif seen_current:
            state = "pending"
        else:
            state = "done"
        out.append({"name": str(name), "state": state})
    return out


def _normalize_workstream(raw: dict[str, Any]) -> dict[str, Any]:
    name = raw.get("name")
    milestones = raw.get("milestones")
    status = raw.get("status", "active")
    current = raw.get("current")

    card: dict[str, Any] = {
        "name": str(name) if name else "(unnamed)",
        "status": status,
        "state": raw.get("state", ""),
        "next": raw.get("next", ""),
        "links": [str(x) for x in (raw.get("links") or [])],
        "updated": raw.get("updated"),
        "milestones": [],
        "error": None,
    }

    if not name:
        card["error"] = "missing 'name'"
        return card
    if not isinstance(milestones, list) or not milestones:
        card["error"] = "missing or empty 'milestones'"
        return card
    if status not in _VALID_STATUS:
        card["error"] = f"invalid status '{status}' (expected {sorted(_VALID_STATUS)})"
        return card
    if status != "done":
        if current is None:
            card["error"] = "missing 'current'"
            return card
        if current not in milestones:
            card["error"] = f"'current' ({current!r}) not in milestones"
            return card

    card["milestones"] = _milestone_states([str(m) for m in milestones], str(current), status)
    return card


def _load_workstreams(repo_dir: Path) -> tuple[list[dict[str, Any]], str | None]:
    path = repo_dir / "config" / "workstreams.yaml"
    if not path.is_file():
        return [], None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        return [], f"workstreams.yaml parse error: {exc}"
    entries = data.get("workstreams") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        return [], None
    return [_normalize_workstream(e if isinstance(e, dict) else {}) for e in entries], None


def build_progress_payload(repo_dir: Path) -> dict[str, Any]:
    workstreams, error = _load_workstreams(repo_dir)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workstreams": workstreams,
        "error": error,
    }


def make_progress_router(repo_dir: Path | None = None, *, serve_files: bool = False) -> APIRouter:
    router = APIRouter()
    root = (repo_dir or Path(__file__).resolve().parents[3]).resolve()

    @router.get("")
    def progress() -> dict[str, Any]:
        payload = build_progress_payload(root)
        payload["file_links_enabled"] = serve_files
        return payload

    if serve_files:
        @router.get("/file", response_class=FileResponse)
        def progress_file(path: str) -> FileResponse:
            workstreams, _ = _load_workstreams(root)
            allowed = {link for card in workstreams for link in card.get("links", [])}
            target = (root / path).resolve()
            if (
                path not in allowed
                or not target.is_relative_to(root)
                or target.suffix.lower() != ".md"
                or not target.is_file()
            ):
                raise HTTPException(status_code=404, detail="unknown progress file")
            return FileResponse(target)

    return router
