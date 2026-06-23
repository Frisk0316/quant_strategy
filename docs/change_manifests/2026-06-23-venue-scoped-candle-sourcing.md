---
status: current
type: manifest
owner: codex
created: 2026-06-23
last_reviewed: 2026-06-23
expires: none
superseded_by: null
---

# Change Manifest: Venue-Scoped Candle Sourcing

## Summary
Venue-tagged replay candle reads now use exchange-scoped canonical Postgres
candles and fail loudly on missing venue bars instead of falling back to
source-less parquet or another venue.

## Business rule(s) affected
R6.2, R6.4.

## Trigger area(s) (DOC_IMPACT_MATRIX)
A5 backtesting; A7 API resolver touch. Data provenance is a business-rule area.

## Files changed
- `backtesting/data_loader.py` - forces venue-tagged candle reads to Postgres canonical source scope and raises explicit venue gaps.
- `backtesting/replay.py` - propagates the run exchange into synthetic L1 candle loads.
- `scripts/run_replay_backtest.py` - explicit `--exchange` runs force Postgres candles and refuse no-DSN parquet fallback.
- `scripts/run_validation_lab_signal_order_check.py` - Validation Lab Binance checks force Postgres candle sourcing.
- `src/okx_quant/api/routes_backtest.py` - backend resolver refuses parquet fallback for venue-scoped requests.
- `tests/unit/test_data_loader.py` - regression coverage for wrong-venue/parquet substitution, fail-loud gaps, and replay exchange propagation.
- `docs/DOMAIN_RULES.md`, `docs/INVARIANTS.md`, `docs/DATA_FLOW.md`, `docs/GOLDEN_CASES.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `docs/validation_lab_report_zh.md` - provenance rule and current evidence updates.
- `results/validation_lab_*_venue_scoped_pg_20260623/` - new regenerated Validation Lab run artifacts.
- `results/validation_lab_ma_crossover_btc_binance_1h_20260622_venue_scoped_pg_20260623/validation/codex_venue_scoped_pg_db_parity_20260623_pass/` - new MA DB-parity PASS evidence.
- `results/**/SUPERSEDED.md` - notes marking stale 2026-06-22 strategy-fill and failed `_20260623_binance_rebuilt` runs superseded.

## Behavior delta
- Before: A Binance-tagged replay could read source-unscoped candles, allowing an OKX/parquet value such as `63258.8` on 2024-04-29 to enter a Binance run.
- After: A Binance-tagged replay reads canonical candles with `source_primary=binance`; 2024-04-29 00:00 close is `63229.2`, and missing Binance bars raise an explicit gap.
- Money/risk impact: no fill, PnL, fee, funding, sizing, risk, or gate math changed. Research conclusions using stale source-unscoped artifacts must be superseded.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A - no strategy assumption changed.
- config/: N/A - no runtime config changed.
- ADR: N/A - restores ADR-0007 venue-scoped source intent; no new policy or schema.

## Docs updated (from DOC_IMPACT_MATRIX row)
- [x] `docs/DATA_FLOW.md` - updated venue-scoped candle flow and parquet fallback boundary.
- [x] `docs/FEATURE_MAP.md` - reviewed; owning files/tests already identify Backtest Run UI and Canonical Candle Pipeline, no ownership change.
- [x] `docs/GOLDEN_CASES.md` - added G-002 for venue-scoped candle loading.
- [x] ADR-0002/0005 - reviewed; no result schema or validation-gate change.
- [x] `docs/DOMAIN_RULES.md` / `docs/INVARIANTS.md` - added R6.4 and I19.

## Invariants / golden cases
- Invariants checked: I12, I16, I19.
- Golden cases affected: G-002 added.

## Tests / checks run
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_data_loader.py -q` - PASS, 7 passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_data_loader.py tests\unit\test_backtest_request_exchange.py tests\unit\test_multi_venue_convergence.py -q` - PASS, 13 passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_backtest_visual_fallbacks.py -q` - PASS, 25 passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_backtesting.py -q` - PASS, 49 passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_data_loader.py tests\unit\test_backtest_request_exchange.py tests\unit\test_multi_venue_convergence.py tests\unit\test_backtest_visual_fallbacks.py -q` - PASS, 38 passed.
- `scripts\run_validation_lab_signal_order_check.py --max-order-notional-usd 250 --max-pos-pct-equity 1.0 --execution-profile strategy_fill --run-suffix venue_scoped_pg_20260623` - PASS, regenerated MA/EMA/MACD runs.
- `scripts\run_source_provenance_validation.py --run-id validation_lab_ma_crossover_btc_binance_1h_20260622_venue_scoped_pg_20260623 --engines vectorbt --validation-id codex_venue_scoped_pg_db_parity_20260623_pass` with `DIFF_VALIDATION_ENABLE_DB_PARITY=1` and repo DSN - PASS.
- `make docs-impact`, `make docs-check`, `make engine-consistency-smoke` - not available directly because `make` is not installed in this Windows shell.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_doc_impact.py --strict` with Git safe-directory env - PASS, 16 changed files, no violations.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_doc_metadata.py` - PASS with 14 pre-existing metadata warnings.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_feature_map_links.py` - PASS.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\run_engine_consistency_smoke.py` - PASS, 3 strategy fixtures.
- `git -c safe.directory=C:/quant_strategy diff --check` - PASS; line-ending warnings only.

## Risks and rollback
- Risks: local no-DB runs that explicitly declare an exchange now fail instead of falling back to parquet; this is intentional for provenance.
- Rollback: revert the changed code/docs and delete the new regenerated result directories plus supersession notes.

## Approval
- Human approval required: yes - task explicitly requested this scope on 2026-06-23.
