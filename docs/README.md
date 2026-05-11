---
status: current
type: governance
owner: human
created: 2026-05-11
last_reviewed: 2026-05-11
expires: none
superseded_by: null
---

# Documentation Index

This directory contains the repository's durable documentation. See `docs/DOC_LIFECYCLE.md` before using any document as implementation authority.

## Current Source of Truth

| Document | Purpose |
|---|---|
| `docs/DOC_LIFECYCLE.md` | Markdown lifecycle, authority, archive, and deprecation rules. |
| `docs/ai_collaboration.md` | Shared collaboration contract between human, Claude, and Codex. |
| `docs/AI_WORKFLOW.md` | Session-level AI workflow and documentation authority rules. |
| `docs/AI_HANDOFF.md` | Current repository state and next actions. Current state only, not a changelog. |
| `docs/ARCHITECTURE.md` | Architecture map. Treat target or known-gap sections as non-implemented until verified. |
| `docs/backtest_live_parity_plan.md` | Backtest/live parity plan. |
| `docs/DEBUGGING_RUNBOOK.md` | Debugging procedures for recurring failures. |
| `docs/ADR/` | Architecture decision records. Only accepted ADRs are current implementation authority. |

## Historical Areas

| Path | Meaning |
|---|---|
| `docs/archive/` | Historical plans, reviews, and old docs retained for context only. |
| `docs/deprecated/` | Replaced docs retained because they may still be referenced. |

## AI Reading Order

For implementation tasks, read in this order:

1. Current user task and permitted files.
2. `docs/AI_HANDOFF.md`.
3. `docs/ai_collaboration.md`.
4. `docs/AI_WORKFLOW.md`.
5. Relevant accepted ADRs.
6. Relevant architecture, runbook, and config docs.
7. Archived, deprecated, proposed, or draft docs only when explicitly referenced.

If a document has no lifecycle metadata, treat it as draft until reviewed.
