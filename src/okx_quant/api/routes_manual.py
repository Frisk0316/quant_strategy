"""Serve the in-dashboard user manual manifest and markdown chapters."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse


def _without_frontmatter(text: str) -> str:
    lines = text.splitlines()
    if lines and lines[0] == "---" and "---" in lines[1:]:
        return "\n".join(lines[lines.index("---", 1) + 1 :]).lstrip()
    return text


def make_manual_router(manual_dir: Path) -> APIRouter:
    router = APIRouter()

    def _manifest() -> dict:
        path = manual_dir / "manual.json"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="manual manifest not found")
        return json.loads(path.read_text(encoding="utf-8"))

    @router.get("")
    def get_manifest() -> dict:
        return _manifest()

    @router.get("/{slug}", response_class=PlainTextResponse)
    def get_chapter(slug: str) -> str:
        chapter = next((c for c in _manifest().get("chapters", []) if c.get("slug") == slug), None)
        if chapter is None:
            raise HTTPException(status_code=404, detail="unknown chapter")
        file_path = manual_dir / chapter["file"]
        if not file_path.is_file():
            raise HTTPException(status_code=404, detail="chapter file missing")
        return _without_frontmatter(file_path.read_text(encoding="utf-8"))

    return router
