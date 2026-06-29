---
status: current
type: manifest
owner: codex
created: 2026-06-24
last_reviewed: 2026-06-24
expires: none
superseded_by: null
---

# Change Manifest: DSR Computation Fix

## Summary

Fixed a validation-harness DSR defect where annualized Sharpe values and
overlapping CPCV paths could saturate DSR to 1.0 even when PSR failed.

## Business rule(s) affected

R6.3, R7.4.

## Trigger area(s) (DOC_IMPACT_MATRIX)

A5 backtesting workflow and A9 validation / gates.

## Files changed

- `src/okx_quant/analytics/dsr.py` - compute the DSR z-stat from the return
  series' per-observation Sharpe and scale supplied Sharpe lists onto that basis.
- `backtesting/cpcv.py` - compute DSR over non-overlapping CPCV path returns,
  require supplied `n_trials` for nonzero DSR, and refuse `DSR > PSR(0)`.
- `tests/unit/test_dsr.py`, `tests/unit/test_cpcv.py`,
  `tests/unit/test_backtesting.py` - guard DSR/PSR basis and honest `n_trials`.
- `docs/DOMAIN_RULES.md`, `docs/INVARIANTS.md`, `docs/FAILURE_MODES.md` -
  record the DSR invariant and bug class.
- `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md` - record current blocked state.

## Behavior delta

- Before: CPCV could concatenate overlapping paths and pass annualized Sharpe to
  a per-observation DSR z-stat, producing impossible `DSR=1.0`.
- After: DSR uses the same return-series basis as PSR, non-overlapping path
  samples, and honest `n_trials`; `DSR <= PSR(0)` is enforced.
- Money/risk impact: promotion-gate validation becomes stricter and removes a
  false-positive DSR pass. No PnL, strategy, risk, or execution behavior changed.

## Source-of-truth updates

- research/strategy_synthesis.md: N/A, Claude-owned and not edited.
- config/: unchanged.
- ADR: ADR-0005 reviewed; unchanged because threshold/gate policy did not change.

## Docs updated (from DOC_IMPACT_MATRIX row)

- [x] `docs/DOMAIN_RULES.md` - added R7.4.
- [x] `docs/INVARIANTS.md` - added I21.
- [x] `docs/FAILURE_MODES.md` - added F20.
- [x] `docs/DATA_FLOW.md` / `docs/FEATURE_MAP.md` - reviewed; no DSR data-flow
  ownership change required.
- [x] ADR-0005 - reviewed; unchanged.

## Invariants / golden cases

- Invariants checked: I13, I21.
- Golden cases affected: N/A.

## Tests / checks run

- `python -m pytest tests/unit/test_dsr.py tests/unit/test_cpcv.py -v` - 3 passed.
- `python -m pytest tests/unit/test_dsr.py tests/unit/test_cpcv.py tests/unit/test_backtesting.py tests/unit/test_parameter_sweep.py -v` - 70 passed.
- `python scripts/docs/check_doc_impact.py` with process-local `safe.directory`
  git config - passed: no impact-matrix violations.

## Risks and rollback

- Risks: callers that omit `n_trials` now receive `dsr=0.0` plus a
  `validation.n_trials_missing` flag instead of a fake fallback DSR.
- Rollback: revert `src/okx_quant/analytics/dsr.py`, `backtesting/cpcv.py`, the
  DSR/CPCV tests, and this manifest/doc invariant update.

## Approval

- Human approval required: no for restoring validation correctness; yes before
  treating any strategy artifact as promotion evidence.
