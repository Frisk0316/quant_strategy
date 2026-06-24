# Session Handoff: Market Data Coverage Fast Path - 2026-06-23

## Implementation summary
Changed Market Data Coverage so the OHLCV list loads from existing
`instrument_bars` metadata instead of aggregating all `canonical_candles`. The
frontend now shows estimated OHLCV row counts with `~` and displays a visible
"Market data coverage unavailable" message when the request fails, instead of
showing "No data in DB". Funding coverage provider labels now come from
`funding_rates.source`, fixing rows that showed provider `okx` with exchange
`binance`. The coverage table now has local exchange, pair/dataset search, and
data-type filters. Funding export now displays fixed `8H` frequency and sends
`bar=funding` instead of showing the disabled OHLCV `1H` value.

## Diff scope
- Files added:
  - `tasks/2026-06-23-market-data-coverage-fast-path-context-handoff.md`
  - `tasks/2026-06-23-market-data-coverage-fast-path-session-handoff.md`
- Files changed:
  - `src/okx_quant/api/routes_data.py`
- `frontend/view-config.js`
  - `tests/unit/test_routes_data_delete.py`
- `tests/unit/test_backtest_visual_fallbacks.py`
  - `docs/UI_MAP.md`
  - `docs/DATA_FLOW.md`
  - `docs/AI_HANDOFF.md`
  - `docs/CURRENT_STATE.md`
- Files deleted: none.

## Business-rule change?
- No. API/UI read-path and docs only; no Change Manifest required for this task.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A
- config/: N/A
- ADR: N/A

## Experiments
- HYPOTHESIS_LEDGER entries: none
- EXPERIMENT_REGISTRY entries: none

## Tests / checks run
- `pytest tests\unit\test_routes_data_delete.py::test_coverage_route_uses_instrument_bars_fast_path tests\unit\test_backtest_visual_fallbacks.py::test_market_data_coverage_fetch_errors_have_visible_state -q -p no:cacheprovider` - failed before implementation, passed after.
- `pytest tests\unit\test_routes_data_delete.py tests\unit\test_backtest_visual_fallbacks.py -q -p no:cacheprovider` - 36 passed after the local coverage filter test was added.
- `python -B -c "... TestClient(...).get('/api/data/coverage') ..."` against
  configured DB - 200, latest check 58 rows.
- `python -B -c "... funding provider/exchange mismatch check ..."` against
  configured DB - 27 funding rows, 0 mismatches.
- Full `frontend-check` equivalent: `node --check` for all Makefile frontend JS files - passed.
- `scripts/docs/check_doc_metadata.py` - passed with 15 pre-existing warnings.
- `scripts/docs/check_feature_map_links.py` - passed.
- `scripts/docs/check_doc_impact.py` with `GIT_CONFIG_* safe.directory` env - passed, no violations.
- `git diff --check` on touched files - passed with CRLF warnings only.

## Docs updated
- `docs/UI_MAP.md`
- `docs/DATA_FLOW.md`
- `docs/AI_HANDOFF.md`
- `docs/CURRENT_STATE.md`

## Known limitations / risks
- OHLCV coverage row counts are estimated from first/last timestamp and bar
  interval. They are fast overview numbers, not exact gap evidence.
- The overview no longer computes mixed source provenance from
  `canonical_candles`; source-detail should be a separate targeted endpoint if
  needed.
- `make` is unavailable in this Windows shell, so Makefile targets were run via
  their underlying commands.

## Rollback plan
- Revert `src/okx_quant/api/routes_data.py`, `frontend/view-config.js`, the two
  test changes, and the docs/handoff edits from this task. No DB migration or
  data rollback is needed.

## Context Handoff
- See `tasks/2026-06-23-market-data-coverage-fast-path-context-handoff.md`.

## Questions for human review
- Should exact row count/gap/source provenance be exposed through a per-symbol
  detail endpoint after the current backfill finishes?

## Next recommended task
- Let the active ingest finish, then run a targeted coverage gate query for
  >=25 non-stablecoin USDT-SWAP symbols with >=12 months before WF/CPCV +
  DSR/PSR.

## Human Learning Notes (required)
Large 1m universes make "overview" queries dangerous if they scan candle facts.
Use metadata for dashboards and save exact fact-table checks for explicit
diagnostics.
