---
status: current
type: reference
owner: human
created: 2026-06-12
last_reviewed: 2026-06-12
expires: none
superseded_by: null
---

# Context Pack: Harness Scaffolding

## Goal
Work on the Doc Sync, Intelligence, and Context Resilience harnesses (docs and
process only; no trading-core behavior).

## Must read (authority)
- `AI_CONTEXT.md` — authority order and do-not-touch list.
- `docs/DOC_LIFECYCLE.md` — lifecycle metadata required on every doc.
- `docs/ai_collaboration.md`, `AGENTS.md`, `CLAUDE.md` — collaboration contract.

## Owning files
- Doc Sync: `docs/DOMAIN_RULES.md`, `docs/DOC_IMPACT_MATRIX.md`,
  `docs/CHANGE_MANIFEST_TEMPLATE.md`, `docs/ADR/README.md`,
  `scripts/docs/check_doc_impact.py`, `Makefile` (`docs-impact`).
- Intelligence: `docs/DESIGN_SPACE.md`, `docs/MENTAL_MODELS.md`,
  `docs/INVARIANTS.md`, `docs/HYPOTHESIS_LEDGER.md`,
  `docs/EXPERIMENT_REGISTRY.md`, `docs/QUESTION_BANK.md`,
  `docs/FAILURE_MODES.md`, `docs/CRITIQUE_PROTOCOL.md`,
  `docs/REVIEW_QUESTIONS.md`, `docs/GOLDEN_CASES.md`, `docs/MODULE_BRIEFS/`.
- Context Resilience: `docs/CONTEXT_INDEX.md`, `docs/CONTEXT_BUDGET.md`,
  `docs/CURRENT_STATE.md`, `docs/COMPRESSION_RULES.md`, `docs/CONTEXT_PACKS/`,
  `tasks/CONTEXT_HANDOFF_TEMPLATE.md`.

## Rules in play
- Invariants: none changed (docs-only). Must not alter I1–I15 semantics.
- Failure modes to watch: F13 (stale doc as current), F14 (memory as truth).

## Tests / checks
- `make docs-check` — lifecycle metadata + feature-map links.
- `make docs-impact` — impact-matrix advisory check.
- `make verify` — light no-DB verification.

## Out of scope / do not touch
- `src/okx_quant/strategies/`, `signals/`, `risk/`, `portfolio/`, `execution/`.
- PnL / fee / funding behavior, DB schema, API behavior, frontend behavior.
- Deployment / shadow / demo gates.
- Unrelated pre-existing working-tree changes.

Related: [[../CONTEXT_INDEX]] · [[../DOMAIN_RULES]].
