---
status: current
type: handoff
owner: codex
created: 2026-07-17
last_reviewed: 2026-07-17
expires: none
superseded_by: null
---

# Session Handoff: Strategy History and Ledger Iterations — 2026-07-17

## Implementation summary

Completed the Claude-planned Tasks A/B/C: added a traceable history for all 22
hypotheses (H-000–H-021) and 57 experiments (E-000–E-056), upgraded the
disposable funnel projection to schema v2 while preserving v1 fields, and added
an expandable read-only Ledger
timeline with graceful schema-v1 fallback. No authoritative ledger, research
file, stored result, strategy implementation, or gate changed.

## Diff scope

- Files added: `docs/STRATEGY_HISTORY.md`, this session handoff, and
  `tasks/2026-07-17-strategy-history-frontend-codex-context-handoff.md`.
- Files changed: `scripts/run_pipeline_funnel_report.py`,
  `tests/unit/test_pipeline_funnel_report.py`, `frontend/view-ledger.js`,
  `tests/unit/test_routes_progress.py`, `docs/DATA_FLOW.md`, `docs/UI_MAP.md`,
  `docs/CONTEXT_INDEX.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`,
  `config/workstreams.yaml`, and lifecycle metadata in the task specification.
- Files deleted: none.

## Business-rule change?

- No. No Change Manifest, DOC_IMPACT_MATRIX row, or ADR is required.

## Source-of-truth updates

- `research/strategy_synthesis.md`: N/A; read-only and unchanged.
- `config/`: updated only the Progress workstream state/date and existing
  allow-list link for the new history document; no strategy/risk/gate value.
- ADR: N/A; no policy or major rule changed.

## Experiments

- HYPOTHESIS_LEDGER entries: none; read-only.
- EXPERIMENT_REGISTRY entries: none; read-only.

## Tests / checks run

- Funnel-report unit tests — 3 passed.
- Progress-route unit tests — 10 passed.
- Targeted Ruff and all frontend Node syntax checks — PASS.
- Docs metadata, Feature Map links, and ledger consistency — PASS.
- Config-only pipeline validation — PASS.
- Real schema-v2 generation and structural H/E coverage checks — PASS.
- Edge/Playwright schema-v2 expansion and schema-v1 fallback — PASS; unrelated
  favicon 404 only.
- `make` was unavailable, so Makefile-equivalent commands were run directly.

## Docs updated

- Added `docs/STRATEGY_HISTORY.md`; updated `docs/DATA_FLOW.md`,
  `docs/UI_MAP.md`, `docs/CONTEXT_INDEX.md`, `docs/AI_HANDOFF.md`, and
  `docs/CURRENT_STATE.md`; added both required handoffs.
- `docs/FEATURE_MAP.md` was reviewed but not changed because ownership/routes did
  not change and the task's explicit documentation scope was DATA_FLOW/UI_MAP.

## Known limitations / risks

- The document intentionally reports most benchmark and annualized-return fields
  as `n/a (not recorded)`; only H-002/E-005 had a valid recorded annualized value.
- H-009 has a source chronology conflict, some historical trial accounting is
  inconsistent, and H-014 support is limited to its RICH short-premium branch.
- The projection parses the ledgers' current Markdown shape; future heading or
  table format changes require regenerating and retesting schema v2.
- The shared worktree contains unrelated pre-existing changes; this task did not
  clean, commit, or revert them.

## Rollback plan

- Remove the three added task-owned documents, revert only the schema-v2 fields,
  Ledger expansion, related tests/docs/index/status edits, and remove the
  `docs/STRATEGY_HISTORY.md` allow-list entry. Leave all pre-existing shared-tree
  changes untouched.

## Context Handoff

- See `tasks/2026-07-17-strategy-history-frontend-codex-context-handoff.md`.

## Questions for human review

- Should a separately approved ledger-normalization task resolve H-009's date
  ordering and historical trial-count vocabulary, or should they remain literal
  historical records?
- Does Claude agree that H-014's supported status must be described as branch-
  specific rather than generalized to the failed CHEAP long-straddle branch?

## Next recommended task

- Claude performs a fresh source-fidelity review of the history document and
  schema-v2 projection; do not begin normalization, retry, ingest, or deployment
  work as part of that review.

## Human Learning Notes (required)

The shortest robust implementation was to expose the ledgers' existing data
through a disposable schema and native disclosure controls. The sparse
annualized-return/benchmark columns reveal a documentation gap in historical
experiments, not missing frontend logic. Keeping raw experiment text visible
also makes inconsistencies reviewable instead of encoding an undocumented
normalization policy.
