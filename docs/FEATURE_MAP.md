---
status: current
type: architecture
owner: human
created: 2026-06-12
last_reviewed: 2026-06-26
expires: none
superseded_by: null
---

# Feature Map

This map helps AI and human maintainers locate the owning files before editing.
When a feature is marked as a known gap, document the gap instead of pretending the
implementation exists.

## Backtest Run UI

- User-facing behavior: configure a strategy, symbols/universe, bar, date range,
  execution exchange, capital, validation mode, risk overrides, and optional
  parameter sweep; queue a run and poll job status.
- Frontend files: `frontend/app.js`, `frontend/data.js`, `frontend/view-config.js`,
  `frontend/styles.css`.
- Backend/API files: `src/okx_quant/api/routes_backtest.py`,
  `src/okx_quant/api/routes_data.py`.
- Backtesting files: `scripts/run_replay_backtest.py`, `scripts/backtest_ohlcv_rotation.py`,
  `backtesting/replay.py`, `backtesting/parameter_sweep.py`,
  `backtesting/daily_winner_backtest.py`, `backtesting/ohlcv_rotation_backtest.py`.
  Execution-profile controls live in `backtesting/research_controls.py` and are
  exposed by `scripts/run_replay_backtest.py`, `src/okx_quant/api/routes_backtest.py`,
  and `frontend/view-config.js`.
- Data / DB / artifact files: `src/okx_quant/data/candle_store.py`,
  `backtesting/artifacts.py`, `sql/migrations/0011_venue_instrument_specs.sql`,
  `sql/seed_venue_instrument_specs.sql`, runtime artifacts under results run
  directories.
- Config files: `config/settings.yaml`, `config/strategies.yaml`, `config/risk.yaml`,
  `config/instrument_specs.yaml`.
- Tests: `tests/unit/test_backtesting.py`, `tests/unit/test_parameter_sweep.py`,
  `tests/unit/test_backtest_request_exchange.py`,
  `tests/unit/test_multi_venue_convergence.py`,
  `tests/integration/test_replay_engine.py`.
- Docs to update: `docs/UI_MAP.md`, `docs/DATA_FLOW.md`, `docs/RUNBOOK.md`,
  `docs/AI_HANDOFF.md`.
- Do-not-touch notes: do not change strategy, risk, portfolio, execution, DB schema,
  or deployment gates for UI-only fixes.

## Backtest Result Charts

- User-facing behavior: inspect equity, drawdown, market price, execution markers,
  per-symbol indicators, metrics, trades, fills, and result-detail tabs.
- Frontend files: `frontend/view-backtest.js`, `frontend/view-results.js`,
  `frontend/charts.js`, `frontend/view-trades.js`, `frontend/view-glossary.js`,
  `frontend/styles.css`.
- Backend/API files: `src/okx_quant/api/routes_backtest.py`.
- Backtesting files: `backtesting/artifacts.py`, `backtesting/artifact_rows.py`,
  `backtesting/replay.py`.
- Data / DB / artifact files: runtime `price_series`, `indicator_series`, `fills`,
  `trades`, `equity`, `returns`, `drawdown`, and `metrics` artifacts;
  `backtest_artifact_rows` is a derived read index, not trading truth.
- Config files: `config/settings.yaml`, `config/strategies.yaml`.
- Tests: `tests/unit/test_artifact_rows.py`,
  `tests/unit/test_backtest_visual_fallbacks.py`,
  `tests/unit/test_frontend_static_mime.py`, `tests/unit/test_backtest_artifact_schema.py`.
- Docs to update: `docs/UI_MAP.md`, `docs/DATA_FLOW.md`, `docs/DEBUGGING_RUNBOOK.md`.
- Do-not-touch notes: chart fixes should not alter artifact schema, replay logic, or
  trading semantics unless the task explicitly permits it.

## Backtest API

- User-facing behavior: list runs, start runs/sweeps, read saved result artifacts,
  delete runs, and expose chart-specific endpoints.
- Frontend files: `frontend/data.js`, `frontend/view-backtest.js`,
  `frontend/view-results.js`, `frontend/view-config.js`.
- Backend/API files: `src/okx_quant/api/routes_backtest.py`,
  `src/okx_quant/api/server.py`.
- Backtesting files: `scripts/run_replay_backtest.py`, `backtesting/artifacts.py`,
  `backtesting/replay.py`, `backtesting/walk_forward.py`, `backtesting/cpcv.py`.
