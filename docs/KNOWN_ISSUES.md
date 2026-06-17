---
status: current
type: handoff
owner: human
created: 2026-06-12
last_reviewed: 2026-06-17
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

- Differential-validation unit coverage and the
  `codex_20260616_signal_validation` fixture batch verify source-data validation,
  portable validation gates, signal-point correctness, and active-strategy
  `reference_signals_only` contracts. These fixtures are signal-point evidence,
  not live execution or profitability evidence. CI now runs this fixture batch as
  a regression gate.
- Nautilus remains advisory in v1. Full Nautilus matching-engine parity for
  order/fill/PnL/funding semantics is not implemented.
- The signal-validation runner disables Numba JIT by default for vectorbt fixture
  validation because vectorbt import/JIT initialization can stall on Windows for
  tiny fixture workloads.
- Advisory validation evidence, in-sample backtests, idealized-fill artifacts, and
  DB parity SKIP states are not promotion evidence.
- ADR-0007 P1 closed the registry-only `ct_val` resolution gap for replay by
  adding venue-aware specs, provenance exchange tags, and frontend/API exchange
  selection. Remaining gap: this session could not confirm a fresh DB-backed
  artifact PASS because local `psql`/`DATABASE_URL` were unavailable.

## Operations

- Monitoring modules exist, but this map does not prove production alert coverage.
  Treat Telegram/metrics deployment readiness as a separate operational check.
