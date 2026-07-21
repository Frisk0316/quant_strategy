---
status: current
type: handoff
owner: codex
created: 2026-07-21
last_reviewed: 2026-07-21
expires: none
superseded_by: null
---

# Session Handoff: strategy-history / H-010 review fixes — 2026-07-21

## Implementation summary

Applied Claude findings A1–A3 and B1–B4, preserved E-057 byte-for-byte, and
split the previously shared working tree into five ordered delivery commits.
The repair reports identity-less Stage-2 artifacts, checks both frontend views,
fails the generic H-010 registry path closed without frozen evidence, amends
future distinctness contracts to be structurally satisfiable, records the exact
power tightening and funding boundary, and updates the authoritative ledgers
without changing E-057's FAIL/shelved outcome.

## Diff scope

- Files added: delivery-owned H-010, OKX-history, and Research Ops modules,
  tests, manifests, review records, and handoffs, plus this context/session pair.
- Files changed: delivery-owned runners/tests/docs plus shared maps, state,
  changelog, workstreams, and runbook.
- Files deleted: none.
- Commits: `5982a7f` H-010/E-057; `b40f15b` OKX history; `315b041` Research
  Ops; `1ef7b13` A1–A3/B1–B4; fifth shared-state commit at HEAD.
- Excluded: `results/ui_funding_carry_2a3cdd23_execution_comparison.json`.

## Business-rule change?

- Yes. The existing H-010 Change Manifest chain at
  `docs/change_manifests/2026-07-18-h010-stage2-pipeline.md` records R3.2 and
  future-only R6.6/I49/F49; `check_doc_impact.py --strict` passes. The Research
  Ops R8.7 lock change is recorded separately in
  `docs/change_manifests/2026-07-18-h014-research-ops-journal-safety.md`.

## Source-of-truth updates

- `research/strategy_synthesis.md`: read only; unchanged.
- `config/`: `config/workstreams.yaml` state text synchronized; no strategy,
  risk, mode, or deployment value changed.
- ADR: ADR-0013/ADR-0014 and ADR-0011 reviewed; unchanged.

## Experiments

- HYPOTHESIS_LEDGER entries: H-010 wording now identifies E-057 distinctness as
  a structural contract defect rather than a data-conditional measurement.
- EXPERIMENT_REGISTRY entries: E-057 wording changed identically; outcome,
  artifact references, n_trials=0, and K=0/2 are unchanged.
- No experiment, reprobe, retry, or Stage 3 run occurred in this task.

## Tests / checks run

- B2 red-first test before fix: `1 failed`; `probe_xvenue` was reached and the
  sentinel raised `AssertionError: xvenue probe ran without frozen calibration
  evidence`.
- Four core regressions after fix: `4 passed in 0.15s`.
- Review-focused modules: `23 passed in 0.35s`.
- Broad H-010/OKX/Research Ops matrix: `80 passed in 27.19s`.
- Full unit suite: `921 passed, 1 skipped, 1273 warnings in 55.70s`.
- Ruff: `All checks passed!`.
- Frontend syntax: `frontend syntax checks passed`.
- Config validation: two PASS lines.
- Backtest smoke: replay/artifact/fill checks PASS; idealized/non-promotion
  caveat preserved.
- Docs metadata: PASS, 0 warnings; feature-map links: PASS, 247 paths; ledger
  consistency: PASS, 22 hypotheses / 58 experiments / 21 K families; strict
  doc impact: PASS.

## Docs updated

- `DOMAIN_RULES`, `INVARIANTS`, `FAILURE_MODES`, existing H-010 Change Manifest,
  Stage-1 spec/task, ledger/registry, feature/data/UI/module maps, runbook,
  known issues, current state, AI handoff, changelog, workstreams, and task
  handoffs.

## Known limitations / risks

- Claude has not yet independently reviewed the repaired tree.
- The existing full-unit warnings are unchanged numerical precision/empty-slice
  warnings; the one skip is the known Windows symlink privilege case.
- No browser eyeball of the expanded Ledger row; 13/22 history sections remain
  not independently digit-checked.
- The stray execution-comparison JSON remains untracked pending user decision.

## Rollback plan

- Revert the five commits in reverse order. No DB/schema migration, existing
  artifact rewrite, strategy/config gate change, or deployment rollback is
  required.

## Context Handoff

- See `tasks/2026-07-21-strategy-history-h010-review-fixes-context-handoff.md`.

## Questions for human review

- After Claude review, decide whether to keep or delete
  `results/ui_funding_carry_2a3cdd23_execution_comparison.json`.

## Next recommended task

- Claude reviews the five commit boundaries and A1–A3/B1–B4 acceptance evidence;
  do not reuse H-010 Stage 2 until that review accepts B1/B2.

## Human Learning Notes (required)

The E-057 verdict did not need rewriting: its cost and funding failures already
stopped promotion. The reusable path did need repair. Separating immutable
evidence from future contract correctness avoided both history rewriting and a
silent recurrence.
