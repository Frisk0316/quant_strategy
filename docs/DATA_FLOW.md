---
status: current
type: architecture
owner: human
created: 2026-06-12
last_reviewed: 2026-06-22
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

## Market Data Fetch Queue Flow

```text
frontend Market Data Coverage form -> POST /api/data/fetch -> in-memory queued job -> routes_data._fetch_lock -> exchange REST + venue spec sync + CandleStore writes -> DB + parquet mirror -> /api/data/fetch/jobs -> frontend job list and coverage refresh
```

Current: fetch jobs are accepted as `queued` and run sequentially behind one
process-local lock. Binance fetches parse `exchangeInfo` precision filters and
upsert `venue_instrument_specs(exchange, symbol)` before candle writes, so
downloaded Binance multiplier contracts such as `1000SHIB-USDT-SWAP` have DB
`ct_val = 1.0` provenance for replay. Queued or running jobs can be cancelled; a
queued job checks for cancellation before it acquires the lock, so it never
starts after a cancel.

## Market Data Pair Delete Flow

```text
frontend coverage row Delete -> DELETE /api/data/pairs/{inst_id} -> transactional DB purge -> data/ticks/<inst_id with dashes replaced>/ directory removal -> coverage/exchange lists refresh
```

Current: the delete route removes the pair from `market_klines`,
`market_funding_rates`, `market_instruments`, `canonical_candles`,
`raw_candles`, `funding_rates`, `instrument_bars`, `instruments`, and the local
parquet mirror directory. The API returns 409 if a non-terminal fetch job lists
the same pair; parquet deletion errors are surfaced but do not roll back the DB
transaction.

## Venue Instrument Spec Flow

```text
venue instrument source -> venue_instrument_specs(exchange, symbol) seed/table -> ReplayBacktestEngine._load_db_instrument_specs(exchange) -> per-symbol ct_val/lot/tick/min specs -> sizing, fills, funding, terminal liquidation, and result.validation.ct_val_sources
```

Current: P1 seeds OKX and Binance BTC/ETH SWAP specs manually, and the Market
Data Fetch Queue now syncs Binance rows from `exchangeInfo` into
`venue_instrument_specs` as `source = binance_exchange_info`. The bundled
`config/instrument_specs.yaml` registry remains an OKX-only fallback for local
replay when DB specs are unavailable; promotion evidence must use DB-backed or
explicit `instrument_specs` provenance tagged with the run `exchange`. Normal
Binance/Bybit USDT-M perps can use the authoritative `exchange_base_unit`
structural identity (`ct_val = 1.0`) without a DB row; canonical `1000...`
multiplier contracts still require explicit `venue_instrument_specs` rows, now
created automatically for Binance symbols that pass through the fetch flow.

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
Validation DB parity filters canonical candles by `source_primary` when a run
records `result.validation.exchange`, so the candle comparison is scoped to the
execution venue rather than only the canonical symbol. For `price_series.csv`
provenance, DB parity compares timestamped `close` values only; artifact OHLCV
structure remains a separate artifact-level check because replay price series may
carry close-flattened O/H/L and quote-volume units. The validation output must
surface the venue scope as `checks.db_parity.canonical_source_primary`; a Binance
DB-backed PASS must show `binance` there.

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

Fast-read path: `save_backtest_artifacts` keeps writing the compatibility
`backtest_artifacts.payload` rows/files, then best-effort writes derived
`backtest_artifact_rows` records for large list artifacts. The row table is a
read index only. API chart/table endpoints try row records first for symbol
filters, `LIMIT/OFFSET`, and downsample reads, then fall back to the old
JSONB/file readers. Existing runs require
`scripts/backfill_backtest_artifact_rows.py --all --verify` after migration
0012 before their first-click artifact reads can use the fast path.

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

Current fast-load behavior: backtest selection calls
`GET /api/backtest/{run_id}/summary` first so metrics, symbols, validation flags,
and artifact availability can paint before chart/table fetches finish. Full
`GET /api/backtest/{run_id}` remains available for compatibility.

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

Run-scoped differential validation CSV artifacts may be indexed in
`backtest_artifact_rows` as `validation/{validation_id}/{artifact_name}` for
faster artifact detail reads. Strategy-validation artifacts stay file-backed
because they are not keyed by `backtest_runs.run_id`.
