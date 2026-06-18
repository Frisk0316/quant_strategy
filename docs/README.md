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
| `docs/BRANCH_VERSIONING.md` | Branch naming, trunk-based workflow, merge policy, and tag/milestone checkpoints. |
| `docs/ai_collaboration.md` | Shared collaboration contract between human, Claude, and Codex. |
| `docs/AI_WORKFLOW.md` | Session-level AI workflow and documentation authority rules. |
| `docs/AI_HANDOFF.md` | Current repository state and next actions. Current state only, not a changelog. |
| `docs/ARCHITECTURE.md` | Architecture map. Treat target or known-gap sections as non-implemented until verified. |
| `docs/backtest_live_parity_plan.md` | Backtest/live parity plan. |
| `docs/DEBUGGING_RUNBOOK.md` | Debugging procedures for recurring failures. |
| `docs/ADR/` | Architecture decision records. Only accepted ADRs are current implementation authority. See `docs/ADR/README.md`. |

## Harnesses

Three harnesses govern how work is done; see `docs/CONTEXT_INDEX.md` for the full map.

### Doc Sync Harness

| Document | Purpose |
|---|---|
| `docs/DOMAIN_RULES.md` | Registry of business rules (PnL, fees, funding, sizing, risk, fills, gates). |
| `docs/DOC_IMPACT_MATRIX.md` | Maps changed areas to docs/manifests/ADRs that must be updated. |
| `docs/CHANGE_MANIFEST_TEMPLATE.md` | Template for the manifest required on every business-rule change. |
| `docs/ADR/README.md` | ADR index and authoring rules. |

Enforced by `scripts/docs/check_doc_impact.py` via `make docs-impact`.

### Intelligence Harness

| Document | Purpose |
|---|---|
| `docs/DESIGN_SPACE.md` | Design-space expansion protocol for design-heavy tasks. |
| `docs/MENTAL_MODELS.md` | Reusable reasoning lenses. |
| `docs/INVARIANTS.md` | Checkable correctness properties and their tests. |
| `docs/HYPOTHESIS_LEDGER.md` | Testable claims from statement to resolution. |
| `docs/EXPERIMENT_REGISTRY.md` | Append-only, reproducible experiment log with trial counts. |
| `docs/QUESTION_BANK.md` | Pre-work questions by area. |
| `docs/FAILURE_MODES.md` | Catalogue of wrong-but-plausible failures. |
| `docs/CRITIQUE_PROTOCOL.md` | How to pressure-test a plan or diff. |
| `docs/REVIEW_QUESTIONS.md` | Review checklist. |
| `docs/GOLDEN_CASES.md` | Reference scenarios with known-correct outputs. |
| `docs/MODULE_BRIEFS/` | One short brief per module. |

### Context Resilience Harness

| Document | Purpose |
|---|---|
| `docs/CONTEXT_INDEX.md` | Master map of where to look; read first on a cold start. |
| `docs/CONTEXT_BUDGET.md` | How to spend limited context window. |
| `docs/CURRENT_STATE.md` | One-screen current-state snapshot. |
| `docs/COMPRESSION_RULES.md` | What to preserve vs. compress. |
| `docs/CONTEXT_PACKS/` | Curated reading lists per feature/area. |
| `tasks/CONTEXT_HANDOFF_TEMPLATE.md` | End-of-session context handoff. |

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
