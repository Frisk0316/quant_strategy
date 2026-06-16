---
status: current
type: architecture
owner: human
created: 2026-06-12
last_reviewed: 2026-06-12
expires: none
superseded_by: null
---

# Data Flow

Each flow uses:

```text
source -> script/module -> storage -> consumer -> artifact/result -> UI/API
```

## Historical OHLCV Ingestion Flow

```text
exchange REST candles -> scripts/market_data/ingest.py or legacy download scripts -> raw_candles plus canonical_candles and optional parquet mirror -> backtesting.data_loader.load_candles -> ReplayBacktestEngine -> price/equity/result artifacts -> routes_backtest.py and frontend charts
```

Current: DB-backed ingestion is available when `DATABASE_URL` or
`config/settings.yaml` DSN is reachable. Known gap: local environments without DB
must rely on parquet fallback or skip DB-dependent validation.

## Funding Ingestion Flow

```text
OKX funding history -> scripts/market_data/backfill_funding.py or scripts/market_data/import_parquet_funding.py -> funding_rates -> backtesting.data_loader.load_funding -> ReplayBacktestEngine funding cashflow path -> funding artifacts and validation fields -> backtest API and review docs
```

Current: funding rates are part of the data layer. Known gap: funding coverage and
DB parity must be verified per strategy before deployment evidence is accepted.

## Parquet Fallback Flow

```text
local parquet candles/funding -> backtesting.data_loader -> scripts/run_replay_backtest.py -> file artifacts under a run directory -> routes_backtest.py file readers -> frontend result display
```

Current: parquet fallback supports no-DB development and historical compatibility.
Known gap: fallback artifacts are not a substitute for DB parity or authoritative
`ct_val` provenance when promotion gates require them.

## TimescaleDB / Canonical Candle Flow

```text
raw exchange rows -> CandleStore upsert and canonicalize methods -> raw_candles, market_klines, canonical_candles, derived aggregate views -> data loader and coverage API -> replay/API consumers -> charts and coverage panels
```

Current: canonical priority is centralized in `okx_quant.data.canonical_policy`.
Target: every promoted run should cite data coverage and source validation evidence.

## Backtest Run Flow

```text
frontend Run Backtest form -> POST /api/backtest/run -> routes_backtest.py background job -> scripts/run_replay_backtest.py or strategy-specific runner -> results run directory or DB artifacts -> job status and run list -> frontend Backtest view
```

Current: the UI can run replay, daily-winner, and OHLCV-rotation paths. Known gap:
lightweight Makefile smoke does not yet run a tiny frozen replay fixture.

## Backtest Artifact Generation Flow

```text
ReplayBacktestResult -> backtesting.artifacts.save_backtest_artifacts -> files, DB rows, or both depending on artifact mode and DSN -> routes_backtest.py artifact readers -> frontend charts, tables, and downloads
```

Current: artifact mode is controlled by environment and DSN availability. Do not
edit existing historical artifacts as part of code or docs cleanup.

## Indicator Series Flow

```text
price_series plus strategy params -> backtesting.artifacts indicator recomputation -> indicator_series artifact with warmup source -> GET /api/backtest/{run_id}/indicators -> frontend IndicatorChart
```

Current: indicator charts are visual review aids. Indicator recomputation must not
silently change strategy signal logic.

## Frontend Result Display Flow

```text
run list selection -> window.API helpers in frontend/data.js -> routes_backtest.py endpoints -> result JSON and time-series artifacts -> frontend/view-backtest.js and frontend/charts.js -> user review
```

Current: frontend result display is a review surface, not a deployment gate by
itself. If API fields are missing, inspect artifacts before changing UI defaults.

## Validation Artifact Flow

```text
saved run artifacts -> validation runner and reference adapters -> validation result directory -> validation API endpoints -> frontend Validation Lab -> promotion review
```

Current: validation views, APIs, and a batch portable signal-validation harness
exist. `make strategy-signal-validation` generates deterministic active-strategy
fixtures and writes validation artifacts under `results/strategy_validation/`.
Known gap status must come from `docs/AI_HANDOFF.md`,
`docs/ai_collaboration.md`, and fresh validation artifacts; missing optional
reference-engine dependencies produce SKIP rows and do not satisfy
`portable_validation_gate`.
