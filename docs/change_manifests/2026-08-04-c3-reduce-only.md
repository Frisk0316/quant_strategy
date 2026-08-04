---
status: current
type: manifest
owner: codex
created: 2026-08-04
last_reviewed: 2026-08-04
expires: none
superseded_by: null
---

# Change Manifest: C3 OKX reduce-only propagation

## Summary
OKX orders admitted as reduce-only now send the matching venue `reduceOnly=true` and `posSide` fields.

## Business rule(s) affected
R4.2.

## Trigger area(s) (DOC_IMPACT_MATRIX)
A2 execution.

## Files changed
- `src/okx_quant/execution/broker.py` — propagate reduce-only venue kwargs.
- `src/okx_quant/execution/order_manager.py` — preserve `OrderPayload.pos_side` at the broker boundary.
- `tests/unit/test_wsc_trade_safety.py` — bind RiskGuard admission through OrderManager to the captured OKX request.
- `docs/DOMAIN_RULES.md`, `docs/INVARIANTS.md`, `docs/FAILURE_MODES.md` — strengthen R4.2 and add I70/F73.

## Behavior delta
- Before: RiskGuard could admit a reduce-only close, but the OKX request omitted the constraint.
- After: admitted reduce-only orders reach OKX with `reduceOnly=true` and the unchanged `OrderPayload.pos_side` value.
- Money/risk impact: prevents an intended close from opening or flipping venue exposure after local risk bypass.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A — no strategy assumption changed.
- config/: N/A — no threshold or mode changed.
- ADR: ADR-0006 confirmed unchanged; this enforces its accepted semantics at the venue boundary.

## Docs updated (from DOC_IMPACT_MATRIX row)
- [x] `docs/DOMAIN_RULES.md` — strengthened R4.2.
- [x] `docs/INVARIANTS.md` — added I70.
- [x] `docs/FAILURE_MODES.md` — added F73.
- [x] Relevant ADR — ADR-0006 reviewed and unchanged.

## Invariants / golden cases
- Invariants checked: I7, I70.
- Golden cases affected: N/A — no PnL formula changed.

## Tests / checks run
- Combined C3/C5 targeted selection (`instrument or ct_val or reduce_only`) — 8 passed, 1 deselected.
- Prior dedicated-commit baseline, `python -m pytest tests/unit -q` — 1133 passed, 1 skipped.
- `ruff check src/okx_quant/engine.py src/okx_quant/execution/order_manager.py tests/unit/test_wsc_trade_safety.py` — passed.
- `python scripts/docs/check_doc_impact.py --strict` — passed.

## Risks and rollback
- Risks: incorrect position-mode metadata can cause venue rejection; the venue now receives the caller's explicit position side instead of an implicit default.
- Rollback: revert the dedicated C3 commit.

## Approval
- Human approval required: yes — obtained 2026-08-04 for WS-C C3.