- Data / DB / artifact files: `sql/migrations/0010_backtest_runs.sql`,
  `sql/migrations/0012_backtest_artifact_rows.sql`, `backtesting/artifacts.py`,
  `backtesting/artifact_rows.py`, runtime result directories.
- Config files: `config/settings.yaml`.
- Tests: `tests/unit/test_routes_data_export.py`, `tests/unit/test_backtesting.py`,
  `tests/unit/test_artifact_rows.py`, `tests/unit/test_backtest_visual_fallbacks.py`,
  `tests/integration/test_api_endpoints.py`.
- Docs to update: `docs/ADR/0002-backtest-result-schema.md`, `docs/DATA_FLOW.md`,
  `docs/RUNBOOK.md`.
- Do-not-touch notes: API schema changes require matching frontend and test updates;
  do not silently rename result fields.

## In-Dashboard User Manual

- User-facing behavior: browse 使用手冊 chapters from the Help nav group, render
  written markdown chapters, and show `待補` for stub chapters.
- Frontend files: `frontend/app.js`, `frontend/index.html`,
  `frontend/view-manual.js`.
- Backend/API files: `src/okx_quant/api/routes_manual.py`,
  `src/okx_quant/api/server.py`.
- Manual content files: `docs/manual/manual.json`, `docs/manual/*.md`.
- Tests: `tests/unit/test_manual_manifest.py`,
  `tests/unit/test_routes_manual.py`.
- Docs to update: `docs/UI_MAP.md`, `docs/FEATURE_MAP.md`.
- Do-not-touch notes: manual content is documentation/read-path only; do not
  change strategy, risk, portfolio, execution, config, result artifacts, or
  live/demo/shadow gates for this feature.

## Progress Panel

- User-facing behavior: browse a read-only workstream milestone view sourced from
  `config/workstreams.yaml` in the Analysis nav group.
- Frontend files: `frontend/app.js`, `frontend/index.html`,
  `frontend/view-progress.js`, `frontend/data.js`, `frontend/styles.css`.
- Backend/API files: `src/okx_quant/api/routes_progress.py`,
  `src/okx_quant/api/server.py`.
- Data / docs files: `config/workstreams.yaml`; linked plan files are only
  surfaced as card links.
- Tests: `tests/unit/test_routes_progress.py`, `make frontend-check`,
  `make api-smoke`.
- Docs to update: `docs/UI_MAP.md`, `docs/DATA_FLOW.md`, `docs/AI_HANDOFF.md`,
  `docs/CURRENT_STATE.md`.
- Do-not-touch notes: progress is ops/meta read-only; do not change DB schema,
  strategy, risk, portfolio, execution, config gates, or result artifacts.

## Indicator Series / Indicator Chart

- User-facing behavior: technical-indicator runs display per-symbol price plus
  MA/EMA/MACD series, warmup source, and independent chart zoom controls.
- Frontend files: `frontend/view-backtest.js`, `frontend/charts.js`,
  `frontend/view-config.js`, `frontend/data.js`.
- Backend/API files: `src/okx_quant/api/routes_backtest.py`.
- Backtesting files: `backtesting/artifacts.py`, `backtesting/replay.py`.
- Data / DB / artifact files: runtime `indicator_series` and `price_series` artifacts;
  optional DB warmup reads from canonical candles.
- Config files: `config/strategies.yaml`, `config/settings.yaml`.
- Tests: `tests/unit/test_backtesting.py`, `tests/unit/test_technical_indicator_strategies.py`,
  `tests/unit/test_backtest_visual_fallbacks.py`.
- Docs to update: `docs/UI_MAP.md`, `docs/DATA_FLOW.md`, `docs/AI_HANDOFF.md`.
- Do-not-touch notes: visual indicator recomputation must not change strategy signal
  logic unless the task explicitly permits a strategy change.

## Market Data Ingestion

- User-facing behavior: fetch or update market data, inspect coverage, export OHLCV,
  funding, or external data, delete stale OHLCV/funding pairs, and use DB-backed
  data for backtests. Fetch jobs are queued sequentially and shown as a job list
  in the Market Data Coverage card. Binance fetches also sync exchangeInfo-derived
  venue specs into `venue_instrument_specs` so replay can resolve multiplier
  contracts such as `1000SHIB-USDT-SWAP` from DB.
