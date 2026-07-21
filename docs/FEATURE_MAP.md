---
status: current
type: architecture
owner: human
created: 2026-06-12
last_reviewed: 2026-07-17
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
  parameter sweep; queue a run and poll job status. An omitted exchange uses
  `config/settings.yaml` primary exchange; an explicit unknown venue returns 400.
- Frontend files: `frontend/app.js`, `frontend/data.js`, `frontend/view-config.js`,
  `frontend/styles.css`.
- Backend/API files: `src/okx_quant/api/routes_backtest.py`,
  `src/okx_quant/api/routes_data.py`.
- Backtesting files: `scripts/run_replay_backtest.py`, `scripts/backtest_ohlcv_rotation.py`,
  `backtesting/replay.py`, `backtesting/parameter_sweep.py`,
  `backtesting/daily_winner_backtest.py`, `backtesting/ohlcv_rotation_backtest.py`,
  `backtesting/turtle_backtest.py`.
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
  `tests/unit/test_artifact_rows.py`,
  `tests/unit/test_multi_venue_convergence.py`,
  `tests/unit/test_turtle_backtest.py`, `tests/unit/test_routes_backtest_turtle.py`,
  `tests/integration/test_replay_engine.py`.
- Docs to update: `docs/UI_MAP.md`, `docs/DATA_FLOW.md`, `docs/RUNBOOK.md`,
  `docs/AI_HANDOFF.md`.
- Do-not-touch notes: do not change strategy, risk, portfolio, execution, DB schema,
  or deployment gates for UI-only fixes.

## Turtle Research Runner

- User-facing behavior: run the standalone Turtle S1/S2 reference port on one
  DB-backed 1D symbol; sweep window params and optional `invest_pct`; review
  standard run artifacts plus native SVG heatmaps, a Plotly surface HTML
  sweep artifact, and batched/resumable large-sweep `rows.csv` artifacts with
  progress/cancel job status; large sweep CSVs stay artifact-link only while
  small 2D/invest sweeps can inline chart rows. Research risk overrides and
  execution-profile controls are explicitly ignored; Turtle fees/sizing come
  from Turtle params only.
- Frontend files: `frontend/data.js`, `frontend/view-config.js`,
  `frontend/charts.js`, `frontend/vendor/plotly.min.js`.
- Backend/API files: `src/okx_quant/api/routes_backtest.py`.
- Backtesting files: `backtesting/turtle_backtest.py`.
- Data / DB / artifact files: DB/canonical or market 1D OHLCV via
  `backtesting/data_loader.py`; run artifacts under `results/<run_id>/`;
  sweep artifacts under `results/turtle_sweeps/<sweep_id>/`.
- Tests: `tests/unit/test_turtle_backtest.py`,
  `tests/unit/test_routes_backtest_turtle.py`.
- Docs to update: `docs/UI_MAP.md`, `docs/DATA_FLOW.md`, `docs/RUNBOOK.md`,
  `docs/GOLDEN_CASES.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`.
- Do-not-touch notes: research-only; no replay strategy, no
  `config/strategies.yaml`, no strategy/risk/live/deployment gate changes, no
  changes to `new_startegy_海龜/`, and no differential-validation contract entry
  without explicit approval.

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
  `src/okx_quant/api/server.py`, `scripts/run_server.py`.
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
  `src/okx_quant/api/server.py`, `scripts/run_server.py`. Only markdown paths
  explicitly listed in `config/workstreams.yaml` are exposed by the read-only
  progress-file endpoint; containment checks prevent serving arbitrary repo files.
  File serving is disabled in the network-facing engine app and enabled only by
  the standalone server when it binds to a loopback host.
- Data / docs files: `config/workstreams.yaml`; linked plan files are only
  surfaced as card links.
- Tests: `tests/unit/test_routes_progress.py`, `make frontend-check`,
  `make api-smoke`.
- Docs to update: `docs/UI_MAP.md`, `docs/DATA_FLOW.md`, `docs/AI_HANDOFF.md`,
  `docs/CURRENT_STATE.md`.
- Do-not-touch notes: progress is ops/meta read-only; do not change DB schema,
  strategy, risk, portfolio, execution, config gates, or result artifacts.

