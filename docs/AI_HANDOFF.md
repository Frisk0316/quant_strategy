---
status: current
type: handoff
owner: human
created: 2026-05-11
last_reviewed: 2026-05-17
expires: none
superseded_by: null
---

> **2026-05-14 architecture shift**: `storage.candle_backend` default flipped to `postgres`; `download_okx_data.py` / `download_binance_data.py` now write parquet + TimescaleDB simultaneously via `scripts/_db_writer.py`. Falls back to parquet when no DSN is reachable. See "Current Change Context" row "DB-primary backtest path".

# AI Handoff

Cross-session memory for Claude and Codex. **Read this before starting any task. Update this before ending any session.**

---

## Current Goal

Implement position-aware close sizing for pairs trading exit/stop flows after design review.

## Current Branch

`main`

## Last Known Good Commit

`cb022c5` — Add TradesView, CompareView, and RiskView components  
_(Status: tests/unit pass locally; integration tests require TimescaleDB — not confirmed clean in CI)_

## System Overview

| Layer | Key files |
|---|---|
| Strategies | `src/okx_quant/strategies/` — funding_carry, pairs_trading, as_market_maker, obi_market_maker |
| Signals | `src/okx_quant/signals/` |
| Portfolio | `src/okx_quant/portfolio/` — sizing, position ledger |
| Execution | `src/okx_quant/execution/` — broker, replay_execution |
| Risk | `src/okx_quant/risk/` — risk guard, drawdown, circuit breaker |
| Backtesting | `backtesting/` — replay engine, CPCV, walk-forward, artifacts |
| API | `src/okx_quant/api/` — FastAPI server, backtest routes |
| Frontend | `frontend/` — dashboard, backtest viewer, charts |
| Data | TimescaleDB — OHLCV, funding rates, canonical candles |
| Config | `config/settings.yaml`, `config/strategies.yaml`, `config/risk.yaml` |

## Current Change Context

