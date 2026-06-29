---
status: current
type: manifest
owner: claude
created: 2026-06-29
last_reviewed: 2026-06-29
expires: none
superseded_by: null
---

# Change Manifest: Venue Gap Tolerates Late-Listing Symbols

## Summary
Multi-symbol backtests no longer crash when a symbol listed after the requested
start date. The venue-scoped candle-gap guard now measures coverage from a
symbol's first observed bar instead of the requested start, so a coin with a
later listing date is accepted as long as it is well-covered from its listing
onward. Empty venue series and genuinely sparse internal gaps still raise, and
no cross-venue / parquet substitution is ever allowed.

## Business rule(s) affected
R6.4 (venue-scoped data provenance). Relaxation only; the no-substitution policy
is unchanged.

## Trigger area(s) (DOC_IMPACT_MATRIX)
A5 backtesting / data provenance.

## Files changed
- `backtesting/data_loader.py` — `_raise_on_venue_gap` measures coverage from the
  first observed bar; new `VENUE_GAP_MIN_COVERAGE = 0.80` tolerance; empty frame
  still raises.
- `tests/unit/test_data_loader.py` — regression tests for late-listing acceptance
  and sparse-internal-gap rejection.
- `docs/DATA_FLOW.md` — documents the late-listing exception.
- `docs/change_manifests/2026-06-29-venue-gap-late-listing.md` — this manifest.

## Behavior delta
- Before: `expected` bars were counted over the full `[start, end]` window, so a
  late-listing symbol (e.g. `CC-USDT-SWAP` 1D: expected 898, found 229) raised
  `ValueError: Venue-scoped candle gap ...` and aborted the whole multi-symbol run.
- After: coverage is counted from `max(start, first_observed_bar)` to `end`; a
  late-listing symbol that is contiguous from its listing passes. An empty venue
  frame still raises (`found 0`); a series below 80% coverage from its first bar
  still raises.
- Money/risk impact: none to PnL, fees, funding sign, sizing, or risk limits.
  Downstream coverage gates (gate3 data coverage, etc.) still surface partial
  coverage as warnings.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A — no strategy assumption changed.
- config/: N/A — no runtime parameter changed (threshold is a module constant).
- ADR: N/A — relaxes ADR-0007/R6.4 provenance strictness without changing the
  no-cross-venue-substitution policy or any schema.

## Docs updated (from DOC_IMPACT_MATRIX row)
- [x] `docs/DATA_FLOW.md` — late-listing coverage exception documented.
- [x] `docs/FEATURE_MAP.md` — reviewed; backtesting/data loader ownership/tests
  already point here, no change needed.
- [x] `docs/INVARIANTS.md` — reviewed; I19 (no cross-venue / parquet substitution)
  still holds — a late listing is a leading absence, not a substitution.

## Invariants / golden cases
- Invariants checked: I19 (preserved — no substitution path added).
- Golden cases affected: none.

## Tests / checks run
- `python -m pytest tests/unit/test_data_loader.py -q` — 10 passed (incl. new
  `test_venue_scoped_gap_allows_late_listing_symbol` and
  `test_venue_scoped_gap_raises_on_sparse_internal_holes`).

## Risks and rollback
- Risks: a venue dataset that is genuinely incomplete but ≥80% covered from its
  first bar will now run instead of erroring; downstream coverage warnings remain
  the signal for that. Lower `VENUE_GAP_MIN_COVERAGE` to tolerate sparser data,
  raise it to be stricter.
- Rollback: revert `_raise_on_venue_gap` in `backtesting/data_loader.py`, the two
  new tests, and the `docs/DATA_FLOW.md` paragraph.

## Approval
- Human approval required: no — user explicitly requested relaxing this rule so
  late-listing coins do not crash multi-symbol backtests; no gate or
  no-substitution policy changed.
