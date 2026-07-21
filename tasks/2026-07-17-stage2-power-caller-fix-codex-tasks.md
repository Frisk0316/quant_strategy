---
status: current
type: task
owner: codex
created: 2026-07-17
last_reviewed: 2026-07-17
expires: 2026-10-17
superseded_by: null
---

# Codex Task: Stage-2 power caller regression and funnel error isolation

This task restores the follow-up referenced, but not present, in
`tasks/2026-07-17-abc-delivery-claude-review.md`. The user explicitly authorized
the review's F1 repair on 2026-07-17, including F2 commit separation and F3
graceful funnel errors.

## Problem and decision

New Stage-2 writers fail closed when statistical-power inputs are missing, but
legacy callers still omit them. That silently records a caller-contract error as
a candidate `stage2_fail`; the orchestrator then treats it as terminal.

- Option A: keep the fail-closed artifacts. Rejected: direction-safe but silently
  over-rejects candidates.
- Option B: invent caller defaults. Rejected: breadth and plausible Sharpe are
  research assertions and family trial counts must remain authoritative.
- Option C: require explicit candidate-specific inputs at each caller boundary
  before a probe or artifact write. Chosen: smallest change that preserves
  ADR-0013 and R6.3.

The batch orchestrator uses a `candidate_id -> power inputs` JSON object; one
global set is invalid for a multi-candidate batch. Malformed funnel artifacts are
reported per file and excluded from feasible counts while valid files continue.

## Permitted files

- `backtesting/pipeline_stage2_registry.py`
- `backtesting/pipeline_orchestrator.py`
- `scripts/run_pipeline_orchestrator.py`
- `scripts/market_data/backfill_universe_funding.py`
- `scripts/run_pipeline_funnel_report.py`
- Focused tests for those callers and the funnel
- ADR-0013, its existing Change Manifest, Stage-2 template, feature/data/runbook,
  invariant/failure-mode, current-state, changelog, and required handoff docs

## Forbidden

- `research/`, `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md`
- Existing `results/**` artifacts
- Strategy, signal, risk, portfolio, execution, PnL, Stage-3, deployment, demo,
  shadow, and live behavior

## Acceptance criteria

- Missing caller inputs raise an explicit error before a Stage-2 probe/artifact.
- Complete inputs retain registry-cumulative `n_trials` enforcement.
- Funding backfill requires inputs only when its Stage-2 probe is enabled.
- Orchestrator first-run and reprobe use candidate-specific mappings.
- One malformed Stage-2 artifact does not abort the funnel; it is reported and
  cannot count as feasible.
- Existing Stage-3 and deployment gates remain unchanged.
