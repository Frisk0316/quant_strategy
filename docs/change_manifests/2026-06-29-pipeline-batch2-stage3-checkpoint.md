---
status: current
type: manifest
owner: codex
created: 2026-06-29
last_reviewed: 2026-06-29
expires: none
superseded_by: null
---

# Change Manifest: Pipeline Batch 2 Stage 2-3 Checkpoint

## Summary

Added research-only C1/C2 vectorized backtest modules, a batch-2 checkpoint
runner, adapter-required validation contracts, and DB-backed checkpoint artifacts
for batch `pipeline_batch2_20260625`. The run stopped at Claude evidence
checkpoint 1; no strategy was promoted or enabled.

## Business rule(s) affected

No rule text changed. Rules reviewed: R3.1 funding sign, R6.1 leakage, R6.3
honest `n_trials`, R7.1 idealized-fill exclusion, R7.4 DSR/PSR gate
interpretation.

## Trigger area(s) (DOC_IMPACT_MATRIX)

A5 backtesting workflow, A9 validation contracts, A11 experiments / research
runs.

## Files changed

- `backtesting/c1_pairs_ou_backtest.py` - research-only rolling BTC/ETH OU pairs
  backtest with one-day target lag and funding cashflow.
- `backtesting/c2_funding_carry_backtest.py` - research-only funding carry plus
  basis-z filter backtest with one-day target lag and funding cashflow.
- `backtesting/differential_validation.py` - adapter-required C1/C2 contract
  entries only.
- `scripts/run_pipeline_batch2_checkpoint.py` - batch-2 checkpoint runner.
- `tests/unit/test_c1_pairs_ou_backtest.py`,
  `tests/unit/test_c2_funding_carry_backtest.py`,
  `tests/unit/test_pipeline_batch2_contracts.py`,
  `tests/unit/test_pipeline_batch2_checkpoint_runner.py` - leak, trial-count,
  contract, and summary-field coverage.
- `results/pipeline_batch2_20260625/**` - C3 Stage-2 fail summary, C2/C1 Stage-3
  checkpoint summaries, and shortlist.
- `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md`,
  `docs/FEATURE_MAP.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`,
  `config/workstreams.yaml` - checkpoint state and ownership updates.
- `tasks/2026-06-29-pipeline-batch2-*.md` - session/context handoffs.

## Behavior delta

- Before: batch-2 C1/C2 research backtest modules and C1/C2 contract entries were
  absent; batch-2 planned rows were unattempted.
- After: C1/C2 research modules and adapter-required contracts exist; C3 fails
  Stage 2 because `fear_greed_btc` has event_count 0; C2 and C1 pass Stage 2 and
  have fold-refit WF/CPCV checkpoint summaries with caller-declared
  family-cumulative `n_trials=24` and CPCV `path_returns` retained. Pass A
  parquet pre-screen is marked skipped because required BTC perp candle/funding
  parquet inputs are missing or incomplete.
- Money/risk impact: none. No live, demo, shadow, risk, portfolio, execution,
  config gate, or strategy-enable behavior changed.

## Source-of-truth updates

- research/strategy_synthesis.md: N/A; Claude-owned and not modified.
- config/: `config/workstreams.yaml` progress text only; no strategy/risk/gate
  config changed.
- ADR: N/A; no result schema, gate policy, or DB schema rule changed.

## Docs updated (from DOC_IMPACT_MATRIX row)

- [x] `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md` - recorded
  Stage-2 PASS/FAIL, runtime rows E-023/E-024/E-025, and trial counts.
- [x] `docs/FEATURE_MAP.md` - added batch-2 ownership map.
- [x] `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md` - current-state handoff.
- [x] `docs/DATA_FLOW.md` - reviewed; no new durable data path beyond the
  existing canonical/funding/external-observation flows.
- [x] `docs/DOMAIN_RULES.md`, `docs/INVARIANTS.md`, ADR-0002/0005/0007 -
  reviewed; no rule text change.

## Invariants / golden cases

- Invariants checked: I4 funding sign, I6/I8 leakage indirectly via one-day
  target-lag tests, I13/I23 honest family trial accounting, I25 CPCV path-return
  retention via runner helper contract.
- Golden cases affected: N/A.

## Tests / checks run

- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_c1_pairs_ou_backtest.py tests\unit\test_c2_funding_carry_backtest.py tests\unit\test_pipeline_batch2_contracts.py tests\unit\test_pipeline_batch2_checkpoint_runner.py -q`
  - 7 passed; pytest cache write warning due `.pytest_cache` permissions.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\run_pipeline_batch2_checkpoint.py`
  - Completed DB-backed checkpoint run and wrote summaries/shortlist.

## Risks and rollback

- Risks: C2's statistical pass is not promotion evidence because portable
  validation is adapter-required/absent; C1/C2 modules are vectorized research
  approximations and not live/replay strategy wiring; Pass A parquet pre-screen
  was skipped for C2/C1 because required local parquet inputs are incomplete; C3
  has no usable sentiment evidence until `fear_greed_btc` exists with coverage.
- Rollback: revert the listed code/test/doc files and remove
  `results/pipeline_batch2_20260625/` if this checkpoint should be discarded.

## Approval

- Human approval required before any strategy promotion, demo, shadow, live, or
  config-gate change. Not requested or obtained in this session.
