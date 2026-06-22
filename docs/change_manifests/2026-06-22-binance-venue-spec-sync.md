---
status: current
type: manifest
owner: codex
created: 2026-06-22
last_reviewed: 2026-06-22
expires: none
superseded_by: null
---

# Change Manifest: Binance Venue Spec Sync

## Summary
Binance market-data fetch now parses `exchangeInfo` precision filters and
upserts `venue_instrument_specs(exchange, symbol)` before candle writes. This
prevents Binance multiplier contracts such as `1000SHIB-USDT-SWAP` from failing
replay with missing DB `ct_val` after their candles have been downloaded.

## Business rule(s) affected
R1.4 venue-matched authoritative `ct_val` source for SWAP replay and promotion
evidence; R6.2 data provenance/source agreement.

## Trigger area(s) (DOC_IMPACT_MATRIX)
A7 `src/okx_quant/api/`. Manual manifest added because the API change affects
`ct_val` provenance behavior even though no DB schema, replay gate, strategy,
risk, portfolio, execution, or config files changed.

## Files changed
- `src/okx_quant/api/routes_data.py` - parse Binance precision filters, build
  venue-spec payloads, and upsert Binance venue specs during fetch.
- `tests/unit/test_routes_data_export.py` - regression tests for Binance filter
  parsing, venue-spec payloads, upsert SQL, and skipped-fetch spec sync.
- `docs/DATA_FLOW.md` - documents the fetch-to-venue-spec flow.
- `docs/UI_MAP.md` - notes the `/api/data/fetch` Binance spec-sync side effect.
- `docs/FEATURE_MAP.md` - maps Market Data Ingestion to venue-spec files/tests.
- `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md` - current state and next action.

## Behavior delta
- Before: Binance OHLCV could be downloaded without a matching
  `venue_instrument_specs` row; replay then failed for canonical `1000...`
  multiplier contracts because `exchange_base_unit` intentionally refuses those
  symbols without DB specs.
- After: Binance fetch writes `ct_val = 1.0`, lot size, tick size, and min size
  from Binance metadata into `venue_instrument_specs` before candle writes or
  skipped-result reporting.
- Money/risk impact: no PnL, fee, funding, sizing, risk, fill, strategy, or
  deployment-gate calculation changed. The change supplies the authoritative
  DB metadata required by the existing replay guard.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A - no strategy assumptions changed.
- config/: N/A - no runtime settings or risk parameters changed.
- ADR: N/A - implements ADR-0007's existing venue-aware table and explicit
  multiplier-contract requirement; no new architectural rule or schema change.

## Docs updated (from DOC_IMPACT_MATRIX row)
- [x] `docs/UI_MAP.md` - updated for Binance fetch spec-sync side effect.
- [x] `docs/DATA_FLOW.md` - updated fetch and venue-spec flows.
- [x] `docs/FEATURE_MAP.md` - updated market-data ownership/tests.
- [x] `docs/AI_HANDOFF.md` - updated current change context.
- [x] `docs/CURRENT_STATE.md` - updated current working state and next action.

## Invariants / golden cases
- Invariants checked: R1.4 reviewed; no invariant text changed.
- Golden cases affected: N/A.

## Tests / checks run
- `python -m pytest -p no:cacheprovider tests/unit/test_routes_data_export.py tests/unit/test_routes_data_queue.py tests/unit/test_routes_data_delete.py tests/unit/test_replay_ct_val_resolution.py tests/unit/test_replay_ct_val_provenance_tag.py -v` - passed, 33 tests.
- `python scripts/docs/check_doc_metadata.py` - passed with 14 pre-existing lifecycle metadata warnings.
- `python scripts/docs/check_feature_map_links.py` - passed.
- `python scripts/docs/check_doc_impact.py` with `GIT_CONFIG_* safe.directory` env - passed, 8 changed tracked files and no impact-matrix violations.
- `node --check` on frontend JS files - passed.
- `git -c safe.directory=C:/quant_strategy diff --check` - exit 0; emitted CRLF conversion warnings only.

## Risks and rollback
- Risks: environments missing migration `0011_venue_instrument_specs.sql` will
  still fail the fetch; Binance symbols downloaded before this fix may need a
  fresh fetch or manual seed to populate the table.
- Rollback: revert this manifest plus the scoped changes to `routes_data.py`,
  `tests/unit/test_routes_data_export.py`, and the updated docs.

## Approval
- Human approval required: yes - user explicitly asked Codex to fix the Binance
  `1000SHIB-USDT-SWAP` missing `ct_val` replay failure.
