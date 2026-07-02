---
status: current
type: handoff
owner: human
created: 2026-06-12
last_reviewed: 2026-06-22
expires: none
superseded_by: null
---

# AI Changelog

Durable history for AI-assisted sessions. `docs/AI_HANDOFF.md` should stay focused
on current state, current goal, do-not-touch constraints, and next actions.

## 2026-07-03 - Project Maintenance Audit And M1 CI Alignment

- Claude completed a whole-project maintenance audit outside the in-flight
  pipeline P1-P8 scope and wrote
  `tasks/2026-07-03-project-maintenance-tasks.md`.
- Verified gaps: CI/local verify drift, bloated/stale governance docs,
  entrypoint-only `backtest-smoke`, monitoring modules without dedicated tests,
  and orphan `src/okx_quant/stocks/` ownership.
- Codex M1 aligned CI with local lint/test intent: ruff now checks
  `src tests backtesting scripts`; CI installs and tests `crypto-alpha-lab`
  separately; CI runs the root-level synthetic Daily Winner/OHLCV Rotation tests;
  `frontend-check` includes `tweaks-panel.js` and `view-manual.js`.
- Local evidence: ruff passed; unit tests passed (555); root synthetic tests
  passed (32); lab tests passed (18); each frontend `node --check` command passed.

## 2026-07-03 - Pipeline Auto-Ideation Review And Improvement Plan

- Claude reviewed the auto-ideation pipeline and concluded the defensive side is
  sufficient: n_trials/K accounting, DSR/PSR gates, checkpoint1 review, and
  append-only state worked across three auto batches plus seven human-seeded
  families, with zero gate-passing candidates.
- Binding constraints are inlet-side: title-only literature scoring, data-blocked
  taxonomy frontier, and unimplemented cross-round feedback.
- User decisions: session-based LLM scoring (no API), public Binance Vision OI
  history (no paid provider), and a power-analysis note with no gate change.
- Deliverables committed before M2: `tasks/2026-07-03-pipeline-improvement-tasks.md`
  and `docs/superpowers/specs/2026-07-03-statistical-power-gates.md`.

## 2026-07-02 - Literature Scorer Review

- Claude reviewed Codex Task B commit `a688de1`, reran the relevant pipeline and
  lab suites, and confirmed the fetch-once/snapshot-once literature scorer path.
- The real Crossref-only batch selected one A-literature draft just above
  threshold; Claude flagged it for Stage-1 scrutiny because it mechanically maps
  to refuted family `F-FUNDING-CARRY`.
- arXiv timed out and Semantic Scholar returned HTTP 429 during the real run; the
  batch honestly reflects only the Crossref query.

## 2026-06-23 - Engine Consistency Smoke And Binance 1H DB Parity Follow-Up

- Added `scripts/run_engine_consistency_smoke.py`, `make engine-consistency-smoke`,
  and frozen real Binance BTC-USDT-SWAP 1H fixtures under
  `tests/fixtures/engine_consistency/`.
- Verified the smoke locally: MA/EMA/MACD all passed vectorbt+backtrader
  signal-logic comparison in 27.581s. MA and EMA fixtures each cover 960 hourly
  bars with 5 signals; MACD covers 120 hourly bars with 5 signals. This is
  signal-logic-only `strategy_fill` evidence, not promotion/live evidence.
- Added `scripts/resample_binance_1h_canonical.py` and used it to seed 20,400
  Binance-sourced BTC-USDT-SWAP 1H canonical rows from existing Binance 1m
  canonical rows in local Postgres.
- Pre-repair MA source-provenance validation failed DB parity with
  `canonical_source_primary=binance`, `artifact_rows=20400`, `db_rows=20376`,
  `missing_in_db=24`, and `value_mismatches=0`.
- Follow-up filled the remaining 2024-04-29 Binance 1H gap with
  `download_binance_data.py --start 2024-04-29 --end 2024-04-30`. Local parquet
  and DB canonical rows now match for that day (24 rows, 0 close mismatches);
  pre-repair validation artifacts need regeneration before a DB-parity PASS can
  be cited.

## 2026-06-22 - Backtest Execution Profiles

- Added first-class `strategy_fill` and `dual_output` execution profile
  implementation path for replay backtests.
- Kept `strategy_fill` as the existing research-only fill-all mechanism, with
  explicit idealized-fill marking.
- Added submitted-fill metrics that exclude terminal liquidation from strategy
  order fill counts.
- Verified BTC-USDT-SWAP Binance 1H with `max_order_notional_usd=250` and
  `max_pos_pct_equity=1`: Strategy Fill produced MA 228/228/228, EMA
  252/252/252, and MACD 1558/1558/1558 signal/order/fill counts with zero
  rejections. Full-period MACD Dual Output confirmed the realistic path still
  has sparse submitted fills: 779 submitted orders, 3 submitted-order fills, and
  1 terminal liquidation fill.