| Commit / PR | Change | Risk |
|---|---|---|
| CME yfinance research proxy `(complete; research-only)` | `cme_btc_yfinance` dataset wired via a new yfinance optional adapter (`config/external_data.yaml`, ingest, analyzer NaN-safe JSON, tests). 598 daily OHLC rows ingested for 2024-01-01 → 2026-05-19; `results/cme_gap_research.json` now populated with 112 gaps, 82.1% fill probability, but the reverse-gap trade simulation shows total return -33.3%, Sharpe -0.52, max drawdown -49.2% on 109 trades (win rate 76% but 27 timeouts sum -12,978 bps vs. 82 fills +9,791 bps). Up-gaps (short BTC) drive the loss. `research/strategy_synthesis.md` Strategy 10 and the Research Feature Data Caveats now classify this as a research-only proxy and document the structural improvements (stop-loss, dust-bucket exclusion, hold-time cap, optional direction filter) pending Codex implementation. | Research-only. Numbers from `cme_btc_yfinance` are **not** admissible as deployment / promotion / shadow evidence; any artefact citing them must carry `source: research_proxy_only`. Yahoo `BTC=F` has quote delay, undocumented continuous stitching, and Yahoo-specific adjustments; not interchangeable with the official CME settle. Even after the recommended structural fixes, in-sample positive expectancy is not validated alpha. |
| External-feature research baselines doc `(complete; docs-only)` | `research/strategy_synthesis.md` adds Strategy 9 (Crypto F&G long-flat sentiment baseline — `Fear`/`Neutral` are intentional hold states, only `Greed`/`Extreme Greed` trigger exit), Strategy 10 (CME daily weekend-gap research baseline — daily cadence with `publish_lag_days=1`, explicitly not a real-time gap-fill strategy), and a Research Feature Data Caveats section covering DGS10 latest-vintage / non-PIT semantics, F&G label-stability dependency, and the discontinued `CHRIS/CME_BTC1` source. Promotion Checklist extended with ct_val provenance, ADR-0006 reduce-only audit, and an External-Feature Coverage Gate (event_count > 0 for required datasets, stale-rate ≤ 10%, missing-rate ≤ 5%, plus per-dataset vintage / source-stability / label-stability attestations). | Documentation-only; no strategy or risk code touched. Codified caveats only; strategies remain `enabled: false` with `research_only: true` signal metadata. |
| MA/MACD long-flat position fix `(committed 8a4f5f9; follow-up pending commit)` | Technical indicator strategies remain long/flat baselines for research acceptance and parameter tuning. Patch fixes partial-exit state handling, replacement cancellation, long/flat-only ledger close sizing, lot-rounded replay partial fills, and incremental EMA/MACD state matching `ewm(adjust=False)`. Reduce-only risk semantics are scoped to long/flat close orders; fat-finger still blocks reduce-only orders, while allowed reduce-only bypasses for kill/position-limit/daily-stop are logged from `RiskGuard.check()` and written to replay `risk_events` with `allowed_reduce_only_bypass:*`. | Not live-ready. MA/MACD profitability is not established; ct_val gate still blocks promotion when provenance is non-authoritative. Pairs/funding-carry close sizing is intentionally unchanged until P2 design implementation is separately approved. |
| Chart UX overhaul fix-up `(complete; pending Claude re-review)` | Backtest viewer market charts now share one `market` X range across price and indicator panels; reset controls split X vs Y semantics; per-panel Y zoom uses shared `MAX_Y_ZOOM`; drawdown Y zoom anchors at the minimum; MACD sub-panel Y zoom is independent; indicator cards show `warmup_source`; metrics glossary is available from the left nav; artifact indicators default to cold-start strategy-aligned values with `indicator_db_warmup` opt-in and `result.validation.indicator_warmup_sources`. | Pending Claude re-review. DB warmup is an opt-in visual aid and can intentionally diverge from cold-start strategy marker timing if enabled. RangeBrush click-outside behavior, binary-search range slicing, and wheel/keyboard zoom remain backlog. |
| Chart zoom + indicator visualization + DB-primary backtest `(complete; pending Codex verification)` | Frontend brush-zoom (now timestamp-domain) across all charts with shared `chartRange` + reset toolbar; per-symbol `IndicatorChart` (price + fast/slow + MACD sub-panel) wired to a new `/api/backtest/{run_id}/indicators` route reading `indicator_series.csv` recomputed at artifact time from `price_series`; download scripts now mirror parquet writes into `raw_candles` + `canonical_candles` via `scripts/_db_writer.py`; canonical writes share `okx_quant.data.canonical_policy` priority `manual > binance > okx > bybit > coinbase/kraken > other`, used by `_db_writer.py`, `CandleStore.canonicalize_from_raw()`, `CandleStore.canonicalize_from_market_klines()`, and `CandleStore.upsert_canonical_candles()`; `routes_backtest._resolve_candle_backend()` + `StorageConfig.candle_backend` default to `postgres` with TCP-probe-based parquet fallback when DSN missing or unreachable; `_to_naive_utc_index` normalises Binance tz-aware vs OKX tz-naive parquet on read; new `config/instrument_specs.yaml` registry + `_resolve_swap_ct_val` writes per-symbol provenance (`db` / `registry` / `hardcoded_btc_eth` / `config_override` / `spot_unit`) into `result.validation.ct_val_sources` with a `ct_val_all_authoritative` boolean for the live/shadow/demo deployment gate | Postgres-by-default may surprise environments without `DATABASE_URL`; fallback is logged but silent in the API. `indicator_series.csv` is additive (does not break ADR-0002 schema). No `src/okx_quant/strategies/` changes. ct_val gate forbids promotion to live unless every symbol's ct_val came from `db`/`config_override`/`spot_unit`; `registry` / `hardcoded_btc_eth` are backtest-only and require explicit reviewer override to ship. |
| P0 web security hardening `(committed fca239f)` | Add API key protection for FastAPI routes/WebSocket, close Swagger UI, add CORS allowlist, and tighten Docker env/port bindings | API clients must send `X-Api-Key` when `API_KEY` is set; standalone `scripts/run_server.py` remains out of scope |
| OHLCV/backtest UI fix `(committed ed283d7, 6d1fd41)` | Fix OHLCV exit code 1, equity scale, drawdown, chart width, background jobs, progress, warm-up transparency, and volume-threshold diagnostics | Frontend + backtest script + routes only; no risk/portfolio code touched |
| P2 position-aware close sizing design `(complete; pending review)` | Design pairs trading exit/stop close sizing from ledger positions | PM owns close sizing; implementation must guard to `pairs_trading`, preserve funding carry dual-leg exit behavior, and handle integer-lot float drift |
| P2 shadow calibration test `(complete; pending review)` | Add mirror fill positive routing unit coverage | `ExecutionHandler.on_fill_ws()` now has mock coverage for filled and partially_filled shadow mirror fills routing to `CalibrationLogger.record_fill()` |
| Daily winner frontend `(complete; pending commit)` | Wire daily_winner into frontend strategy dropdown + Run Backtest UI | `frontend/data.js` adds strategy entry with tag=Validation; `frontend/view-config.js` adds universe checkbox, bar locked to 1D, StrategyParams; `routes_backtest.py` adds daily_winner to allowed set, `_run_daily_winner_job` embeds equity/returns/trades in result.json (no CSV artifacts) |
| OHLCV rotation frontend `(complete; uncommitted)` | Wire ohlcv_rotation into frontend strategy dropdown + Run Backtest UI | `frontend/data.js` adds strategy entry; `frontend/view-config.js` adds universe checkbox, benchmark, rebalance_min, top_k controls; `routes_backtest.py` adds ohlcv_rotation to allowed set, new job + post-process functions, and extra request fields |
| OHLCV rotation `(merged)` | Add Phase 1 OHLCV rotation research/backtest workflow | Vectorised strategy/backtest, CLI, synthetic tests, and XLSX export support added separately from PR14B |
| PR14B `(merged)` | Implement shadow mode parity fixes | `run_shadow.py` now requires `mode=shadow`; shadow primary SimBroker receives instrument specs; broker routing tests added |
| PR14A `(merged)` | Design shadow mode parity plan | `docs/shadow_mode_parity_plan.md` documents current ShadowBroker path, remaining gaps, and PR14B scope |
| PR13 `(merged)` | Implement remaining ADR-0005 replay validation gates | Gate 2 fill-rate warning, Gate 3 data coverage, Gate 4 funding coverage implemented; ADR-0005 moved to Accepted |
| PR12B | Implement replay terminal liquidation | Gate 1 terminal position check implemented via `validation["terminal_positions_closed"]`; replay default closes terminal positions; CLI can opt out; focused regression tests added |
| PR12A | Add replay terminal liquidation design plan | Docs-only design; no replay behavior change |
| PR11 | Add funding carry dual-leg regression tests for signal metadata and PM order alignment | Test-only coverage for long spot + short perp carry behavior |
| PR10B | Add pairs exit/stop hedge close metadata and remove hedge metadata xfail | Strategy metadata only; sizing remains unchanged |
| PR10 | Add pairs trading hedge-close regression coverage | Test-only coverage for linked hedge close behavior |
| PR9 | Add backtest artifact schema regression tests for ADR-0002 frozen fields | Test-only coverage for artifact contract |
| PR8 | Add frontend MIME smoke tests for `.js` and legacy `.jsx` ES modules | Test-only coverage for FastAPI StaticFiles MIME behavior |
| PR7 | Add branch/version management policy and PR template checklist | Governance docs only |

