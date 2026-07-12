"""Check Markdown lifecycle metadata for durable documentation."""

from __future__ import annotations

import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = REPO_ROOT / "docs"
TASKS_DIR = REPO_ROOT / "tasks"
# User decision 2026-07-12: new tasks/ files require lifecycle frontmatter;
# dated files before this cutoff are historical records and are never scanned.
TASKS_CUTOFF = "2026-07-01"
_TASK_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-")

REQUIRED_FIELDS = {
    "status",
    "type",
    "owner",
    "created",
    "last_reviewed",
    "expires",
    "superseded_by",
}
CURRENT_STATUSES = {"current", "accepted"}
KNOWN_STATUSES = CURRENT_STATUSES | {"draft", "proposed", "deprecated", "archived"}

REQUIRED_NEW_DOCS = {
    Path("AI_CONTEXT.md"),
    Path("docs/FEATURE_MAP.md"),
    Path("docs/UI_MAP.md"),
    Path("docs/DATA_FLOW.md"),
    Path("docs/RUNBOOK.md"),
    Path("docs/CHANGELOG_AI.md"),
    Path("docs/KNOWN_ISSUES.md"),
}


def _repo_rel(path: Path) -> Path:
    return path.resolve().relative_to(REPO_ROOT)


def _metadata_block(text: str) -> dict[str, str] | None:
    if not text.startswith("---"):
        return None
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    end = None
    for idx, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end = idx
            break
    if end is None:
        return None

    meta: dict[str, str] = {}
    for line in lines[1:end]:
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
        if match:
            meta[match.group(1)] = match.group(2).strip()
    return meta


def _markdown_files() -> list[Path]:
    files = sorted(DOCS_DIR.rglob("*.md"))
    root_context = REPO_ROOT / "AI_CONTEXT.md"
    if root_context.exists():
        files.append(root_context)
    return files


def _task_files() -> list[Path]:
    """Dated tasks/ files at or after the cutoff; templates/legacy exempt."""
    if not TASKS_DIR.is_dir():
        return []
    selected = []
    for path in sorted(TASKS_DIR.glob("*.md")):
        match = _TASK_DATE_RE.match(path.name)
        if match and match.group(1) >= TASKS_CUTOFF:
            selected.append(path)
    return selected


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    task_paths = set(_task_files())
    for path in _markdown_files() + sorted(task_paths):
        rel = _repo_rel(path)
        text = path.read_text(encoding="utf-8")
        meta = _metadata_block(text)
        # New tasks/ files are enforced at error level per the 2026-07-12 decision.
        is_task = path in task_paths
        is_required_new = rel in REQUIRED_NEW_DOCS

        if meta is None:
            message = f"{rel}: missing lifecycle metadata"
            if is_required_new or is_task:
                errors.append(message)
            else:
                warnings.append(message)
            continue

        missing = sorted(REQUIRED_FIELDS.difference(meta))
        status = meta.get("status", "")
        if missing:
            message = f"{rel}: missing metadata fields: {', '.join(missing)}"
            if is_required_new or is_task:
                errors.append(message)
            else:
                warnings.append(message)
        if status and status not in KNOWN_STATUSES:
            errors.append(f"{rel}: unknown lifecycle status {status!r}")
        if is_required_new and status not in CURRENT_STATUSES:
            errors.append(f"{rel}: new durable docs must use current/accepted status")

    for warning in warnings:
        print(f"WARN  {warning}")
    for error in errors:
        print(f"ERROR {error}")

    if errors:
        print(f"docs metadata check failed: {len(errors)} error(s), {len(warnings)} warning(s)")
        return 1
    print(f"docs metadata check passed with {len(warnings)} warning(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
