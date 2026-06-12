---
status: current
type: architecture
owner: human
created: 2026-06-12
last_reviewed: 2026-06-12
expires: none
superseded_by: null
---

# Feature Map

This map helps AI and human maintainers locate the owning files before editing.
When a feature is marked as a known gap, document the gap instead of pretending the
implementation exists.

## Backtest Run UI

- User-facing behavior: configure a strategy, symbols/universe, bar, date range,
  capital, validation mode, risk overrides, and optional parameter sweep; queue a
  run and poll job status.
- Frontend files: `frontend/app.js`, `frontend/data.js`, `frontend/view-config.js`,
  `frontend/styles.css`.
- Backend/API files: `src/okx_quant/api/routes_backtest.py`,
  `src/okx_quant/api/routes_data.py`.
- Backtesting files: `scripts/run_replay_backtest.py`, `scripts/backtest_ohlcv_rotation.py`,
  `backtesting/replay.py`, `backtesting/parameter_sweep.py`,
  `backtesting/daily_winner_backtest.py`, `backtesting/ohlcv_rotation_backtest.py`.
- Data / DB / artifact files: `src/okx_quant/data/candle_store.py`,
  `backtesting/artifacts.py`, runtime artifacts under results run directories.
- Config files: `config/settings.yaml`, `config/strategies.yaml`, `config/risk.yaml`,
  `config/instrument_specs.yaml`.
- Tests: `tests/unit/test_backtesting.py`, `tests/unit/test_parameter_sweep.py`,
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
- Backtesting files: `backtesting/artifacts.py`, `backtesting/replay.py`.
- Data / DB / artifact files: runtime `price_series`, `indicator_series`, `fills`,
  `trades`, `equity`, `returns`, `drawdown`, and `metrics` artifacts.
- Config files: `config/settings.yaml`, `config/strategies.yaml`.
- Tests: `tests/unit/test_backtest_visual_fallbacks.py`,
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
  `backtesting/artifacts.py`, runtime result directories.
- Config files: `config/settings.yaml`.
- Tests: `tests/unit/test_routes_data_export.py`, `tests/unit/test_backtesting.py`,
  `tests/integration/test_api_endpoints.py`.
- Docs to update: `docs/ADR/0002-backtest-result-schema.md`, `docs/DATA_FLOW.md`,
  `docs/RUNBOOK.md`.
- Do-not-touch notes: API schema changes require matching frontend and test updates;
  do not silently rename result fields.

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
  funding, or external data, and use DB-backed data for backtests.
- Frontend files: `frontend/view-config.js`, `frontend/data.js`.
- Backend/API files: `src/okx_quant/api/routes_data.py`.
- Backtesting files: `backtesting/data_loader.py`.
- Data / DB / artifact files: `src/okx_quant/data/candle_store.py`,
  `src/okx_quant/data/exchange_clients/okx_public.py`,
  `src/okx_quant/data/exchange_clients/binance_public.py`,
  `src/okx_quant/data/exchange_clients/bybit_public.py`,
  `scripts/market_data/ingest.py`, `scripts/market_data/update_all.py`,
  `scripts/market_data/repair_gaps.py`, `scripts/market_data/export_ohlcv_csv.py`.
- Config files: `config/settings.yaml`, `config/external_data.yaml`.
- Tests: `tests/unit/test_market_ingest.py`, `tests/unit/test_external_data.py`.
- Docs to update: `docs/DATA_FLOW.md`, `docs/RUNBOOK.md`,
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
  `scripts/market_data/import_parquet_ohlcv.py`, `sql/canonicalize_binance_to_legacy.sql`.
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
  `scripts/run_differential_validation.py`, `backtesting/walk_forward.py`,
  `backtesting/cpcv.py`.
- Data / DB / artifact files: runtime validation result directories and validation
  artifacts.
- Config files: `config/strategies.yaml`, `config/risk.yaml`,
  `config/instrument_specs.yaml`.
- Tests: `tests/unit/test_differential_validation.py`,
  `tests/unit/test_parameter_sweep.py`, `tests/unit/test_backtesting.py`.
- Docs to update: `docs/ai_collaboration.md`, `docs/backtest_live_parity_plan.md`,
  `docs/results_validation_manifest.md`, `docs/AI_HANDOFF.md`.
- Do-not-touch notes: this session is not the differential-validation implementation
  session; do not edit validation engine files here. Advisory validation output is
  not live-readiness evidence.

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
- Tests: no dedicated monitoring test is mapped here yet.
- Docs to update: `docs/RUNBOOK.md`, `docs/DEBUGGING_RUNBOOK.md`,
  `docs/KNOWN_ISSUES.md`.
- Do-not-touch notes: monitoring gaps should be recorded as operational gaps; do not
  infer alerting is production-ready from module presence alone.
