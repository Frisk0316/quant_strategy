---
status: current
type: manifest
owner: codex
created: 2026-06-22
last_reviewed: 2026-06-22
expires: none
superseded_by: null
---

# Change Manifest: Delete Trading Pair Data

## Summary
Market Data Coverage can now hard-delete a stale OHLCV/funding trading pair from
the API/UI. The delete removes both DB rows and the local parquet mirror so
coverage and backtest pair lists do not keep showing ghost pairs.

## Business rule(s) affected
R6.2 data provenance/source agreement: DB and parquet mirrors are removed
together for the selected pair.

## Trigger area(s) (DOC_IMPACT_MATRIX)
A7 `src/okx_quant/api/`, A8 `frontend/`, plus a manual manifest because the new
route is a destructive data-provenance path.

## Files changed
- `src/okx_quant/api/routes_data.py` - queued fetch execution and delete-pair API.
- `frontend/view-config.js` - fetch job list, per-job cancel, and delete button.
- `frontend/data.js` - delete-pair API client method.
- `tests/unit/test_routes_data_queue.py` - queue serialization and queued cancel tests.
- `tests/unit/test_routes_data_delete.py` - delete statement, guard, route, and parquet tests.
- `docs/DATA_FLOW.md` - fetch queue and pair delete flows.
- `docs/UI_MAP.md` - Market Data Coverage UI/API calls.
- `docs/FEATURE_MAP.md` - market-data ownership and tests.
- `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md` - current state and risks.

## Behavior delta
- Before: only one frontend fetch could be started while another was active; stale
  pairs required CLI purge and could linger in coverage/UI lists.
- After: fetch submissions are accepted as queued and run one at a time; OHLCV
  and funding coverage rows can be deleted through a guarded API/UI path.
- Money/risk impact: none directly; no PnL, fee, funding cashflow, sizing, risk,
  fill, strategy, or deployment-gate behavior changed.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A - no strategy assumptions changed.
- config/: N/A - no runtime settings or risk parameters changed.
- ADR: N/A - no DB schema, promotion gate, authority order, or architectural rule
  changed.

## Docs updated (from DOC_IMPACT_MATRIX row)
- [x] `docs/UI_MAP.md` - updated for fetch job list, cancel, and delete API/UI.
- [x] `docs/DATA_FLOW.md` - updated for queue and destructive pair delete path.
- [x] `docs/FEATURE_MAP.md` - updated market-data behavior, files, and tests.
- [x] `docs/AI_HANDOFF.md` - updated current change context.
- [x] `docs/CURRENT_STATE.md` - updated current working state and next smoke step.

## Invariants / golden cases
- Invariants checked: R6.2 reviewed; no invariant change required.
- Golden cases affected: N/A.

## Tests / checks run
- `python -m pytest -p no:cacheprovider tests/unit/test_routes_data_queue.py tests/unit/test_routes_data_delete.py tests/unit/test_routes_data_export.py -v` - passed, 18 tests.
- `node --check` on all files from `FRONTEND_JS` - passed.
- `make frontend-check` - not run because `make` is unavailable in this Windows sandbox.
- `python scripts/docs/check_doc_impact.py` with `GIT_CONFIG_* safe.directory` env - passed, 13 changed files and no impact-matrix violations.

## Risks and rollback
- Risks: accidental deletion of the wrong pair, stale in-memory fetch jobs after
  process restart, and untested manual browser/DB flow in this sandbox.
- Rollback: revert this manifest plus the scoped changes to `routes_data.py`,
  `frontend/view-config.js`, `frontend/data.js`, the two route test files, and
  the updated docs.

## Approval
- Human approval required: yes - scope was explicitly supplied by the user via
  the approved spec and implementation plan in `docs/superpowers/`.
