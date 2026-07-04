---
status: current
type: manifest
owner: codex
created: 2026-07-03
last_reviewed: 2026-07-03
expires: none
superseded_by: null
---

# Change Manifest: Turtle Research Runner

## Summary
Added a research-only Turtle S1/S2 standalone backtest runner, API run/sweep
surface, and frontend controls/visualization. The implementation preserves the
user-provided reference script semantics instead of routing through replay.

## Business rule(s) affected
R1 PnL/accounting, R2 fees, R4 sizing, and R5 fills are affected only inside the
new research-only Turtle runner. R5.5 records the reference-semantics scope.
Existing replay/live rules are unchanged.

## Trigger area(s) (DOC_IMPACT_MATRIX)
A5 backtesting; A7 frontend/API artifact review surface.

## Files changed
- `backtesting/turtle_backtest.py` - standalone pandas port, metrics, grid/sweep
  helpers, Plotly surface generation.
- `src/okx_quant/api/routes_backtest.py` - Turtle `/run` and `/sweep` branches
  plus allow-listed sweep artifact readers.
- `frontend/data.js`, `frontend/view-config.js`, `frontend/charts.js`,
  `frontend/vendor/plotly.min.js` - strategy metadata, controls, heatmaps, and
  vendored Plotly 2.x for `surface.html`.
- `tests/unit/test_turtle_backtest.py`,
  `tests/unit/test_routes_backtest_turtle.py` - reference semantics and API
  artifact tests.
- `backtesting/differential_validation.py` - one declarative `turtle`
  REFERENCE_VALIDATION_CONTRACTS entry (user-approved RF1 scope amendment);
  remediation `d4047ed` relabeled its engine statuses `implemented` ->
  `not_targeted` so the contract does not imply runnable external adapters
  (`portable_validation_required: False`, engines SKIP with honest reasons);
  `tests/unit/test_differential_validation.py` now enforces `not_targeted`
  for nonportable contracts and all-`implemented` for portable ones.
- Project docs and handoffs listed below.

## Behavior delta
- Before: the standalone turtle script was outside the platform; no API, UI, or
  result artifacts existed for it.
- After: users can run one 1D-symbol Turtle research backtest and submit Turtle
  sweeps that write platform-readable artifacts.
- Money/risk impact: no live/demo/shadow impact. Turtle research PnL uses close
  fills, strict cash gate, static sizing capital, same-day ATR, fees on buy/sell,
  S1 skip-after-win, and no end liquidation by reference parity.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A; user-provided `new_startegy_海龜/` is the
  reference source for this task.
- config/: `config/workstreams.yaml` only, for Progress panel state.
- ADR: N/A; this is a new research-only standalone runner following the
  `daily_winner` precedent and existing ADR-0002 artifact shape.

## Docs updated (from DOC_IMPACT_MATRIX row)
- [x] `docs/FEATURE_MAP.md` - Turtle owning files/tests.
- [x] `docs/DOMAIN_RULES.md` - R5.5 Turtle reference semantics scope.
- [x] `docs/INVARIANTS.md` - I31 Turtle isolation invariant.
- [x] `docs/UI_MAP.md` - Turtle controls, API helpers, and heatmap/Plotly surface.
- [x] `docs/DATA_FLOW.md` - Turtle run and sweep artifact flow.
- [x] `docs/RUNBOOK.md` - manual Turtle check/run notes.
- [x] `docs/GOLDEN_CASES.md` - G-003 reference quirks.
- [x] `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`,
  `config/workstreams.yaml` - current state and progress.

## Invariants / golden cases
- Invariants checked: I1, I2, I31 via reference-style unit tests.
- Golden cases affected: G-003 added.

## Tests / checks run
- `python -m pytest tests/unit/test_turtle_backtest.py tests/unit/test_routes_backtest_turtle.py -q -o cache_dir=...` - passed.
- `node --check frontend/data.js`, `frontend/charts.js`,
  `frontend/view-config.js` - passed.

## Risks and rollback
- Risks: pandas port may still diverge from untested corners of the reference
  script; DB daily candles must match UTC daily bars; Turtle's
  differential-validation contract is declarative-only (`not_targeted`
  engines - no runnable external validation exists or is claimed); high
  `invest_pct` can plateau on the reference cash gate.
- Rollback: remove `backtesting/turtle_backtest.py`, Turtle branches/helpers in
  `routes_backtest.py`, Turtle frontend additions/vendor Plotly, the two Turtle
  test files, this manifest, and the associated docs/handoff updates.

## Approval
- Human approval required: yes for platform integration and vendored Plotly;
  obtained in the 2026-07-03 turtle task/spec handoff. No live/demo/shadow
  approval was requested or granted.
