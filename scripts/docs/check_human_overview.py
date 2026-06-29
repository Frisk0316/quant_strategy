"""Check Human Review Overview documents for basic completeness.

Scans ``docs/human_overviews/*.md`` (ignoring ``README.md``) and verifies each
overview has the required YAML frontmatter fields, a valid ``risk_level``,
existing ``source_docs`` / ``human_must_read`` paths, and all required body
sections. Pure stdlib; no YAML dependency — a minimal frontmatter parser handles
the scalar + block-list subset these documents use.

Advisory-free: any problem makes the script exit 1 so it can gate a doc check
workflow later. Run:

    python scripts/docs/check_human_overview.py
    python scripts/docs/check_human_overview.py --selftest   # parser/logic check
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
OVERVIEW_DIR = REPO_ROOT / "docs" / "human_overviews"

REQUIRED_FIELDS = (
    "status",
    "type",
    "created",
    "topic",
    "source_docs",
    "decision_required",
    "risk_level",
    "human_must_read",
)
LIST_FIELDS = ("source_docs", "human_must_read")
VALID_RISK = {"low", "medium", "high"}
EXPECTED_TYPE = "human_review_overview"

REQUIRED_SECTIONS = (
    "## 1. 這次在做什麼？",
    "## 2. 為什麼要做？",
    "## 3. 本次產生 / 修改了哪些文件？",
    "## 4. 這次真正的決策點",
    "## 5. 主要風險",
    "## 6. 不能只看摘要的地方",
    "## 7. AI 尚未驗證 / 不確定的地方",
    "## 8. 測試與檢查狀態",
    "## 9. 對現有系統的影響",
    "## 10. 下一步",
)

# Scalar spellings that mean "empty list" when a list field is written inline.
_EMPTY_LIST_SCALARS = {"", "[]", "null", "none", "~"}


def parse_frontmatter(text: str) -> dict[str, object] | None:
    """Parse the leading ``---`` YAML block into a dict.

    Scalars become ``str``; block lists (``key:`` then ``  - item`` lines) become
    ``list[str]``. Returns ``None`` when there is no frontmatter block.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    end = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end = idx
            break
    if end is None:
        return None

    body = lines[1:end]
    meta: dict[str, object] = {}
    i = 0
    while i < len(body):
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", body[i])
        if not match:
            i += 1
            continue
        key, raw = match.group(1), match.group(2).strip()
        if raw == "":
            # Block list: collect following "- item" lines.
            items: list[str] = []
            j = i + 1
            while j < len(body):
                item = re.match(r"^\s+-\s+(.*)$", body[j])
                if not item:
                    break
                items.append(item.group(1).strip().strip('"').strip("'"))
                j += 1
            meta[key] = items
            i = j
        else:
            meta[key] = raw.strip('"').strip("'")
            i += 1
    return meta


def _as_list(value: object) -> list[str] | None:
    """Coerce a parsed field to a list, or None if it is not list-shaped."""
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip().lower() in _EMPTY_LIST_SCALARS:
        return []
    return None


def validate_overview(name: str, text: str, exists=None) -> list[str]:
    """Return a list of human-readable problems for one overview document."""
    exists = exists or (lambda p: (REPO_ROOT / p).exists())
    errors: list[str] = []

    meta = parse_frontmatter(text)
    if meta is None:
        return [f"{name}: missing YAML frontmatter block"]

    for field in REQUIRED_FIELDS:
        if field not in meta:
            errors.append(f"{name}: missing frontmatter field '{field}'")

    if meta.get("type") not in (None, EXPECTED_TYPE):
        errors.append(
            f"{name}: type must be '{EXPECTED_TYPE}', got {meta.get('type')!r}"
        )

    risk = meta.get("risk_level")
    if risk is not None and risk not in VALID_RISK:
        errors.append(
            f"{name}: risk_level must be one of low/medium/high, got {risk!r}"
        )

    for field in LIST_FIELDS:
        if field not in meta:
            continue
        paths = _as_list(meta[field])
        if paths is None:
            errors.append(f"{name}: {field} must be a YAML list")
            continue
        for rel in paths:
            if not exists(rel):
                errors.append(f"{name}: {field} path does not exist: {rel}")

    for section in REQUIRED_SECTIONS:
        if not any(line.strip() == section for line in text.splitlines()):
            errors.append(f"{name}: missing required section '{section}'")

    return errors


def _overview_files() -> list[Path]:
    if not OVERVIEW_DIR.exists():
        return []
    return sorted(
        p for p in OVERVIEW_DIR.glob("*.md") if p.name.lower() != "readme.md"
    )


def main() -> int:
    files = _overview_files()
    if not files:
        print(f"human overview check: no overviews found in {OVERVIEW_DIR}")
        return 0

    all_errors: list[str] = []
    for path in files:
        rel = path.relative_to(REPO_ROOT).as_posix()
        all_errors.extend(validate_overview(rel, path.read_text(encoding="utf-8")))

    if all_errors:
        for err in all_errors:
            print(f"ERROR {err}")
        print(
            f"human overview check FAILED: {len(all_errors)} error(s) "
            f"across {len(files)} overview(s)"
        )
        return 1

    print(f"human overview check passed: {len(files)} overview(s) OK")
    return 0


def _selftest() -> int:
    """In-memory check of the parser and validator branches."""
    good = "\n".join(
        [
            "---",
            "status: draft",
            "type: human_review_overview",
            "owner: human",
            "created: 2026-06-25",
            "topic: \"selftest\"",
            "source_docs:",
            "  - docs/exists-a.md",
            "decision_required: true",
            "risk_level: low",
            "human_must_read: []",
            "superseded_by: null",
            "---",
            "",
        ]
        + list(REQUIRED_SECTIONS)
    )
    meta = parse_frontmatter(good)
    assert meta is not None
    assert meta["source_docs"] == ["docs/exists-a.md"], meta["source_docs"]
    assert _as_list(meta["human_must_read"]) == []
    assert validate_overview("good.md", good, exists=lambda p: True) == []

    # Missing fields, bad risk, wrong type, missing section, dead path.
    bad = "\n".join(
        [
            "---",
            "type: something_else",
            "risk_level: extreme",
            "source_docs:",
            "  - docs/missing.md",
            "human_must_read: []",
            "---",
            "## 1. 這次在做什麼？",
        ]
    )
    errs = validate_overview("bad.md", bad, exists=lambda p: False)
    assert any("missing frontmatter field 'status'" in e for e in errs), errs
    assert any("risk_level" in e for e in errs), errs
    assert any("type must be" in e for e in errs), errs
    assert any("does not exist" in e for e in errs), errs
    assert any("missing required section '## 2." in e for e in errs), errs

    # No frontmatter at all.
    assert validate_overview("none.md", "# just a title")[0].endswith(
        "missing YAML frontmatter block"
    )

    print("selftest passed")
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        raise SystemExit(_selftest())
    raise SystemExit(main())
