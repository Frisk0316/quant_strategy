---
status: current
type: manifest
owner: codex
created: 2026-07-18
last_reviewed: 2026-07-18
expires: none
superseded_by: null
---

# Change Manifest: H-014 Research Ops journal safety

## Summary

Expose the existing H-014 public-data shadow cycle in the local frontend while
preserving append-only evidence integrity across UI, CLI, and scheduled processes.
The same delivery adds a bounded, explicitly non-promotion H-009 sensitivity UI.

## Business rule(s) affected

R8.7 is strengthened with a single-writer cross-process journal-cycle rule.
R7.1/R7.4 are reviewed: the H-009 UI is in-sample only and labels its trial
count as a lower bound, so it cannot be used for a promotion DSR calculation.

## Trigger area(s) (DOC_IMPACT_MATRIX)

A2 execution, A7 API, A8 frontend, A9 research execution controls/trial
provenance, and A12 options shadow evidence safety.

## Files changed

- `src/okx_quant/execution/deribit_shadow/runner.py` — standard-library,
  non-blocking cross-process cycle lock.
- `src/okx_quant/api/routes_research.py`, `src/okx_quant/api/server.py`,
  `scripts/run_server.py` — research-only status/actions and safety boundary.
- `scripts/run_funding_xs_dispersion_checkpoint.py` — bounded H-009 screen with
  configured DSN and honest trial lower-bound provenance.
- `frontend/app.js`, `frontend/data.js`, `frontend/view-research.js`, `Makefile`
  — navigation, controls, custom local-action header, and syntax check.
- `tests/unit/test_h014_shadow.py`, `tests/unit/test_routes_research.py`,
  `tests/unit/test_funding_xs_dispersion_backtest.py` — lock, route, DSN,
  action-header, worker-thread, and trial-accounting regressions.
- Project maps, runbook, current-state/handoff, rule/invariant/failure registries,
  and workstream/changelog docs — behavior and safety boundary synchronization.

## Behavior delta

- Before: H-014 could run only through operational scripts; adding a second UI
  process without a shared lock could race the approved scheduler's journal.
- After: loopback Research Ops can run one existing H-014 cycle, while every
  journal-producing process shares a non-blocking OS lock. One overlapping cycle
  fails before journal state is loaded or written. H-009 can run only a bounded
  lookback/quantile in-sample screen and reports a known trial lower bound.
- Money/risk impact: none. H-014 still has no credential, private endpoint,
  broker, or order method; H-009 remains research-only.

## Source-of-truth updates

- `research/strategy_synthesis.md`: N/A — read-only source; assumptions unchanged.
- `config/`: only `config/workstreams.yaml` status text updated; no strategy,
  risk, mode, or deployment config changed.
- ADR: ADR-0011 reviewed and unchanged; this implements its append-only evidence
  boundary without authorizing live execution. ADR-0005 reviewed and unchanged.

## Docs updated (from DOC_IMPACT_MATRIX row)

- [x] `docs/DOMAIN_RULES.md` — R8.7 single-writer evidence rule.
- [x] `docs/INVARIANTS.md` — I39 strengthened.
- [x] `docs/FAILURE_MODES.md` — F48 added.
- [x] `docs/FEATURE_MAP.md`, `docs/UI_MAP.md`, `docs/DATA_FLOW.md`,
  `docs/RUNBOOK.md` — ownership, API/UI, flow, and operations.
- [x] `docs/ai_collaboration.md` and `docs/backtest_live_parity_plan.md` — reviewed,
  unchanged because no promotion/deployment gate or replay behavior changed.
- [x] `docs/EXPERIMENT_REGISTRY.md` — reviewed, unchanged because no H-009 sweep
  was executed and UI output is not registered promotion evidence.

## Invariants / golden cases

- Invariants checked: I39/I40; R7 promotion invariants remain unchanged.
- Golden cases affected: none; R8 accounting and fills are unchanged.

## Tests / checks run

- `pytest tests/unit/test_routes_research.py tests/unit/test_h014_shadow.py tests/unit/test_funding_xs_dispersion_backtest.py -q` — 24 passed.
- Final targeted unit/integration matrix — 45 passed.
- Targeted Ruff, frontend syntax, config validation, docs checks, strict
  doc-impact, API smoke, backtest smoke, and Playwright/Edge UI smoke — passed.

## Risks and rollback

- Risks: platform-specific file-lock behavior, stale UI job state after server
  restart, or misuse of H-009's lower-bound trial count. Windows and POSIX lock
  branches fail closed; runtime sidecars persist; UI/docs label non-promotion.
- Rollback: remove the Research Ops route/view/runner wrapper changes and revert
  the R8.7 lock addition. No DB/schema migration, existing result rewrite, or
  deployment rollback is required.

## Approval

- Human approval required: yes — obtained 2026-07-18 for a frontend-operable
  research/shadow surface. This does not approve live deployment or trading.
