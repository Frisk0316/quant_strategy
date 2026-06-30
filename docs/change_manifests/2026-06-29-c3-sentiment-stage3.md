---
status: current
type: manifest
owner: codex
created: 2026-06-29
last_reviewed: 2026-06-29
expires: none
superseded_by: null
---

# Change Manifest: C3 Sentiment Stage 3

## Summary
Added the research-only C3 Fear & Greed vectorized Stage-3 backtest path and
fixed the populated external-feature gate timestamp conversion. The run now
produces a real C3 checkpoint artifact instead of stopping after Stage 2.

## Business rule(s) affected
R3.1 funding sign, R6.1 no leakage, R6.3 trial count, R7.1/R7.2/R7.3/R7.4
promotion and validation gates. No rule text changed.

## Trigger area(s) (DOC_IMPACT_MATRIX)
A5 backtesting, A11 experiments / research runs.

## Files changed
- `backtesting/c3_sentiment_backtest.py` - research-only vectorized long/flat C3 runner.
- `scripts/run_pipeline_batch2_checkpoint.py` - C3 Stage-3 wiring and tz-aware gate fix.
- `tests/unit/test_c3_sentiment_backtest.py` - leak, parity, and funding-sign coverage.
- `tests/unit/test_pipeline_batch2_checkpoint_runner.py` - C3 Stage-3 wiring coverage.
- `docs/HYPOTHESIS_LEDGER.md` - H-008 updated to refuted with `n_trials=9`.
- `docs/EXPERIMENT_REGISTRY.md` - E-027 appended.
- `docs/FEATURE_MAP.md` - Pipeline Batch 2 ownership updated for C3 runner/tests.
- `results/pipeline_batch2_20260625/c3_sentiment/summary.json` - regenerated C3 checkpoint output.

## Behavior delta
- Before: C3 could pass Stage 2 only and then wrote `stage2_passed_stage3_not_run`.
- After: C3 runs the pre-registered 9-combo Stage-3 fold-refit WF/CPCV path after Stage-2 PASS.
- Money/risk impact: research-only artifact generation; no live strategy, portfolio,
  risk, execution, sizing, config gate, demo, shadow, or live behavior changed.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A - Claude-owned and no assumptions changed.
- config/: N/A for trading config; `config/workstreams.yaml` updated only for progress state.
- ADR: N/A - restored/implemented documented research workflow; no rule or schema policy changed.

## Docs updated (from DOC_IMPACT_MATRIX row)
- [ ] `docs/DATA_FLOW.md` - confirmed unchanged; no data-path contract changed.
- [ ] `docs/FEATURE_MAP.md` - updated Pipeline Batch 2 files and C3 status.
- [ ] `docs/GOLDEN_CASES.md` - confirmed unchanged; no golden case changed.
- [ ] `docs/INVARIANTS.md` - confirmed unchanged; I4/I23/I25 are covered by tests/artifact fields.
- [ ] ADR-0002/0005 - confirmed unchanged; result schema and replay gates unchanged.
- [ ] `docs/KNOWN_ISSUES.md` - confirmed unchanged; no durable bug class added.
- [ ] `docs/HYPOTHESIS_LEDGER.md` - updated H-008.
- [ ] `docs/EXPERIMENT_REGISTRY.md` - appended E-027.

## Invariants / golden cases
- Invariants checked: I4, I8, I13, I14, I15, I16, I23, I25.
- Golden cases affected: N/A.

## Tests / checks run
- `python -m pytest tests/unit/test_c3_sentiment_backtest.py tests/unit/test_pipeline_batch2_checkpoint_runner.py -q` - passed.
- `python -c "from scripts.run_pipeline_batch2_checkpoint import run_c3; run_c3()"` - wrote C3 Stage-3 summary.

## Risks and rollback
- Risks: vectorized C3 could drift from event-driven hold/exit behavior; guarded by parity test.
- Rollback: revert `backtesting/c3_sentiment_backtest.py`,
  `scripts/run_pipeline_batch2_checkpoint.py`, the two test files, E-027/H-008 doc edits,
  and regenerate/remove `results/pipeline_batch2_20260625/c3_sentiment/summary.json`.

## Approval
- Human approval required: no for research-only Stage-3 checkpoint within task scope;
  yes before any promotion, adapter, demo, shadow, live, or strategy enablement work.
