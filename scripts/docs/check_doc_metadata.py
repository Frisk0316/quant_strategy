"""Check Markdown lifecycle metadata for durable documentation."""

from __future__ import annotations

import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = REPO_ROOT / "docs"
TASKS_DIR = REPO_ROOT / "tasks"
# User decision 2026-07-12: every new tasks/ file requires lifecycle
# frontmatter. The pre-policy files below are historical records and are
# permanently exempt. This list is FROZEN — do not add entries; a file created
# later with a backdated name is still enforced because it is not listed here.
TASKS_LEGACY_EXEMPT = frozenset({
    "2026-06-17-binance-bybit-base-unit-ct-val-context-handoff.md",
    "2026-06-17-binance-bybit-base-unit-ct-val-session-handoff.md",
    "2026-06-17-multi-venue-instrument-specs-context-handoff.md",
    "2026-06-17-multi-venue-instrument-specs-session-handoff.md",
    "2026-06-18-adr0007-p1-task6-closeout-context-handoff.md",
    "2026-06-18-adr0007-p1-task6-closeout-session-handoff.md",
    "2026-06-18-adr0007-source-scope-followup-context-handoff.md",
    "2026-06-18-adr0007-source-scope-followup-session-handoff.md",
    "2026-06-18-db-parity-close-only-context-handoff.md",
    "2026-06-18-db-parity-close-only-session-handoff.md",
    "2026-06-18-task4-db-parity-exchange-scope-context-handoff.md",
    "2026-06-18-task4-db-parity-exchange-scope-session-handoff.md",
    "2026-06-22-binance-venue-spec-sync-context-handoff.md",
    "2026-06-22-binance-venue-spec-sync-session-handoff.md",
    "2026-06-22-fast-artifact-rows-context-handoff.md",
    "2026-06-22-fast-artifact-rows-session-handoff.md",
    "2026-06-22-fill-all-yzoom-sparse-trading-context-handoff.md",
    "2026-06-22-fill-all-yzoom-sparse-trading-session-handoff.md",
    "2026-06-22-market-data-queue-delete-context-handoff.md",
    "2026-06-22-market-data-queue-delete-session-handoff.md",
    "2026-06-22-validation-lab-db-only-run-context-handoff.md",
    "2026-06-22-validation-lab-db-only-run-session-handoff.md",
    "2026-06-22-validation-lab-report-context-handoff.md",
    "2026-06-22-validation-lab-report-session-handoff.md",
    "2026-06-23-funding-carry-venue-fallback-context-handoff.md",
    "2026-06-23-funding-carry-venue-fallback-session-handoff.md",
    "2026-06-23-market-data-coverage-fast-path-context-handoff.md",
    "2026-06-23-market-data-coverage-fast-path-session-handoff.md",
    "2026-06-23-validation-lab-report-refresh-context-handoff.md",
    "2026-06-23-validation-lab-report-refresh-session-handoff.md",
    "2026-06-23-validation-report-audience-rewrite-context-handoff.md",
    "2026-06-23-validation-report-audience-rewrite-session-handoff.md",
    "2026-06-23-xs-momentum-d3-review.md",
    "2026-06-23-xs-momentum-phase-c-context-handoff.md",
    "2026-06-23-xs-momentum-phase-c-session-handoff.md",
    "2026-06-23-xs-momentum-universe-context-handoff.md",
    "2026-06-23-xs-momentum-universe-session-handoff.md",
    "2026-06-23-xs-momentum-validation-context-handoff.md",
    "2026-06-23-xs-momentum-validation-session-handoff.md",
    "2026-06-24-cpcv-path-return-retention-honest-ntrials-task.md",
    "2026-06-24-dsr-allstrategy-recheck-task.md",
    "2026-06-24-dsr-computation-fix-task.md",
    "2026-06-24-xs-momentum-lookahead-fix-task.md",
    "2026-06-24-xs-momentum-phase-c-review.md",
    "2026-06-24-xs-momentum-portfolio-vol-task.md",
    "2026-06-25-manual-progress-route-context-handoff.md",
    "2026-06-25-manual-progress-route-session-handoff.md",
    "2026-06-25-pipeline-batch1-stage3-context-handoff.md",
    "2026-06-25-pipeline-batch1-stage3-session-handoff.md",
    "2026-06-25-pipeline-batch1-strategy-impl-task.md",
    "2026-06-25-progress-panel-context-handoff.md",
    "2026-06-25-progress-panel-session-handoff.md",
    "2026-06-25-s7-spot-canonical-data-task.md",
    "2026-06-29-c3-sentiment-stage3-context-handoff.md",
    "2026-06-29-c3-sentiment-stage3-session-handoff.md",
    "2026-06-29-c3-sentiment-stage3-verification-context-handoff.md",
    "2026-06-29-c3-sentiment-stage3-verification-session-handoff.md",
    "2026-06-29-c3-stage2-pass-summary-fix-task.md",
    "2026-06-29-stage2-feasibility-automation-context-handoff.md",
    "2026-06-29-stage2-feasibility-automation-session-handoff.md",
    "2026-06-29-work-log.md",
    "2026-06-30-idea-generator-context-handoff.md",
    "2026-06-30-idea-generator-session-handoff.md",
    "2026-06-30-xs-trials-and-idea-probe-context-handoff.md",
    "2026-06-30-xs-trials-and-idea-probe-session-handoff.md",
})

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
    """All tasks/ markdown recursively; templates and frozen legacy exempt."""
    if not TASKS_DIR.is_dir():
        return []
    selected = []
    for path in sorted(TASKS_DIR.rglob("*.md")):
        if "TEMPLATE" in path.name:
            continue
        if path.parent == TASKS_DIR and path.name in TASKS_LEGACY_EXEMPT:
            continue
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
