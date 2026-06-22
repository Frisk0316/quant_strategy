---
status: current
type: adr
owner: codex
created: 2026-06-22
last_reviewed: 2026-06-22
expires: none
superseded_by: null
---

# ADR-0008: Fast Backtest Artifact Rows

## Status

Accepted - 2026-06-22, user-approved Option C implementation.

## Context

DB-backed saved runs can store large chart/table artifacts as one JSONB payload
per artifact in `backtest_artifacts`. API endpoints then read the whole payload
before filtering by symbol, slicing pages, or downsampling chart rows. Old runs
can therefore take several seconds to tens of seconds to paint after selection,
even when the user only needs a single symbol chart or the first page of fills.

The existing `result.json`, CSV files, and `backtest_artifacts.payload` contract
is already used by validation, reporting, and compatibility readers. Replacing it
would be high blast radius. The faster path must not change strategy logic,
fills, PnL, fees, funding, sizing, risk, deployment gates, or validation
semantics.

## Decision

Add `backtest_artifact_rows` as a derived read index for list-like artifacts.

- `backtest_artifacts.payload` and file artifacts remain the compatibility
  source of truth.
- New runs dual-write row-index records for large list artifacts after the
  existing artifact payload is built.
- Existing runs are made fast by `scripts/backfill_backtest_artifact_rows.py`,
  which derives rows from DB JSONB first and file artifacts second.
- API chart/table endpoints read row-index records first, with DB-side symbol
  filtering, `LIMIT/OFFSET`, and downsample selection. If rows are missing or
  invalid, endpoints fall back to the existing JSONB/file readers.
- `GET /api/backtest/{run_id}/summary` is the lightweight initial selection
  payload. `GET /api/backtest/{run_id}` remains the full result payload.
- Run-scoped differential validation CSV artifacts may be indexed as
  `validation/{validation_id}/{artifact_name}`. Strategy-validation artifacts
  remain on the existing file reader because the row table is keyed by
  `backtest_runs.run_id`.

## Consequences

- Saved-result UI reads can avoid loading full JSONB/CSV artifacts for common
  chart and table views.
- Row-index data is disposable and can be rebuilt; it is not trading evidence.
- Backfill verification must compare source row count and normalized source row
  hash against row-index payloads before claiming old runs are fast.
- Deleting a backtest run cascades derived rows via the `backtest_runs` foreign
  key.
- Schema migrations and docs-impact checks are required for this storage change,
  but no business-rule manifest should claim a PnL/fill/risk semantics delta.