- Frontend files: `frontend/view-config.js`, `frontend/data.js`.
- Backend/API files: `src/okx_quant/api/routes_data.py`.
- Backtesting files: `backtesting/data_loader.py`.
- Data / DB / artifact files: `src/okx_quant/data/candle_store.py`,
  `src/okx_quant/data/exchange_clients/okx_public.py`,
  `src/okx_quant/data/exchange_clients/binance_public.py`,
  `src/okx_quant/data/exchange_clients/bybit_public.py`,
  `sql/migrations/0011_venue_instrument_specs.sql`,
  `sql/seed_venue_instrument_specs.sql`,
  `scripts/market_data/ingest.py`, `scripts/market_data/update_all.py`,
  `scripts/market_data/repair_gaps.py`, `scripts/market_data/export_ohlcv_csv.py`,
  local parquet mirrors under `data/ticks/<inst_id>/`.
- Config files: `config/settings.yaml`, `config/external_data.yaml`.
- Tests: `tests/unit/test_market_ingest.py`, `tests/unit/test_external_data.py`,
  `tests/unit/test_routes_data_export.py`, `tests/unit/test_routes_data_queue.py`,
  `tests/unit/test_routes_data_delete.py`.
- Docs to update: `docs/DATA_FLOW.md`, `docs/UI_MAP.md`, `docs/RUNBOOK.md`,
  `docs/DEBUGGING_RUNBOOK.md`.
- Do-not-touch notes: ingestion changes can affect backtest reproducibility; do not
  alter DB schema without an explicit schema task.

## Canonical Candle Pipeline

- User-facing behavior: use canonical, deduplicated, source-prioritized candles for
  DB-backed backtests and coverage views.
- Frontend files: `frontend/view-config.js`.
- Backend/API files: `src/okx_quant/api/routes_data.py`,
  `src/okx_quant/api/routes_backtest.py`.
- Backtesting files: `backtesting/data_loader.py`.
- Data / DB / artifact files: `src/okx_quant/data/candle_store.py`,
  `src/okx_quant/data/canonical_policy.py`,
  `src/okx_quant/data/migrations/001_ohlcv_pipeline_v2.sql`,
  `src/okx_quant/data/migrations/002_market_canonical_bridge.sql`,
  `scripts/_db_writer.py`, `scripts/market_data/canonicalize.py`,
  `scripts/market_data/import_parquet_ohlcv.py`,
  `scripts/resample_binance_1h_canonical.py`, `sql/canonicalize_binance_to_legacy.sql`.
- Config files: `config/settings.yaml`.
- Tests: `tests/unit/test_market_ingest.py`, `tests/unit/test_db_writer.py`.
- Docs to update: `docs/DATA_FLOW.md`, `docs/RUNBOOK.md`,
  `docs/backtest_live_parity_plan.md`.
- Do-not-touch notes: source priority and canonicalization policy are data-quality
  behavior; changes need tests and documented migration impact.

## Funding Rate Pipeline

- User-facing behavior: ingest funding rates and include funding cashflow evidence
  in replay/backtest review where strategies require it.
- Frontend files: `frontend/view-backtest.js`, `frontend/view-config.js`.
- Backend/API files: `src/okx_quant/api/routes_data.py`,
  `src/okx_quant/api/routes_backtest.py`.
- Backtesting files: `backtesting/data_loader.py`, `backtesting/replay.py`,
  `backtesting/artifacts.py`.
- Data / DB / artifact files: `src/okx_quant/data/candle_store.py`,
  `scripts/market_data/backfill_funding.py`,
  `scripts/market_data/import_parquet_funding.py`,
  `scripts/market_data/validate_funding.py`.
- Config files: `config/settings.yaml`, `config/strategies.yaml`.
- Tests: `tests/unit/test_backtesting.py`, `tests/integration/test_replay_engine.py`.
- Docs to update: `docs/DATA_FLOW.md`, `docs/DEBUGGING_RUNBOOK.md`,
  `docs/backtest_live_parity_plan.md`.
- Do-not-touch notes: funding cashflow sign and `ct_val` scaling are high-risk
  accounting paths.

## Point-In-Time Universe Membership

- User-facing behavior: build a deterministic liquid USDT-perp universe artifact
  for cross-sectional research without pre-listing or delisting survivorship
  leakage.
