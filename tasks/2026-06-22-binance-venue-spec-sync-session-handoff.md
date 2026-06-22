# Session Handoff: Binance Venue Spec Sync - 2026-06-22

## Implementation summary
Fixed the Binance venue-spec gap that caused replay to fail on downloaded multiplier contracts such as `1000SHIB-USDT-SWAP`. The Market Data fetch path now preserves Binance `exchangeInfo` precision filters, builds a DB venue-spec payload with `ct_val = 1.0`, and upserts `venue_instrument_specs(exchange, symbol)` before candle writes or skipped-result reporting.

## Diff scope
- Files added: `docs/change_manifests/2026-06-22-binance-venue-spec-sync.md`, `tasks/2026-06-22-binance-venue-spec-sync-context-handoff.md`, `tasks/2026-06-22-binance-venue-spec-sync-session-handoff.md`.
- Files changed: `src/okx_quant/api/routes_data.py`, `tests/unit/test_routes_data_export.py`, `docs/DATA_FLOW.md`, `docs/UI_MAP.md`, `docs/FEATURE_MAP.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`.
- Files deleted: none.

## Business-rule change?
- Yes, data-provenance / `ct_val` authority path. Change Manifest at `docs/change_manifests/2026-06-22-binance-venue-spec-sync.md`; DOC_IMPACT_MATRIX checked row A7, with manual manifest because R1.4 provenance behavior is affected.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A.
- config/: N/A.
- ADR: N/A; this implements ADR-0007's existing venue-aware table behavior and does not change schema or policy.

## Experiments
- HYPOTHESIS_LEDGER entries: none.
- EXPERIMENT_REGISTRY entries: none.

## Tests / checks run
- `python -m pytest -p no:cacheprovider tests/unit/test_routes_data_export.py tests/unit/test_routes_data_queue.py tests/unit/test_routes_data_delete.py tests/unit/test_replay_ct_val_resolution.py tests/unit/test_replay_ct_val_provenance_tag.py -v` - passed, 33 tests.
- `python scripts/docs/check_doc_metadata.py` - passed with 14 pre-existing lifecycle metadata warnings.
- `python scripts/docs/check_feature_map_links.py` - passed.
- `python scripts/docs/check_doc_impact.py` with `GIT_CONFIG_* safe.directory` env - passed, 8 changed tracked files and no impact-matrix violations.
- `node --check frontend/data.js frontend/charts.js frontend/view-config.js frontend/view-backtest.js frontend/view-results.js frontend/view-validation.js frontend/view-trades.js frontend/view-glossary.js frontend/app.js` - passed.
- `git -c safe.directory=C:/quant_strategy diff --check` - exit 0; emitted CRLF conversion warnings only.
- `make` targets - not run; `make` is unavailable in this Windows sandbox.

## Docs updated
- `docs/DATA_FLOW.md`
- `docs/UI_MAP.md`
- `docs/FEATURE_MAP.md`
- `docs/AI_HANDOFF.md`
- `docs/CURRENT_STATE.md`
- `docs/change_manifests/2026-06-22-binance-venue-spec-sync.md`

## Known limitations / risks
- No real DB-backed Binance fetch/replay was executed in this sandbox.
- Existing Binance data downloaded before this fix may still lack rows in `venue_instrument_specs`; rerun fetch or seed the table before replaying multiplier contracts.
- Environments missing migration `0011_venue_instrument_specs.sql` will still fail when fetch tries to upsert specs.

## Rollback plan
- Revert this bugfix's scoped files: `routes_data.py`, `tests/unit/test_routes_data_export.py`, the Binance spec-sync manifest, the two Binance spec-sync handoffs, and the docs updates. The replay guard remains unchanged.

## Context Handoff
- See `tasks/2026-06-22-binance-venue-spec-sync-context-handoff.md`.

## Questions for human review
- Should we immediately run a DB-backed fetch for `1000SHIB-USDT-SWAP` to populate the local table and rerun the failed latest replay?

## Next recommended task
- DB smoke the exact failing symbol: fetch `1000SHIB-USDT-SWAP` from Binance, verify `venue_instrument_specs`, rerun replay.

## Human Learning Notes (required)
The confusing part is that OHLCV availability and venue spec availability are separate data products. Binance candles can be present while `venue_instrument_specs` is empty, and ADR-0007 correctly refuses `1000...` multiplier contracts without an explicit DB row.
