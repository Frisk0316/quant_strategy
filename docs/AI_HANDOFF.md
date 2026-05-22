---
status: current
type: handoff
owner: human
created: 2026-05-11
last_reviewed: 2026-05-22
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
| Daily winner normalization + calendar ticks `(complete; Claude conditionally approved; pending human review/commit)` | Daily Winner result payloads now expose `round_trips` plus synthetic BUY/SELL execution rows at read time, so legacy runs such as `ui_daily_winner_e9614719` show buy and sell legs, inferred qty/notional, exit-side PnL, and no auto-generated WF/CPCV when validation is none. Backtest charts use calendar-aware month ticks for multi-month/multi-year ranges. UI labels Daily Winner aggregate cost as `Total Costs` with `(fee+slip)` because the source is combined `cost_rate`, not pure exchange fees. | Validation-only strategy remains non-deployable and not admissible as edge evidence. Synthetic costs are display/accounting aids only; `daily_winner` trades still are not ADR-0002 fills and funding remains not modeled. |
| Validation status convention + results manifest `(docs-only; current)` | Defines five repo-wide `validation_status` labels (`naive_backtest`, `in_sample`, `hold_out`, `walk_forward`, `cpcv`) in `research/strategy_synthesis.md`, links them from the collaboration and backtest-live parity gates, and classifies all 101 current `results/**/*.json` files in `docs/results_validation_manifest.md` without modifying frozen result artifacts. | Conservative default: artifacts without explicit frozen hold-out, WalkForward, CPCV, or documented pre-dataset parameter-freeze proof are `in_sample`; `naive_backtest` and `in_sample` are research records, not OOS evidence or promotion evidence. |
| CME yfinance research proxy + structural fixes + long_only default `(complete; commit 655af31)` | `cme_btc_yfinance` dataset wired via yfinance optional adapter (598 daily rows, 2024-01-01 → 2026-05-19). Stop-loss (`stop_loss_bps_mult=1.5`), dust-bucket exclusion (`min_gap_bps=25`), and shortened hold (`max_hold_days=2`) implemented in `CMEGapFillStrategy` + `analyze_cme_gaps.py`. **Three in-sample runs**: (1) baseline `cme_gap_research.json` = -33.3% / Sharpe -0.52 / MDD -49.2% (109 trades, no stop); (2) post-fix `both` `cme_gap_research_with_stop.json` = -28.1% / Sharpe -0.82 / MDD -37.0% (99 trades, 1.5× stop); (3) post-fix `long_only` default `cme_gap_research_long_only_default.json` = **+7.09%** / Sharpe +0.35 / MDD -14.7% (46 trades, 26 target-fills / 13 stop-losses / 7 timeouts, win 63%, PF 1.24, worst -980 bps). **Route B applied in commit 655af31**: `allow_direction` default flipped to `long_only` in `core/config.py`, `config/strategies.yaml`, `external_features.py`, and `analyze_cme_gaps.py` (functions + CLI). Regression tests `test_cme_gap_fill_default_skips_up_gaps_and_trades_down_gaps` and `test_simulate_reverse_gap_trades_default_excludes_short_side` lock the default. `research/strategy_synthesis.md` Strategy 10 updated. | Research-only proxy; not admissible as deployment evidence. `long_only` default is **regime-fitted to BTC 2024-26**; bear-regime walk-forward remains required before any promotion claim, and failure on that segment must revert the default to "do not deploy". Even on long-only, edge is ~15 bps avg per trade (only ~3 bps above 12 bps round-trip cost) with single -980 bps worst trade — not validated alpha. Deployment still requires an official CME source, bear-regime walk-forward / CPCV pass, and DSR ≥ 0.95. |
| External-feature research baselines doc `(complete; docs-only)` | `research/strategy_synthesis.md` adds Strategy 9 (Crypto F&G long-flat sentiment baseline — `Fear`/`Neutral` are intentional hold states, only `Greed`/`Extreme Greed` trigger exit), Strategy 10 (CME daily weekend-gap research baseline — daily cadence with `publish_lag_days=1`, explicitly not a real-time gap-fill strategy), and a Research Feature Data Caveats section covering DGS10 latest-vintage / non-PIT semantics, F&G label-stability dependency, and the discontinued `CHRIS/CME_BTC1` source. Promotion Checklist extended with ct_val provenance, ADR-0006 reduce-only audit, and an External-Feature Coverage Gate (event_count > 0 for required datasets, stale-rate ≤ 10%, missing-rate ≤ 5%, plus per-dataset vintage / source-stability / label-stability attestations). | Documentation-only; no strategy or risk code touched. Codified caveats only; strategies remain `enabled: false` with `research_only: true` signal metadata. |
| MA/MACD long-flat position fix `(committed 8a4f5f9; follow-up pending commit)` | Technical indicator strategies remain long/flat baselines for research acceptance and parameter tuning. Patch fixes partial-exit state handling, replacement cancellation, long/flat-only ledger close sizing, lot-rounded replay partial fills, and incremental EMA/MACD state matching `ewm(adjust=False)`. Reduce-only risk semantics are scoped to long/flat close orders; fat-finger still blocks reduce-only orders, while allowed reduce-only bypasses for kill/position-limit/daily-stop are logged from `RiskGuard.check()` and written to replay `risk_events` with `allowed_reduce_only_bypass:*`. | Not live-ready. MA/MACD profitability is not established; ct_val gate still blocks promotion when provenance is non-authoritative. Pairs/funding-carry close sizing is intentionally unchanged until P2 design implementation is separately approved. |
| Chart UX overhaul fix-up `(complete; Claude reviewed 2026-05-22)` | Backtest viewer market charts now share one `market` X range across price and indicator panels; reset controls split X vs Y semantics; per-panel Y zoom uses shared `MAX_Y_ZOOM`; drawdown Y zoom anchors at the minimum; MACD sub-panel Y zoom is independent; indicator cards show `warmup_source`; metrics glossary is available from the left nav; artifact indicators default to cold-start strategy-aligned values with `indicator_db_warmup` opt-in and `result.validation.indicator_warmup_sources`. | Claude review accepted the chart/normalization direction with documentation and Daily Winner cost-label follow-up. DB warmup is an opt-in visual aid and can intentionally diverge from cold-start strategy marker timing if enabled. RangeBrush click-outside behavior, binary-search range slicing, and wheel/keyboard zoom remain backlog. |
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
14. **External-feature deployment caveats** (P1): Documented in `research/strategy_synthesis.md` as required ADR attestations. (a) **Budget-blocked, not on roadmap**: `CHRIS/CME_BTC1` was discontinued; paid CME alternatives (DataMine, Databento, Polygon) are not provisioned under this project's budget. The strategy's _operating_ signal source is `cme_btc_yfinance` (Yahoo `BTC=F` daily) — research-proxy, never deployment evidence. Trading venue is OKX BTC-USDT-SWAP (crypto/USDT perp), not CME futures itself; this is a cross-venue signal-to-trade setup, not arbitrage on CME. (b) `dgs10` ingest uses latest-vintage upsert and is not point-in-time — any DGS10-conditioned signal must remain `research_only` or move to FRED ALFRED vintage ingest. **Resolved in code**: `fear_greed_btc` label-stability — `FearGreedSentimentParams` now ships a `validate_extreme_fear_label` allow-list validator plus numeric `extreme_fear_threshold` / `exit_value_threshold` fallbacks driven off `value_num`; promotion ADR can attest against this implementation rather than treating it as an open blocker.
15. **Cross-strategy single-period selection-bias prohibition** (P1, normative, applies retroactively): Any `results/*.json` or `results/**/*.json` artifact with `validation_status: in_sample` or `validation_status: naive_backtest` is prohibited from being cited as edge evidence, used as a promotion basis, or used to satisfy the `docs/ai_collaboration.md` Deployment Gate stage `Historical backtest`, regardless of how strong total_return / Sharpe / PF / win-rate appears. Such use is **不得** and shall not pass review. The Deployment Gate stage `Walk-forward 或 CPCV` must be satisfied by an artifact with `validation_status: walk_forward` or `validation_status: cpcv`; CPCV must pass DSR >= 0.95 and PSR >= 0.95. `n_trials` must be reported honestly and must include all grid-sweep variants, manually adjusted versions, and trial variants discussed in chat / issues / commits even if no result file was retained; hidden trials count toward N. Future promotion artifacts using `backtesting/cpcv.py::CPCV.evaluate()` must provide `n_trials` explicitly and may not rely on a fallback default. This rule is retroactive: every current `results/**/*.json` artifact and every prior chat conclusion about "strategy performance" must be re-evaluated under this prohibition. Illustrative `cme_gap_fill` example, preserving the original warning: Route B was applied in commit `655af31` (2026-05-19), flipping `allow_direction` from `both` to `long_only` because up-gaps (short BTC) were -3,799 bps vs down-gaps +803 bps on the post-fix yfinance proxy run. Default re-run `results/cme_gap_research_long_only_default.json` reports total_return +7.09%, Sharpe +0.35, MDD -14.7% over 46 trades. Because this was a three-round manually tuned single-period backtest, its `validation_status` is `in_sample`, and the +7.09% number is not edge evidence. **Route B is still explicitly regime-fitted to BTC 2024-26; bear-regime walk-forward remains required before any promotion claim.** If `long_only` fails on a bear or sideways segment in the walk-forward, the default must revert to "do not deploy" and the strategy retired. Even on `long_only`, edge is only ~3 bps above round-trip cost — not validated alpha. The three `results/cme_gap_research*.json` artifacts are classified `in_sample` in `docs/results_validation_manifest.md`.
16. **In-sample envelope methodology lesson** (P2 process note): Claude's earlier estimate that a 1.5× stop would flip the CME gap-fill run from -3,187 to +3,308 bps was wrong because it only re-priced existing timeout exits and assumed target-fill trades were unchanged. The real bar-by-bar simulator triggered stop-loss on intra-trade adverse high/low excursions and converted 35/82 fills into stop-loss losses. Any future "what-if" stop / target replacement estimate on this style of strategy must walk every bar of every trade, not just re-cap existing exit reasons. Apply this lesson to MA/MACD baseline and any other long/flat exit-replacement review.
17. **Analyzer ↔ replay measurement divergence on `cme_gap_fill`** (P1 documentation only, no code change planned): `analyze_cme_gaps.simulate_reverse_gap_trades` uses each OKX bar's `high`/`low` to detect target / stop touches; the replay engine feeds the strategy a single L1 book event per bar synthesised from the bar `close` (`_synthetic_l1_from_candles`), so `_target_touched` / `_stop_loss_touched` only see the close mid. On 1H bars (intra-bar range 20-100 bps) many analyzer `target_fill` trades become replay `timeout` — replay is systematically more negative on the same gap signal. Secondary divergence: funding (perp), maker queue/partial-fill mechanics, entry-price reference (bar open vs close mid), broker-modelled fees vs flat 12 bps. **Interpretation rule**: analyzer JSON is an upper bound under idealised execution; replay artefact is a coarse close-mid lower bound. Neither is admissible as deployment evidence in isolation. Closing the gap requires either bar-high/low events in replay (changes strategy semantics; separate research item) or shadow trading for ground truth.
18. **Pending CME gap-fill exit-throttle + timestamp-normalisation commit** (P1): Uncommitted diff against `src/okx_quant/strategies/external_features.py` adds `_ActiveGap.exit_requested` to suppress duplicate exit signals while an exit order is pending (regression test `test_cme_gap_fill_does_not_repeat_exit_signal_while_exit_order_pending`). A separate uncommitted change in `backtesting/replay.py::_to_ms_int` + `backtesting/data_loader.py::_timestamp_to_ms` normalises multi-precision timestamps (s/ms/us/ns) in the L1 book loader and feature loader, with tests in `test_external_data.py` and `test_external_feature_strategies.py`. These should be split into two commits — exit-throttle is the alignment fix for the analyzer baseline; timestamp normalisation is an unrelated robustness fix.