- Frontend files: none.
- Backend/API files: none.
- Backtesting files: `backtesting/data_loader.py` is the downstream candle
  aggregation authority; no dedicated backtest runner is wired yet.
- Data / DB / artifact files: `scripts/build_universe_membership.py`,
  local candles under `data/ticks/<inst_id>/candles_1m.parquet`, generated
  artifact `data/universe/universe_membership.parquet`.
- Config files: `config/universe.yaml`, `config/settings.yaml`.
- Tests: `tests/unit/test_universe_membership.py`.
- Docs to update: `docs/DATA_FLOW.md`, `docs/INVARIANTS.md`,
  `docs/FAILURE_MODES.md`, `docs/AI_HANDOFF.md`.
- Do-not-touch notes: do not use a hand-picked final symbol list as historical
  membership; promotion-grade runs still need venue-scoped DB coverage evidence.

## XS Momentum Research Strategy

- User-facing behavior: disabled-by-default research strategy scaffold for
  dollar-neutral cross-sectional momentum target weights over a point-in-time
  universe.
- Frontend files: none yet.
- Backend/API files: none yet.
- Backtesting files: `backtesting/replay.py` can instantiate the no-op strategy
  stub when explicitly requested. `backtesting/xs_momentum_backtest.py` is a
  research-only vectorized runner for target weights, corrected R3.1 funding
  cashflow signs, family-cumulative grid trial counts via
  `prior_family_n_trials`, portfolio-vol gross sizing, and optional
  `market_close` crash filtering; it is not wired into UI/API promotion gates.
- Data / DB / artifact files: consumes `data/universe/universe_membership.parquet`
  and venue-scoped OHLCV/funding data. Local smoke artifacts such as
  `results/xs_momentum_db_smoke_20260623.json` are research evidence only.
- Config files: `config/strategies.yaml`, `config/universe.yaml`.
- Strategy / portfolio files: `src/okx_quant/strategies/xs_momentum.py`,
  `src/okx_quant/portfolio/allocation.py`.
- Tests: `tests/unit/test_xs_momentum.py`,
  `tests/unit/test_xs_momentum_backtest.py`,
  `tests/unit/test_universe_membership.py`.
- Docs to update: `docs/ADR/0009-xs-momentum-research-strategy.md`,
  `docs/change_manifests/2026-06-23-xs-momentum-universe.md`,
  `docs/change_manifests/2026-06-23-xs-momentum-phase-c.md`,
  `docs/INVARIANTS.md`, `docs/FAILURE_MODES.md`,
  `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md`.
- Do-not-touch notes: `XSMomentumStrategy.on_market()` is intentionally no-op;
  do not claim live, demo, shadow, or promotion readiness until WF/CPCV,
  DSR/PSR, source parity, funding accounting, and human approval are complete.

## Pipeline Batch 1 Research Candidates

- User-facing behavior: disabled-by-default research candidate scaffolds for S5
  residual mean reversion, S6 slow time-series momentum, and S7 perp-vs-spot
  basis mean reversion. These are checkpoint artifacts only, not UI/API
  promotion surfaces.
- Frontend files: none.
- Backend/API files: none.
- Backtesting files: `backtesting/s5_residual_meanrev_backtest.py`,
  `backtesting/s6_ts_momentum_backtest.py`,
  `backtesting/s7_basis_meanrev_backtest.py`,
  `backtesting/pipeline_refit.py`,
  `backtesting/differential_validation.py` contract entries,
  `scripts/run_pipeline_batch1_checkpoint.py`.
- Data / DB / artifact files: consumes venue-scoped Binance canonical
  `canonical_candles` and `funding_rates`; generated checkpoint summaries live
  under `results/pipeline_batch1_20260625/` and
  `results/pipeline_batch1_20260625_refit/`. Binance S6/S7 data is loaded for
  BTC/ETH perps and BTC/ETH spot (1m OHLCV) plus BTC/ETH perp funding. S6 failed
  the fold-refit statistical gate, S7 is shelved after the non-degenerate
  half-life rerun, and S5 is a data-universe artifact.
- Config files: `config/strategies.yaml`, `config/universe.yaml`.
- Strategy / portfolio files: `src/okx_quant/strategies/s5_residual_meanrev.py`,
  `src/okx_quant/strategies/s6_ts_momentum.py`,
  `src/okx_quant/strategies/s7_basis_meanrev.py`.
