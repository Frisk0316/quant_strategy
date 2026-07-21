---
status: current
type: handoff
owner: codex
created: 2026-07-18
last_reviewed: 2026-07-18
expires: none
superseded_by: null
---

# Session Handoff: H-014/H-009 local Research Ops — 2026-07-18

## Implementation summary

Added a local Analysis > Research Ops view and `/api/research` router. H-014
shows its frozen signal and shadow-exit report and can run one accepted
credential-free cycle. H-009 can submit a bounded lookback/quantile full-sample
screen with immutable request/result/error sidecars and honest lower-bound trial
provenance. Mutations are loopback-only, require a custom frontend header, and
have no live/order surface. H-014 UI work runs off the API event loop and shares
a cross-process journal lock with CLI/scheduler invocations.

## Diff scope

- Files added: `src/okx_quant/api/routes_research.py`,
  `frontend/view-research.js`, `tests/unit/test_routes_research.py`,
  `docs/change_manifests/2026-07-18-h014-research-ops-journal-safety.md`,
  and this context/session handoff pair.
- Files changed: `Makefile`, `frontend/app.js`, `frontend/data.js`,
  `scripts/run_server.py`, `src/okx_quant/api/server.py`,
  `scripts/run_funding_xs_dispersion_checkpoint.py`,
  `src/okx_quant/execution/deribit_shadow/runner.py`,
  `tests/unit/test_funding_xs_dispersion_backtest.py`,
  `tests/unit/test_h014_shadow.py`, `config/workstreams.yaml`, and the mapped
  architecture/runbook/current-state/rule/invariant/failure/changelog docs.
- Files deleted: none. Generated `.playwright-cli/` state was cleaned up.

## Business-rule change?

- Yes, safety-only: R8.7 now requires a non-blocking cross-process single writer
  for H-014 journal-producing cycles. Change Manifest at
  `docs/change_manifests/2026-07-18-h014-research-ops-journal-safety.md`;
  DOC_IMPACT_MATRIX rows A2/A7/A8/A9/A12 checked.

## Source-of-truth updates

- `research/strategy_synthesis.md`: N/A — read only; no strategy assumption changed.
- `config/`: `config/workstreams.yaml` status text only; strategy/risk/mode/deploy
  configuration unchanged.
- ADR: none added or changed; ADR-0011 and ADR-0005 reviewed and remain governing.

## Experiments

- HYPOTHESIS_LEDGER entries: none.
- EXPERIMENT_REGISTRY entries: none. No actual H-009 screen or new H-014 cycle
  was executed during implementation verification.

## Tests / checks run

- `pytest tests/unit/test_routes_research.py tests/unit/test_h014_shadow.py tests/unit/test_funding_xs_dispersion_backtest.py -q` — 24 passed.
- Final targeted unit/integration command covering routes, H-014 accounting,
  H-009 scan, checkpoint contract, and API endpoints — 45 passed.
- Targeted Ruff — passed.
- Makefile-equivalent frontend syntax check including `view-research.js` — passed.
- `validate_pipeline.py --check-config-only` — 2 checks passed.
- Doc metadata, feature-map links, ledger consistency — passed.
- `check_doc_impact.py --strict` — passed, no violations.
- API smoke against `127.0.0.1:8082` — backtest-runs/data-exchanges passed.
- Backtest smoke — replay/artifacts/fills passed; idealized fixture only.
- Playwright/Edge — Research Ops view and current H-014 status rendered; browser
  console 0 errors/warnings. Missing action-header POSTs returned 403.
- `git diff --check` — passed; only existing LF/CRLF conversion warnings.

## Docs updated

- `docs/FEATURE_MAP.md`, `docs/UI_MAP.md`, `docs/DATA_FLOW.md`, `docs/RUNBOOK.md`.
- `docs/DOMAIN_RULES.md`, `docs/INVARIANTS.md`, `docs/FAILURE_MODES.md`, and the
  H-014 module brief.
- `docs/CURRENT_STATE.md`, `docs/AI_HANDOFF.md`, `docs/CHANGELOG_AI.md`,
  `config/workstreams.yaml`, Change Manifest, and handoffs.

## Known limitations / risks

- H-014 remains at 0.29/8 journal weeks and 1/8 distinct weeks; bias metrics and
  live-ADR discussion are locked. This UI does not alter that gate.
- H-009 jobs are held in memory and disappear from the UI after server restart;
  request/result/error artifacts persist.
- H-009's displayed count is a known lower bound (E-031 baseline plus this UI's
  requests), not an authoritative substitute for the Experiment Registry.
- No real DB-backed H-009 UI job was run. Pytest could not write `.pytest_cache`
  due workspace permissions; test execution itself passed.
- The working tree contains extensive unrelated H-010/E-057 and data-promotion
  changes from other sessions. Do not commit/revert them as part of this delivery.

## Rollback plan

- Remove the Research Ops route/view registrations and H-009 screen wrapper,
  revert the H-014 cycle-lock block and mapped docs/tests, then stop the local
  standalone server. No DB/schema migration, existing artifact rewrite, strategy
  config rollback, or deployment action is required.

## Context Handoff

- See `tasks/2026-07-18-h014-h009-research-ops-context-handoff.md`.

## Questions for human review

- None required to use the local research UI. Live deployment remains a separate
  future decision after the evidence gate and review.

## Next recommended task

- Claude reviews F48/I39 lock safety and the H-009 lower-bound provenance; then
  use the local Research Ops page for shadow collection and exploratory parameter
  navigation without treating the output as promotion evidence.

## Human Learning Notes (required)

The practical boundary is now visible in the product: H-014 is an append-only
shadow evidence collector, while H-009 is an exploratory screen. Neither is a
deploy button. The important engineering surprise was that a harmless-looking UI
created cross-process concurrency with the approved scheduler; a single-writer
OS lock was therefore part of the minimum safe frontend implementation.
