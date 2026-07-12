---
status: archived
type: handoff
owner: codex
created: 2026-07-03
last_reviewed: 2026-07-03
expires: none
superseded_by: null
---

# Context Handoff: Universe Membership Timestamp Precision - 2026-07-03

## Goal (one sentence)
Fix the PR merge blocker where DB and parquet universe membership outputs failed
strict parity because timestamp storage units differed.

## Current state
- Branch: `codex/pipeline-batch1-stage3`.
- Last known good commit / state: working tree was clean before this fix.
- In-progress edits (files): `scripts/build_universe_membership.py`,
  `tests/unit/test_universe_membership.py`, docs/manifest/handoff updates.
- What works right now: targeted universe membership tests pass locally.
- What does not work / unfinished: full suite not rerun locally in this Windows
  sandbox.

## Decisions made (and why)
- Normalize candle timestamps in `_daily_dollar_volume()` to `datetime64[ns]`
  because it is the shared source path for DB and parquet membership math.

## Open questions / unverified assumptions
- CI should now match local parity because both `date` and `listing_ts` derive
  from normalized timestamps.

## Rules in play (preserve verbatim)
- Invariants touched: I20 - universe membership is point-in-time and timestamp
  storage precision does not change membership output.
- Domain rules touched: R6.2.
- Do-not-touch: `research/`, `results/`, strategy/risk/portfolio/execution,
  live/shadow/demo gates, differential-validation implementation.

## Context to load next (the reading list)
- Source of truth: `AI_CONTEXT.md`, `docs/FEATURE_MAP.md` point-in-time universe
  membership, `docs/DATA_FLOW.md` point-in-time universe membership flow,
  `config/universe.yaml`, ADR-0009.
- Owning files / MODULE_BRIEFS: `scripts/build_universe_membership.py`,
  `tests/unit/test_universe_membership.py`.
- Context Pack: none exists for universe membership; use `docs/CONTEXT_INDEX.md`.

## Checks run
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_universe_membership.py::test_build_membership_ignores_timestamp_storage_precision -q` - failed before fix, passed after fix.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_universe_membership.py -q` - passed, 6 tests.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_doc_metadata.py` - passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_feature_map_links.py` - passed.
- `check_doc_impact.py --strict` with temporary `safe.directory` git config - passed, 10 changed files.

## Approvals
- Human approval needed / obtained: not needed; direct bug fix requested by user.

## Next action (single, concrete)
- Commit this scoped fix if the PR rerun is green.

## Human Learning Notes
Timestamp dtype units can differ by source path and pandas/CI version even when
calendar days are identical; normalize at the shared data boundary before strict
parity assertions.
