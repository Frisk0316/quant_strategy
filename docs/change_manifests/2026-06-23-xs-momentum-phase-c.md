---
status: current
type: manifest
owner: codex
created: 2026-06-23
last_reviewed: 2026-06-23
expires: none
superseded_by: null
---

# Change Manifest: XS Momentum Phase C Research Runner

## Summary

Added the research-only XS momentum vectorized runner and Phase C guardrails:
R3.1 funding cashflow signs, annualized volatility targeting, optional
`market_close` crash-filter wiring, honest grid trial counts, and a DB-backed
smoke artifact that is explicitly not promotion evidence.

## Business rule(s) affected

R3.1, R4.1, R4.3, R6.2, R6.3, R7.1, R7.2. No rule text changed; the code now
implements the existing R3.1 convention for this runner.

## Trigger area(s) (DOC_IMPACT_MATRIX)

A1 strategy/signal logic and A5 backtesting workflow.

## Files changed

- `backtesting/xs_momentum_backtest.py` - add research-only XS momentum
  vectorized backtest runner, funding cashflow, DB input loader, and parameter
  scan summary.
- `src/okx_quant/strategies/xs_momentum.py` - annualize realized volatility
  before applying `vol_target_annual`.
- `tests/unit/test_xs_momentum.py` - guard annualized volatility targeting.
- `tests/unit/test_xs_momentum_backtest.py` - guard short-positive-funding
  cashflow, honest `n_trials`, and `market_close` crash-filter wiring.
- `docs/FEATURE_MAP.md` - record the Phase C runner ownership and limits.
- `docs/DATA_FLOW.md` - record the XS research runner flow and non-promotion
  status.
- `docs/INVARIANTS.md` - attach concrete XS tests to I4 and I13.
- `tasks/2026-06-23-xs-momentum-phase-c-context-handoff.md` - context handoff.
- `tasks/2026-06-23-xs-momentum-phase-c-session-handoff.md` - session handoff.

## Behavior delta

- Before: XS momentum had target-weight helpers and a no-op strategy stub, but
  no vectorized backtest runner, funding cashflow path, or `market_close` crash
  proxy wiring.
- After: local research code can run a funding-aware XS momentum vectorized
  smoke backtest and parameter scan, with `market_close` passed to the existing
  crash regime scaler.
- Money/risk impact: funding sign now affects XS research runner PnL according
  to existing R3.1. No live, demo, shadow, UI/API run path, deployment gate, or
  promotion gate behavior changed.

## Source-of-truth updates

- research/strategy_synthesis.md: N/A, Claude-owned; not touched by Codex.
- config/: unchanged.
- ADR: ADR-0009 reviewed; no update needed because the research-only strategy
  decision and promotion prerequisites remain unchanged.

## Docs updated (from DOC_IMPACT_MATRIX row)

- [x] `docs/FEATURE_MAP.md` - updated for runner ownership and limits.
- [x] `docs/DATA_FLOW.md` - updated for research runner data flow and promotion
  gap.
- [x] `docs/INVARIANTS.md` - updated I4 and I13 enforcing tests.
- [x] `docs/DOMAIN_RULES.md` - reviewed; unchanged because R3.1 already states
  the corrected sign convention.
- [x] `docs/GOLDEN_CASES.md` - reviewed; unchanged because no frozen replay
  golden case was added.
- [x] relevant ADR - ADR-0009 reviewed; unchanged.

## Invariants / golden cases

- Invariants checked: I4, I13, I14, I15, I20.
- Golden cases affected: N/A; smoke artifact is not a frozen golden case.

## Tests / checks run

- `python -m pytest tests/unit/test_xs_momentum.py tests/unit/test_xs_momentum_backtest.py tests/unit/test_universe_membership.py -v` - 13 passed; `.pytest_cache` permission warning only.
- `python scripts/validate_pipeline.py --check-config-only` - PASS
  `config_thresholds` and `strategy_symbol_overlap`.
- Docs checks are recorded in the session handoff.

## Risks and rollback

- Risks: DB-backed smoke has only 22 included Binance symbols, one strict venue
  gap, no WF/CPCV, no DSR/PSR, and crash proxy disabled in the artifact because
  ETH proxy zeroed exposure in this window.