## Research Ledger Projection

- User-facing behavior: browse a read-only `研究總表 / Ledger` Analysis view with
  aggregate funnel KPIs, one row per research family, statistical evidence, K
  usage, funnel counts, and contained links to the authoritative ledgers.
- Current: frontend/research_funnel.json is an optional generated schema-v3
  projection (schema-v2 family details plus isolated artifact errors). Its
  absence produces an explicit generation command. Funnel loading
  is independent from Progress capability discovery, so a failed `/api/progress`
  request disables links without hiding the table.
- Target: regenerate the static projection after pipeline or ledger updates with
  `python scripts/run_pipeline_funnel_report.py --json-output
  frontend/research_funnel.json`.
- Known gap: generation is not automatic, so the projection can be absent or
  stale. `docs/HYPOTHESIS_LEDGER.md` and `docs/EXPERIMENT_REGISTRY.md` remain the
  source of truth; the UI is not promotion evidence.
- Frontend files: `frontend/app.js`, `frontend/data.js`,
  `frontend/view-ledger.js`; existing card, KPI, and table styles are reused.
- Backend/API files: no new backend route. The static frontend serves the JSON;
  `src/okx_quant/api/routes_progress.py` supplies the existing read-only,
  allow-listed markdown route and its `file_links_enabled` capability flag.
- Data / docs files: generated frontend/research_funnel.json (not checked in by
  this task), `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md`.
- Config files: `config/workstreams.yaml` allow-lists exactly those two ledger
  markdown files on the full-auto pipeline workstream.
- Tests: `tests/unit/test_routes_progress.py`; syntax checks for
  `frontend/view-ledger.js`, `frontend/data.js`, and `frontend/app.js`.
- Docs to update: `docs/UI_MAP.md`, `docs/FEATURE_MAP.md`.
- Do-not-touch notes: strictly read-only; do not add a write API, mutation control,
  strategy/config gate, automatic generation, or broader repository file serving.

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

- User-facing behavior: fetch or update market data, inspect coverage, chart
  Deribit external observations in the Run Backtest Derivatives context card,
  export OHLCV, funding, or external data, delete stale OHLCV/funding pairs, and
  use DB-backed data for backtests. Fetch jobs are queued sequentially and shown
  as a job list in the Market Data Coverage card. Binance fetches also sync
  exchangeInfo-derived venue specs into `venue_instrument_specs` so replay can
  resolve multiplier contracts such as `1000SHIB-USDT-SWAP` from DB.
  External coverage rows label Exchange from the dataset provider, and external
  export downloads DB rows even when the optional refresh pre-step skips or fails.
  OKX liquidation forward accumulation is wrapped by
  `scripts/market_data/run_liq_ingest_task.cmd`; `docs/RUNBOOK.md` owns its
  two-hour least-privilege S4U task registration, run, rollback, and removal.
  The checkpointed CLI also backfills and forward-tops-up Deribit public
  BTC/ETH-PERPETUAL 1m candles under native canonical ids with venue-scoped
  `source_primary='deribit'`; index prices are never a fallback.
- Frontend files: `frontend/view-config.js`, `frontend/data.js`.
- Backend/API files: `src/okx_quant/api/routes_data.py`.
- Backtesting files: `backtesting/data_loader.py`.
- Data / DB / artifact files: `src/okx_quant/data/candle_store.py`,
  `src/okx_quant/data/exchange_clients/okx_public.py`,
  `src/okx_quant/data/exchange_clients/binance_public.py`,
  `src/okx_quant/data/exchange_clients/bybit_public.py`,
  `src/okx_quant/data/exchange_clients/deribit_public.py`,
  `src/okx_quant/data/external_clients/deribit_dvol.py`,
  `src/okx_quant/data/external_clients/deribit_funding.py`,
  `src/okx_quant/data/external_clients/deribit_option_surface.py`,
  `src/okx_quant/data/external_clients/deribit_option_flow.py`,
  `sql/migrations/0011_venue_instrument_specs.sql`,
  `sql/seed_venue_instrument_specs.sql`,
  `scripts/market_data/ingest.py`, `scripts/market_data/update_all.py`,
  `scripts/market_data/repair_gaps.py`, `scripts/market_data/export_ohlcv_csv.py`,
  `scripts/market_data/ingest_external.py`,
  `scripts/market_data/run_liq_ingest_task.cmd`,
  `scripts/market_data/snapshot_deribit_options.py`,
  `scripts/market_data/backfill_deribit_option_flow.py`,
  `scripts/market_data/download_binance_vision_metrics.py`,
  local parquet mirrors under `data/ticks/<inst_id>/`.