## Latest Codex Verification Commands

Chart UX review fix-up + indicator warmup alignment, run on 2026-05-17:

- `node --check frontend/charts.js` - passed
- `node --check frontend/view-backtest.js` - passed
- `node --check frontend/view-glossary.js` - passed
- `node --check frontend/app.js` - passed
- `& 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' -m pytest tests/unit/test_frontend_static_mime.py -v` - 2 passed
- `& 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' -m pytest tests/unit/test_backtesting.py::test_indicator_series_uses_warmup_candles_before_trimming tests/unit/test_backtesting.py::test_indicator_series_trims_leading_rows_when_warmup_missing tests/unit/test_backtesting.py::test_indicator_series_ema_macd_default_cold_start_does_not_fetch_db tests/unit/test_backtesting.py::test_save_artifacts_records_indicator_warmup_sources -v` - 4 passed
- `& 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' -m pytest tests/unit/test_technical_indicator_strategies.py -v` - 5 passed
- `git -c safe.directory=C:/quant_strategy diff --check` - passed

Note: focused indicator artifact tests used explicit pytest node ids because pytest does not expand `::test_indicator_series_*` as a node-id glob. Pytest emitted a non-fatal cache permission warning for `.pytest_cache`.

## Known Bugs / Open Issues

1. **Shadow mode parity gap** (resolved in PR14B): `run_shadow.py` requires `mode=shadow`, and shadow primary `SimBroker` receives instrument specs for notional/fee accounting.
2. **SimBroker fill event gap** (P0): `ExecutionHandler.on_order()` expects WebSocket fill, but `SimBroker.submit()` does not emit a simulated fill event — blocks unified backtest/live engine path.
3. **Replay bar-level approximation** (P1): `scripts/run_backtest.py` uses per-bar approximation formulas, not the true `Strategy → Signal → Order → Fill → Ledger` path.
4. **CI gate is minimal**: `.github/workflows/ci.yml` runs ruff fatal-only baseline and unit tests only. This is a temporary baseline until existing lint debt is cleaned up; integration tests still require TimescaleDB planning.
5. **Missing regression tests**:
   - Frontend MIME smoke test exists.
   - Backtest artifact schema regression test exists.
   - Pairs trading hedge-close regression exists; exit/stop hedge metadata implemented.
   - Funding carry dual-leg regression exists.
   - Replay terminal liquidation regression tests exist.
   - Shadow mirror fill positive routing to `CalibrationLogger.record_fill()` is covered by a focused mock unit test for filled and partially_filled mirror updates.
