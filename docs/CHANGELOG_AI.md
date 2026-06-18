---
status: current
type: handoff
owner: human
created: 2026-06-12
last_reviewed: 2026-06-17
expires: none
superseded_by: null
---

# AI Changelog

Durable history for AI-assisted sessions. `docs/AI_HANDOFF.md` should stay focused
on current state, current goal, do-not-touch constraints, and next actions.

## 2026-06-12 - AI Context And Harness

- Added root `AI_CONTEXT.md` for project-wide AI onboarding context.
- Added feature, UI, data-flow, and runbook maps under `docs/`.
- Added docs-check scripts and Makefile harness targets.
- Added Codex prompt templates under `.codex/prompts/`.

## 2026-06-16 - Strategy Signal Validation Interface

- Added a selectable `--engines` CLI to `scripts/run_all_strategy_signal_validation.py`.
- Added `make strategy-signal-validation` and Runbook instructions for active-strategy
  portable signal-point validation.
- Added a default `NUMBA_DISABLE_JIT=1` guard for vectorbt fixture validation to
  avoid Windows import/JIT stalls on tiny fixtures.
- Generated batch `codex_20260616_signal_validation`, which produced PASS rows
  for all active strategies under `results/strategy_validation/`.

## 2026-06-17 - Strategy Signal Validation CI

- Added a CI `strategy-signal-validation` job that installs validation extras and
  runs the active-strategy fixture signal-validation batch.
- Added `VALIDATION_RESULTS_DIR` to `make strategy-signal-validation` so CI can
  keep generated validation artifacts in runner temp storage.
- Recorded the next validation priority as real-data/source-provenance evidence
  before full execution parity work.

## 2026-06-17 - Source Provenance Validation Gate

- Added `scripts/run_source_provenance_validation.py` to gate existing or freshly
  generated differential-validation evidence for real-data/source provenance.
- Added `make source-provenance-validation` as a thin wrapper around the script.
- Locked the rule that DB parity `SKIP` is not enough: the gate requires
  `source_data_validation`, `ct_val_provenance`, and `db_parity` to pass, with
  `ohlcv_source_validation == "db_parity_pass"`.

## 2026-06-18 - DB Parity Close-Only Contract

- Confirmed the saved Binance ADR-0007 run has 192/192 artifact closes matching
  DB canonical Binance closes with zero close mismatches.
- Updated `db_parity` to compare timestamped `close` values only for
  `price_series.csv` provenance; close-flattened artifact O/H/L and quote-volume
  units are not treated as like-for-like DB candle fields.
- Added regression coverage for close-flattened artifacts with matching close
  values.
- Generated durable source-provenance PASS evidence under
  `results/adr0007_binance_btc_1h_db_pass_20260618/validation/codex_close_only_db_parity_pass_20260618/`.

## Pending Migration

Historical session records in `docs/AI_HANDOFF.md` should move here over time when
they are no longer active current-state notes. Do not bulk-migrate history without a
dedicated docs cleanup task.