- Rollback: revert this change's code/docs/tests and delete local
  `results/xs_momentum_db_smoke_20260623.json` if the smoke artifact is not
  needed.

## Approval

- Human approval required: yes before treating any XS momentum result as
  promotion, demo, shadow, or live evidence. Not obtained in this session.

## 2026-06-24 Follow-up: Daily Target Lookahead Fix

### Summary

Fixed a daily-to-intraday lookahead leak in the XS momentum research runner.
Daily target weights are now shifted one full day before intraday expansion, so
day-D positions cannot use day-D close information.

### Business rule(s) affected

R5.3, R6.1, R6.3, R7.1, R7.2. No rule text changed.

### Trigger area(s) (DOC_IMPACT_MATRIX)

A5 backtesting workflow and A11 research run/artifact.

### Files changed

- `backtesting/xs_momentum_backtest.py` - shift daily targets by one day before
  intraday expansion.
- `tests/unit/test_xs_momentum_backtest.py` - add regression proving day-D
  positions do not trade on day-D close information; the old one-bar-lag path
  remains profitable on the synthetic panel, so the test bites.
- `results/xs_momentum_validation_20260623/SUPERSEDED.md` - mark leaked
  validation artifact invalid.
- `results/xs_momentum_validation_20260624_leakfix/` - leak-free research
  rerun with `promotion_gate_passed:false` and `status:"review_required"`.
- `docs/DATA_FLOW.md` - record the daily-target lag in the point-in-time
  universe / XS research-runner data flow.
- `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md` - record corrected state and
  non-promotion result.

### Behavior delta

- Before: day-D target weights were built from day-D closes and traded from
  day-D intraday bar 01:00 onward.
- After: day-D positions can only use target weights known through day D-1,
  plus the existing one-bar execution lag.
- Money/risk impact: leaked WF/CPCV performance is invalidated. Leak-free rerun
  has WF combined OOS Sharpe 0.8825, CPCV overall OOS Sharpe 0.5577, DSR 1.0,
  PSR 0.7961, and does not support promotion because PSR is below 0.95.

### Source-of-truth updates

- research/strategy_synthesis.md: N/A, Claude-owned and not permitted for this
  Codex fix.
- config/: unchanged.
- ADR: ADR-0009 reviewed; no update needed because this restores documented
  no-lookahead behavior rather than changing policy.

### Docs updated (from DOC_IMPACT_MATRIX row)

- [x] `docs/DATA_FLOW.md` - updated to document the daily-target lag before
  intraday expansion.
- [x] `docs/FEATURE_MAP.md` - reviewed; unchanged because ownership/scope did
  not change.
- [x] `docs/GOLDEN_CASES.md` - reviewed; unchanged because this regression is
  unit-test scoped, not a frozen accounting golden case.
- [x] ADR-0002 / ADR-0005 / ADR-0009 - reviewed; unchanged because no result
  schema, replay gate, or strategy-family policy changed.
- [x] `docs/AI_HANDOFF.md` and `docs/CURRENT_STATE.md` - updated.

### Invariants / golden cases

- Invariants checked: I8, I13, I14, I15, I20.
- Golden cases affected: N/A.

### Tests / checks run

- `python -m pytest tests/unit/test_xs_momentum_backtest.py::test_daily_close_target_is_not_traded_on_same_day -v` - failed before the fix, then passed after the fix.
- `python -m pytest tests/unit/test_xs_momentum_backtest.py tests/unit/test_xs_momentum.py -v` - 12 passed; pytest cache permission warning only.
- `python scripts/docs/check_doc_impact.py` with process-local `safe.directory`
  git config - passed: 10 changed files, no impact-matrix violations.
- Leak-free DB rerun wrote `results/xs_momentum_validation_20260624_leakfix/`.

### Risks and rollback

- Risks: the validation rerun was reconstructed from the prior inline artifact
  handoff and direct canonical SQL aggregation because no durable rerun script
  exists. It is review-required evidence, not promotion evidence.
- Rollback: revert this follow-up's code/test/docs changes and remove
  `results/xs_momentum_validation_20260624_leakfix/` plus the old artifact's
  `SUPERSEDED.md` if the fix must be backed out.

### Approval

- Human approval required: yes before treating any XS momentum result as
  promotion, demo, shadow, or live evidence. Not obtained in this session.
