---
status: current
type: reference
owner: human
created: 2026-06-12
last_reviewed: 2026-07-17
expires: none
superseded_by: null
---

# Context Index

The single map of **where to look** so a session can rebuild context without
relying on chat history (which is not a source of truth). Read this first when
starting cold or resuming after compression.

## Authority order (canonical)

Use `AI_CONTEXT.md` → "Source Of Truth List" as the master. Summary:

1. Current user instruction and approved scope.
2. `research/strategy_synthesis.md` — strategy assumptions.
3. `config/` — runtime settings and parameters.
4. `docs/ai_collaboration.md` — gates, roles, conflict handling.
5. `docs/DOC_LIFECYCLE.md`, `docs/AI_WORKFLOW.md`, `docs/BRANCH_VERSIONING.md`.
6. Accepted ADRs (`docs/ADR/`, index in `docs/ADR/README.md`).
7. Architecture/navigation docs (below).
8. `docs/AI_HANDOFF.md` / `docs/CURRENT_STATE.md` — current state.

## Map by need

| I need to… | Read |
|---|---|
| Understand the project at all | `AI_CONTEXT.md` |
| Know the current state / next action | `docs/CURRENT_STATE.md`, `docs/AI_HANDOFF.md` |
| Know the rules I must not break | `docs/DOMAIN_RULES.md`, `docs/INVARIANTS.md` |
| Review strategy-family history and iterations | `docs/STRATEGY_HISTORY.md`, `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md` |
| Find the owning files for a feature | `docs/FEATURE_MAP.md`, `docs/MODULE_BRIEFS/` |
| Trace data/artifacts | `docs/DATA_FLOW.md` |
| Understand resolved vs source-aware canonical candles | `docs/ADR/0014-source-aware-canonical-candles.md`, `tasks/2026-07-17-okx-canonical-promotion-codex-tasks.md` |
| Trace UI/API | `docs/UI_MAP.md` |
| Run / verify | `docs/RUNBOOK.md`, `Makefile` |
| Design something new | `docs/DESIGN_SPACE.md`, `docs/MENTAL_MODELS.md`, `docs/QUESTION_BANK.md` |
| Review a change | `docs/REVIEW_QUESTIONS.md`, `docs/CRITIQUE_PROTOCOL.md` |
| Know what breaks silently | `docs/FAILURE_MODES.md` |
| Assess a business-rule change | `docs/DOC_IMPACT_MATRIX.md`, `docs/CHANGE_MANIFEST_TEMPLATE.md` |
| Resume after context loss | `docs/COMPRESSION_RULES.md`, `docs/CONTEXT_PACKS/` |
| Know token budget rules | `docs/CONTEXT_BUDGET.md` |
| Hand off a session | `tasks/CONTEXT_HANDOFF_TEMPLATE.md`, `tasks/SESSION_HANDOFF_TEMPLATE.md` |

## Harness map

- **Doc Sync Harness:** [[DOMAIN_RULES]], [[DOC_IMPACT_MATRIX]],
  [[CHANGE_MANIFEST_TEMPLATE]], `docs/ADR/README.md`,
  `scripts/docs/check_doc_impact.py` (`make docs-impact`).
- **Intelligence Harness:** [[DESIGN_SPACE]], [[MENTAL_MODELS]], [[INVARIANTS]],
  [[HYPOTHESIS_LEDGER]], [[EXPERIMENT_REGISTRY]], [[QUESTION_BANK]],
  [[FAILURE_MODES]], [[CRITIQUE_PROTOCOL]], [[REVIEW_QUESTIONS]],
  [[GOLDEN_CASES]], `docs/MODULE_BRIEFS/`.
- **Context Resilience Harness:** this file, [[CONTEXT_BUDGET]],
  [[CURRENT_STATE]], [[COMPRESSION_RULES]], `docs/CONTEXT_PACKS/`,
  `tasks/CONTEXT_HANDOFF_TEMPLATE.md`.

Rule: when in doubt, read the file. Do not reconstruct rules or state from memory.
