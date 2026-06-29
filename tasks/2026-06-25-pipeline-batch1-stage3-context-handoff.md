# Context Handoff: Pipeline Batch 1 Stage 3 2026-06-25

## Goal (one sentence)
Complete pipeline batch 1 data repair and S5/S6/S7 Stage 3 checkpoint artifacts
without enabling strategy/gate/deployment behavior.

## Current state
- Branch: `codex/xs-momentum-universe-scaffold`.
- Last known good commit / state: working tree has pre-existing unrelated edits
  in `scripts/backtest_ohlcv_rotation.py` and an untracked
  `tasks/2026-06-24-cpcv-path-return-retention-honest-ntrials-task.md`; do not
  revert them.
- In-progress edits (files): S5/S6/S7 strategy stubs, vectorized research
  runners, downloader/writer/ingest fixes, disabled config entries, REFERENCE
  contract entries, tests, docs/handoff updates, fold-refit checkpoint runner,
  `backtesting/pipeline_refit.py`, and generated
  `results/pipeline_batch1_20260625{,_refit}/**/summary.json`.
- What works right now: Binance S6/S7 data is loaded in DB for
  `BTC-USDT-SWAP`, `ETH-USDT-SWAP`, `BTC-USDT`, and `ETH-USDT` 1m canonical
  candles (1,293,120 rows each, 0 gaps) plus BTC/ETH perp funding (2,694 rows
  each). S5/S6/S7 checkpoint summaries have been rerun with fold-refit parameter
  selection. S6 did **not** re-earn the statistical gate; S7 is shelved after a
  non-degenerate half-life rerun; S5 is a no-trade/data-universe artifact.
- What does not work / unfinished: Portable validation adapters and
  authoritative ct_val evidence remain missing, but they should not start for S6
  because the refit statistical gate failed. S5 needs membership/canonical
  coverage reconciliation before interpretation. Full-window perp parquet
  pre-screen remains unavailable because local parquet cache is incomplete.

## Decisions made (and why)
- Treat S7 spot gate as complete because DB coverage is 1,293,120 / 1,293,120
  rows for both BTC-USDT and ETH-USDT, gap count is 0, and sampled parquet-vs-DB
  close parity has 0 mismatches.
- Loaded `ETH-USDT-SWAP` canonical candles instead of proxying with ETH spot or
  BTC-only runs because the hypothesis specs require BTC/ETH perps and/or ETH
  perp-vs-spot basis.
- Fixed Binance funding ingest to window `/fapi/v1/fundingRate` requests and
  mirror Binance/Bybit funding into legacy `funding_rates`, because current
  backtest loaders read the legacy table.
- Treat S5 as a data-universe artifact because current point-in-time membership
  plus strict venue-scoped complete-window candle coverage produces
  `nonzero_grid_activity:false`; do not interpret as support or refutation.
- Treat S6 E-012 as invalid OOS evidence because the old runner selected params
  on the full sample and sliced one return path. E-015 supersedes it with
  fold-refit WF/CPCV and fails DSR/PSR.
- Treat S7 as shelved, not refuted. E-016 reran with non-degenerate finite
  half-life gates and produced nonzero activity but failed DSR/PSR.
- Leave all S5/S6/S7 config entries `enabled:false` because no promotion gate is
  passed and no user deployment approval exists.

## Open questions / unverified assumptions
- Should the project generate full-window local perp parquet from DB for Pass A,
  or should Stage 3 officially allow DB-derived pre-screen when parquet cache is
  incomplete?
- Should Claude count S7's no-trade E-013 as invalid/replaced or as a family
  retry for future `n_trials` accounting?
- What membership/canonical-coverage policy should S5 use when point-in-time
  membership includes symbols without complete-window Binance canonical candles?

## Rules in play (preserve verbatim)
- Invariants touched: I13 hidden trials, I21 DSR <= PSR(0), I23 family
  cumulative n_trials, I24 fold-refit WF/CPCV evidence.
