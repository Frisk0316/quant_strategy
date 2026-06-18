"""Validate concrete repo-relative paths listed in docs/FEATURE_MAP.md."""

from __future__ import annotations

import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FEATURE_MAP = REPO_ROOT / "docs" / "FEATURE_MAP.md"
ROOT_FILENAMES = {"AGENTS.md", "AI_CONTEXT.md", "CLAUDE.md", "Makefile", "README.md", "pyproject.toml"}
PATH_EXTENSIONS = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".md",
    ".py",
    ".sql",
    ".toml",
    ".yaml",
    ".yml",
}


def _looks_like_path(value: str) -> bool:
    token = value.strip().strip(".,;:")
    if not token:
        return False
    if "://" in token or "#" in token or token.startswith("$"):
        return False
    if any(mark in token for mark in ("<", ">", "*", "(", ")", "{", "}")):
        return False
    if re.search(r"\s", token):
        return False
    if token in ROOT_FILENAMES:
        return True
    if token.startswith((".", "docs/", "frontend/", "src/", "scripts/", "backtesting/", "config/", "tests/", "sql/", "docker/")):
        return True
    return Path(token).suffix in PATH_EXTENSIONS


def _normalize(value: str) -> Path:
    token = value.strip().strip(".,;:")
    return Path(token.replace("\\", "/"))


def main() -> int:
    if not FEATURE_MAP.exists():
        print("ERROR docs/FEATURE_MAP.md does not exist")
        return 1

    text = FEATURE_MAP.read_text(encoding="utf-8")
    candidates = sorted({_normalize(match) for match in re.findall(r"`([^`\n]+)`", text) if _looks_like_path(match)})

    missing: list[Path] = []
    for rel in candidates:
        target = REPO_ROOT / rel
        if not target.exists():
            missing.append(rel)

    for rel in missing:
        print(f"ERROR docs/FEATURE_MAP.md references missing path: {rel.as_posix()}")

    if missing:
        print(f"feature map link check failed: {len(missing)} missing path(s)")
        return 1

    print(f"feature map link check passed: {len(candidates)} concrete path(s) checked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
