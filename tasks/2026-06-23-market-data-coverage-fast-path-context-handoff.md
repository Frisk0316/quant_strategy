# Context Handoff: Market Data Coverage Fast Path - 2026-06-23

## Goal (one sentence)
Make Market Data Coverage load quickly from metadata and stop showing DB-empty
copy when the coverage request times out or fails.

## Current state
- Branch: `codex/xs-momentum-universe-scaffold` as observed in this session context.
- Last known good commit / state: working tree already contained unrelated
  funding-carry fallback, XS momentum, and report-doc changes before this task.
- In-progress edits (files): `src/okx_quant/api/routes_data.py`,
  `frontend/view-config.js`, `tests/unit/test_routes_data_delete.py`,
  `tests/unit/test_backtest_visual_fallbacks.py`, `docs/UI_MAP.md`,
  `docs/DATA_FLOW.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`.
- What works right now: `/api/data/coverage` reads OHLCV rows from
  `instrument_bars` and returns sub-second responses against the configured DB
  via FastAPI TestClient. Latest check returned 58 coverage rows. Funding
  coverage rows label provider/exchange from `funding_rates.source`, so Binance
  funding no longer displays provider `okx`. The table supports local
  exchange, pair/dataset search, and data-type filters over the loaded rows.
  Funding export displays fixed `8H` frequency and sends `bar=funding`.
- What does not work / unfinished: exact OHLCV row counts and mixed source detail
  are no longer computed by the main coverage list; use targeted diagnostics for
  exact counts/gaps.

## Decisions made (and why)
- Use `instrument_bars` as the coverage fast path because it already stores
  per-`(inst_id, bar)` first/last timestamps and avoids a 35M-row
  `canonical_candles` aggregation.
- Mark OHLCV row counts as estimated because they are derived from first/last
  timestamps and bar interval rather than exact `COUNT(*)`.
- Show a visible coverage unavailable state because a timeout is not evidence
  that the DB is empty.
- Derive funding provider from the stored funding source because a hard-coded
  `okx` provider created false provider/exchange mismatches for Binance funding.
- Keep coverage filters in the frontend because the fast-path payload is already
  small enough for local filtering and this avoids another API/DB path.
- Treat funding export frequency as fixed display state because the funding API
  payload already carries `funding_interval_hours`; it is not an OHLCV bar.

## Open questions / unverified assumptions
- Whether to add a separate on-demand detail endpoint for exact row count, gap
  count, and mixed source provenance per symbol/bar.

## Rules in play (preserve verbatim)
- Invariants touched: none.
- Domain rules touched: none.
- Do-not-touch: `research/`, `src/okx_quant/strategies/`,
  `src/okx_quant/signals/`, `src/okx_quant/risk/`,
  `src/okx_quant/portfolio/`, `src/okx_quant/execution/`, DB schema/migrations,
  existing result artifacts, live/shadow/demo gates.

## Context to load next (the reading list)
- Source of truth: `AI_CONTEXT.md`, `docs/FEATURE_MAP.md`, `docs/UI_MAP.md`,
  `docs/DATA_FLOW.md`.
- Owning files / MODULE_BRIEFS: Market Data Ingestion and Canonical Candle
  Pipeline entries in `docs/FEATURE_MAP.md`.
- Context Pack: no dedicated market-data pack exists; use `docs/CONTEXT_INDEX.md`.

## Checks run
- `pytest tests\unit\test_routes_data_delete.py::test_coverage_route_uses_instrument_bars_fast_path tests\unit\test_backtest_visual_fallbacks.py::test_market_data_coverage_fetch_errors_have_visible_state -q -p no:cacheprovider` - failed before implementation, passed after.
- `pytest tests\unit\test_routes_data_delete.py tests\unit\test_backtest_visual_fallbacks.py -q -p no:cacheprovider` - 35 passed.
- FastAPI TestClient against configured DB `/api/data/coverage` - 200, latest
  check 58 rows.
- FastAPI TestClient against configured DB funding coverage check -
  27 funding rows, 0 provider/exchange mismatches.
- Full `frontend-check` equivalent via `node --check` on all Makefile frontend
  JS files - passed.
- `scripts/docs/check_doc_metadata.py` - passed with 15 pre-existing warnings.
- `scripts/docs/check_feature_map_links.py` - passed.
- `scripts/docs/check_doc_impact.py` with `GIT_CONFIG_* safe.directory` env -
  passed, 16 changed files, no impact-matrix violations.
- `git diff --check` on touched files - passed with CRLF warnings only.

## Approvals
- Human approval obtained in chat to change `/api/data/coverage` fast path and
  frontend timeout empty-state.

## Next action (single, concrete)
- Let the other ingestion session finish; then use the fast coverage panel or a
  targeted DB coverage query to confirm the >=25-symbol / >=12-month gate before
  WF/CPCV + DSR/PSR.

## Human Learning Notes
The old empty coverage screen was a false empty-state caused by timeout handling.
For large 1m universes, dashboard overview queries must use metadata tables;
exact counts belong in targeted diagnostics, not first-page UI loads.
