---
status: current
type: manifest
owner: codex
created: 2026-06-22
last_reviewed: 2026-06-22
expires: none
superseded_by: null
---

# Change Manifest: Fast Backtest Artifact Rows

## Summary

Add a derived `backtest_artifact_rows` read index, row-first API reads, bulk
backfill, and benchmark tooling so saved backtest artifacts can load quickly
without changing existing result payloads or trading semantics.

## Business rule(s) affected

None. This is a storage/read-path optimization only.

## Trigger area(s) (DOC_IMPACT_MATRIX)

A5 backtesting artifacts, A6 DB schema/storage, A8 frontend/API result display,
A10 validation artifact inspection.

## Files changed

- `sql/migrations/0012_backtest_artifact_rows.sql` - derived row-index table and
  indexes.
- `backtesting/artifact_rows.py` - row conversion, hash parity, DB read/write
  helpers.
- `backtesting/artifacts.py` - best-effort dual-write of derived rows after
  existing artifact payloads.
- `src/okx_quant/api/routes_backtest.py` - row-first artifact reads and
  lightweight summary endpoint.
- `frontend/data.js`, `frontend/view-backtest.js` - summary-first selection and
  short in-flight caches for run/data coverage reads.
- `scripts/backfill_backtest_artifact_rows.py` - bulk backfill and verification.
- `scripts/benchmark_artifact_reads.py` - API latency benchmark report.
- Tests and docs listed in this changeset.

## Behavior delta

- Before: chart/table endpoints loaded whole artifact payloads before filtering,
  slicing, or downsampling.
- After: endpoints use `backtest_artifact_rows` first and fall back to the old
  JSONB/file readers when rows are missing.
- Money/risk impact: none. PnL, fees, funding, sizing, fills, risk, strategy
  signals, deployment gates, and validation semantics are unchanged.

## Source-of-truth updates

- research/strategy_synthesis.md: N/A - no strategy or promotion evidence change.
- config/: N/A - no config change.
- ADR: ADR-0008 added.

## Docs updated (from DOC_IMPACT_MATRIX row)

- [x] `docs/ADR/README.md` - index ADR-0008.
- [x] `docs/DATA_FLOW.md` - derived row-index artifact flow.
- [x] `docs/RUNBOOK.md` - migration/backfill/benchmark commands.
- [x] `docs/FEATURE_MAP.md` - artifact row files and tests.
- [x] `docs/UI_MAP.md` - summary-first and row-backed endpoints.
- [x] `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md` - current handoff state.

## Invariants / golden cases

- Invariants checked: no trading-core invariant changed; row parity is checked by
  normalized count/hash tests and backfill `--verify`.
- Golden cases affected: N/A.

## Tests / checks run

- Focused unit/API/frontend tests for row helper, row-first routes, summary
  endpoint, and frontend summary-first wiring.
- JavaScript syntax checks for touched frontend modules.
- Full verification results are recorded in the session handoff.

## Risks and rollback

- Risks: row table may be absent until migration/backfill runs; API falls back to
  old readers in that case. Backfilled rows are only as current as their source
  artifacts.
- Rollback: revert ADR-0008 implementation files and drop
  `backtest_artifact_rows`; existing `backtest_artifacts` and files remain
  compatible.

## Approval

- Human approval required: yes - user selected Option C and requested
  implementation on 2026-06-22.
