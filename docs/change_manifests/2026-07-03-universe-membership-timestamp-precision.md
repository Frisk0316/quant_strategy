---
status: current
type: manifest
owner: codex
created: 2026-07-03
last_reviewed: 2026-07-03
expires: none
superseded_by: null
---

# Change Manifest: Universe Membership Timestamp Precision

## Summary
Normalize candle timestamp storage precision before point-in-time universe
membership math. This fixes a PR merge blocker where DB-sourced and
parquet-sourced membership outputs differed only by `datetime64` unit.

## Business rule(s) affected
R6.2 DB and parquet sources must agree.

## Trigger area(s) (DOC_IMPACT_MATRIX)
A5-equivalent backtesting/research data workflow; `scripts/build_universe_membership.py`
is not directly listed in the current executable trigger table, but the change
affects the universe artifact used by backtests and research probes.

## Files changed
- `scripts/build_universe_membership.py` - normalize candle timestamp index units
  to `datetime64[ns]` before daily dollar-volume resampling.
- `tests/unit/test_universe_membership.py` - add regression coverage for
  `datetime64[us]` vs `datetime64[s]` parity.
- `docs/INVARIANTS.md` - strengthen I20 with timestamp-precision parity.
- `docs/FAILURE_MODES.md` - add F24 for timestamp precision drift.
- `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `config/workstreams.yaml`,
  and session handoffs - record current state.

## Behavior delta
- Before: equivalent calendar-day inputs could produce membership outputs with
  different datetime units, causing strict DB/parquet parity checks to fail.
- After: membership calculations use a stable `datetime64[ns]` timestamp basis.
- Money/risk impact: none directly; this restores source-parity validation for
  research universe artifacts.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A - no strategy assumption changed.
- config/: `config/workstreams.yaml` updated only to keep the Progress panel in
  sync with `docs/AI_HANDOFF.md`; no runtime config changed.
- ADR: N/A - no rule, schema, gate, or architecture decision changed.

## Docs updated (from DOC_IMPACT_MATRIX row)
- [x] `docs/DATA_FLOW.md` - reviewed; current DB/parquet parity target already
  describes the intended behavior.
- [x] `docs/FEATURE_MAP.md` - reviewed; owning files/tests are already listed.
- [x] `docs/INVARIANTS.md` - updated I20.
- [x] `docs/FAILURE_MODES.md` - added F24.
- [x] ADR-0009 - reviewed; no change needed because research-only scope is
  unchanged.

## Invariants / golden cases
- Invariants checked: I20.
- Golden cases affected: N/A.

## Tests / checks run
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_universe_membership.py::test_build_membership_ignores_timestamp_storage_precision -q` - failed before fix, passed after fix.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_universe_membership.py -q` - passed, 6 tests.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_doc_metadata.py` - passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_feature_map_links.py` - passed.
- `check_doc_impact.py --strict` with temporary `safe.directory` git config - passed, 10 changed files.

## Risks and rollback
- Risks: converting timestamps to nanosecond precision could reject dates outside
  pandas' nanosecond range; this data path uses market history dates well inside
  that range.
- Rollback: revert `scripts/build_universe_membership.py`,
  `tests/unit/test_universe_membership.py`, and this manifest/doc update set.

## Approval
- Human approval required: no - bug fix restoring documented R6.2 behavior.
