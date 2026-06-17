---
status: current
type: manifest
owner: claude
created: 2026-06-17
last_reviewed: 2026-06-17
expires: none
superseded_by: null
---

# Change Manifest: Multi-venue instrument specifications

> **P0 skeleton.** This manifest records the intended blast radius of the
> multi-venue work decided in [ADR-0007](../ADR/0007-multi-venue-instrument-specs.md).
> Code-level fields (Files changed, Tests run, Approval-obtained) are filled when
> **P1** lands; P0 itself is docs-only.

## Summary
Introduce an `exchange` dimension so the same logical pair can be backtested on
a chosen single venue (Binance/OKX/Bybit) with that venue's correct
`ct_val/lot/tick/min`, via a new `venue_instrument_specs` table, with the
ct_val provenance gate tagged by venue.

## Business rule(s) affected
- R1–R5 (PnL/sizing/accounting): ct_val multiplier resolution becomes
  venue-aware. Values themselves are unchanged in backtest PnL (ct_val cancels
  under notional sizing); the rule change is *provenance*, not accounting.
- R7 (validation/gates): ct_val authoritative source + db_parity become
  venue-scoped.
- Exact sub-ids to be confirmed against `docs/DOMAIN_RULES.md` when P1 edits it.

## Trigger area(s) (DOC_IMPACT_MATRIX)
A6 (DB schema — Manifest + ADR), A9 (validation gate — Manifest + ADR), A2
(portfolio/execution read path), A5 (backtesting/replay resolution), A7 (API
request gains `exchange`), A8 (frontend venue selector), A4 (config default/
allowed exchanges).

## Files changed
- P0 (this change): `docs/ADR/0007-multi-venue-instrument-specs.md` (added),
  `docs/ADR/README.md` (index row), this manifest (added).
- P1 (planned, to be enumerated by writing-plans): `sql/` migration (new
  `venue_instrument_specs` table), `backtesting/replay.py` (venue-aware ct_val
  resolution + run `exchange`), `backtesting/differential_validation.py` (venue
  tag on provenance/source-data block), `config/settings.yaml`
  (default/allowed exchanges), `src/okx_quant/api/routes_backtest.py` (request
  `exchange`), `frontend/` (venue selector), symbol-mapping module, tests.

## Behavior delta
- Before: ct_val resolves single-venue (DB `instruments.contract_value` →
  OKX-labelled registry); provenance is venue-blind.
- After: ct_val resolves per `(exchange, symbol)`; a run is single-venue and its
  provenance PASS attests the venue.
- Money/risk impact: **none in backtest PnL** (ct_val cancels under notional
  sizing). Impact is at live execution and in which runs can pass the
  live-readiness provenance gate. Per-venue fee/funding divergence is deferred
  to P2 and out of this manifest.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A for P0; P1 should note the venue/contract
  assumption and the cross-venue convergence expectation.
- config/: N/A for P0; P1 adds default/allowed `exchange`.
- ADR: ADR-0007 added (Proposed).

## Docs updated (from DOC_IMPACT_MATRIX row)
- [ ] `docs/DATA_FLOW.md` — P1 (new table + venue in resolution path)
- [ ] `docs/DOMAIN_RULES.md` — P1 (venue-aware ct_val provenance rule)
- [ ] `docs/FEATURE_MAP.md` — P1 (venue selection ownership)
- [ ] `docs/INVARIANTS.md` — P1 (per-venue ct_val authoritative invariant)
- [ ] `docs/ai_collaboration.md` — P1 (ct_val gate venue tagging)
- [ ] `docs/UI_MAP.md` — P1 (frontend venue selector)
- [ ] `docs/KNOWN_ISSUES.md` — P1 (close registry-only ct_val provenance gap)
- [x] `docs/ADR/README.md` — P0, index row added

## Invariants / golden cases
- Invariants checked: P1 to add "ct_val authoritative source must match the
  run's execution venue".
- Golden cases affected: P1 to add cross-venue convergence case (same
  strategy/params, Binance vs OKX → identical metrics modulo lot-rounding).

## Tests / checks run
- P0: docs-only; `make docs-impact` / `make docs-check` to confirm ADR + manifest
  satisfy the gate. (run before commit)
- P1: replay venue-resolution unit tests, provenance-gate venue-tag tests,
  convergence golden case, plus existing differential/source-provenance suites.

## Risks and rollback
- Risks: provenance field shape drifting from the gate if P1 splits across
  sessions (ADR-0007 forbids this); seeding a wrong per-venue ct_val (mitigated
  by db_parity + authoritative source requirement); accidentally repurposing
  `instruments` instead of the new table.
- Rollback: P0 is additive docs — delete the two files and the index row. P1
  rollback restores single-venue resolution (additive table/resolver).

## Approval
- Human approval required: **yes** — ADR-0007 is Proposed; P1 implementation
  must not start until the user approves and a permitted-files task is issued.
  Obtained? Not yet.
