"""Idempotently backfill lifecycle frontmatter on durable docs.

Only adds missing required fields; never overwrites existing values. Mirrors the
required-field set in check_doc_metadata.py. Safe to re-run.

Usage: python scripts/docs/backfill_doc_metadata.py [--dry-run]
"""
from __future__ import annotations

import re
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = REPO_ROOT / "docs"
TODAY = date.today().isoformat()
FALLBACK_CREATED = "2026-06-12"
REQUIRED = ["status", "type", "owner", "created", "last_reviewed", "expires", "superseded_by"]


def _git_created(path: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "log", "--diff-filter=A", "--format=%ad", "--date=short", "--", str(path)],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=20,
        ).stdout.strip().splitlines()
        if out:
            return out[-1]
    except Exception:  # ponytail: git missing/oddities -> fall back, not fatal
        pass
    m = re.search(r"(\d{4}-\d{2}-\d{2})", path.name)
    return m.group(1) if m else FALLBACK_CREATED


def _infer_type(rel: Path) -> str:
    p = rel.as_posix()
    if "/ADR/" in p:
        return "adr"
    if "/manual/" in p:
        return "manual"
    if "/plans/" in p:
        return "plan"
    if "/specs/" in p:
        return "design"
    if "/human_overviews/" in p:
        return "overview"
    if "/templates/" in p:
        return "template"
    return "reference"


def _parse_block(text: str) -> dict[str, str] | None:
    if not text.startswith("---"):
        return None
    lines = text.splitlines()
    for idx, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            meta: dict[str, str] = {}
            for ln in lines[1:idx]:
                m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", ln)
                if m:
                    meta[m.group(1)] = m.group(2).strip()
            return meta
    return None


def _defaults(rel: Path, path: Path) -> dict[str, str]:
    doc_type = _infer_type(rel)
    return {
        "status": "accepted" if doc_type == "adr" else "current",
        "type": doc_type,
        "owner": "human",
        "created": _git_created(path),
        "last_reviewed": TODAY,
        "expires": "none",
        "superseded_by": "null",
    }


def process(path: Path, dry_run: bool) -> str | None:
    rel = path.resolve().relative_to(REPO_ROOT)
    text = path.read_text(encoding="utf-8")
    meta = _parse_block(text)
    defaults = _defaults(rel, path)

    if meta is None:
        block = "---\n" + "".join(f"{k}: {defaults[k]}\n" for k in REQUIRED) + "---\n\n"
        new_text = block + text
        action = "prepend full frontmatter"
    else:
        missing = [k for k in REQUIRED if k not in meta]
        if not missing:
            return None
        lines = text.splitlines(keepends=True)
        close_idx = next(i for i, ln in enumerate(lines[1:], start=1) if ln.strip() == "---")
        insert = "".join(f"{k}: {defaults[k]}\n" for k in missing)
        new_text = "".join(lines[:close_idx]) + insert + "".join(lines[close_idx:])
        action = f"add {', '.join(missing)}"

    if not dry_run:
        path.write_text(new_text, encoding="utf-8", newline="\n")
    return action


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    files = sorted(DOCS_DIR.rglob("*.md"))
    root_context = REPO_ROOT / "AI_CONTEXT.md"
    if root_context.exists():
        files.append(root_context)
    changed = 0
    for path in files:
        action = process(path, dry_run)
        if action:
            changed += 1
            print(f"{'[dry] ' if dry_run else ''}{path.resolve().relative_to(REPO_ROOT)}: {action}")
    print(f"{'would change' if dry_run else 'changed'} {changed} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
