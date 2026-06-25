# Session Handoff: Pipeline Batch 1 Stage 3 2026-06-25

## Implementation summary
Completed the S7 Binance spot canonical data gate, loaded missing
`ETH-USDT-SWAP` 1m canonical OHLCV and ETH funding, implemented research-only
S5/S6/S7 strategy/backtest scaffolding, replaced the defective
full-sample-select-then-slice checkpoint harness with fold-refit WF/CPCV
selection, emitted S5/S6 `_refit` summaries, and reran S7 with a non-degenerate
finite half-life grid.

## Diff scope
- Files added: S5/S6/S7 strategy modules, S5/S6/S7 backtest runners,
  `backtesting/pipeline_refit.py`, reproducible checkpoint runner, unit tests,
  pipeline batch 1 + refit Change Manifests, context/session handoffs, S5/S6
  superseded markers.
- Files changed: `scripts/download_binance_data.py`, `scripts/_db_writer.py`,
  `scripts/market_data/ingest.py`,
  `backtesting/differential_validation.py`, `config/strategies.yaml`,
  `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md`,
  `docs/KNOWN_ISSUES.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`,
  `docs/INVARIANTS.md`, `docs/FAILURE_MODES.md`.
- Files deleted: none.

## Business-rule change?
- Yes. Change Manifests at
  `docs/change_manifests/2026-06-25-pipeline-batch1-stage3.md` and
  `docs/change_manifests/2026-06-25-refitting-wf-cpcv-harness.md`; DOC impact
  rows A1, A4, A5, A9, A11 checked in the manifests.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A; Claude-owned and not modified.
- config/: updated with disabled S5/S6/S7 research entries only.
- ADR: N/A.

## Experiments
- HYPOTHESIS_LEDGER entries: H-003 marked shelved, H-004 inconclusive/data
  artifact, H-005 inconclusive after refit statistical failure.
- EXPERIMENT_REGISTRY entries: E-009, E-010, E-011 added earlier; E-012/E-013
  appended after data repair; E-014/E-015/E-016 appended after refit and
  non-degenerate reruns.

## Tests / checks run
- Coverage probes -> passed: BTC/ETH perps and BTC/ETH spot each have 1,293,120
  Binance canonical 1m rows and 0 gaps; BTC/ETH perp funding each has 2,694 rows
  and no >8h05m large gaps.
- `python -m pytest tests\unit\test_market_ingest.py -q`
  -> 11 passed; pytest cache write warning only.
- `python -m pytest tests\unit\test_download_binance_data.py tests\unit\test_pipeline_batch1_contracts.py tests\unit\test_s5_residual_meanrev_backtest.py tests\unit\test_s6_ts_momentum_backtest.py tests\unit\test_s7_basis_meanrev_backtest.py -q`
  -> 12 passed; pytest cache write warning only.
- `python -B -m pytest tests\unit\test_pipeline_refit.py tests\unit\test_pipeline_batch1_checkpoint_runner.py tests\unit\test_pipeline_batch1_contracts.py -q -p no:cacheprovider`
  -> 5 passed.
- `python -B -m pytest tests\unit\test_pipeline_refit.py tests\unit\test_pipeline_batch1_checkpoint_runner.py tests\unit\test_pipeline_batch1_contracts.py tests\unit\test_s5_residual_meanrev_backtest.py tests\unit\test_s6_ts_momentum_backtest.py tests\unit\test_s7_basis_meanrev_backtest.py tests\unit\test_download_binance_data.py tests\unit\test_market_ingest.py -q -p no:cacheprovider`
  -> 27 passed.
- `python -B -u scripts\run_pipeline_batch1_checkpoint.py`
  -> S5 `_refit` summary: status `shelved_data_universe_mismatch`,
  `nonzero_grid_activity:false`, DSR/PSR 0.0. S6 `_refit` summary: WF OOS
  Sharpe 0.0088, CPCV OOS Sharpe 0.5422, DSR 0.1963, PSR 0.7387,
  `statistical_gate_passed:false`, `promotion_gate_passed:false`. S7 summary:
  WF OOS Sharpe -0.4359, CPCV OOS Sharpe -1.1124, DSR/PSR ~0,
  `status:shelved_pending_research_review`.
- `python scripts/validate_pipeline.py --check-config-only` -> PASS.
- `python scripts/docs/check_doc_metadata.py` -> PASS with 18 pre-existing
  metadata warnings.
- `python scripts/docs/check_feature_map_links.py` -> PASS.
- `python scripts/docs/check_doc_impact.py --strict` -> exited 0 but reported
  no changed files detected.
- `make check-config` / `make docs-check` -> not run directly because `make` is
  unavailable in this Windows shell; equivalent Python commands were run.

## Docs updated
- `docs/EXPERIMENT_REGISTRY.md`
- `docs/HYPOTHESIS_LEDGER.md`
- `docs/KNOWN_ISSUES.md`
- `docs/FEATURE_MAP.md`
- `docs/AI_HANDOFF.md`
- `docs/CURRENT_STATE.md`
- `docs/change_manifests/2026-06-25-pipeline-batch1-stage3.md`
- `docs/change_manifests/2026-06-25-refitting-wf-cpcv-harness.md`
- `tasks/2026-06-25-pipeline-batch1-stage3-context-handoff.md`

## Known limitations / risks
- S6 did not re-earn the statistical gate on the fold-refit harness; do not
  start adapter/ct_val work for it.
- S7 is shelved after the non-degenerate half-life rerun; Claude should review
  whether the invalid no-trade attempt counts toward future family n_trials.
- S5 is a data-universe artifact until point-in-time membership and strict
  venue-scoped canonical coverage are reconciled.
- Local full-window perp parquet pre-screen is unavailable; generated summaries
  record this blocker and use DB-derived checkpoint evidence where possible.
- No promotion evidence exists.

## Rollback plan
- Revert code/config/doc/test changes from this session and remove generated
  `results/pipeline_batch1_20260625/` summaries. Leave DB spot/perp/funding rows
  in place as source data unless a separate approved data-delete task requests
  removal.

## Context Handoff
- See tasks/CONTEXT_HANDOFF_TEMPLATE.md filled at:
  `tasks/2026-06-25-pipeline-batch1-stage3-context-handoff.md`.

## Questions for human review
- Should Stage 3 allow DB-derived pre-screen when local full-window parquet is
  incomplete, or should we build the parquet cache first?
- Should Claude review S6 for portable-adapter investment, or reject/defer it
  despite statistical pass because validation gates remain incomplete?

## Next recommended task
- Claude evidence review for S5/S6/S7 refit/non-degenerate artifacts; decide S5
  universe policy and S7 family retry accounting. Do not start S6 portable
  validation unless a future refit run passes DSR/PSR.

## Human Learning Notes (required)
The raw data gap moved from missing spot to missing perp, then was resolved by
loading `ETH-USDT-SWAP` and ETH funding. The more important blocker turned out
to be validation quality: a full-sample-selected return path can look like OOS
evidence until the harness forces per-fold selection. Local parquet cache also
should not be assumed to mirror canonical DB coverage.