6. **Pairs close sizing gap** (P2): Exit/stop order size is still driven by signal sizing rather than current ledger position. Position-aware close sizing design is documented in `docs/pairs_position_aware_close_sizing_plan.md`; implementation remains next. Funding carry also uses `metadata["action"] == "exit"`, so the implementation must make the close-sizing branch pairs-only unless a separate funding-carry design explicitly expands scope. The MA/MACD long-flat fix deliberately guards its close-sizing branch with `mode == "long_flat"` and does not implement this P2 pairs/funding-carry work.
7. **`test_run_replay_backtest_cli_passes_no_liquidate_on_end` fails** (P2): Test passes `--strategy as_market_maker` to `run_replay_backtest.py` which only accepts `{funding_carry, pairs_trading}`. Pre-existing Codex issue from commit `94a4222`. Not related to ohlcv_rotation changes.
8. **ADR-0005 replay validation gates**: Gates 1-4 are implemented and ADR-0005 is Accepted. Gate 1 terminal position check is implemented via `validation["terminal_positions_closed"]`; PR13 added Gate 2 fill-rate warning, Gate 3 data coverage, and Gate 4 funding coverage.
9. **OHLCV rotation 1m data missing** (data gap, not a code bug): `data/ticks/` only has `candles_1H.parquet` for BTC and ETH; no `candles_1m.parquet` and no SOL data. Running OHLCV rotation at 1m bar will fail at parquet level. Since 2026-05 download scripts also write `canonical_candles` and `routes_backtest` defaults to postgres backend, the DB Coverage panel (`canonical_candles`) is the authoritative source of "what bar/inst is queryable". For parquet-only environments, run `scripts/download_okx_data.py --inst BTC-USDT-SWAP --bar 1m` to populate files.
10. **No-trading for long periods** (multi-cause): For pairs trading, warm-up is 168h (7 days). For OHLCV rotation, regime filter suppresses trading when benchmark is below 240-min EMA. Both are expected behavior. `warmup_bars` and `data_coverage_pct` are now in the OHLCV rotation metrics. UI shows warm-up warning when date range < 3× warm-up time.
11. **Web API public exposure gap** (P0, patch committed): `src/okx_quant/api/server.py` now supports `API_KEY` auth for API routes and WebSocket handshakes, closes `/api/docs`, and applies optional `ALLOWED_ORIGINS`. Full deployment smoke test confirmation is still pending.
12. **Live WS partial-fill remaining-size metadata gap** (P1): Replay fills include `metadata["remaining_sz"]`, but `ExecutionHandler.on_fill_ws()` currently copies order-time metadata and does not derive remaining size from OKX `sz` / `accFillSz`. Long/flat strategies still work if OKX sends a final `state="filled"` update, but the live path should add remaining-size metadata and unit coverage before any promotion.
13. **MA/MACD research baseline doc gap** (P1 docs-only, **still open**): F&G sentiment and CME daily gap baselines are now documented in `research/strategy_synthesis.md` (Strategies 9-10), but the analogous MA/EMA/MACD long-flat baseline section is still missing. Add it as a separate docs-only update covering long/flat execution assumptions, partial-fill semantics, incremental EMA/MACD state, and OOS/WF/CPCV acceptance gates.
14. **External-feature deployment blockers** (P1): Documented in `research/strategy_synthesis.md` as required ADR attestations. Live blockers: (a) `CHRIS/CME_BTC1` is discontinued by Nasdaq Data Link and must be replaced before any CME-based research result is reproducible — migration 003 has been applied so `external_observations` exists, but `results/cme_gap_research.json` now reports `research_status.reason="missing_cme_data"` because ingest produces zero rows against the discontinued dataset code; (b) `dgs10` ingest uses latest-vintage upsert and is not point-in-time — any DGS10-conditioned signal must remain `research_only` or move to FRED ALFRED vintage ingest. **Resolved in code**: `fear_greed_btc` label-stability — `FearGreedSentimentParams` now ships a `validate_extreme_fear_label` allow-list validator plus numeric `extreme_fear_threshold` / `exit_value_threshold` fallbacks driven off `value_num`; promotion ADR can attest against this implementation rather than treating it as an open blocker.

