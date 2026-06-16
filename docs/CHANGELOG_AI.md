---
status: current
type: handoff
owner: human
created: 2026-06-12
last_reviewed: 2026-06-12
expires: none
superseded_by: null
---

# AI Changelog

Durable history for AI-assisted sessions. `docs/AI_HANDOFF.md` should stay focused
on current state, current goal, do-not-touch constraints, and next actions.

## 2026-06-12 - AI Context And Harness

- Added root `AI_CONTEXT.md` for project-wide AI onboarding context.
- Added feature, UI, data-flow, and runbook maps under `docs/`.
- Added docs-check scripts and Makefile harness targets.
- Added Codex prompt templates under `.codex/prompts/`.

## 2026-06-16 - Strategy Signal Validation Interface

- Added a selectable `--engines` CLI to `scripts/run_all_strategy_signal_validation.py`.
- Added `make strategy-signal-validation` and Runbook instructions for active-strategy
  portable signal-point validation.
- Added a default `NUMBA_DISABLE_JIT=1` guard for vectorbt fixture validation to
  avoid Windows import/JIT stalls on tiny fixtures.
- Generated batch `codex_20260616_signal_validation`, which produced PASS rows
  for all active strategies under `results/strategy_validation/`.

## Pending Migration

Historical session records in `docs/AI_HANDOFF.md` should move here over time when
they are no longer active current-state notes. Do not bulk-migrate history without a
dedicated docs cleanup task.
