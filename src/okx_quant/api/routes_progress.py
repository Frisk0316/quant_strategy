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


def _branch_names(repo_dir: Path, shas: list[str]) -> dict[str, str]:
    """Map each sha to its nearest local-branch name in one name-rev call.

    name-rev walks the commit graph once regardless of how many shas it names,
    so batching all 60 timeline shas costs ~the same as naming one.
    """
    if not shas:
        return {}
    try:
        names = _run_git(repo_dir, ["name-rev", "--name-only", "--refs=refs/heads/*", *shas]).splitlines()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return {}
    return {sha: ("" if name == "undefined" else name) for sha, name in zip(shas, names)}


def _timeline(repo_dir: Path) -> list[dict[str, Any]]:
    # One `git log --name-only` carries commit fields AND changed files; one
    # batched name-rev resolves branches. Replaces the old ~2 subprocesses per
    # commit (diff-tree + name-rev) with 2 subprocesses total.
    # The trailing %x1f after %B delimits the body from the appended file list
    # (body never contains \x1f); records are split on the leading %x1e.
    raw = _run_git(
        repo_dir,
        ["log", "--all", "-n", "60", "--date=iso-strict", "--name-only",
         "--format=%x1e%H%x1f%aI%x1f%s%x1f%B%x1f"],
    )
    rows = []
    for chunk in raw.split("\x1e"):
        if not chunk.strip():
            continue
        fields = chunk.split("\x1f")
        while len(fields) < 5:
            fields.append("")
        sha, date, subject, body, files_blob = fields[:5]
        files = [line for line in files_blob.splitlines() if line.strip()]
        rows.append((sha.strip(), date.strip(), subject, body, files))
    branches = _branch_names(repo_dir, [sha for sha, *_ in rows])
    return [
        {
            "sha": sha[:12],
            "date": date,
            "actor": classify_actor(body),
            "branch": branches.get(sha, ""),
            "subject": subject,
            "docs": [path for path in files if _interesting_doc(path)],
        }
        for sha, date, subject, body, files in rows
    ]


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