- Tests: `tests/unit/test_s5_residual_meanrev_backtest.py`,
  `tests/unit/test_s6_ts_momentum_backtest.py`,
  `tests/unit/test_s7_basis_meanrev_backtest.py`,
  `tests/unit/test_pipeline_refit.py`,
  `tests/unit/test_pipeline_batch1_checkpoint_runner.py`,
  `tests/unit/test_pipeline_batch1_contracts.py`.
- Docs to update: `docs/EXPERIMENT_REGISTRY.md`, `docs/KNOWN_ISSUES.md`,
  `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, relevant Change Manifest.
- Do-not-touch notes: keep entries `enabled:false`; do not wire to UI/API,
  demo/shadow/live gates, risk/portfolio/execution, or promotion until
  source parity, portable validation, ct_val provenance, WF/CPCV gates, and
  human approval are complete.

## Pipeline Batch 2 Research Candidates

- User-facing behavior: checkpoint-only research candidates for C3 sentiment,
  C2 funding carry + basis-z filter, and C1 BTC/ETH OU-gated pairs RV. These are
  evidence-review artifacts only, not UI/API promotion surfaces.
- Frontend files: none.
- Backend/API files: none.
- Backtesting files: `backtesting/c1_pairs_ou_backtest.py`,
  `backtesting/c2_funding_carry_backtest.py`,
  `backtesting/c3_sentiment_backtest.py`, `backtesting/pipeline_refit.py`,
  `backtesting/differential_validation.py` contract entries,
  `scripts/run_pipeline_batch2_checkpoint.py`.
- Data / DB / artifact files: consumes venue-scoped Binance canonical
  `canonical_candles`, `funding_rates`, and for C3 `external_observations`;
  generated checkpoint records live under `results/pipeline_batch2_20260625/`.
  Current checkpoint has C3, C2, and C1 DB-backed fold-refit summaries with
  CPCV `path_returns` retained; C3 is refuted after Stage-2 PASS and Stage-3
  statistical failure. C3 sentiment decisions use the last `published_at` before
  each UTC decision day closes, then apply the existing one-day target lag.
- Config files: none changed. The `fear_greed_sentiment` entry in
  `config/strategies.yaml` remains `enabled:false`; live funding-carry strategy
  behavior was not changed.
- Strategy / portfolio files: none changed.
- Tests: `tests/unit/test_c1_pairs_ou_backtest.py`,
  `tests/unit/test_c2_funding_carry_backtest.py`,
  `tests/unit/test_c3_sentiment_backtest.py`,
  `tests/unit/test_pipeline_batch2_contracts.py`,
  `tests/unit/test_pipeline_batch2_checkpoint_runner.py`.
- Docs to update: `docs/EXPERIMENT_REGISTRY.md`,
  `docs/HYPOTHESIS_LEDGER.md`, `docs/AI_HANDOFF.md`,
  `docs/CURRENT_STATE.md`, relevant Change Manifest.
- Do-not-touch notes: do not enable candidates, touch `config/risk.yaml`, alter
  live/shadow/demo gates, change live funding-carry strategy behavior, edit
  `src/okx_quant/analytics/dsr.py`, or mutate existing result artifacts.

## Strategy Research Pipeline Automation

- User-facing behavior: generate and review advisory research-pipeline sidecars
  before any candidate enters durable ledgers or backtests. Current sidecars are
  stage2 feasibility JSON, checkpoint1 auto JSON, family-minting JSON, idea-batch
  JSON, and hypothesis-ledger draft Markdown. Idea-batch B-half enumeration uses
  supplied Stage-2 data-availability probe results before falling back to
  taxonomy text; occupied-family verdicts come from `docs/HYPOTHESIS_LEDGER.md`
  `Status`, while `docs/EXPERIMENT_REGISTRY.md` remains the trial/K-budget
  source. Inconclusive/refuted/shelved occupied families require an explicit
  twist marker to be drafted, and overlay-only taxonomy rows are skipped until a
  deterministic base-family contract exists. The A-half literature driver runs
  paper fetch/scoring through the crypto-alpha-lab prompt firewall, writes a
  weekly screen, and registers literature drafts as `pending_llm` sidecars
  without automatic family minting.
- Frontend files: none.
- Backend/API files: none.
- Backtesting files: `backtesting/pipeline_feasibility.py`,
  `backtesting/pipeline_checkpoint1.py`, `backtesting/pipeline_family_minting.py`,
  `backtesting/pipeline_idea_generator.py`.
- Script files: `scripts/run_pipeline_stage2_check.py`,
  `scripts/run_pipeline_checkpoint1_check.py`,
  `scripts/run_pipeline_family_minting_check.py`,
  `scripts/run_pipeline_idea_generator.py`,
  `scripts/run_pipeline_literature_ideas.py`,
  `scripts/literature_keyword_scorer.py`.
- Data / DB / artifact files: reads `docs/EXPERIMENT_REGISTRY.md` and
  `docs/HYPOTHESIS_LEDGER.md`; writes advisory sidecars under new
  `results/<batch_id>/` directories without mutating existing artifacts.
- Config files: none.
- Tests: `tests/unit/test_pipeline_checkpoint1_check.py`,
  `tests/unit/test_pipeline_family_minting.py`,
  `tests/unit/test_pipeline_idea_generator.py`,
  `tests/unit/test_pipeline_literature_ideas.py`,
  `tests/unit/test_literature_keyword_scorer.py`.
- Docs to update: `docs/INVARIANTS.md`, `docs/KNOWN_ISSUES.md`,
  `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `config/workstreams.yaml`,
  relevant Change Manifest.
