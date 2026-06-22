---
status: current
type: architecture
owner: human
created: 2026-06-12
last_reviewed: 2026-06-22
expires: none
superseded_by: null
---

# UI Map

Use this map to locate frontend behavior before changing code. Do not modify
frontend code during documentation-only work unless the user explicitly approves it.

## App Entry

- `frontend/index.html` loads the static React/HTM app and module scripts.
- `frontend/app.js` owns top-level app state, left navigation, selected run state,
  live status polling, and view routing.
- `frontend/data.js` defines `window.MOCK`, strategy metadata, metric descriptions,
  and `window.API` helpers.
- `src/okx_quant/api/server.py` mounts the frontend and API routers.

Main app views in `frontend/app.js`:

- `config`: `window.RunConfigView` from `frontend/view-config.js`.
- `backtest`: `window.BacktestView` from `frontend/view-backtest.js`.
- `validation`: `window.ValidationLabView` from `frontend/view-validation.js`.
- `wf` / `cpcv`: walk-forward and CPCV panels from `frontend/view-results.js`.
- `trades`, `compare`, `metrics`, and `risk`: secondary review views.

## Backtest View

- `frontend/view-backtest.js` owns run selection, result loading, metrics cards,
  market charts, indicator cards, execution markers, fills/trades summaries, and
  visual state such as chart ranges and Y zoom. The run detail header separates
  long display names from metadata chips so DB/display-name-heavy runs can wrap;
  the Risk events tab summarizes top blocked reasons, symbols, strategies, and
  the signal-to-fill gap for the selected chart symbols.
- It calls `window.API.fetchBacktestSummary` for initial selection,
  falls back to `window.API.fetchBacktest`, then calls `fetchBacktestEquity`,
  `fetchBacktestFills`, `fetchBacktestTrades`, `fetchBacktestSignals`,
  `fetchBacktestPriceSeries`, `fetchBacktestExecutionMarkers`,
  `fetchBacktestIndicators`,
  `fetchBacktestRiskEvents`, `fetchWalkForward`, and `fetchCPCV`.
- Backend endpoints are implemented in `src/okx_quant/api/routes_backtest.py`.
- Chart/table endpoints are row-index backed when `backtest_artifact_rows`
  contains derived records; the UI response shape is unchanged.

## Chart Components

- `frontend/charts.js` exports `LineChart`, `BarChart`, `HistogramChart`,
  `TradePriceChart`, `IndicatorChart`, `adaptiveDateLabel`, and `MAX_Y_ZOOM`.
- `TradePriceChart` is used for market price series plus execution markers.
- The Backtest "Price + Trade Markers" card is strategy-agnostic: every selected
  chart symbol gets its own price panel, loading state, and empty/error state.
  Price panels expose inline Y reset/Y+/Y-/slider controls; technical indicator
  overlays remain gated to `ma_crossover`, `ema_crossover`, and
  `macd_crossover`.
- `IndicatorChart` is used for technical strategies and supports price, fast/slow
  series, MACD/signal/histogram, warmup source display, visible-series controls,
  shared market X range, and independent Y zoom, including visible Y scale
  controls on indicator and MACD sub-panels.
- `frontend/view-backtest.js` owns chart state maps: market/equity/drawdown ranges,
  per-chart Y zooms, selected chart symbols, loaded price rows, indicator rows, and
  symbol load status.

## Strategy Parameter Controls

- Strategy list lives in `frontend/data.js` under `STRATEGIES`.
- Backtest controls live in `frontend/view-config.js`.
- Parameter defaults live in `STRATEGY_PARAM_DEFAULTS`.
- Parameter sweep defaults/specs live in `SWEEP_PARAM_DEFAULTS` and
  `SWEEP_PARAM_SPECS`.
- `frontend/view-config.js` owns the run-level Exchange selector. It sends
  `exchange` on both run-backtest and parameter-sweep payloads; the API stores it
  as `cfg.storage.primary_exchange`.
- Technical strategies are `ma_crossover`, `ema_crossover`, and `macd_crossover`.
- External-feature research baselines are `fear_greed_sentiment` and `cme_gap_fill`.
- `daily_winner` is tagged as validation-only and is not deployment evidence.

## Metrics Glossary

- `frontend/view-glossary.js` groups metric descriptions for the Metrics Glossary
  view.
- Metric descriptions are sourced from `window.METRIC_DESCRIPTIONS` in
  `frontend/data.js`.
