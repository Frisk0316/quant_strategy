# Session Handoff: Deribit data ingestion and frontend - 2026-07-11

## Implementation summary
Implemented the signed-off Deribit D2-D5 plan in the requested order: hourly DVOL, funding, option-surface snapshot ingestion, option-flow hourly aggregates, and a frontend/API read path for external derivative context. D2/D1 backfills and one D3 live snapshot are complete; D4 pilot passed but full backfill is checkpointed and unfinished; D5 is browser-verified.

## Diff scope
- Files added: `src/okx_quant/data/external_clients/deribit_funding.py`, `src/okx_quant/data/external_clients/deribit_option_surface.py`, `src/okx_quant/data/external_clients/deribit_option_flow.py`, `scripts/market_data/snapshot_deribit_options.py`, `scripts/market_data/backfill_deribit_option_flow.py`, `tests/unit/test_deribit_dvol_client.py`, `tests/unit/test_deribit_funding_client.py`, `tests/unit/test_deribit_option_surface.py`, `tests/unit/test_deribit_option_flow.py`, `tests/unit/test_routes_data_external_series.py`, this context handoff, this session handoff.
- Files changed: `src/okx_quant/data/external_clients/deribit_dvol.py`, `src/okx_quant/data/external_clients/__init__.py`, `scripts/market_data/ingest_external.py`, `config/external_data.yaml`, `src/okx_quant/api/routes_data.py`, `frontend/data.js`, `frontend/view-config.js`, `docs/DATA_FLOW.md`, `docs/RUNBOOK.md`, `docs/UI_MAP.md`, `docs/FEATURE_MAP.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `config/workstreams.yaml`.
- Files deleted: none. Generated `.playwright-cli` temp output was removed.

## Business-rule change?
- No. `docs/DOC_IMPACT_MATRIX.md` was checked; API/frontend rows A7/A8 are Manifest=No, and no PnL, fee, funding cashflow, sizing, fill, risk, gate, strategy, or schema rule changed. `check_doc_impact.py --strict` passed with 0 violations.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A.
- config/: `config/external_data.yaml` and `config/workstreams.yaml` updated.
- ADR: N/A.

## Experiments
- HYPOTHESIS_LEDGER entries: none.
- EXPERIMENT_REGISTRY entries: none.

## Tests / checks run
- `node --check frontend\data.js` - passed.
- `node --check frontend\view-config.js` - passed.
- `python -m pytest tests/unit -k "deribit"` - 13 passed.
- `python -m pytest tests/unit` - 637 passed.
- `python scripts/docs/check_doc_metadata.py` - passed.
- `python scripts/docs/check_feature_map_links.py` - passed.
- `python scripts/docs/check_doc_impact.py --strict` with `safe.directory` env config - passed, 44 changed files, 0 violations.
- DB row/gap summary: D2 hourly DVOL 22,128 rows per currency, no >2h gaps; D1 funding 22,127 rows per currency, no >2h gaps; D3 surface 1 row per currency; D4 current stored BTC 888 rows through 2024-02-06 23:00 UTC and ETH 744 rows through 2024-01-31 23:00 UTC, no >6h gaps in stored range.
- Browser check: Run Backtest Derivatives context card rendered `dvol_deribit_btc_1h`, SVG chart present, last point displayed, `/api/data/external-series?...` returned 200.

## Docs updated
- `docs/DATA_FLOW.md`, `docs/RUNBOOK.md`, `docs/UI_MAP.md`, `docs/FEATURE_MAP.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `config/workstreams.yaml`, and handoff files under `tasks/`.

## Known limitations / risks
- D4 full 2024-01-01 to 2026-07-11 option-flow backfill is not complete; resume command is documented in the context handoff.
- D5 manual browser check used `dvol_deribit_btc_1h` because the legacy daily `dvol_deribit_btc` dataset had no rows in this DB.
- Deribit endpoint behavior differed in pagination shape from a plain continuation-token model; implementation handles observed behavior, but Claude should review the deviations before strategy design.
- Full history-host backfill is hours-scale; rate limits should be monitored at <=5 req/s.

## Rollback plan
- Revert the added Deribit clients/scripts/tests, `config/external_data.yaml` dataset entries, `ingest_external.py` dispatch additions, `routes_data.py` external-series route, and frontend card/helper changes. If DB data must be rolled back, delete only the new Deribit dataset ids from `external_observations`, `external_datasets`, `external_fetch_jobs`, and `external_ingestion_checkpoints` after taking a DB backup.

## Context Handoff
- See filled context handoff at: `tasks/2026-07-11-deribit-data-ingestion-context-handoff.md`.

## Questions for human review
- Should Claude treat inverse-option premium amounts in BTC/ETH units as the research signal unit, or convert to USD notional before H-013?
- Are the endpoint deviations acceptable to record as implementation notes, or should the research doc be amended before H-013?
- Should the full D4 history-host backfill be run overnight as a separate supervised data job?

## Next recommended task
- Resume and complete D4 full option-flow backfill, then rerun the task-file gap scan and ask Claude to review premium units, endpoint deviations, and history-host rate limits before drafting F-VRP-TIMING H-013.

## Human Learning Notes (required)
The main surprise was that all four Deribit public surfaces paginate differently enough to require endpoint-specific clients. The repo's existing external data store absorbed the new datasets cleanly, but long historical option-tape ingestion needs checkpoint-first operational thinking, not an all-at-once mindset.
