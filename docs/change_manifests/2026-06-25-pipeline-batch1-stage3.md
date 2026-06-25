---
status: current
type: manifest
owner: codex
created: 2026-06-25
last_reviewed: 2026-06-25
expires: none
superseded_by: null
---

# Change Manifest: Pipeline Batch 1 Stage 3 Checkpoint

## Summary

Implemented research-only S5/S6/S7 strategy/backtest scaffolding, completed the
S7 Binance spot canonical data gate, loaded missing `ETH-USDT-SWAP` perp OHLCV
and ETH funding data, emitted checkpoint `summary.json` artifacts for pipeline
batch 1, and recorded the initial S6/S7 outcomes. Later in the same session,
those initial statistical interpretations were superseded by the fold-refit
WF/CPCV rerun in `docs/change_manifests/2026-06-25-refitting-wf-cpcv-harness.md`.

## Business rule(s) affected

R3.1 funding sign convention, R6.3 honest `n_trials`, R7.1 idealized-fill
exclusion, R7.4 validation status / promotion-gate interpretation.

## Trigger area(s) (DOC_IMPACT_MATRIX)

A1 PnL/funding accounting, A4 data provenance, A5 backtesting workflow, A9
validation / gates, A11 experiments / research runs.

## Files changed

- `scripts/download_binance_data.py` - support Binance spot endpoint/limit for
  non-SWAP symbols while preserving futures behavior for SWAP symbols.
- `scripts/_db_writer.py` - chunk raw candle DB upserts to avoid single huge
  `executemany` stalls on multi-year spot backfills.
- `scripts/market_data/ingest.py` - window Binance funding-rate backfills and
  mirror Binance/Bybit funding into legacy `funding_rates` with internal SWAP
  symbols for current backtest loaders.
- `scripts/run_pipeline_batch1_checkpoint.py` - reproducible S5/S6/S7 checkpoint
  runner; later updated to use fold-refit validation.
- `src/okx_quant/strategies/s5_residual_meanrev.py` - research strategy stub and
  params.
- `src/okx_quant/strategies/s6_ts_momentum.py` - research strategy stub and
  params.
- `src/okx_quant/strategies/s7_basis_meanrev.py` - research strategy stub and
  params.
- `backtesting/s5_residual_meanrev_backtest.py` - vectorized research runner
  with one-day target lag, funding cashflow, and residual-z exit hysteresis.
- `backtesting/s6_ts_momentum_backtest.py` - vectorized research runner with
  one-day target lag and funding cashflow.
- `backtesting/s7_basis_meanrev_backtest.py` - vectorized research runner with
  one-day target lag, funding cashflow, basis-z exits, max hold, and half-life
  filter.
- `backtesting/differential_validation.py` - REFERENCE validation contract
  entries for S5/S6/S7, all adapter-required.
- `config/strategies.yaml` - disabled-by-default research entries for S5/S6/S7.
- `tests/unit/test_*s5/s6/s7*`, `tests/unit/test_download_binance_data.py`,
  `tests/unit/test_pipeline_batch1_contracts.py`, `tests/unit/test_market_ingest.py`
  - leak, data downloader, funding ingest, and contract coverage.
- `docs/EXPERIMENT_REGISTRY.md`, `docs/KNOWN_ISSUES.md`,
  `docs/FEATURE_MAP.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md` -
  checkpoint state, ownership map, and blockers.
- `results/pipeline_batch1_20260625/**/summary.json` and
  `results/pipeline_batch1_20260625_refit/**/summary.json` - generated
  checkpoint artifacts.

## Behavior delta

- Before: Binance downloader treated all symbols as futures, causing spot
  `BTC-USDT` / `ETH-USDT` downloads to use the wrong endpoint and pagination
  completion rule.
- After: spot symbols use Binance spot klines with a 1000-row page cap; SWAP
  symbols keep futures klines with a 1500-row page cap.
- Before: S5/S6/S7 first-batch strategy scaffolds and summaries were absent.
- After: scaffolds and checkpoint summaries exist, but all strategies remain
  disabled / non-promotable. `ETH-USDT-SWAP` 1m canonical candles and ETH
  funding are loaded. The initial S6 statistical-pass interpretation was
  invalidated by a non-refitting harness defect and superseded by the fold-refit
  artifact: S6 now has `DSR=0.1963`, `PSR=0.7387`,
  `statistical_gate_passed:false`. S7 is shelved after a non-degenerate
  half-life rerun, not refuted by the earlier all-zero no-trade artifact. S5
  reran with ETH factor data but is a data-universe artifact because current
  point-in-time membership plus strict venue-scoped complete-window candle
  coverage produces no grid activity.