## Do Not Touch (without explicit issue + user approval)

- `src/okx_quant/strategies/` — all strategy implementations
- `src/okx_quant/risk/` — risk guard, drawdown tracker, circuit breaker
- `src/okx_quant/portfolio/` — sizing, position ledger
- `src/okx_quant/execution/broker.py` — SimBroker and execution handler
- `config/risk.yaml` — risk limits
- Any file not listed in the current issue's permitted scope

## Next Steps (in order)

1. **[P0]** Claude re-review MA/MACD long-flat position fix follow-up, especially live/replay reduce-only bypass audit logging and ADR-0006.
2. **[P0 — DONE 2026-05-22]** Claude re-reviewed Chart UX overhaul / Daily Winner normalization follow-up; remaining accepted changes were documentation alignment and Daily Winner cost labeling.
3. **[P0]** Remaining DB-primary backend verification from prior handoff: end-to-end SOL download + backtest, DSN-invalid fallback path, and grep for stray `--backend parquet` outside fallback/tests.
4. **[P0]** Run deployment smoke tests for API key auth, CORS, WebSocket auth, and Docker port bindings before any public AWS deployment.
5. **[P1]** Add live WS remaining-size metadata from OKX `sz` / `accFillSz` and unit coverage before any MA/MACD promotion.
6. **[P1]** Claude docs-only update: add MA/EMA/MACD long-flat baseline section to `research/strategy_synthesis.md` (F&G + CME daily baselines and external-feature data caveats already added in this session).
6a. **[P3 — budget-blocked, no current plan]** Replace `CHRIS/CME_BTC1` adapter target with a maintained official CME BTC futures source (paid: DataMine, Databento, Polygon, or equivalent). Not on the active roadmap — this project trades OKX crypto/USDT pairs and uses CME only as a _signal_; the yfinance proxy (`cme_btc_yfinance`) is the operating signal source under budget. Re-open at P1 only if/when budget approves a paid feed; until then, all CME-gap research stays on the yfinance proxy and must be labelled accordingly.
6c. **[P1 — DONE 2026-05-19, commit `655af31`]** Codex flipped `CMEGapFillParams.allow_direction` default from `both` to `long_only` (Route B). Touched `core/config.py`, `config/strategies.yaml`, `external_features.py`, `analyze_cme_gaps.py` (functions + CLI), plus regression tests `test_cme_gap_fill_default_skips_up_gaps_and_trades_down_gaps` and `test_simulate_reverse_gap_trades_default_excludes_short_side`. Re-run `results/cme_gap_research_long_only_default.json` confirms `allow_direction="long_only"` and total_return = +7.09% on the yfinance proxy. `research/strategy_synthesis.md` Strategy 10 and Current Change Context updated.
6d. **[P1]** Bear-regime walk-forward / CPCV for `cme_gap_fill` on the `cme_btc_yfinance` proxy (since the official CME source is budget-blocked per 6a). Identify bear / sideways segments inside the available proxy window (e.g. extended drawdown stretches in 2024-2025) and run walk-forward separately on those. If `long_only` fails on any such segment, revert default to "do not deploy" and mark the strategy retired in Strategy 10. Any promotion ADR opened on the proxy alone must explicitly attest to the signal-source fidelity gap and require post-promotion monitoring against any future official feed. Until 6d completes, no promotion claim may cite the +7.09% proxy number as evidence — it is regime-fitted to BTC 2024-26.
6e. **[P1]** Codex follow-up: write `validation_status` field into `result.json` via `backtesting/artifacts.py` (separate issue, will touch ADR-0002 frozen schema — requires user approval).
6f. **[P1]** Codex follow-up: make `backtesting/cpcv.py::CPCV.evaluate()` require explicit `n_trials` (remove the `None` fallback), and add an equivalent trials-reporting parameter to `WalkForward.evaluate()`; separate issue because it will touch `backtesting/`.
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