- Config files: `config/settings.yaml`, `config/external_data.yaml`.
- Tests: `tests/unit/test_market_ingest.py`, `tests/unit/test_external_data.py`,
  `tests/unit/test_deribit_public_client.py`,
  `tests/unit/test_routes_data_export.py`, `tests/unit/test_routes_data_queue.py`,
  `tests/unit/test_routes_data_delete.py`,
  `tests/unit/test_deribit_dvol_client.py`,
  `tests/unit/test_deribit_funding_client.py`,
  `tests/unit/test_deribit_option_surface.py`,
  `tests/unit/test_deribit_option_flow.py`,
  `tests/unit/test_ingest_external_liquidation.py`,
  `tests/unit/test_snapshot_deribit_options.py`,
  `tests/unit/test_routes_data_external_series.py`.
- Docs to update: `docs/DATA_FLOW.md`, `docs/UI_MAP.md`, `docs/RUNBOOK.md`,
  `docs/DEBUGGING_RUNBOOK.md`.
- Do-not-touch notes: ingestion changes can affect backtest reproducibility; do not
  alter DB schema without an explicit schema task.

## Canonical Candle Pipeline

- User-facing behavior: use canonical, deduplicated, source-prioritized candles for
  DB-backed backtests and coverage views; run a read-only canonical/external
  history audit and fail-closed H-010 cross-venue coverage verifier. ADR-0014
  preserves that resolved default while explicit venue reads use a source-aware
  identity; the authorized OKX frozen-window promotion is complete.
- Frontend files: `frontend/view-config.js`.
- Backend/API files: `src/okx_quant/api/routes_data.py`,
  `src/okx_quant/api/routes_backtest.py`.
- Backtesting files: `backtesting/data_loader.py`.
- Data / DB / artifact files: `src/okx_quant/data/candle_store.py`,
  `src/okx_quant/data/canonical_policy.py`,
  `src/okx_quant/data/migrations/001_ohlcv_pipeline_v2.sql`,
  `src/okx_quant/data/migrations/002_market_canonical_bridge.sql`,
  `src/okx_quant/data/migrations/004_venue_canonical_candles.sql`,
  `scripts/_db_writer.py`, `scripts/market_data/canonicalize.py`,
  `scripts/market_data/import_parquet_ohlcv.py`,
  `scripts/resample_binance_1h_canonical.py`, `scripts/audit_history_coverage.py`,
  `scripts/promote_okx_canonical_1m.py`,
  `scripts/verify_okx_1m_backfill.py`, `sql/canonicalize_binance_to_legacy.sql`.
- Config files: `config/settings.yaml`.
- Tests: `tests/unit/test_market_ingest.py`, `tests/unit/test_db_writer.py`,
  `tests/unit/test_audit_history_coverage.py`,
  `tests/unit/test_venue_canonical_promotion.py`.
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
  `scripts/market_data/backfill_universe_funding.py`,
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

## Funding XS Dispersion Research Candidate

- User-facing behavior: checkpoint-only research candidate for
  F-FUNDING-XS-DISPERSION. It tests a dollar-neutral perp-only book that goes
  long low trailing funding APR and short high trailing funding APR across the
  point-in-time liquid USDT-perp universe. This is evidence-review tooling only,
  with no UI or API promotion entrypoint.
- Frontend files: none.
- Backend/API files: none.
- Backtesting files: `backtesting/funding_xs_dispersion_backtest.py`,
  `backtesting/pipeline_stage3_registry.py`,
  `scripts/run_funding_xs_dispersion_checkpoint.py`.
