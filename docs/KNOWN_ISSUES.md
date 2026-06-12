---
status: current
type: handoff
owner: human
created: 2026-06-12
last_reviewed: 2026-06-12
expires: none
superseded_by: null
---

# Known Issues

Durable backlog for bugs, gaps, and open operational risks. `docs/AI_HANDOFF.md`
may still reference active issues, but long-lived backlog items should move here
over time.

## Governance / Documentation

- `docs/AI_HANDOFF.md` still contains substantial historical session detail. Known
  gap: migrate completed history to `docs/CHANGELOG_AI.md` in a dedicated cleanup
  task.
- Some older Markdown files do not yet include lifecycle metadata. Current
  docs-check warns for older files and hard-fails only for new durable docs.

## Harness

- `make api-smoke` is a real smoke only when `API_BASE_URL` points at a running
  server; otherwise it exits with an explicit SKIP.
- `make backtest-smoke` verifies entrypoints only. Known gap: add a tiny frozen
  no-DB fixture before treating it as replay execution coverage.
- `make verify-full` may require TimescaleDB and seeded data.

## Validation

- Differential-validation implementation is being handled by a separate session.
  This AI-context/harness task intentionally does not edit validation engine files.
- Advisory validation evidence, in-sample backtests, idealized-fill artifacts, and
  DB parity SKIP states are not promotion evidence.

## Operations

- Monitoring modules exist, but this map does not prove production alert coverage.
  Treat Telegram/metrics deployment readiness as a separate operational check.
