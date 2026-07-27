---
status: current
type: handoff
owner: codex
created: 2026-07-21
last_reviewed: 2026-07-21
expires: none
superseded_by: null
---

# Context Handoff: DB and UI data reliability - 2026-07-21

## Goal (one sentence)

Remove the measured Market Data Coverage bottleneck and make runtime DB
unavailability distinguishable from genuinely absent UI data without changing
schema, strategy, execution, or deployment gates.

## Current state

- Branch: `feature/h014-e052-shadow`.
- Last known good commit / state: `f38b6c0`; this task remains an uncommitted,
  verified working-tree change.
- In-progress edits (files): `src/okx_quant/api/routes_data.py`,
  `src/okx_quant/api/routes_backtest.py`, `docker/docker-compose.yml`, three
  owning unit-test files, runtime/UI/data-flow/governance docs,
  `config/workstreams.yaml`, and this task's two handoffs.
- What works right now: external coverage uses one grouped scan; a real DB call
  returned HTTP 200 with 137 combined rows in 1.704 seconds. Compose waits for
  TimescaleDB health, `DATABASE_URL` overrides the YAML candle DSN, and backtest
  run-list/result-summary reads return 503 for DB outage without a precise file
  fallback while preserving healthy 404 and existing-file fallback behavior.
- What does not work / unfinished: Docker is unavailable in this environment, so
  container integration was not executed. No API listener was running during
  diagnosis, so no browser smoke was claimed. F52 engine-dashboard auth,
  remaining per-artifact DB error paths, and post-fix connection-pool measurement
  remain follow-ups.

## Decisions made (and why)

- Replace the correlated per-dataset aggregate with one grouped scan because the
  old query exceeded the 10-second UI budget while the grouped shape completed
  well below it; no index or schema migration was justified.
- Preserve registered zero-observation datasets with null timestamps and
  `row_count=0` because this is the existing API meaning of a known empty source.
- Treat DB source reads as outage / healthy-absent / available-file-fallback
  states because swallowing connection failures created plausible empty data.
- Give runtime `DATABASE_URL` precedence over static YAML because container
  service discovery must override the host-local `localhost` DSN.
- Defer a shared pool until concurrent post-query-fix timing shows connection
  setup is material; avoid speculative infrastructure.

## Open questions / unverified assumptions

- Which explicit authentication contract should the engine-hosted browser use
  when `API_KEY` is enabled (F52)?
- After the SQL repair, how much of run-selection latency is still asyncpg
  connection setup rather than query/artifact serialization?
- Has migration 0012 plus artifact-row backfill been applied to every historical
  DB-only run in the user's active database?

## Rules in play (preserve verbatim)

- Invariants touched: none; result/PnL/fill semantics are unchanged.
- Domain rules touched: none.
- Do-not-touch: `research/`, existing `results/**`, strategy/signal/risk/
  portfolio/execution behavior, DB schema, differential validation, and all
  demo/shadow/live gates.

## Context to load next (the reading list)

- Source of truth: `AI_CONTEXT.md`, `docs/AI_HANDOFF.md`,
  `docs/CURRENT_STATE.md`, `docs/DOMAIN_RULES.md`, `config/settings.yaml`, and
  `docs/ADR/0014-source-aware-canonical-candle-identity.md`.
- Owning files / MODULE_BRIEFS: `src/okx_quant/api/routes_data.py`,
  `src/okx_quant/api/routes_backtest.py`, `backtesting/artifact_rows.py`,
  `frontend/data.js`, `frontend/view-config.js`, `frontend/view-backtest.js`,
  `docker/docker-compose.yml`, `docs/UI_MAP.md`, and `docs/DATA_FLOW.md`.
- Context Pack: no DB/API-specific pack exists; use `docs/CONTEXT_INDEX.md` and
  the files above rather than the unrelated harness-scaffolding pack.

## Checks run

- Focused API/data matrix (six test files) - `119 passed`.
- Targeted Ruff on changed Python files/tests - pass.
- `scripts/validate_pipeline.py --check-config-only` - both checks pass.
- Compose YAML parse/dependency assertions - pass.
- Real in-process `GET /api/data/coverage` - HTTP 200, 137 rows, 1.704 seconds.
- Old correlated query - exceeded a 12-second cold statement timeout; separate
  warm SQL comparison also measured approximately 4.5x improvement.
- Documentation metadata, feature-link, ledger-consistency, and advisory impact
  checks - pass; `git diff --check` also passes.

## Approvals

- Human approval needed / obtained: the user explicitly requested the DB/UI
  reliability fix. No authority was inferred for auth removal, schema changes,
  execution/risk edits, automated scheduling, or deployment-gate changes.

## Next action (single, concrete)

- Measure a normal multi-request BacktestView selection against a running API,
  then use that evidence to decide whether the next patch is remaining 503
  propagation or a bounded shared asyncpg pool.

## Human Learning Notes

The visible timeout came primarily from query shape, not a missing index: a
correlated aggregate repeatedly scanned a roughly 10 GB table. Two independent
availability defects made the same UI symptom misleading: Docker backtests could
use container-local `localhost`, and DB exceptions could look like empty/missing
runs. Diagnose status, server mode, DSN, and query latency separately before
increasing timeouts.