- Added Run Detail execution-profile visibility plus a comparison JSON link for
  dual-output child runs.

## 2026-06-22 - Validation Lab Report Package

- Added `docs/validation_lab_report_zh.md`, a Chinese report explaining the
  Validation Lab architecture, vectorbt/backtrader/Nautilus roles, source-data
  validation boundaries, parameter interpretation, max-order-notional
  differences, limitations, and a beginner no-code strategy-builder plan.
- Updated `scripts/generate_backtest_external_validation_report.py` and
  regenerated `docs/backtest_external_validation_report_zh.pptx` with
  Validation Lab report slides.
- Added `scripts/run_validation_lab_signal_order_check.py` and generated
  `results/validation_lab_signal_order_check_20260622.json` for
  BTC-USDT-SWAP Binance 1H MA/EMA 10/200 and MACD 12/26/9 signal-to-order
  evidence. The long-window differential-validation attempts for those
  generated runs did not complete locally and remain follow-up work.
- Updated reduce-only risk semantics after user approval: bounded reduce-only
  close orders may bypass the single-order fat-finger cap up to current position
  notional. Added Change Manifest
  `docs/change_manifests/2026-06-22-reduce-only-fat-finger-bypass.md` and reran
  the 250 USD / 100% equity sensitivity check.

## 2026-06-22 - Fast Backtest Artifact Rows (ADR-0008)

- Added ADR-0008 and a Change Manifest for Option C: a derived
  `backtest_artifact_rows` table that accelerates saved-result reads without
  changing existing artifact payloads or trading semantics.
- Added row-first API reads for common chart/table endpoints plus a lightweight
  `/api/backtest/{run_id}/summary` endpoint for immediate UI selection.
- Added backfill and benchmark scripts so old runs can be indexed, verified by
  count/hash parity, and measured through the running API.

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

## 2026-06-17 - Multi-Venue Instrument Specs (ADR-0007) Design + Coordination

Claude session (planning/review/risk; ponytail full). Design + plan + review;
implementation by Codex.

- Diagnosed the open "which saved run for the first DB-backed source-provenance
  PASS" question: no existing run qualifies (fixtures -> `db_parity` SKIP; real
  BTC and `ui_sweep` MA/EMA/MACD runs -> ct_val from `registry`, non-authoritative
  -> FAIL). The gate reads ct_val from the artifact, not live DB.
- Established the key correctness fact: ct_val cancels in notional-sized backtest
  PnL (`n=notional/(ct_val*price)`, `pnl=n*dprice*ct_val` -> `notional*dprice/price`).
  The ct_val provenance gate is therefore a **live-readiness gate, not a
  backtest-correctness gate**.
- Authored ADR-0007 (multi-venue instrument specs): single venue per run; new
  `venue_instrument_specs (exchange, symbol)` table; canonical symbol + thin
  native mapping; venue-aware ct_val resolution (Binance/Bybit USDT-M = 1.0, OKX
  BTC 0.01 / ETH 0.1); provenance gate stays shape-compatible + gains a venue
  tag. Added Change Manifest skeleton and ADR index row.
- Wrote the P1 implementation plan
  (`docs/superpowers/plans/2026-06-17-multi-venue-instrument-specs-p1.md`) as the
  Codex task spec (6 TDD tasks).
- Added a workstream sequencing note to `AI_HANDOFF.md` (multi-venue P1 owns the
  ct_val provenance gate; validation parallelizes except that surface + the
  Binance DB-backed PASS milestone; price chart independent).
- Reviewed the price-chart fix (`76dcecc`, branch `codex/fix-price-chart-universal`):
  per-symbol loading/empty/error states and indicator-overlay gating scoping are
  correct. Pass; pending human sign-off + merge.
- Diagnosed a backtest crash (Binance run on unseeded swap): `venue_instrument_specs`
  not applied to DB + resolver raises for non-OKX unseeded swaps. Provided a seed
  stopgap (A) and the structural fix (B): Binance/Bybit USDT-M perps resolve to
  `exchange_base_unit` (authoritative 1.0); 1000x-multiplier symbols still need an
  explicit DB row.
- Codex implemented P1 on `codex/impl-multi-venue-instrument-specs`: table+seed
  (`171b3f4`), exchange-aware resolution (`1aa85e2`), provenance tag (`e7eb3ed`),
  gate venue-tag (`519385e`), API+frontend exchange selector (`7be7f65`),
  convergence golden case (`71cd90c`), and the structural base-unit fix
  (`9bef416`). Remaining: Task 6 docs/Manifest fill-in + end-to-end DB-backed
  Binance PASS verification.

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
