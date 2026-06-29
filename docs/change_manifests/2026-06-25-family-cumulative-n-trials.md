---
status: current
type: manifest
owner: codex
created: 2026-06-25
last_reviewed: 2026-06-25
expires: none
superseded_by: null
---

# Change Manifest: Family-Cumulative n_trials

## Summary

Candidate scans now support family-cumulative `n_trials`, so future CPCV/DSR
evaluation can include prior attempts in the same hypothesis family rather than
only the current run's grid size.

## Business rule(s) affected

R6.3, R7.4.

## Trigger area(s) (DOC_IMPACT_MATRIX)

A5 backtesting workflow, A9 validation / gates, A11 experiments / research runs.

## Files changed

- `backtesting/xs_momentum_backtest.py` - add `prior_family_n_trials` to the
  scan and record `prior + len(grid)` in both rows and attrs.
- `tests/unit/test_xs_momentum_backtest.py` - regression for prior family trials
  plus backward-compatible 16-combo behavior.
- `docs/EXPERIMENT_REGISTRY.md` - record `family_id` and family trial accounting.
- `docs/HYPOTHESIS_LEDGER.md` - record family IDs and cumulative trial counts.
- `docs/INVARIANTS.md` - add I23 for family-cumulative CPCV trial counts.
- `docs/FEATURE_MAP.md` - record the XS momentum scan's family-cumulative trial
  count behavior.
- `docs/superpowers/pipeline/*.md` - document the manual Stage 1 driver and
  templates that pass family counts into Stage 3.
- `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`,
  `research/strategy_synthesis.md` - register the Stage 1 machinery.

## Behavior delta

- Before: `scan_xs_momentum` reported only `len(grid)` for `n_trials`, so a retry
  in the same family could understate DSR's multiple-trial penalty.
- After: callers can pass `prior_family_n_trials`; scan outputs report
  `prior_family_n_trials + len(grid)`.
- Money/risk impact: no live, demo, shadow, portfolio, risk, fill, or artifact
  value changes. Future research validation becomes more conservative when a
  family has prior trials.

## Source-of-truth updates

- research/strategy_synthesis.md: updated with the Stage 1 first-batch note.
- config/: unchanged.
- ADR: N/A; this operationalizes existing R6.3/R7.4 trial honesty, without
  changing the promotion-gate policy.

## Docs updated (from DOC_IMPACT_MATRIX row)

- [x] `docs/INVARIANTS.md` - added I23.
- [x] `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md` - added family
  trial accounting.
- [x] `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md` - current-state registration.
- [x] `research/strategy_synthesis.md` - first-batch backlog note.
- [x] `docs/FEATURE_MAP.md` - updated XS momentum runner behavior.
- [x] `docs/DATA_FLOW.md` - confirmed unchanged; no data path changed.
- [x] ADR-0005/ADR-0009 - confirmed unchanged; policy already requires honest
  `n_trials`, and this is a source/passthrough fix.

## Invariants / golden cases

- Invariants checked: I13, I21, I23.
- Golden cases affected: N/A.

## Tests / checks run

- `python -m pytest tests/unit/test_xs_momentum_backtest.py::test_scan_adds_prior_family_trials_to_n_trials -v` - failed before implementation with unexpected keyword argument.
- `python -m pytest tests/unit/test_xs_momentum_backtest.py -v` - passed.
- `python scripts/docs/check_doc_impact.py` - pending final verification.

## Risks and rollback

- Risks: callers that pass stale prior-family counts will still undercount. The
  Stage 1 driver docs make the ledger lookup explicit, but Stage 2 can add a
  machine-readable validator if manual review proves too brittle.
- Rollback: revert `backtesting/xs_momentum_backtest.py`, the unit test, and the
  docs listed above. No result artifacts require migration.

## Approval

- Human approval required: yes before treating any strategy as promotion, demo,
  shadow, or live evidence. Not requested or obtained in this session.
