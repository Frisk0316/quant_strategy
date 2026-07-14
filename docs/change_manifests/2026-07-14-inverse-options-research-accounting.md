---
status: current
type: manifest
owner: claude
created: 2026-07-14
last_reviewed: 2026-07-14
expires: none
superseded_by: null
---

# Change Manifest: Inverse-options research accounting (H-014 Stage-3)

User signed off 2026-07-14 (ADR-0010 accepted + Stage-3/data-extension/E-051
authorized in one decision). Implementation proceeds under this manifest.

## Summary

Introduce coin-margined (inverse) options accounting — premium, settlement,
fees, and daily marks in BTC/ETH terms — for the H-014 research backtest,
governed by ADR-0010. Research-grade only; no engine/live accounting change.

## Business rule(s) affected

None existing (R1.x/R3.x are perp/spot USDT accounting and are untouched).
ADDS a new DOMAIN_RULES "Options (research)" section registering ADR-0010
rules 1–7 on acceptance.

## Trigger area(s) (DOC_IMPACT_MATRIX)

A5 backtesting (new research runner + validation artifacts); new options
accounting trigger row to be added to the matrix on acceptance.

## Files changed

- `docs/ADR/0010-inverse-options-research-accounting.md` — decision (accepted)
- `docs/DOMAIN_RULES.md` — new "Options (research)" section
- `docs/DOC_IMPACT_MATRIX.md` — new trigger row
- `research/probes/h014_stage3_backtest.py` — research runner (on authorization)
- `research/probes/h014_collect_leg_marks.py` — extension: t+1 entry marks,
  daily M2M marks, official delivery prices
- `docs/EXPERIMENT_REGISTRY.md` / `docs/HYPOTHESIS_LEDGER.md` — E-row + H-014

## Behavior delta

- Before: no options accounting exists anywhere; H-014 evidence is
  probe-level (synthetic pricing + calibration ratios).
- After: a research backtest can compute coin-denominated overlay returns for
  covered calls and put spreads with real traded marks, official delivery
  settlement, and published Deribit fees.
- Money/risk impact: none on any live/demo/engine path (research artifacts
  only). Within research artifacts: PnL unit switches to coin for this family.

## Source-of-truth updates

- research/strategy_synthesis.md: N/A until H-014 survives Stage 3.
- config/: N/A — no strategy/risk/gate config.
- ADR: ADR-0010 (proposed → needs user acceptance).

## Docs updated (from DOC_IMPACT_MATRIX row)

- [ ] DOMAIN_RULES.md — on acceptance
- [ ] DOC_IMPACT_MATRIX.md — on acceptance
- [ ] INVARIANTS.md — candidate new invariant: "coin-denominated options PnL
  uses official delivery prices and bounded-loss structures only" — on
  acceptance
- [x] HYPOTHESIS_LEDGER / EXPERIMENT_REGISTRY — already carry H-014 state

## Invariants / golden cases

- Invariants checked: I13/I23/I25/I27 apply to the Stage-3 run unchanged;
  new candidate invariant above. Golden cases: a hand-computed covered-call
  cycle (entry premium, ITM settlement, fees) will be added as the module's
  golden test before the grid runs.

## Tests / checks run

- None yet (draft). Planned: golden-cycle unit test, leak tests (both
  classes), docs checkers, fresh-verifier pass per MODEL_DISPATCH.

## Risks and rollback

- Risks: mark fallback (BS-on-DVOL offset) could smooth returns → mitigated
  by the 30% fallback cap + reported ratio; tiny cycle count → mitigated by
  the pre-registered daily-tranche construction (see Stage-3 spec); silent
  unit mixing (coin vs USD) → golden test pins units.
- Rollback: delete the research runner + result dir; revert the
  DOMAIN_RULES/matrix sections; ADR-0010 → rejected. No engine surface.

## Approval

- Human approval required: YES — OBTAINED 2026-07-14 in-session ("好, 都簽核"):
  ADR-0010 acceptance and Stage-3 implementation authorization, one decision.