- Do-not-touch notes: automation sidecars are advisory research controls only.
  They must not append durable ledger rows, change `research/strategy_synthesis.md`,
  enable strategies, run backtests, change CPCV/DSR/gate semantics, alter
  config gates, or touch demo/shadow/live behavior without explicit approval.

## Strategy Registry / Strategy Selection

- User-facing behavior: expose active strategies to the Run Backtest UI and API
  allow-list with matching parameter controls.
- Frontend files: `frontend/data.js`, `frontend/view-config.js`.
- Backend/API files: `src/okx_quant/api/routes_backtest.py`.
- Backtesting files: `scripts/run_replay_backtest.py`, `backtesting/replay.py`,
  `backtesting/research_controls.py`.
- Data / DB / artifact files: runtime result directories and config snapshots.
- Config files: `config/strategies.yaml`, `config/settings.yaml`.
- Tests: `tests/unit/test_research_strategy_hooks.py`,
  `tests/integration/test_signal_strategy_integration.py`.
- Docs to update: `docs/AI_HANDOFF.md`, `docs/UI_MAP.md`,
  `docs/ai_collaboration.md`.
- Do-not-touch notes: adding a strategy requires API, frontend registry, UI controls,
  reference portability contract, tests, and docs; do not revive retired strategies
  without explicit user approval.

## Result Artifacts

- User-facing behavior: make each backtest reviewable through result JSON, CSV/DB
  artifacts, charts, logs, metrics, and validation metadata.
- Frontend files: `frontend/view-backtest.js`, `frontend/view-results.js`,
  `frontend/view-trades.js`, `frontend/data.js`.
- Backend/API files: `src/okx_quant/api/routes_backtest.py`.
- Backtesting files: `backtesting/artifacts.py`, `backtesting/result_utils.py`,
  `backtesting/replay.py`.
- Data / DB / artifact files: `sql/migrations/0010_backtest_runs.sql`,
  runtime `result`, `metrics`, `config`, `price_series`, `indicator_series`, `fills`,
  `orders`, `trades`, `funding`, `risk_events`, and coverage artifacts.
- Config files: `config/settings.yaml`, `config/risk.yaml`, `config/strategies.yaml`.
- Tests: `tests/unit/test_backtest_artifact_schema.py`,
  `tests/unit/test_backtesting.py`.
- Docs to update: `docs/ADR/0002-backtest-result-schema.md`,
  `docs/results_validation_manifest.md`, `docs/DATA_FLOW.md`.
- Do-not-touch notes: do not edit frozen historical result artifacts; schema changes
  require an ADR-aware task and tests.

## Validation / Promotion Gates

- User-facing behavior: show whether evidence is research-only, advisory, blocked,
  or eligible for promotion review.
- Frontend files: `frontend/view-validation.js`, `frontend/view-backtest.js`,
  `frontend/data.js`.
