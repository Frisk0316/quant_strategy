# Context Handoff: Deribit data ingestion and frontend - 2026-07-11

## Goal (one sentence)
Implement Deribit DVOL, funding, option surface, option flow, and frontend external-series read path from the signed-off D1-D5 task plan without changing strategy, risk, execution, or DB schema semantics.

## Current state
- Branch: `codex/pipeline-batch1-stage3`.
- Last known good state: full unit suite passes locally (`637 passed`) after the Deribit changes.
- In-progress edits (files): Deribit clients/scripts/tests, `config/external_data.yaml`, `scripts/market_data/ingest_external.py`, `src/okx_quant/api/routes_data.py`, `frontend/data.js`, `frontend/view-config.js`, docs, `config/workstreams.yaml`, and this handoff pair.
- What works right now: D2 hourly DVOL and D1 funding backfills are complete through 2026-07-10 23:00 UTC; D3 option-surface snapshot script stored one live BTC/ETH snapshot; D5 external-series API and Run Backtest Derivatives context card are browser-verified.
- What does not work / unfinished: D4 full option-flow backfill is not complete. BTC is stored through 2024-02-06 23:00 UTC and ETH through 2024-01-31 23:00 UTC.

## Decisions made (and why)
- Use existing `external_observations` schema and `ExternalDataStore` because the signed-off architecture explicitly forbids new tables/migrations.
- Store Deribit hourly DVOL as `dvol_deribit_btc_1h` / `dvol_deribit_eth_1h` because existing daily DVOL dataset ids remain daily and should not be silently changed.
- Store funding `value_num = interest_1h` with `fields.unit = rate_1h_decimal` because Deribit funding history exposes hourly event rows.
- Store option-surface rows as forward-only snapshots because Deribit public surface/open-interest data is live-only.
- Aggregate D4 inverse option trades only and record USDC-linear exclusions because the task file pre-registered v1 aggregation semantics.
- Verify D5 manually with `dvol_deribit_btc_1h` because that is the newly backfilled hourly dataset; legacy `dvol_deribit_btc` had no rows in this DB.

## Open questions / unverified assumptions
- Premium-currency units: option-flow premium is recorded in BTC/ETH units for inverse instruments; Claude should confirm the research interpretation.
- Endpoint deviations: DVOL continuation behaves as a backward timestamp cursor; funding history returns capped latest rows; option history returns `{trades, has_more}`.
- History-host rate limits: <=5 req/s worked for pilot/full start, but the full D4 run is hours-scale and should be monitored.

## Rules in play (preserve verbatim)
- Invariants touched: none.
- Domain rules touched: none.
- Do-not-touch: `research/`, `results/**`, strategies/signals/risk/portfolio/execution, `config/risk.yaml`, deployment/shadow/demo/live gates, existing migrations, and backtesting engine semantics.

## Context to load next (the reading list)
- Source of truth: `tasks/2026-07-11-deribit-data-ingestion-tasks.md`, `research/deribit_data_strategy_research.md` sections 1-2, `config/external_data.yaml`.
- Owning files / MODULE_BRIEFS: `docs/FEATURE_MAP.md`, `docs/UI_MAP.md`, `docs/DATA_FLOW.md`, `docs/RUNBOOK.md`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run
- `node --check frontend\data.js` - passed.
- `node --check frontend\view-config.js` - passed.
- `python -m pytest tests/unit -k "deribit"` - 13 passed.
- `python -m pytest tests/unit` - 637 passed.
- `python scripts/docs/check_doc_metadata.py` - passed.
- `python scripts/docs/check_feature_map_links.py` - passed.
- `python scripts/docs/check_doc_impact.py --strict` with `safe.directory` env config - passed, 44 changed files, 0 violations.
- Browser check on `http://localhost:8080` - Derivatives context card rendered `dvol_deribit_btc_1h`, SVG chart present, `/api/data/external-series?...` returned 200.

## Approvals
- Human approval obtained: 2026-07-11 sign-off for D1-D5 and starting D3 snapshot collection.
- Human approval still needed: user must register the Windows scheduled task for `snapshot_deribit_options.py`; Codex did not register it.

## Next action (single, concrete)
- Resume D4 with: `python scripts\market_data\backfill_deribit_option_flow.py --start 2024-01-01T00:00:00+00:00 --end 2026-07-11T00:00:00+00:00 --resume`.

## Human Learning Notes
Deribit's public endpoints are usable but not uniform: DVOL, funding, and option history each paginate differently. The existing external-observation harness was flexible enough, but long history-host backfills should be treated as resumable data operations rather than something to cram into a single interactive session.
