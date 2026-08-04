---
status: current
type: handoff
owner: codex
created: 2026-08-03
last_reviewed: 2026-08-03
expires: none
superseded_by: null
---

# Context Handoff: PR #19 API security CI fix — 2026-08-03

## Goal (one sentence)

Keep the standalone API-key test independent of database availability so PR #19
validates authentication without weakening the documented 503 outage behavior.

## Current state

- Branch: `feature/deribit-moneyness-hypotheses`.
- Fix commit: `6176849` (synced to the PR branch on origin).
- In-progress edits: only this task's two handoffs.
- What works right now: the security test passes even when the process starts with
  an unreachable `DATABASE_URL`; the dedicated DB-outage test still returns 503.
- What does not work / unfinished: PR #19 checks must be rerun after delivery.
- Separate concurrent commit: `9d89912` updated
  `tasks/2026-08-03-project-optimization-codex-plan.md`; it was not part of this
  task's fix.

## Decisions made (and why)

- Isolate the security test from `_db_dsn()` and `DATABASE_URL` because its subject
  is the API-key dependency, while 503 is the intended result of a separate data
  availability contract.
- Do not change `routes_backtest.py` because its outage behavior is documented and
  already guarded by a focused unit test.

## Open questions / unverified assumptions

- None.

## Rules in play (preserve verbatim)

- Invariants touched: none.
- Domain rules touched: none.
- Do-not-touch: production API behavior, strategy logic, risk/PnL rules, config,
  research files, deployment gates, and existing result artifacts.

## Context to load next (the reading list)

- Source of truth: `docs/FEATURE_MAP.md` — Backtest API.
- Owning files: `tests/unit/test_api_security.py`, `scripts/run_server.py`,
  `src/okx_quant/api/routes_backtest.py`, `src/okx_quant/api/server.py`.
- Context Pack: none; this is a unit-test isolation fix.

## Checks run

- Poisoned-DSN security and outage tests — 2 passed.
- `python -m ruff check src tests backtesting scripts` — passed.
- `python -m pytest tests/unit -p no:cacheprovider -q` — 1106 passed, 1 skipped.
- Root synthetic backtest tests — 32 passed.

## Approvals

- Human approval obtained in the request to fix PR #19.

## Next action (single, concrete)

- Monitor PR #19's new GitHub Actions run and confirm all three checks pass.

## Human Learning Notes

An authentication test should control downstream availability dependencies. A
valid API key only proves the request crossed the auth boundary; it does not make
TimescaleDB available, and the run-list route is correct to report that outage.
