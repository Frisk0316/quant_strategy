---
status: current
type: manifest
owner: codex
created: 2026-07-12
last_reviewed: 2026-07-12
expires: none
superseded_by: null
---

# Change Manifest: ct_val validation contract

## Summary

Reconcile the shared `ct_val` validator with accepted multi-venue multiplier
metadata while rejecting NaN, infinity, non-positive values and corruption.

## Design-space decision

- Keep `<=1` rejects valid venue contracts.
- Venue-specific dynamic bounds duplicate the existing provenance contract.
- Chosen: accept finite `0 < ct_val <= 1e7`; the fixed cap provides 10x headroom
  over the largest known `1e6` contract without new machinery.

## Business rule(s) affected

R1.5 numeric value-integrity rule changed. R1.2 formulas and R1.4 provenance
were reviewed and remain unchanged.

## Trigger area(s) (DOC_IMPACT_MATRIX)

A2 portfolio/sizing.

## Files changed

- `src/okx_quant/portfolio/sizing.py` — shared validator only.
- `tests/unit/test_sizing.py` — multiplier and invalid-boundary regressions.
- `docs/ADR/0003-position-pnl-accounting.md` — dated contract amendment.
- `docs/DOMAIN_RULES.md`, `docs/INVARIANTS.md`, `docs/FAILURE_MODES.md` — rule,
  I34 and F32 closure.
- `docs/change_manifests/2026-07-12-ct-val-validation-contract.md` — this audit
  record.

## Behavior delta

- Before: finite metadata multipliers above 1 were rejected; NaN was accepted.
- After: finite positive multipliers through `1e7` are accepted; zero, negative,
  NaN, infinity and values above `1e7` are rejected.
- Money/risk impact: formulas and previously accepted values are unchanged;
  configured XRP/ADA/DOGE/SHIB-style multipliers can now use existing formulas.
  Numeric acceptance alone does not establish promotion-grade provenance.

## Source-of-truth updates

- research/strategy_synthesis.md: N/A — no strategy assumption changed.
- config/: reviewed unchanged; current maximum metadata value is `1e6`.
- ADR: ADR-0003 amended; ADR-0007 reviewed unchanged.

## Docs updated (from DOC_IMPACT_MATRIX row)

- [x] `docs/DOMAIN_RULES.md` — R1.5 added.
- [x] `docs/INVARIANTS.md` / `docs/FAILURE_MODES.md` — I34/F32 enforced.
- [x] ADR-0003 — obsolete `<=1` statement superseded by dated amendment.
- [x] `docs/FEATURE_MAP.md` / `docs/DATA_FLOW.md` — reviewed unchanged; ownership
  and metadata flow did not move.

## Invariants / golden cases

- Invariants checked: I1, I16, I34.
- Golden cases affected: G-001 remains unchanged; valid multipliers still enter
  the same linear formulas.

## Tests / checks run

- Targeted sizing/execution/PnL/ct_val/OI/replay suite: `79 passed`; final P0
  target suite: `306 passed, 1 skipped`.
- Full unit `768 passed, 1 skipped`; integration `38 passed`; full Ruff,
  docs/config/backtest-smoke passed. Details:
  `tasks/2026-07-12-p0-implementation-session-handoff.md`.

## Risks and rollback

- Risks: corrupt but finite values below the cap still depend on R1.4 provenance.
- Rollback: restore the previous helper/tests/docs; no data or artifact migration.

## Approval

- Human approval required: yes — the user ratified the Claude-proposed `1e7` cap
  by requesting implementation on 2026-07-12.