- Money/risk impact: no live, demo, shadow, portfolio, risk, order, fill, or
  deployment gate changes. No strategy is ready for live trading.

## Source-of-truth updates

- research/strategy_synthesis.md: unchanged; Claude-owned.
- config/: updated only with disabled research strategy entries.
- ADR: N/A; no promotion, deployment, or major policy change.

## Docs updated (from DOC_IMPACT_MATRIX row)

- [x] `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md` - updated S5/S6/S7
  trial accounting and appended E-014/E-015/E-016 refit/non-degenerate rows.
- [x] `docs/KNOWN_ISSUES.md` - marked the `ETH-USDT-SWAP` data blocker resolved
  and recorded remaining validation-quality gaps.
- [x] `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md` - current-state handoff.
- [x] `docs/DOMAIN_RULES.md` - reviewed; no rule text change.
- [x] `docs/INVARIANTS.md`, `docs/FAILURE_MODES.md` - added I24/F22 for
  fold-refit WF/CPCV evidence and pseudo-OOS full-sample selection.
- [x] `docs/FEATURE_MAP.md` - added S5/S6/S7 pipeline batch 1 ownership entry.
- [x] `docs/DATA_FLOW.md`, `docs/UI_MAP.md` - reviewed; no data-flow/UI map
  change needed beyond this manifest and handoff.

## Invariants / golden cases

- Invariants checked: I13 hidden trials, I21 DSR <= PSR(0), I23 family
  cumulative n_trials; one-day target lag leak tests guard the new runners.
- Golden cases affected: N/A.

## Tests / checks run

- `python -m pytest tests\unit\test_download_binance_data.py tests\unit\test_pipeline_batch1_contracts.py tests\unit\test_s5_residual_meanrev_backtest.py tests\unit\test_s6_ts_momentum_backtest.py tests\unit\test_s7_basis_meanrev_backtest.py -q`
  - 12 passed; pytest emitted a cache write warning for `.pytest_cache`.
- `python -m pytest tests\unit\test_market_ingest.py -q`
  - 11 passed; pytest emitted the same cache write warning.
- `python -B -u scripts\run_pipeline_batch1_checkpoint.py`
  - Wrote updated fold-refit/non-degenerate summaries. S5:
    `results/pipeline_batch1_20260625_refit/s5/summary.json`,
    `nonzero_grid_activity:false`, `status:shelved_data_universe_mismatch`.
    S6: `results/pipeline_batch1_20260625_refit/s6/summary.json`, WF OOS
    Sharpe 0.0088, CPCV OOS Sharpe 0.5422, DSR 0.1963, PSR 0.7387,
    `promotion_gate_passed:false`. S7:
    `results/pipeline_batch1_20260625/s7/summary.json`, WF OOS Sharpe -0.4359,
    CPCV OOS Sharpe -1.1124, DSR/PSR ~0, `status:shelved_pending_research_review`.
- `python scripts/validate_pipeline.py --check-config-only` - PASS
  (`config_thresholds`, `strategy_symbol_overlap`).
- `python scripts/docs/check_doc_metadata.py` - PASS with 18 pre-existing
  metadata warnings.
- `python scripts/docs/check_feature_map_links.py` - PASS.
- `python scripts/docs/check_doc_impact.py --strict` - exited 0 but reported
  "no changed files detected; nothing to verify" in this Windows shell.
- `make check-config` / `make docs-check` - not available directly because
  `make` is not installed in this Windows shell; equivalent Python commands
  above were run.

## Risks and rollback

- Risks: no first-batch candidate has credible promotion evidence. S6 did not
  re-earn the statistical gate on the fold-refit harness, so adapter/ct_val work
  should not start. S7 is shelved pending Claude review after a non-degenerate
  half-life rerun. S5 is a data-universe artifact until membership/canonical
  coverage are reconciled. Local full-window perp parquet pre-screen remains
  unavailable, so checkpoint summaries record DB venue-scoped grid execution
  instead.
- Rollback: revert the listed code/test/config/doc changes and remove generated
  `results/pipeline_batch1_20260625/` summaries. DB spot/perp/funding rows can
  be left in place as source data or explicitly deleted with a separate approved
  data-delete task.

## Approval

- Human approval required before any strategy promotion, demo, shadow, or live
  claim. Not requested or obtained in this session.
