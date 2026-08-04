---
status: current
type: manifest
owner: codex
created: 2026-08-04
last_reviewed: 2026-08-04
expires: none
superseded_by: null
---

# Change Manifest: C5 runtime ct_val fail closed

## Summary
Runtime startup now rejects unavailable or incomplete venue instrument metadata instead of fabricating a BTC/ETH SWAP multiplier.

## Business rule(s) affected
R1.2, R1.5, R1.6.

## Trigger area(s) (DOC_IMPACT_MATRIX)
A2 portfolio/execution and A7 API/runtime orchestration.

## Files changed
- `src/okx_quant/engine.py` — require complete retrieved specs and validate SWAP `ct_val` with the shared validator. This is the relocated owner of the task's stale `src/okx_quant/api/engine.py` path.
- `src/okx_quant/portfolio/portfolio_manager.py` — remove BTC/ETH SWAP fallback.
- `tests/unit/test_wsc_trade_safety.py` — guard startup and ETH missing-spec failure.
- `docs/DOMAIN_RULES.md`, `docs/INVARIANTS.md`, `docs/FAILURE_MODES.md` — record R1.6/I69/F72.

## Behavior delta
- Before: instrument lookup failure fabricated `ctVal=0.01`; missing BTC/ETH SWAP specs could do the same during sizing.
- After: missing or incomplete configured-symbol specs stop startup, and missing SWAP `ct_val` stops sizing.
- Money/risk impact: prevents 10x ETH contract-quantity and notional errors.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A — no strategy assumption changed.
- config/: N/A — no parameter or mode changed.
- ADR: ADR-0003 and ADR-0007 confirmed unchanged; this enforces their existing metadata/provenance decisions.

## Docs updated (from DOC_IMPACT_MATRIX row)
- [x] `docs/DOMAIN_RULES.md` — added R1.6.
- [x] `docs/INVARIANTS.md` — added I69.
- [x] `docs/FAILURE_MODES.md` — added F72.
- [x] `docs/FEATURE_MAP.md` — confirmed unchanged; ownership paths are already represented by the deployment-gate/runtime surface.
- [x] `docs/UI_MAP.md` — confirmed unchanged; no API or UI schema changed.
- [x] `docs/DATA_FLOW.md` — confirmed unchanged; no data/artifact path changed.

## Invariants / golden cases
- Invariants checked: I34, I69.
- Golden cases affected: N/A — no accounting formula changed.

## Tests / checks run
- `python -m pytest tests/unit/test_wsc_trade_safety.py -k "instrument or ct_val" -v` — 5 passed.
- `python -m pytest tests/unit -q` — 1131 passed, 1 skipped.
- `ruff check src/okx_quant/engine.py src/okx_quant/portfolio/portfolio_manager.py tests/unit/test_wsc_trade_safety.py` — passed.
- `python scripts/docs/check_doc_impact.py --strict` — passed.

## Risks and rollback
- Risks: a venue metadata outage now prevents startup instead of using guessed quantities; this is the intended fail-closed direction.
- Rollback: revert the dedicated C5 commit.

## Approval
- Human approval required: yes — obtained 2026-08-04 for WS-C C5.