- Backtest metric cards are rendered from result metrics in `frontend/view-backtest.js`
  and summary panels in `frontend/view-results.js`.

## API Calls Used By Frontend

`frontend/data.js` maps frontend calls to FastAPI endpoints:

- `fetchRuns` / `fetchBacktestRuns`: `GET /api/backtest/runs`.
- `triggerBacktestRun`: `POST /api/backtest/run`.
- `fetchBacktestRunStatus`: `GET /api/backtest/run/status/{job_id}`.
- `triggerBacktestSweep`: `POST /api/backtest/sweep`.
- `fetchBacktest`: `GET /api/backtest/{run_id}`.
- `fetchBacktestSummary`: `GET /api/backtest/{run_id}/summary`.
- `fetchBacktestMetrics`: `GET /api/backtest/{run_id}/metrics`.
- `fetchBacktestEquity`: `GET /api/backtest/{run_id}/equity`.
- `fetchBacktestReturns`: `GET /api/backtest/{run_id}/returns`.
- `fetchBacktestDrawdown`: `GET /api/backtest/{run_id}/drawdown`.
- `fetchBacktestFills`: `GET /api/backtest/{run_id}/fills`.
- `fetchBacktestTrades`: `GET /api/backtest/{run_id}/trades`.
- `fetchBacktestSignals`: `GET /api/backtest/{run_id}/signals`.
- `fetchBacktestRiskEvents`: `GET /api/backtest/{run_id}/risk-events`.
- `fetchBacktestExecutionMarkers`: `GET /api/backtest/{run_id}/execution-markers`.
- `fetchBacktestPriceSeries`: `GET /api/backtest/{run_id}/price-series`.
- `fetchBacktestIndicators`: `GET /api/backtest/{run_id}/indicators`.
- `fetchDataCoverage`: `GET /api/data/coverage`.
- `fetchDataInstruments`: `GET /api/data/instruments`.
- `triggerDataFetch`: `POST /api/data/fetch`.
- `fetchDataFetchJobs`: `GET /api/data/fetch/jobs`.
- `fetchDataFetchStatus`: `GET /api/data/fetch/status/{job_id}`.
- `cancelDataFetch`: `POST /api/data/fetch/cancel/{job_id}`.

`fetchRuns` / `fetchBacktestRuns` and `fetchDataCoverage` use a short in-flight
cache in `frontend/data.js` to dedupe repeated UI requests while preserving fresh
manual reload behavior.
- `deleteDataPair`: `DELETE /api/data/pairs/{inst_id}`.
- `dataExportUrl`: `GET /api/data/export`.

## Market Data Coverage

- `frontend/view-config.js` owns the Market Data Coverage card.
- Fetch submissions are no longer blocked by another active fetch. The card
  renders the `/api/data/fetch/jobs` list with queued/running/done/error/cancelled
  statuses and per-job cancel controls. For Binance, `POST /api/data/fetch`
  also syncs exchangeInfo-derived venue specs into `venue_instrument_specs`
  before candle writes.
- Coverage rows for OHLCV and funding pairs include a Delete button. The button
  uses a native confirmation dialog, calls `deleteDataPair`, and refreshes
  coverage when the API succeeds. External dataset rows are not pair-delete
  targets.

Validation-lab calls live in `frontend/view-validation.js`. The selector merges
saved Backtest Runs from `GET /api/backtest/runs` with strategy fixture candidates:
saved runs trigger run-scoped `POST /api/backtest/{run_id}/differential-validation/run`,
while remaining strategy fixtures use `POST /api/backtest/strategy-validation/run`.
Run-scoped mismatch previews use the run validation artifact endpoint.

## Common UI Bug Locate Flow

1. Check browser console for module load, syntax, fetch, or rendering errors.
2. Check Network tab for failed `/api/...` calls and response shape.
3. Locate the view in `frontend/app.js`.
4. Locate API helper in `frontend/data.js`.
5. Locate the owning component in `frontend/view-*.js` or `frontend/charts.js`.
6. Locate backend route in `src/okx_quant/api/routes_backtest.py` or
   `src/okx_quant/api/routes_data.py`.
7. If the issue is data shape, inspect `backtesting/artifacts.py` and the run
   artifact directory before changing frontend assumptions.
8. Run `make frontend-check` and a targeted Python test if API shape changed.