- Backend/API files: `src/okx_quant/api/routes_backtest.py`.
- Backtesting files: `backtesting/differential_validation.py`,
  `scripts/run_differential_validation.py`,
  `scripts/run_engine_consistency_smoke.py`, `backtesting/walk_forward.py`,
  `backtesting/cpcv.py`.
- Data / DB / artifact files: runtime validation result directories and validation
  artifacts; frozen offline engine-consistency fixtures live under
  `tests/fixtures/engine_consistency/`.
- Config files: `config/strategies.yaml`, `config/risk.yaml`,
  `config/instrument_specs.yaml`.
- Tests: `tests/unit/test_differential_validation.py`,
  `tests/unit/test_engine_consistency_smoke.py`,
  `tests/unit/test_parameter_sweep.py`, `tests/unit/test_backtesting.py`.
- Docs to update: `docs/ai_collaboration.md`, `docs/backtest_live_parity_plan.md`,
  `docs/results_validation_manifest.md`, `docs/AI_HANDOFF.md`.
- Do-not-touch notes: validation harness/interface changes must not alter strategy,
  risk, portfolio, execution, DB schema, existing result artifacts, or reference
  adapter tolerances unless the task explicitly permits it. Advisory validation
  output is not live-readiness evidence.

## Shadow / Demo / Live Deployment Gate

- User-facing behavior: prevent live/shadow/demo claims or mode switches unless
  policy gates and human approvals are satisfied.
- Frontend files: `frontend/app.js`, `frontend/view-results.js`.
- Backend/API files: `src/okx_quant/api/routes_live.py`,
  `src/okx_quant/api/server.py`, `src/okx_quant/engine.py`.
- Backtesting files: `backtesting/replay.py`, `backtesting/artifacts.py`.
- Data / DB / artifact files: logs, metrics, risk events, fills, orders, and
  deployment evidence artifacts generated by approved runs.
- Config files: `config/settings.yaml`, `config/risk.yaml`, `docker/docker-compose.yml`,
  `docker/Dockerfile`, `docker/prometheus.yml`.
- Tests: `tests/integration/test_execution_integration.py`,
  `tests/integration/test_risk_integration.py`, `tests/unit/test_execution_flow.py`,
  `tests/unit/test_risk_guard.py`.
- Docs to update: `docs/ai_collaboration.md`, `docs/backtest_live_parity_plan.md`,
  `docs/shadow_mode_parity_plan.md`, `docs/RUNBOOK.md`.
- Do-not-touch notes: never switch modes or relax gates without explicit human
  approval.

## Telegram / Monitoring

- User-facing behavior: expose operational metrics and Telegram-style alert hooks
  where configured.
- Frontend files: `frontend/app.js`, `frontend/view-results.js`.
- Backend/API files: `src/okx_quant/api/routes_live.py`,
  `src/okx_quant/api/server.py`.
- Backtesting files: none in current implementation.
- Data / DB / artifact files: `src/okx_quant/monitoring/metrics.py`,
  `src/okx_quant/monitoring/telegram_alert.py`,
  `src/okx_quant/monitoring/calibration_log.py`.
- Config files: `config/settings.yaml`, `docker/prometheus.yml`.
- Tests: `tests/unit/test_monitoring.py`.
- Docs to update: `docs/RUNBOOK.md`, `docs/DEBUGGING_RUNBOOK.md`,
  `docs/KNOWN_ISSUES.md`.
- Do-not-touch notes: monitoring gaps should be recorded as operational gaps; do not
  infer alerting is production-ready from module presence alone.

## Stocks Research Sandbox

- User-facing behavior: local TW/US stock minute-bar research sandbox for
  CSV/parquet experiments only; it is not wired into crypto replay, UI, API, or
  deployment gates.
- Frontend files: none.
- Backend/API files: none.
- Backtesting files: `src/okx_quant/stocks/`, `scripts/run_stock_backtest.py`.
- Data / DB / artifact files: user-supplied stock minute-bar CSV/parquet files;
  no managed DB/artifact pipeline is registered for this sandbox.
- Config files: none.
- Tests: `tests/unit/test_stock_system.py`.
- Docs to update: `docs/FEATURE_MAP.md`; add broader docs only if an explicit
  task promotes this sandbox into a supported workflow.
- Do-not-touch notes: do not treat stocks results as crypto strategy evidence;
  do not connect stocks code to live/shadow/demo gates, shared backtest artifacts,
  or frontend/API surfaces without explicit human approval.