- Data / DB / artifact files: consumes `data/universe/universe_membership.parquet`,
  Binance venue-scoped `canonical_candles`, `funding_rates`, and
  `venue_instrument_specs`; generated sidecars live under
  `results/idea_batch_20260701_taxonomy_002/f_funding_xs_dispersion/`.
- Config files: none changed.
- Strategy / portfolio files: none changed; target-weight construction reuses
  `okx_quant.strategies.xs_momentum.target_weights` from the research path.
- Tests: `tests/unit/test_funding_xs_dispersion_backtest.py`,
  `tests/unit/test_pipeline_stage3_registry.py`,
  `tests/unit/test_pipeline_checkpoint1_check.py`.
- Docs to update: `docs/EXPERIMENT_REGISTRY.md`,
  `docs/HYPOTHESIS_LEDGER.md`, relevant Change Manifest and session/context
  handoffs.
- Do-not-touch notes: do not enable a strategy, change live funding-carry
  behavior, touch `config/strategies.yaml`, `config/risk.yaml`, risk,
  portfolio, execution, demo/shadow/live gates, or mutate existing result
  artifacts. Stop at checkpoint 1 unless Claude/human explicitly opens the next
  task.

## OI Positioning Research Candidate

- User-facing behavior: checkpoint-only research candidate for
  F-OI-POSITIONING. It tests a daily time-series fade book over the OI-good
  PIT USDT-perp universe, using falling contract-count open interest as the
  positioning signal. This is evidence-review tooling only, with no UI, API,
  config gate, demo, shadow, live, risk, portfolio, or execution entrypoint.
- Frontend files: none.
- Backend/API files: none.
- Backtesting files: `backtesting/oi_positioning_backtest.py`,
  `backtesting/pipeline_stage3_registry.py`,
  `backtesting/differential_validation.py`,
  `scripts/run_oi_positioning_checkpoint.py`.
- Data / DB / artifact files: consumes `data/universe/universe_membership.parquet`,
  Binance venue-scoped `canonical_candles`, `funding_rates`,
  `venue_instrument_specs`, and Binance Vision OI rows in
  `external_observations.fields.open_interest_contracts`; generated sidecars
  live under `results/idea_batch_20260701_taxonomy_002/f_oi_positioning/`.
- Config files: none changed except `config/workstreams.yaml` progress text.
- Strategy / portfolio files: none changed.
- Tests: `tests/unit/test_oi_positioning_backtest.py`,
  `tests/unit/test_pipeline_stage3_registry.py`,
  `tests/unit/test_pipeline_batch2_contracts.py`,
  `tests/unit/test_pipeline_checkpoint1_check.py`.
- Docs to update: `docs/EXPERIMENT_REGISTRY.md`,
  `docs/HYPOTHESIS_LEDGER.md`, `docs/AI_HANDOFF.md`,
  `docs/CURRENT_STATE.md`, relevant Change Manifest and session/context
  handoffs.
- Do-not-touch notes: do not enable a strategy, use `value_num` as OI signal
  input, touch `config/strategies.yaml`, `config/risk.yaml`, risk, portfolio,
  execution, demo/shadow/live gates, or mutate existing result artifacts. Stop
  at checkpoint 1 unless Claude/human explicitly opens the next task.

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
  without automatic family minting. Pipeline improvement P1-P8 adds
  session-scoring handoff files, feedback ranking tags, advisory Stage2
  reprobe, and per-batch funnel metrics; all remain research-only sidecars.
  ADR-0013 adds a registry-scoped, fail-closed statistical-power triage check
  and a ledger/registry-wide derived funnel without changing Stage-3 gates.
  Active callers require candidate-specific power inputs before probes or
  artifacts; the orchestrator carries them on first run and reprobe, and a
  malformed artifact is isolated rather than aborting the schema-v3 funnel.
  F-OI-POSITIONING Stage-2 data availability first read BTC/ETH Binance Vision
  5m OI (`oi_binance_hist_btc` / `oi_binance_hist_eth`, E-034), then the
  user-directed universe-wide backfill/probe generalized the dataset convention
  to `oi_binance_hist_<base>` and evaluates PIT-eligible days per symbol
  (E-036). E-037 then ran the signed-off Stage-3 Task B checkpoint with
  family-minting vs F-FUNDING-XS-DISPERSION and the pre-registered 4-combo
  fold-refit WF/CPCV grid; checkpoint1 fails the DSR/PSR threshold, so
  promotion remains blocked. F-VOL-REGIME-OPT E-040/E-041 are separate one-off
  Stage-2 calibrations: they deterministically sample E-039 month-first rows,
  stream free Tardis Deribit option chains to the 08:00 UTC as-of snapshot,
  and write real-vs-BS premium diagnostics or a fail-closed record. E-041 uses
  DB hourly DVOL published as-of 08:00 for the synthetic denominator and stops
  before Tardis acquisition when that DB input is unavailable. Taxonomy_004
  adds the research-only F-XVENUE-FUNDING-SPREAD path: E-053 is retained as
  F41-invalid evidence, E-054 is the bounded settlement-timestamp reprobe, and
  E-055 verifies complete venue-scoped Deribit perpetual 1m prices. The
  separately authorized Stage-3 runner uses the identical frozen four-cell
  signal grid, ADR-0012 exact inverse-perpetual accounting, base-cost fold-refit
  WF/CPCV, stress re-costing, and checkpoint-only artifacts. It is not wired to
  any UI/API or deployment surface.
