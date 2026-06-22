---
status: current
type: manifest
owner: codex
created: 2026-06-22
last_reviewed: 2026-06-22
expires: none
superseded_by: null
---

# Change Manifest: Reduce-only fat-finger bypass

## Summary
Reduce-only close orders can now bypass the single-order fat-finger cap only up
to current position notional. This lets valid exits close after price movement
without allowing exposure-increasing orders to exceed configured caps.

## Business rule(s) affected
R4.2, R4.3.

## Trigger area(s) (DOC_IMPACT_MATRIX)
A3 risk/config semantics.

## Files changed
- `src/okx_quant/risk/risk_guard.py` — allow bounded reduce-only fat-finger bypass.
- `tests/unit/test_risk_guard.py` — regression tests for allowed close and oversized close block.
- `docs/DOMAIN_RULES.md` — record bounded reduce-only exception.
- `docs/INVARIANTS.md` — update I6/I7 wording and enforcement.
- `docs/ADR/0006-reduce-only-risk-semantics.md` — update reduce-only decision.
- `docs/FAILURE_MODES.md` — add close-blocked-by-entry-cap failure mode.

## Behavior delta
- Before: any order above `max_order_notional_usd`, including reduce-only closes,
  was blocked as `fat_finger`.
- After: reduce-only closes above `max_order_notional_usd` pass only when
  notional is less than or equal to current position notional.
- Money/risk impact: closing risk is easier; exposure-increasing orders remain
  capped.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A — no strategy assumption change.
- config/: N/A — thresholds unchanged.
- ADR: `docs/ADR/0006-reduce-only-risk-semantics.md` updated.

## Docs updated (from DOC_IMPACT_MATRIX row)
- [x] `docs/DOMAIN_RULES.md` — updated R4.2/R4.3.
- [x] `docs/INVARIANTS.md` — updated I6/I7.
- [x] `docs/ai_collaboration.md` — confirmed unchanged; deployment gates unchanged.
- [x] relevant ADR — ADR-0006 updated.

## Invariants / golden cases
- Invariants checked: I6, I7.
- Golden cases affected: N/A.

## Tests / checks run
- `python -m pytest tests/unit/test_risk_guard.py -q` — passed.

## Risks and rollback
- Risks: a wrong current-position notional could allow too-large reduce-only
  orders; callers must pass current position notional correctly.
- Rollback: revert `src/okx_quant/risk/risk_guard.py`, the risk tests, and the
  listed docs.

## Approval
- Human approval required: yes — user explicitly requested the modification on
  2026-06-22.
