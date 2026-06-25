"""Read-only git/branch progress dashboard API."""
from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from fastapi import APIRouter


def classify_actor(body: str) -> str:
    if re.search(r"AI-Origin:\s*.*Codex", body, re.IGNORECASE):
        return "codex"
    if re.search(r"(Co-Authored-By:\s*.*Claude|AI-Origin:\s*.*Claude)", body, re.IGNORECASE):
        return "claude"
    return "you"


def _task_counts(plan_path: Path) -> tuple[int | None, int | None]:
    if not plan_path.is_file():
        return None, None
    text = plan_path.read_text(encoding="utf-8", errors="replace")
    boxes = re.findall(r"^\s*-\s*\[([ xX])\]", text, flags=re.MULTILINE)
    if not boxes:
        return None, None
    return sum(1 for mark in boxes if mark.lower() == "x"), len(boxes)


def parse_status_md(text: str, base_dir: Path | None = None) -> list[dict[str, Any]]:
    base_dir = base_dir or Path.cwd()
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells or cells[0].lower() == "branch" or set(cells[0]) <= {"-"}:
            continue
        if len(cells) < 6:
            continue
        plan = cells[4]
        done, total = _task_counts(base_dir / plan) if plan else (None, None)
        rows.append({
            "branch": cells[0],
            "state": cells[1],
            "whose_turn": cells[2],
            "next": cells[3],
            "plan": plan,
            "updated": cells[5],
            "tasks_done": done,
            "tasks_total": total,
        })
    return rows


def _run_git(repo_dir: Path, args: list[str]) -> str:
    command = ["git", "-c", f"safe.directory={repo_dir.as_posix()}", *args]
    completed = subprocess.run(
        command,
        cwd=repo_dir,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=True,
    )
    return completed.stdout.strip()


def _interesting_doc(path: str) -> bool:
    posix = PurePosixPath(path.replace("\\", "/"))
    return (
        posix.suffix == ".md"
        or (len(posix.parts) >= 2 and posix.parts[0] == "results" and posix.suffix == ".json")
        or (posix.parts and posix.parts[0] in {"config", "tasks"})
    )


def _commit_branch(repo_dir: Path, sha: str) -> str:
    try:
        name = _run_git(repo_dir, ["name-rev", "--name-only", "--refs=refs/heads/*", sha])
    except (FileNotFoundError, subprocess.CalledProcessError):
        return ""
    return "" if name == "undefined" else name


def _timeline(repo_dir: Path) -> list[dict[str, Any]]:
    raw = _run_git(
        repo_dir,
        ["log", "--all", "-n", "60", "--date=iso-strict", "--format=%H%x1f%aI%x1f%s%x1f%B%x1e"],
    )
    items = []
    for record in raw.strip("\x1e").split("\x1e"):
        if not record.strip():
            continue
        parts = record.strip().split("\x1f", 3)
        while len(parts) < 4:
            parts.append("")
        sha, date, subject, body = parts[:4]
        try:
            paths = _run_git(repo_dir, ["diff-tree", "--no-commit-id", "--name-only", "-r", sha]).splitlines()
        except (FileNotFoundError, subprocess.CalledProcessError):
            paths = []
        items.append({
            "sha": sha[:12],
            "date": date,
            "actor": classify_actor(body),
            "branch": _commit_branch(repo_dir, sha),
            "subject": subject,
            "docs": [path for path in paths if _interesting_doc(path)],
        })
    return items


def _branch_git(repo_dir: Path, branch: str, now: datetime) -> dict[str, Any]:
    try:
        last_commit_at = _run_git(repo_dir, ["log", "-1", "--format=%cI", branch])
        committed = datetime.fromisoformat(last_commit_at.replace("Z", "+00:00"))
        age_days = max(0, int((now - committed).total_seconds() // 86_400))
        counts = _run_git(repo_dir, ["rev-list", "--left-right", "--count", f"main...{branch}"]).split()
        behind, ahead = (int(counts[0]), int(counts[1])) if len(counts) == 2 else (None, None)
        return {
            "last_commit_at": last_commit_at,
            "age_days": age_days,
            "ahead": ahead,
            "behind": behind,
            "git_error": None,
        }
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        return {
            "last_commit_at": None,
            "age_days": None,
            "ahead": None,
            "behind": None,
            "git_error": str(exc),
        }


def build_progress_payload(repo_dir: Path) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    generated_at = now.isoformat()
    try:
        current_branch = _run_git(repo_dir, ["rev-parse", "--abbrev-ref", "HEAD"])
        timeline = _timeline(repo_dir)
    except FileNotFoundError:
        return _empty_payload(generated_at, "git executable not found")
    except subprocess.CalledProcessError as exc:
        return _empty_payload(generated_at, exc.stderr.strip() or str(exc))

    status_path = repo_dir / "STATUS.md"
    branches = parse_status_md(status_path.read_text(encoding="utf-8", errors="replace"), repo_dir) if status_path.is_file() else []
    branches = [{**row, **_branch_git(repo_dir, row["branch"], now)} for row in branches]
    counts = {actor: sum(1 for item in timeline if item["actor"] == actor) for actor in ("you", "claude", "codex")}
    return {
        "generated_at": generated_at,
        "current_branch": current_branch,
        "attribution": {
            **counts,
            "note": "Untagged commits are attributed to you.",
        },
        "timeline": timeline,
        "branches": branches,
        "error": None,
    }


def _empty_payload(generated_at: str, error: str) -> dict[str, Any]:
    return {
        "generated_at": generated_at,
        "current_branch": None,
        "attribution": {"you": 0, "claude": 0, "codex": 0, "note": "Untagged commits are attributed to you."},
        "timeline": [],
        "branches": [],
        "error": error,
    }


def make_progress_router(repo_dir: Path | None = None) -> APIRouter:
    router = APIRouter()
    root = (repo_dir or Path(__file__).resolve().parents[3]).resolve()

    @router.get("")
    def progress() -> dict[str, Any]:
        return build_progress_payload(root)

    return router
