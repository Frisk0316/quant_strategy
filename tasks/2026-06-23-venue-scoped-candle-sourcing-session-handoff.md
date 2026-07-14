---
status: archived
type: handoff
owner: codex
created: 2026-06-23
last_reviewed: 2026-06-23
expires: none
superseded_by: null
---

# Session Handoff: Venue-Scoped Candle Sourcing - 2026-06-23

## Implementation summary
Implemented venue-scoped candle sourcing for replay: exchange-tagged candle loads now route to canonical Postgres with `source_primary=<exchange>`, refuse provenance-less parquet fallback, propagate the run exchange through replay synthetic L1 construction, and raise explicit venue-gap errors. Regenerated MA/EMA/MACD Binance 1H `strategy_fill` runs and produced a new MA source-provenance DB-parity PASS artifact.

## Diff scope
- Files added: `docs/change_manifests/2026-06-23-venue-scoped-candle-sourcing.md`, this handoff pair, new ignored result run/validation directories, six `SUPERSEDED.md` notes under stale result dirs.
- Files changed: `backtesting/data_loader.py`, `backtesting/replay.py`, `scripts/run_replay_backtest.py`, `scripts/run_validation_lab_signal_order_check.py`, `src/okx_quant/api/routes_backtest.py`, `tests/unit/test_data_loader.py`, `docs/DOMAIN_RULES.md`, `docs/INVARIANTS.md`, `docs/DATA_FLOW.md`, `docs/GOLDEN_CASES.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `docs/validation_lab_report_zh.md`.
- Files deleted: none.

## Business-rule change?
- Yes. Change Manifest at `docs/change_manifests/2026-06-23-venue-scoped-candle-sourcing.md`; DOC_IMPACT_MATRIX checked rows A5 and A7.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A.
- config/: N/A.
- ADR: N/A; restores ADR-0007 venue-scoped source intent without schema/gate changes.

## Experiments
- HYPOTHESIS_LEDGER entries: none.
- EXPERIMENT_REGISTRY entries: none.

## Tests / checks run
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_data_loader.py -q` - PASS, 7 passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_backtesting.py -q` - PASS, 49 passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_data_loader.py tests\unit\test_backtest_request_exchange.py tests\unit\test_multi_venue_convergence.py tests\unit\test_backtest_visual_fallbacks.py -q` - PASS, 38 passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\run_engine_consistency_smoke.py` - PASS, MA/EMA/MACD fixture rows passed.
- Direct docs-check equivalents passed: `check_doc_metadata.py` with 14 pre-existing warnings, `check_feature_map_links.py` clean.
- `check_doc_impact.py --strict` with Git safe-directory env - PASS.
- `git -c safe.directory=C:/quant_strategy diff --check` - PASS; line-ending warnings only.
- `scripts\run_validation_lab_signal_order_check.py --max-order-notional-usd 250 --max-pos-pct-equity 1.0 --execution-profile strategy_fill --run-suffix venue_scoped_pg_20260623` - PASS.
- `scripts\run_source_provenance_validation.py --run-id validation_lab_ma_crossover_btc_binance_1h_20260622_venue_scoped_pg_20260623 --engines vectorbt --validation-id codex_venue_scoped_pg_db_parity_20260623_pass` with DB parity env - PASS.

## Docs updated
- `docs/DOMAIN_RULES.md`, `docs/INVARIANTS.md`, `docs/DATA_FLOW.md`, `docs/GOLDEN_CASES.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `docs/validation_lab_report_zh.md`, Change Manifest, context/session handoffs.

## Known limitations / risks
- Explicit venue-scoped runs now require reachable Postgres; local no-DB development should avoid passing an exchange into candle loads or use legacy fixture paths.
- MA DB parity is reproduced; EMA/MACD were regenerated and spot-checked for the Binance 2024-04-29 close but were not separately source-provenance validated.
- All regenerated runs are `strategy_fill` idealized evidence, not promotion/live evidence.

## Rollback plan
- Revert the listed code/docs changes and remove the new regenerated result directories plus supersession notes.

## Context Handoff
- See `tasks/2026-06-23-venue-scoped-candle-sourcing-context-handoff.md`.

## Questions for human review
- Should EMA and MACD receive their own DB-parity validation artifacts, or is the MA source-data proof sufficient for the report slice?
- Should we add a dedicated context pack for canonical candle/provenance work?

## Next recommended task
- Claude/human review this diff for source-provenance scope, then decide whether to run EMA/MACD source-provenance validations or move to the next validation-lab gap.

## Human Learning Notes (required)
The main surprise was that a correct DB repair still produced wrong evidence because the replay loader was not carrying venue scope. Future source-data fixes should verify the consumer path immediately, not only the repaired rows.
