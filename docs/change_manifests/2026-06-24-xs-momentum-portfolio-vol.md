---
status: current
type: manifest
owner: codex
created: 2026-06-24
last_reviewed: 2026-06-24
expires: none
superseded_by: null
---

# Change Manifest: XS Momentum Portfolio Vol Targeting

## Summary

Changed XS momentum sizing from median single-name vol targeting to estimated
portfolio book-vol targeting with an explicit max gross-leverage cap.

## Business rule(s) affected

R4.4, R6.3, R7.1, R7.2, R7.3.

## Trigger area(s) (DOC_IMPACT_MATRIX)

A1 strategy implementation, A5 backtesting workflow, A11 research run/artifact.

## Files changed

- `src/okx_quant/strategies/xs_momentum.py` - size gross from diagonal estimated
  book vol and cap gross at `MAX_GROSS_LEVERAGE = 2.0`.
- `tests/unit/test_xs_momentum.py` - guard book-vol sizing and cap behavior.
- `tests/unit/test_xs_momentum_backtest.py` - keep the lookahead regression
  biting under the new sizing.
- `results/xs_momentum_validation_20260624_portfoliovol/` - correctness-only
  WF/CPCV rerun artifact.
- `docs/DOMAIN_RULES.md`, `docs/INVARIANTS.md`, `docs/FAILURE_MODES.md`,
  `docs/ADR/0009-xs-momentum-research-strategy.md`, `docs/DATA_FLOW.md`,
  `docs/FEATURE_MAP.md`, `docs/HYPOTHESIS_LEDGER.md`,
  `docs/EXPERIMENT_REGISTRY.md`, `docs/AI_HANDOFF.md`,
  `docs/CURRENT_STATE.md` - record rule, invariant, artifact, and blocked state.

## Behavior delta

- Before: XS momentum gross was sized by median constituent annual vol and capped
  at 1.0, under-levering the diversified market-neutral book.
- After: gross is sized from estimated book vol using current long/short weights
  and constituent realized vols, capped at 2.0, then crash-regime scaling and
  per-name caps still apply.
- Money/risk impact: strategy sizing changes for research artifacts only;
  `xs_momentum` remains disabled and `on_market()` remains no-op.

## Source-of-truth updates

- research/strategy_synthesis.md: N/A, Claude-owned and not edited.
- config/: unchanged; `xs_momentum.enabled` remains false.
- ADR: ADR-0009 updated to record portfolio-vol targeting and max-gross cap.

## Docs updated (from DOC_IMPACT_MATRIX row)

- [x] `docs/DOMAIN_RULES.md` - added R4.4.
- [x] `docs/INVARIANTS.md` - added I22.
- [x] `docs/FAILURE_MODES.md` - added F21.
- [x] `docs/FEATURE_MAP.md` - updated XS momentum behavior/docs list.
- [x] `docs/DATA_FLOW.md` - updated XS research-runner data flow.
- [x] `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md` - recorded
  E-004/E-005 and refuted H-002 under current evidence.
- [x] ADR-0009 - updated.

## Invariants / golden cases

- Invariants checked: I4, I8, I13, I15, I20, I21, I22.
- Golden cases affected: N/A.

## Tests / checks run

- `python -m pytest tests/unit/test_xs_momentum.py tests/unit/test_xs_momentum_backtest.py -v` - 12 passed.
- `python scripts/docs/check_doc_impact.py` with process-local `safe.directory`
  git config - passed: no impact-matrix violations.
- `make docs-impact` - not run; `make` is unavailable in this Windows shell.
- Correctness-only rerun wrote `results/xs_momentum_validation_20260624_portfoliovol/`:
  WF OOS Sharpe 1.2412, CPCV OOS Sharpe 0.6027, DSR 0.7823, PSR 0.8234,
  `promotion_gate_passed:false`, `status:"review_required"`.

## Risks and rollback

- Risks: diagonal book-vol ignores covariance and the 2.0 max-gross/per-name caps
  mean realized vol can remain below target in constrained regimes.
- Rollback: revert `src/okx_quant/strategies/xs_momentum.py`, related tests/docs,
  and remove `results/xs_momentum_validation_20260624_portfoliovol/`.

## Approval

- Human approval required: yes before treating any XS momentum result as
  promotion, demo, shadow, or live evidence. Not obtained in this session.