- Domain rules touched: R3.1 funding sign convention, R6.3 honest n_trials,
  R7.1 idealized-fill exclusion, R7.4 validation/promotion interpretation.
- Do-not-touch: `research/`, live/demo/shadow gates, risk/portfolio/execution,
  existing result artifact values, differential-validation implementation beyond
  contract entries, unrelated `scripts/backtest_ohlcv_rotation.py`.

## Context to load next (the reading list)
- Source of truth: `research/strategy_synthesis.md`,
  `docs/superpowers/specs/2026-06-25-{s5,s6,s7}*.md`,
  `docs/superpowers/pipeline/stage3-implement-backtest.md`,
  `docs/EXPERIMENT_REGISTRY.md`, `docs/KNOWN_ISSUES.md`.
- Owning files / MODULE_BRIEFS: `docs/FEATURE_MAP.md`, `docs/DATA_FLOW.md`,
  `docs/UI_MAP.md`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run
- Coverage probes -> passed: BTC/ETH perps and BTC/ETH spot each have 1,293,120
  Binance canonical 1m rows and 0 gaps; BTC/ETH perp funding each has 2,694 rows
  and no >8h05m large gaps.
- `python -m pytest tests\unit\test_market_ingest.py -q` -> 11 passed; pytest
  cache write warning only.
- `python -m pytest tests\unit\test_download_binance_data.py tests\unit\test_pipeline_batch1_contracts.py tests\unit\test_s5_residual_meanrev_backtest.py tests\unit\test_s6_ts_momentum_backtest.py tests\unit\test_s7_basis_meanrev_backtest.py -q`
  -> 12 passed; pytest cache write warning only.
- `python -B -m pytest tests\unit\test_pipeline_refit.py tests\unit\test_pipeline_batch1_checkpoint_runner.py tests\unit\test_pipeline_batch1_contracts.py -q -p no:cacheprovider`
  -> 5 passed.
- `python -B -m pytest tests\unit\test_pipeline_refit.py tests\unit\test_pipeline_batch1_checkpoint_runner.py tests\unit\test_pipeline_batch1_contracts.py tests\unit\test_s5_residual_meanrev_backtest.py tests\unit\test_s6_ts_momentum_backtest.py tests\unit\test_s7_basis_meanrev_backtest.py tests\unit\test_download_binance_data.py tests\unit\test_market_ingest.py -q -p no:cacheprovider`
  -> 27 passed.
- `python -B -u scripts\run_pipeline_batch1_checkpoint.py` -> wrote
  fold-refit/non-degenerate summaries: S5 `_refit` status
  `shelved_data_universe_mismatch`; S6 `_refit` WF 0.0088, CPCV 0.5422,
  DSR 0.1963, PSR 0.7387, promotion false; S7 WF -0.4359, CPCV -1.1124,
  DSR/PSR ~0, status `shelved_pending_research_review`.
- `python scripts/validate_pipeline.py --check-config-only` -> PASS.
- `python scripts/docs/check_doc_metadata.py` -> PASS with 18 pre-existing
  metadata warnings.
- `python scripts/docs/check_feature_map_links.py` -> PASS.
- `python scripts/docs/check_doc_impact.py --strict` -> exited 0 but reported
  no changed files detected.

## Approvals
- Human approval needed / obtained: No approval requested or obtained for
  strategy promotion, demo, shadow, or live trading. Network approval was
  obtained for Binance downloads/ingest.

## Next action (single, concrete)
- Send S5/S6/S7 refit/non-degenerate checkpoint summaries to Claude evidence
  review; decide S5 universe policy and S7 family retry accounting. Do not start
  S6 adapter/ct_val work unless a future refit run re-earns DSR/PSR >= 0.95.

## Human Learning Notes
The data blocker is resolved, but the first-batch evidence did not survive the
cleaner harness. The important lesson is not "S6 almost passed"; it is that OOS
validation must refit/select inside each fold. Local parquet cache is still not
equivalent to canonical DB coverage; Pass A needs either a proper full-window
parquet cache or an explicit DB-derived fallback policy.
