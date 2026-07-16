---
status: current
type: manifest
owner: claude
created: 2026-07-15
last_reviewed: 2026-07-15
expires: none
superseded_by: null
---

# Change Manifest: Inverse-perpetual research accounting (H-021 Stage-3 path)

User signed off 2026-07-15 in-session. Governs ADR-0012 and the DOMAIN_RULES
R9 section; no code exists yet — the Stage-3 runner lands under a separate
task after D6/E-055.

## Summary

Adds coin-margined (inverse) perpetual accounting rules — exact 1/P PnL,
USD pair unit, hourly coin funding, unlevered-only margin assumption,
pre-registered cost model, venue-scoped provenance — for research backtests,
currently only H-021.

## Business rule(s) affected

None existing changed (R1–R8 untouched). ADDS DOMAIN_RULES R9.1–R9.6 per
ADR-0012.

## Trigger area(s) (DOC_IMPACT_MATRIX)

A12 (extended to cover coin-margined derivatives research accounting).

## Files changed

- `docs/ADR/0012-inverse-perpetual-research-accounting.md` — decision
- `docs/DOMAIN_RULES.md` — new R9 section
- `docs/INVARIANTS.md` — I44 (golden inverse-perp cycle required)
- `docs/DOC_IMPACT_MATRIX.md` — A12 wording extension
- Planned (separate task, after D6/E-055): H-021 Stage-3 runner + golden test

## Behavior delta

- Before: no inverse-perp accounting exists; H-021 full PnL untestable.
- After: research runners may compute Deribit inverse-perp PnL under R9.
- Money/risk impact: none on any live/engine path (research artifacts only).

## Source-of-truth updates

- research/strategy_synthesis.md: N/A until H-021 survives Stage 3.
- config/: N/A. ADR: ADR-0012 accepted.

## Docs updated (from DOC_IMPACT_MATRIX row)

- [x] DOMAIN_RULES.md (R9) · [x] INVARIANTS.md (I44) · [x] matrix (A12)
- [ ] Golden test — lands with the Stage-3 runner (I44 blocks the grid on it)

## Invariants / golden cases

- New I44; I19/I41/I13/I23 apply unchanged to the future runner.

## Tests / checks run

- Docs checkers (metadata + ledger consistency) — pass. Code tests N/A (docs
  only); golden test required before the Stage-3 grid per I44.

## Risks and rollback

- Risks: unit mixing between R8.1 coin books and R9.2 USD pairs → mitigated
  by the explicit split + I44 golden test; silent leverage creep → R9.4
  restricts the no-margin-model assumption to unlevered bounded-gross books.
- Rollback: revert the four doc sections; ADR-0012 → rejected. No code.

## Approval

- Human approval required: YES — OBTAINED 2026-07-15 in-session ("簽核").
