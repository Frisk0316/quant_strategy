---
status: current
type: architecture
owner: human
created: 2026-06-12
last_reviewed: 2026-06-12
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
  visual state such as chart ranges and Y zoom.
- It calls `window.API.fetchBacktest`, `fetchBacktestEquity`,
  `fetchBacktestFills`, `fetchBacktestTrades`, `fetchBacktestPriceSeries`,
  `fetchBacktestExecutionMarkers`, `fetchBacktestIndicators`,
  `fetchBacktestRiskEvents`, `fetchWalkForward`, and `fetchCPCV`.
- Backend endpoints are implemented in `src/okx_quant/api/routes_backtest.py`.

## Chart Components

- `frontend/charts.js` exports `LineChart`, `BarChart`, `HistogramChart`,
  `TradePriceChart`, `IndicatorChart`, `adaptiveDateLabel`, and `MAX_Y_ZOOM`.
- `TradePriceChart` is used for market price series plus execution markers.
- `IndicatorChart` is used for technical strategies and supports price, fast/slow
  series, MACD/signal/histogram, warmup source display, visible-series controls,
  shared market X range, and independent Y zoom.
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
- `fetchBacktestMetrics`: `GET /api/backtest/{run_id}/metrics`.
- `fetchBacktestEquity`: `GET /api/backtest/{run_id}/equity`.
- `fetchBacktestReturns`: `GET /api/backtest/{run_id}/returns`.
- `fetchBacktestDrawdown`: `GET /api/backtest/{run_id}/drawdown`.
- `fetchBacktestFills`: `GET /api/backtest/{run_id}/fills`.
- `fetchBacktestTrades`: `GET /api/backtest/{run_id}/trades`.
- `fetchBacktestExecutionMarkers`: `GET /api/backtest/{run_id}/execution-markers`.
- `fetchBacktestPriceSeries`: `GET /api/backtest/{run_id}/price-series`.
- `fetchBacktestIndicators`: `GET /api/backtest/{run_id}/indicators`.
- `fetchDataCoverage`: `GET /api/data/coverage`.
- `fetchDataInstruments`: `GET /api/data/instruments`.
- `triggerDataFetch`: `POST /api/data/fetch`.
- `dataExportUrl`: `GET /api/data/export`.

Validation-lab calls exist in `frontend/view-validation.js`, but validation engine
implementation is out of scope for AI-context/harness work when another session owns
that area.

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
