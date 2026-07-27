---
status: current
type: handoff
owner: codex
created: 2026-07-21
last_reviewed: 2026-07-21
expires: none
superseded_by: null
---

# Session Handoff: DB and UI data reliability - 2026-07-21

## Implementation summary

Replaced the external coverage N-times aggregate with one grouped scan, fixed
container DB readiness and DSN precedence, and made backtest run-list/result
summary reads distinguish DB outage (503), healthy absence (404), corrupt JSON
(500), and precise file fallback (200). The API payload and DB schema are
unchanged.

## Diff scope

- Files added: this session handoff and
  `tasks/2026-07-21-db-coverage-performance-context-handoff.md`.
- Files changed: `docker/docker-compose.yml`, `config/workstreams.yaml`,
  `src/okx_quant/api/routes_data.py`, `src/okx_quant/api/routes_backtest.py`,
  `tests/unit/test_routes_data_delete.py`,
  `tests/unit/test_backtest_request_exchange.py`,
  `tests/unit/test_backtest_visual_fallbacks.py`, `docs/AI_HANDOFF.md`,
  `docs/CHANGELOG_AI.md`, `docs/CURRENT_STATE.md`, `docs/DATA_FLOW.md`,
  `docs/DEBUGGING_RUNBOOK.md`, `docs/FAILURE_MODES.md`,
  `docs/FEATURE_MAP.md`, `docs/KNOWN_ISSUES.md`, `docs/RUNBOOK.md`, and
  `docs/UI_MAP.md`.
- Files deleted: none.

Pre-existing user/other-session changes in
`tasks/2026-07-18-strategy-history-h010-claude-review.md`,
`tasks/2026-07-21-b1-distinctness-guard-codex-tasks.md`, and
`results/ui_funding_carry_2a3cdd23_execution_comparison.json` were preserved and
are not part of this task.

## Business-rule change?

- No. No Change Manifest or ADR is required; PnL, fees, funding, sizing, fills,
  gates, strategy assumptions, and DB schema are unchanged.

## Source-of-truth updates

- research/strategy_synthesis.md: N/A; read only.
- config/: `config/workstreams.yaml` updated for honest runtime milestone state;
  trading settings are unchanged.
- ADR: N/A.

## Experiments

- HYPOTHESIS_LEDGER entries: none.
- EXPERIMENT_REGISTRY entries: none.

## Tests / checks run

- Focused API/data matrix - `119 passed in 9.99s`.
- Targeted Ruff - pass.
- Config validation - both checks pass.
- Compose YAML dependency assertion - pass.
- Real coverage endpoint - HTTP 200, 137 rows, 1.704 seconds.
- Documentation metadata, feature-link, ledger-consistency, and advisory impact
  checks - pass; `git diff --check` also passes.

## Docs updated

- Updated the feature/UI/data-flow maps, runbook/debugging flow, F28 and
  F50-F52 failure modes, known issues, durable changelog, current handoff/state,
  and runtime workstream.

## Known limitations / risks

- Docker is unavailable locally, so Compose was parsed but not started.
- A running browser/API smoke was unavailable; no frontend rendering claim.
- F52 authentication contract and remaining per-artifact DB outage propagation
  remain open. A pool is deferred until measured after the SQL fix.
- Runtime environment variables now intentionally override the static YAML DSN;
  an incorrectly supplied `DATABASE_URL` will therefore take precedence.

## Rollback plan

- Revert only this task's route SQL/error-contract hunks, Compose dependency,
  DSN precedence line, owning tests, docs, workstream update, and two handoffs.
  No migration or artifact rollback is needed.

## Context Handoff

- See `tasks/2026-07-21-db-coverage-performance-context-handoff.md`.

## Questions for human review

- Should engine-hosted UI authentication use a browser session/cookie, or remain
  a loopback-only dashboard with a separate external API-key surface?
- After measurement, should remaining artifact endpoints get explicit 503 first,
  or should connection pooling and observability be delivered together?

## Next recommended task

- Run a real concurrent BacktestView selection benchmark, then close the
  remaining DB-error observability gap with the smallest measured change.

## Human Learning Notes (required)

The DB was healthy and indexed; the worst latency was caused by repeating a
large aggregate once per dataset. Startup order, DSN precedence, and swallowed
exceptions independently produced the same “no data” user experience, so future
diagnosis should separate query performance, reachability, and error semantics.