- Frontend files: `frontend/app.js`, `frontend/data.js`, and
  `frontend/view-ledger.js` provide only the read-only generated funnel projection;
  no pipeline runner or promotion control is exposed.
- Backend/API files: none.
- Backtesting files: `backtesting/pipeline_feasibility.py`,
  `backtesting/pipeline_checkpoint1.py`, `backtesting/pipeline_family_minting.py`,
  `backtesting/pipeline_idea_generator.py`, `backtesting/pipeline_refit.py`,
  `backtesting/pipeline_power_screen.py`, `backtesting/pipeline_stage2_registry.py`,
  `backtesting/pipeline_stage3_registry.py`,
  `backtesting/xvenue_funding_spread_probe.py`,
  `backtesting/xvenue_funding_spread_backtest.py`.
- Script files: `scripts/run_pipeline_stage2_check.py`,
  `scripts/run_pipeline_checkpoint1_check.py`,
  `scripts/run_pipeline_family_minting_check.py`,
  `scripts/run_pipeline_idea_generator.py`,
  `scripts/run_pipeline_literature_ideas.py`,
  `scripts/run_pipeline_orchestrator.py`,
  `scripts/run_pipeline_funnel_report.py`,
  `scripts/literature_keyword_scorer.py`;
  E-040/E-041 use `research/probes/f_vol_regime_opt_stage2.py`.
- Data / DB / artifact files: reads `docs/EXPERIMENT_REGISTRY.md` and
  `docs/HYPOTHESIS_LEDGER.md`; writes advisory sidecars under new
  `results/<batch_id>/` directories without mutating existing artifacts.
  E-040/E-041 read immutable
  `results/stage1_probe_20260713_f_vol_regime_opt/series_*.csv`; E-041 also
  reads `dvol_deribit_{btc,eth}_1h` from `external_observations`. Each run
  writes only its new `results/stage2_probe_*_f_vol_regime_opt*/` directory.
  E-053/E-054 read `funding_rates`, `external_observations`, and venue-scoped
  `canonical_candles`, then write only
  `results/idea_batch_20260715_taxonomy_004/` sidecars.
- Config files: `config/pipeline_feedback_tags.yaml` for Claude/human-owned
  feedback ranking tags. This is not a strategy, risk, settings, or deployment
  gate config.
- Tests: `tests/unit/test_pipeline_checkpoint1_check.py`,
  `tests/unit/test_pipeline_power_screen.py`,
  `tests/unit/test_pipeline_stage2_data_probe.py`,
  `tests/unit/test_pipeline_stage2_registry.py`,
  `tests/unit/test_pipeline_family_minting.py`,
  `tests/unit/test_pipeline_idea_generator.py`,
  `tests/unit/test_pipeline_literature_ideas.py`,
  `tests/unit/test_literature_keyword_scorer.py`,
  `tests/unit/test_pipeline_orchestrator.py`,
  `tests/unit/test_pipeline_funnel_report.py`,
  `tests/unit/test_f_vol_regime_opt_stage2.py`,
  `tests/unit/test_xvenue_funding_spread_probe.py`,
  `tests/unit/test_h021_inverse_perp_accounting.py`.
