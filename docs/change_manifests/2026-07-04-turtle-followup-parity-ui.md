---
status: current
type: manifest
owner: codex
created: 2026-07-04
last_reviewed: 2026-07-04
expires: none
superseded_by: null
---

# Change Manifest: Turtle Follow-Up Parity And UI Honesty

## Summary
Fixed Turtle review-surface bugs and added sweep parity validation tooling. The
Turtle engine, metric formulas, strategy assumptions, risk, fills, PnL, and gates
are unchanged.

## Business rule(s) affected
None, mechanical/presentation/validation only. R5.5 and R7.1 were checked because
the touched runner is the research-only Turtle path.

## Trigger area(s) (DOC_IMPACT_MATRIX)
A5 `backtesting/` because `backtesting/turtle_backtest.py` surface rendering was
touched.

## Files changed
- `backtesting/turtle_backtest.py` - surface.html title/hover presentation only.
- `scripts/turtle/validate_sweep_parity.py` - read-only parity validation script.
- `src/okx_quant/api/routes_backtest.py` - marker timestamp parsing and Turtle
  ignored-control result metadata.
- `frontend/view-config.js` - Turtle slider/live-control presentation.
- `tests/unit/test_turtle_backtest.py` - sweep/surface regression coverage.
- `tests/unit/test_routes_backtest_turtle.py` - marker and ignored-control
  regression coverage.
- `docs/FEATURE_MAP.md`, `docs/UI_MAP.md`, `docs/FAILURE_MODES.md`,
  `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md` - task docs.

## Behavior delta
- Before: file-backed Turtle CSV fills/trades could lose execution markers when
  epoch timestamps round-tripped as strings; Turtle UI implied risk/execution
  controls applied; API records could echo `fill_all_signals=true` even though
  Turtle ignores it; surface.html omitted fixed params and hover metric
  formatting.
- After: numeric-string epoch timestamps render markers; Turtle explicitly records
  ignored risk/execution/`fill_all_signals` controls; surface.html title/hover
  matches the reference shape.
- Money/risk impact: none. No sizing, fee, PnL, fill, risk, or promotion-gate
  semantics changed.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A, no strategy assumption change.
- config/: N/A, no runtime/config change.
- ADR: N/A, no result schema, DB schema, or gate change.

## Docs updated (from DOC_IMPACT_MATRIX row)
- [x] `docs/DATA_FLOW.md` - confirmed unchanged; artifact flow and file names stay
  the same.
- [x] `docs/FEATURE_MAP.md` - updated Turtle ignored-control behavior.
- [x] `docs/GOLDEN_CASES.md` - confirmed unchanged; golden daily-frame parity still
  applies and targeted tests passed.
- [x] `docs/INVARIANTS.md` - confirmed unchanged; I31 still describes Turtle
  research-runner isolation.
- [x] ADR-0002/0005 - confirmed unchanged; no schema or replay gate change.

## Invariants / golden cases
- Invariants checked: I31.
- Golden cases affected: Turtle fixture parity; unchanged, targeted tests passed.

## Tests / checks run
- `python scripts/turtle/validate_sweep_parity.py` - PASS Tier A, all 27 columns
  match on 270 combos.
- `python scripts/turtle/validate_sweep_parity.py --reference-csv ...` - Tier B
  fingerprint failed because DB-synthesized input does not reproduce the user CSV.
- `python -m pytest tests/unit/test_turtle_backtest.py tests/unit/test_routes_backtest_turtle.py -q` - targeted Turtle tests passed; local result-artifact regressions are skip-gated for fresh CI checkouts.
- `node --check frontend/*.js` via the Makefile file list - passed.
- `python scripts/docs/check_doc_metadata.py` - passed.
- `python scripts/docs/check_feature_map_links.py` - passed.
- `python scripts/docs/check_doc_impact.py --strict` - rerun after this manifest.
- `python scripts/validate_pipeline.py --check-config-only` - passed.

## Risks and rollback
- Risks: UI copy could still be unclear; surface title/hover presentation could
  regress without browser-level visual testing.
- Rollback: revert this changeset; no generated result artifacts or DB data need
  migration.

## Approval
- Human approval required: no for this mechanical follow-up; original task scope
  was user-supplied on 2026-07-04.
