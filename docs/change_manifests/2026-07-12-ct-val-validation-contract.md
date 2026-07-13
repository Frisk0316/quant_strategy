---
status: current
type: manifest
owner: codex
created: 2026-07-12
last_reviewed: 2026-07-13
expires: none
superseded_by: null
---

# Change Manifest: ct_val validation contract

## Summary

Reconcile the shared `ct_val` validator with accepted multi-venue multiplier
metadata while rejecting NaN, infinity, non-positive values and corruption.

## Design-space decision

- Keeping `<=1` rejects valid venue contracts.
- Venue-specific dynamic bounds duplicate the existing provenance contract.
- Chosen: accept finite `0 < ct_val <= 1e7`; the fixed cap provides 10x
  headroom over the largest known `1e6` contract without new machinery.

## Business rule(s) affected

R1.5 numeric value-integrity enforcement changed. R1.2 formulas and R1.4
provenance were reviewed and remain unchanged.

## Trigger area(s) (DOC_IMPACT_MATRIX)

A2 portfolio/sizing, A5 backtesting/replay, and A9 validation/gates.

## Files changed

- `src/okx_quant/portfolio/sizing.py` — shared validator only.
- `src/okx_quant/portfolio/positions.py` — validate before mutating ledger
  state and validate the existing-position fallback.
- `backtesting/replay.py` — validate DB, registry, and caller-supplied
  multipliers before assigning provenance.
- `tests/unit/test_sizing.py`, `tests/unit/test_position_pnl_accounting.py`,
  `tests/unit/test_backtesting.py`, and
  `tests/unit/test_replay_ct_val_resolution.py` — boundary and atomicity
  regressions.
- `docs/ADR/0003-position-pnl-accounting.md` — dated contract amendment.
- `docs/DOMAIN_RULES.md`, `docs/INVARIANTS.md`, `docs/FAILURE_MODES.md`, and
  `docs/DATA_FLOW.md` — rule, invariant, failure-mode, and flow closure.

## Addendum 2026-07-13 (Codex PR #9 follow-up repair)

The first review addendum closed only two call sites. Follow-up review found
the same contract still bypassed at DB/registry resolution, malformed caller
specs, and the order of ledger mutation. The complete closure is:

- `src/okx_quant/portfolio/positions.py` routes every explicitly provided
  multiplier through `validate_ct_val()`; only a truly absent fill value can
  reuse the position's already-validated value or the existing fallback.
- `PositionLedger.on_fill()` resolves and validates `ct_val` before inserting a
  new `Position`. A rejected fill therefore leaves positions, trade log, and
  equity unchanged; an existing-position fallback is validated too.
- `backtesting/replay.py` validates caller-supplied `instrument_specs` before
  assigning `config_override` provenance. DB loader/resolver and registry
  values use the same validator; an invalid explicit DB value raises and is
  never silently replaced by another source.
- Caller specs must be mappings with a present, non-`None`, valid `ctVal`; the
  normalized numeric value is stored before provenance is attached.
- Regressions cover invalid DB/registry/caller values, malformed caller specs,
  normalized values, provenance, and ledger atomicity. No PnL formula changed.

## Behavior delta

- Before the original change: finite metadata multipliers above 1 were
  rejected; NaN was accepted.
- After complete enforcement: finite positive multipliers through `1e7` are
  accepted; zero, negative, NaN, infinity, values above `1e7`, and incomplete
  explicit instrument specs are rejected before state or provenance mutation.
- Money/risk impact: formulas and previously accepted values are unchanged;
  configured XRP/ADA/DOGE/SHIB-style multipliers can use existing formulas.
  Numeric acceptance alone does not establish promotion-grade provenance.

## Source-of-truth updates

- `research/strategy_synthesis.md`: N/A — no strategy assumption changed.
- `config/`: reviewed unchanged; current maximum metadata value is `1e6`.
- ADR: ADR-0003 retains its dated amendment; ADR-0007 reviewed unchanged.

## Docs updated (from DOC_IMPACT_MATRIX rows)

- [x] `docs/DOMAIN_RULES.md` — R1.5 fail-closed enforcement clarified.
- [x] `docs/INVARIANTS.md` / `docs/FAILURE_MODES.md` — I34 and F32/F37
  enforced.
- [x] `docs/DATA_FLOW.md` — validation before replay/provenance and fail-closed
  incomplete explicit specs documented.
- [x] ADR-0003 — obsolete `<=1` statement remains superseded by the dated
  amendment; formulas unchanged.
- [x] `docs/FEATURE_MAP.md`, `docs/GOLDEN_CASES.md`, ADR-0002, ADR-0005, and
  `docs/ai_collaboration.md` — reviewed unchanged; ownership, result schema,
  and promotion gates did not move.

## Invariants / golden cases

- Invariants checked: I1, I16, I34.
- Golden cases affected: G-001 remains unchanged; valid multipliers still enter
  the same linear formulas.

## Tests / checks run

- Original change: targeted suite `79 passed`; final P0 target suite
  `306 passed, 1 skipped`; full unit `768 passed, 1 skipped`; integration
  `38 passed`; full Ruff, docs/config/backtest-smoke passed.
- Follow-up repair: unit `841 passed, 1 skipped`; integration `38 passed`; lab
  `18 passed`; full Ruff/docs/config/backtest smoke and strict doc impact from
  base `00c7a51` passed. Full evidence:
  `tasks/2026-07-13-pr9-followup-fixes-session-handoff.md`.

## Risks and rollback

- Risk: corrupt but finite values below the cap still depend on R1.4
  provenance.
- Rollback: revert the follow-up repair commit; no data, schema, formula, or
  artifact migration is involved.

## Approval

- Human approval obtained: yes — the user ratified the Claude-proposed `1e7`
  cap by requesting implementation on 2026-07-12, then explicitly requested
  that Codex repair PR #9 on 2026-07-13.