- Docs to update: `docs/INVARIANTS.md`, `docs/KNOWN_ISSUES.md`,
  `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `config/workstreams.yaml`,
  relevant Change Manifest, and `docs/ADR/0013-stage2-statistical-power-triage.md`
  for the Stage-2 power contract.
- Do-not-touch notes: automation sidecars are advisory research controls only.
  They must not append durable ledger rows, change `research/strategy_synthesis.md`,
  enable strategies, run backtests, change CPCV/DSR/gate semantics, alter
  config gates, or touch demo/shadow/live behavior without explicit approval.
  H-021 is a one-run explicit exception limited to E-056 checkpoint ①; its
  runner refuses to overwrite an existing summary and never substitutes an
  index price.

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
  `backtesting/replay.py`; shared artifact-ID validation and contained child
  resolution live in `backtesting/artifact_rows.py`.
- Data / DB / artifact files: `sql/migrations/0010_backtest_runs.sql`,
  runtime `result`, `metrics`, `config`, `price_series`, `indicator_series`, `fills`,
  `orders`, `trades`, `funding`, `risk_events`, and coverage artifacts.
- Config files: `config/settings.yaml`, `config/risk.yaml`, `config/strategies.yaml`.
- Tests: `tests/unit/test_backtest_artifact_schema.py`,
  `tests/unit/test_backtesting.py`, `tests/unit/test_artifact_rows.py`.
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
  `tests/unit/test_parameter_sweep.py`, `tests/unit/test_backtesting.py`,
  `tests/unit/test_all_strategy_signal_validation.py`,
  `tests/unit/test_source_provenance_validation.py`.
- Trust boundary: caller-controlled run, sweep, fixture, strategy, validation,
  and validation-artifact identifiers are rejected unless they are safe single
  path components; every filesystem child is resolved below its intended root.
- Docs to update: `docs/ai_collaboration.md`, `docs/backtest_live_parity_plan.md`,
  `docs/results_validation_manifest.md`, `docs/AI_HANDOFF.md`.
- Do-not-touch notes: validation harness/interface changes must not alter strategy,
  risk, portfolio, execution, DB schema, existing result artifacts, or reference
  adapter tolerances unless the task explicitly permits it. Advisory validation
  output is not live-readiness evidence.

## H-014 Deribit Options Shadow Execution

- User-facing behavior: manually run one credential-free daily H-014 cycle;
  reproduce the accepted research signal from F26-safe DB inputs, select the
  current nearest-30d option chain, atomically simulate sells at bid/buys at
  ask, append R8 records (including journaled chain misses and R8.3 rejections),
  and generate the ADR-0011 bias report.
- Frontend/API files: none.
- Execution files: `src/okx_quant/execution/deribit_shadow/`,
  `scripts/run_h014_shadow.py`.
- Data / artifacts: reads `external_observations` and `canonical_candles`, then
  Deribit allow-listed public REST data; appends runtime JSONL under
  `results/shadow_h014/`. No DB write or schema change.
- Config: `config/h014_shadow.yaml` freezes `ivp_min=85`, `z_min=0.5`,
  1/30-unit tranches, and the 1.0-unit cap; `config/risk.yaml` is untouched.
- Research imports (read-only): `research/probes/f_vol_regime_opt_probe.py`,
  `research/probes/h014_collect_leg_marks.py`,
  `research/probes/h014_stage3_backtest.py`.
- Tests: `tests/unit/test_h014_shadow.py`,
  `tests/unit/test_h014_options_accounting.py`.
- Docs: ADR-0011, `docs/DOMAIN_RULES.md` R8, `docs/DATA_FLOW.md`, this map,
  `docs/RUNBOOK.md`, and the change manifest.
- Do-not-touch notes: no private/authenticated endpoint, broker/order path,
  credential, scheduler registration, strategy/risk/portfolio module, DB
  schema, live gate, or frozen parameter change is allowed.

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
