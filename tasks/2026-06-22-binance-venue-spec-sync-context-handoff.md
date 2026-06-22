# Context Handoff: Binance Venue Spec Sync - 2026-06-22

## Goal (one sentence)
Fix Binance replay failures for downloaded multiplier contracts such as `1000SHIB-USDT-SWAP` by syncing Binance venue specs during market-data fetch.

## Current state
- Branch: `codex/impl-multi-venue-instrument-specs`.
- Last known good commit / state: branch already carried ADR-0007 P1, price-chart integration, and uncommitted Market Data Coverage queue/delete work.
- In-progress edits (files): `src/okx_quant/api/routes_data.py`, `tests/unit/test_routes_data_export.py`, docs and manifest listed in the session handoff.
- What works right now: Binance `exchangeInfo` filters are parsed into instrument metadata; fetch upserts `venue_instrument_specs(exchange, symbol)` before candle writes or skipped-result reporting; targeted pytest and docs checks pass.
- What does not work / unfinished: no real DB-backed Binance fetch was executed in this sandbox; existing Binance candles downloaded before this fix may still need a fresh fetch or manual seed before replay.

## Decisions made (and why)
- Kept `ReplayBacktestEngine._resolve_swap_ct_val` unchanged because ADR-0007 intentionally requires DB specs for canonical `1000...` multiplier contracts; relaxing replay would hide venue metadata gaps.
- Wrote Binance specs from `exchangeInfo` during fetch because the data acquisition path already has the authoritative native symbol and precision metadata.
- Used `source = binance_exchange_info` in `venue_instrument_specs` so DB rows remain auditable even though replay provenance reports them as DB-backed authority.

## Open questions / unverified assumptions
- Real DB smoke still pending: run a Binance fetch for `1000SHIB-USDT-SWAP`, confirm `venue_instrument_specs` has the row, then rerun the failing replay.

## Rules in play (preserve verbatim)
- Invariants touched: R1.4 reviewed; no invariant text changed.
- Domain rules touched: R1.4 venue-matched authoritative `ct_val`; R6.2 data provenance/source agreement.
- Do-not-touch: `src/okx_quant/strategies/`, `src/okx_quant/signals/`, `src/okx_quant/risk/`, `src/okx_quant/portfolio/`, `src/okx_quant/execution/`, `config/`, `backtesting/`, existing result artifacts, deployment gates.

## Context to load next (the reading list)
- Source of truth: `AI_CONTEXT.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `docs/DATA_FLOW.md`, `docs/FEATURE_MAP.md`, `docs/ADR/0007-multi-venue-instrument-specs.md`.
- Owning files / MODULE_BRIEFS: Market Data Ingestion row in `docs/FEATURE_MAP.md`; `src/okx_quant/api/routes_data.py`; `tests/unit/test_routes_data_export.py`.
- Context Pack: no dedicated market-data pack exists; use `docs/CONTEXT_INDEX.md`.

## Checks run
- `python -m pytest -p no:cacheprovider tests/unit/test_routes_data_export.py tests/unit/test_routes_data_queue.py tests/unit/test_routes_data_delete.py tests/unit/test_replay_ct_val_resolution.py tests/unit/test_replay_ct_val_provenance_tag.py -v` - passed, 33 tests.
- `python scripts/docs/check_doc_metadata.py` - passed with 14 pre-existing lifecycle metadata warnings.
- `python scripts/docs/check_feature_map_links.py` - passed.
- `python scripts/docs/check_doc_impact.py` with `GIT_CONFIG_* safe.directory` env - passed, 8 changed tracked files and no impact-matrix violations.
- `node --check` on frontend JS files - passed.
- `git -c safe.directory=C:/quant_strategy diff --check` - exit 0; emitted CRLF conversion warnings only.

## Approvals
- Human approval needed / obtained: user explicitly approved fixing the Binance missing `ct_val` replay failure; human still needs to approve merge and real DB smoke.

## Next action (single, concrete)
- Run a DB-backed Binance fetch for `1000SHIB-USDT-SWAP` or seed `venue_instrument_specs`, then rerun the latest replay that previously failed.

## Human Learning Notes
Downloaded Binance candles do not imply `venue_instrument_specs` has been seeded. For `1000...` canonical symbols, the replay guard is intentionally strict; the right fix is to seed/sync venue metadata, not to fall back to `exchange_base_unit`.
