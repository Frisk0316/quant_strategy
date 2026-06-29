---
status: current
type: manifest
owner: codex
created: 2026-06-25
last_reviewed: 2026-06-25
expires: none
superseded_by: null
---

# Change Manifest: Refitting WF/CPCV Harness

## Summary

Replaced the pipeline checkpoint's full-sample-select-then-slice validation with
fold-local parameter selection for WF/CPCV evidence. S5/S6 were rerun under
`results/pipeline_batch1_20260625_refit/`; S7 was rerun with a non-degenerate
finite half-life grid and left shelved.

## Business rule(s) affected

R6.3 honest trial accounting and R7.4 validation status / promotion-gate
interpretation. No trading, sizing, fee, funding, or live gate behavior changed.

## Trigger area(s) (DOC_IMPACT_MATRIX)

A5 backtesting workflow, A9 validation / gates, A11 experiments / research runs.

## Files changed

- `backtesting/pipeline_refit.py` - pure helper for train-fold combo selection
  and refit WF/CPCV summary generation.
- `scripts/run_pipeline_batch1_checkpoint.py` - uses the refit helper, writes
  S5/S6 `_refit` artifacts, removes unconditional `leak_test_passed:true`, and
  keeps S7 shelved after a non-degenerate half-life rerun.
- `tests/unit/test_pipeline_refit.py`,
  `tests/unit/test_pipeline_batch1_checkpoint_runner.py` - regression coverage
  for train-only selection and non-degenerate CPCV paths.
- `results/pipeline_batch1_20260625_refit/**/summary.json` - S5/S6 refit
  checkpoint artifacts.
- `results/pipeline_batch1_20260625/{s5,s6}/SUPERSEDED.md` - points readers to
  the refit artifacts.
- `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md`,
  `docs/CURRENT_STATE.md`, `docs/AI_HANDOFF.md`, `docs/KNOWN_ISSUES.md` -
  updated interpretation and handoff state.
- `docs/INVARIANTS.md`, `docs/FAILURE_MODES.md` - added I24/F22.

## Behavior delta

- Before: the pipeline checkpoint selected one best parameter combo on the full
  sample and sliced that same return series inside WF/CPCV callbacks, making the
  reported OOS metrics in-sample selection evidence.
- After: each WF/CPCV callback selects the best combo using only `train.index`
  from precomputed causal daily-return series, then returns that combo's
  `test.index` returns. S6 no longer passes the statistical gate; S5 is a
  no-trade/data-universe artifact; S7 is shelved, not refuted from the earlier
  all-zero artifact.
- Money/risk impact: none. No live, demo, shadow, portfolio, risk, order, fill,
  config gate, or deployment behavior changed.

## Source-of-truth updates

- research/strategy_synthesis.md: unchanged; Claude-owned.
- config/: unchanged by this refit harness follow-up.
- ADR: N/A; no major policy change beyond adding I24/F22 guardrails.

## Docs updated (from DOC_IMPACT_MATRIX row)

- [x] `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md` - added
  E-014/E-015/E-016 and corrected H-003/H-004/H-005 interpretation.
- [x] `docs/INVARIANTS.md`, `docs/FAILURE_MODES.md` - added I24/F22.
- [x] `docs/KNOWN_ISSUES.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md` -
  current-state and durable gap updates.
- [x] `docs/DATA_FLOW.md`, `docs/FEATURE_MAP.md`, ADR-0002/0005 - reviewed;
  no additional map/ADR change required for a runner-local validation harness.

## Invariants / golden cases

- Invariants checked: I13, I23, I24.
- Golden cases affected: N/A.

## Tests / checks run

- `python -B -m pytest tests\unit\test_pipeline_refit.py tests\unit\test_pipeline_batch1_checkpoint_runner.py tests\unit\test_pipeline_batch1_contracts.py -q -p no:cacheprovider`
  - 5 passed.
- `python -B -m pytest tests\unit\test_pipeline_refit.py tests\unit\test_pipeline_batch1_checkpoint_runner.py tests\unit\test_pipeline_batch1_contracts.py tests\unit\test_s5_residual_meanrev_backtest.py tests\unit\test_s6_ts_momentum_backtest.py tests\unit\test_s7_basis_meanrev_backtest.py tests\unit\test_download_binance_data.py tests\unit\test_market_ingest.py -q -p no:cacheprovider`
  - 27 passed.
- `python -B -u scripts\run_pipeline_batch1_checkpoint.py`
  - Wrote S5/S6 `_refit` summaries and S7 shelved summary from DB-backed
    Binance canonical data.

## Risks and rollback

- Risks: S5 cannot be interpreted until point-in-time membership and strict
  venue-scoped canonical coverage are reconciled. S7's family trial accounting
  should be reviewed by Claude if the non-degenerate retry is treated as a
  separate retry budget rather than a replacement for an invalid no-trade
  artifact.
- Rollback: revert `backtesting/pipeline_refit.py`,
  `scripts/run_pipeline_batch1_checkpoint.py`, the associated tests/docs, and
  remove `results/pipeline_batch1_20260625_refit/` plus the superseded marker
  files.

## Approval

- Human approval required before any strategy promotion, demo, shadow, or live
  claim. Not requested or obtained in this session.