## Do Not Touch (without explicit issue + user approval)

- `src/okx_quant/strategies/` — all strategy implementations
- `src/okx_quant/risk/` — risk guard, drawdown tracker, circuit breaker
- `src/okx_quant/portfolio/` — sizing, position ledger
- `src/okx_quant/execution/broker.py` — SimBroker and execution handler
- `config/risk.yaml` — risk limits
- Any file not listed in the current issue's permitted scope

## Next Steps (in order)

1. **[P0]** Claude re-review MA/MACD long-flat position fix follow-up, especially live/replay reduce-only bypass audit logging and ADR-0006.
2. **[P0]** Claude re-review Chart UX overhaul fix-up and indicator warmup alignment; confirm shared market X behavior, split reset semantics, cold-start artifact parity, and `warmup_source` UI/metadata.
3. **[P0]** Remaining DB-primary backend verification from prior handoff: end-to-end SOL download + backtest, DSN-invalid fallback path, and grep for stray `--backend parquet` outside fallback/tests.
4. **[P0]** Run deployment smoke tests for API key auth, CORS, WebSocket auth, and Docker port bindings before any public AWS deployment.
5. **[P1]** Add live WS remaining-size metadata from OKX `sz` / `accFillSz` and unit coverage before any MA/MACD promotion.
6. **[P1]** Claude docs-only update: add MA/EMA/MACD long-flat baseline section to `research/strategy_synthesis.md` (F&G + CME daily baselines and external-feature data caveats already added in this session).
6a. **[P1]** Replace `CHRIS/CME_BTC1` adapter target with a maintained CME BTC futures source; re-run `analyze_cme_gaps.py` once `external_observations` ingest succeeds, with roll-day and US-holiday filters in place before any CME-gap research claim.
6b. **[P1]** F&G label allow-list validator + numeric `value_num` thresholds are now in place (`FearGreedSentimentParams.validate_extreme_fear_label`, `extreme_fear_threshold`, `exit_value_threshold`). Remaining work for F&G promotion ADR is the Neutral/Fear hold-through DSR validation, not the validator itself.
7. **[P1]** Download 1m candle data for BTC-USDT-SWAP, ETH-USDT-SWAP, SOL-USDT-SWAP to enable 1m OHLCV rotation backtests (now routes through DB on download).
8. **[P2]** Review `docs/pairs_position_aware_close_sizing_plan.md`.
9. **[P2]** Implement position-aware close sizing after design review.

## Documentation Cleanup Next Step

After PR4 is merged, classify existing Markdown files with lifecycle metadata in a dedicated docs-only cleanup PR. Do not change strategy assumptions or implementation behavior during that cleanup.

## Open Questions

- Should `AI_WORKFLOW.md` content eventually be merged back into `ai_collaboration.md`, or kept separate permanently?
- Which commit is the last confirmed clean state for integration tests (requires DB)?
- Is `config/risk.yaml` the authoritative risk limit file or is there per-strategy risk config in `strategies.yaml`?

## Session Handoff Checklist

Before ending a session, confirm:

- [ ] Changed files listed
- [ ] Tests run (or reason stated why not)
- [ ] `AI_HANDOFF.md` updated (Known Bugs, Next Steps, Current Change Context)
- [ ] Commit has `AI-Origin:` trailer
- [ ] Issue acceptance criteria met or partial progress noted
