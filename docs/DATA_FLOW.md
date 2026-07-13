---
status: current
type: architecture
owner: human
created: 2026-06-12
last_reviewed: 2026-07-13
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
Venue-tagged replay runs are stricter: when a run declares `exchange`, candles
must come from the canonical Postgres path filtered by `source_primary=<exchange>`.
If that venue's bar is missing, the run reports a gap/error instead of falling
back to source-less parquet or another venue. A late-listing symbol is the
exception: coverage is measured from its first observed bar (not the requested
start), so multi-symbol backtests can mix coins with different listing dates.
An empty venue series still errors, and an internal hole below
`VENUE_GAP_MIN_COVERAGE` (0.80 from the first bar) still raises — no cross-venue
substitution is ever allowed.
Funding-carry spot synthetic books may use an explicit same-venue perp fallback
when spot candles are absent; the fallback remains venue-scoped.

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
Every DB, registry, or caller-supplied multiplier is validated as finite
`0 < ct_val <= 1e7` before it enters replay specs or receives a provenance
label. A malformed or incomplete explicit instrument spec fails closed; it is
not converted into a fallback or an authoritative `None` value.

## Funding Ingestion Flow

```text
OKX funding history -> scripts/market_data/backfill_funding.py or scripts/market_data/import_parquet_funding.py -> funding_rates -> backtesting.data_loader.load_funding -> ReplayBacktestEngine funding cashflow path -> funding artifacts and validation fields -> backtest API and review docs
Binance funding history + PIT universe -> scripts/market_data/backfill_universe_funding.py -> funding_rates plus local coverage report -> advisory Stage2 data reprobe
```

Current: funding rates are part of the data layer. Known gap: funding coverage and
DB parity must be verified per strategy before deployment evidence is accepted.
The coverage API labels funding provider/exchange from `funding_rates.source`
instead of a hard-coded venue label. `backfill_universe_funding.py` is a
research-pipeline utility for Binance universe-wide funding coverage and writes
local parquet/coverage JSON before attempting DB upsert and advisory Stage2
reprobe; it does not alter funding cashflow math or strategy gates. The Stage-2
funding breadth probe (`backtesting/pipeline_stage2_registry.py`) evaluates its
breadth minimum from `START + breadth_warmup_days` (30, mirroring
`config/universe.yaml` warmup) because PIT eligibility cannot exist during
warmup; warmup days stay recorded in probe details for audit (user-approved
2026-07-03, manifest `2026-07-03-stage2-breadth-warmup.md`).

## External Observations Ingestion Flow

```text
keyless external HTTP endpoint -> scripts/market_data/ingest_external.py adapter -> external_datasets and external_observations -> Stage-2 external-feature coverage probes and as-of feature loaders plus GET /api/data/external-series -> research artifacts / data export / Derivatives context chart
```

Current: `config/external_data.yaml` registers keyless adapters for
Alternative.me Fear & Greed, Binance futures open interest, Deribit DVOL,
Deribit funding, Deribit option-surface snapshots, and Deribit option flow,
plus API-key or research-only adapters for FRED, Nasdaq Data Link, and
yfinance. Built-in `ingest_external.py` datasets now add keyless OKX
liquidation forward accumulation (`liq_okx_btc`, `liq_okx_eth`) without changing
the checked-in `config/external_data.yaml`. `BinanceOIClient` writes
`oi_binance_btc` / `oi_binance_eth` as hourly USDT-notional open-interest
observations (`value_num = sumOpenInterestValue`, `fields.unit =
"USDT_notional"`). `download_binance_vision_metrics.py` is the public historical
OI path for Binance Vision UM daily metrics; it validates the BTCUSDT schema
fail-closed before ingesting 5m `sum_open_interest_value` observations with
`provenance = binance_vision_metrics`, stores contract-count OI in
`fields.open_interest_contracts`, and can derive PIT-universe dataset ids as
`oi_binance_hist_<base>` from `data/universe/universe_membership.parquet`
starting each symbol at its first eligible day. `OKXLiquidationClient` writes raw
long/short liquidation event observations from OKX public REST when available;
notional is source-provided or computed from `sz * bkPx * contract_value` and
raw payloads are preserved. `DeribitDVOLClient` writes `dvol_deribit_btc` /
`dvol_deribit_eth` as daily DVOL close observations and
`dvol_deribit_btc_1h` / `dvol_deribit_eth_1h` as hourly DVOL close
observations (`fields.unit = "dvol_index_points"`). For bucketed external
aggregates, `observed_at` is the market bucket label and `published_at` is the
bucket end, which is the earliest safe as-of timestamp for replay joins; Deribit
hourly DVOL and option-flow rows therefore publish one hour after
`observed_at`, and daily DVOL publishes one day after `observed_at`.
`DeribitFundingClient` writes `funding_deribit_btc` / `funding_deribit_eth` as
hourly BTC-PERPETUAL/ETH-PERPETUAL funding observations with `value_num =
interest_1h` and `fields.unit = "rate_1h_decimal"`; Deribit funding timestamps
are treated as accrual-period end and are safe to use as both `observed_at` and
`published_at`.
`DeribitOptionSurfaceClient` writes forward-only `optsurf_deribit_btc` /
`optsurf_deribit_eth` snapshots as one hourly aggregate row per currency:
`value_num` is total option open interest, fields carry put/call OI, put/call
ratio, max pain pooled across all listed expiries in the one-row-per-currency
snapshot, OI-weighted mark IV, and spot index, and raw payloads are bounded to
the top 20 instruments by open interest. `DeribitOptionFlowClient`
and `backfill_deribit_option_flow.py` write `optflow_deribit_btc` /
`optflow_deribit_eth` as hourly inverse-option trade-flow aggregates from the
Deribit options tape: `value_num` is put-vs-call taker-buy premium imbalance,
fields carry buy/sell premium amounts, IV, trade/liquidation counts, and the
USDC-linear exclusion count, and raw payloads keep only a bounded trade sample.
Hours containing only excluded USDC-linear option trades still emit a row with
`value_num = null` and `fields.excluded_linear_usdc_count > 0`, so inverse-only
v1 coverage preserves the exclusion evidence. Empty option-flow backfill chunks
can advance cleanly because zero inverse trades is a valid historical outcome;
other required external datasets marked `fail_on_empty_fetch` still fail closed
on an empty generic ingest.
`GET /api/data/external-series` reads `external_observations` by `dataset_id`,
optional UTC `start`/`end` bounds, filters to numeric `value_num`, downsamples to
at most 5000 points while preserving endpoints, and exposes `{t, v}` rows plus
the first available `fields.unit`; unknown dataset ids return 404 before the
series query. The Run Backtest Derivatives context card uses this route for
Deribit datasets through `window.API.fetchExternalSeries` and the existing
`window.Charts.LineChart`.
External export reads DB rows directly through `GET /api/data/export?kind=external`.
The frontend runs the optional best-effort refresh pre-step only for selected
yfinance datasets. Selected DB-only datasets bypass refresh and export existing
rows directly, so they are not presented as skipped. The refresh API still
returns `skipped` for non-on-demand or dynamically registered DB datasets when
called directly; only datasets unknown in both yaml and `external_datasets` are
rejected.

Known gap: Binance's public `openInterestHist` endpoint only exposes roughly the
recent ~30-day window, so that adapter remains forward accumulation; historical
OI should come from Binance Vision public dumps rather than a paid provider or
proxy series. OKX liquidation REST also appears to be a recent-window source, so
liquidation datasets are forward-accumulated from the first successful run; no
daemon or Binance websocket collector exists yet. Deribit DVOL has historical
windows available through its public endpoint, but whether a Deribit
options-volatility signal is tradable on this repo's perp execution track
remains a research-layer question, not an ingestion-layer gate change. Adding
these datasets makes future Stage-2 data-availability probes possible; it does
not create strategies, families, or promotion evidence.

E-040/E-041 are intentionally outside the option-chain DB ingestion path:

```text
immutable E-039 series_{btc,eth}.csv -> deterministic month-first IVP extremes
  + (E-041) external_observations hourly DVOL published as-of 08:00 UTC
  + Tardis.dev free Deribit options_chain daily gzip -> nearest-08:00 UTC as-of chain
  -> results/stage2_probe_*_f_vol_regime_opt*/{per_day_legs.csv,stage2_feasibility.json}
```

The probe streams gzip input without retaining vendor source files, stops on the
first network/schema/size failure, records the command and error, and never
substitutes DB option-surface snapshots or another vendor. Its artifacts are
research diagnostics only, not option-chain ingestion or promotion evidence.
E-041 keeps the 2 GiB ceiling as a compressed bytes-read guard, never falls back
from missing hourly to daily DVOL, and writes `probe_status=FAIL_CLOSED` without
a pricing `verdict.status` when the complete fixed sample cannot be evaluated.

## Point-In-Time Universe Membership Flow

```text
1m candle parquet by symbol -> scripts/build_universe_membership.py --source parquet -> data/universe/universe_membership.parquet -> xs_momentum target-weight and validation consumers
canonical_candles daily dollar volume (DB) -> scripts/build_universe_membership.py --source db -> data/universe/universe_membership.parquet -> Stage-2 funding/xvenue probes and xs_momentum consumers
venue-scoped canonical OHLCV/funding -> backtesting.xs_momentum_backtest.load_xs_momentum_inputs -> backtesting.xs_momentum_backtest.run_xs_momentum_backtest -> local research artifact
```

Current: `config/universe.yaml` defines the Binance USDT-perp research universe
rules, including top-N, rolling ADV threshold, warmup, rebalance cadence, and
deny-list patterns. `scripts/build_universe_membership.py` derives daily dollar
volume either from local 1m candle parquet (`--source parquet`, default) or
from `canonical_candles` daily aggregates (`--source db`), feeding the exact
same `build_membership()` eligibility formula either way; it uses only prior
history for ADV and warmup eligibility and does not forward-fill symbols
across missing or ended candle history. Known gap fixed 2026-07-04: the
parquet source is only a thin local mirror, so it silently understated PIT
eligibility (median 2 eligible/day) versus the DB source (median 28); the
shared `data/universe/universe_membership.parquet` was rebuilt with
`--source db` and Stage-2 funding breadth now passes data availability
(`docs/HYPOTHESIS_LEDGER.md` H-009, `docs/EXPERIMENT_REGISTRY.md` E-030).
`backtesting/xs_momentum_backtest.py` can consume venue-scoped canonical
OHLCV/funding inputs for research smoke runs, applies the R3.1 funding sign
convention, shifts daily target weights one full day before intraday expansion to
avoid same-day-close lookahead, sizes XS momentum gross from estimated portfolio
book volatility with a max-gross cap, and can pass a `market_close` proxy into
the crash filter. Known gap:
this remains research-tier until the A2 coverage task verifies at least 25
symbols with 12 months of both parquet and venue-scoped canonical DB coverage and
promotion validation runs WF/CPCV plus DSR/PSR.

## Parquet Fallback Flow

```text
local parquet candles/funding -> backtesting.data_loader -> scripts/run_replay_backtest.py -> file artifacts under a run directory -> routes_backtest.py file readers -> frontend result display
```

Current: parquet fallback supports no-DB development and historical compatibility.
Known gap: fallback artifacts are not a substitute for DB parity or authoritative
`ct_val` provenance when promotion gates require them.
Parquet fallback is disabled for venue-tagged candle reads because local parquet
mirrors do not carry a per-row source venue.

## TimescaleDB / Canonical Candle Flow

```text
raw exchange rows -> CandleStore upsert and canonicalize methods -> raw_candles, market_klines, canonical_candles, derived aggregate views -> data loader and coverage API -> replay/API consumers -> charts and coverage panels
```

Current: canonical priority is centralized in `okx_quant.data.canonical_policy`.
The Market Data Coverage API reads OHLCV list rows from `instrument_bars`
metadata first, not from a full `canonical_candles` aggregation. That keeps the
UI responsive while large 1m backfills are running; the displayed OHLCV row count
is an estimate from first/last timestamp and bar interval. Targeted diagnostics
or export paths remain the place for exact counts and gap inspection. Funding
coverage rows still come from `funding_rates` and label provider/exchange from
the stored `source`.
Target: every promoted run should cite data coverage and source validation evidence.
Validation DB parity filters canonical candles by `source_primary` when a run
records `result.validation.exchange`, so the candle comparison is scoped to the
execution venue rather than only the canonical symbol. For `price_series.csv`
provenance, DB parity compares timestamped `close` values only; artifact OHLCV
structure remains a separate artifact-level check because replay price series may
carry close-flattened O/H/L and quote-volume units. The validation output must
surface the venue scope as `checks.db_parity.canonical_source_primary`; a Binance
DB-backed PASS must show `binance` there.
Replay candle loading now uses the same venue scope before artifact generation,
not only during post-run validation.
`scripts/resample_binance_1h_canonical.py` can derive Binance 1H canonical rows
from already-ingested Binance 1m canonical rows without changing schema or gate
logic.

## Backtest Run Flow

```text
frontend Run Backtest form -> POST /api/backtest/run -> routes_backtest.py background job -> scripts/run_replay_backtest.py or strategy-specific runner -> results run directory or DB artifacts -> job status and run list -> frontend Backtest view
```

Current: the UI can run replay, daily-winner, and OHLCV-rotation paths. XS
momentum has a separate research-only vectorized runner and is not wired into
the UI/API run flow or promotion gates. Known gap: lightweight Makefile smoke
does not yet run a tiny frozen replay fixture.
Run and sweep requests use `config/settings.yaml` primary exchange only when the
field is omitted/blank; any explicit unknown exchange returns HTTP 400 before a
background job is queued.

Research-only `fill_all_signals` replay raises capacity and stop thresholds
inside the copied run config before replay starts: order notional, position
percent of equity, stale quote tolerance, daily loss, soft drawdown, and hard
drawdown limits are all lifted, latency is zeroed, and replay execution uses
`fill_all_on_submit`. The output records these values in
`result.validation.fill_all_signals_controls`. These runs remain idealized-fill
artifacts and are not live, promotion, or edge evidence.

Execution-profile flow:

```text
UI/API execution_profile -> scripts/run_replay_backtest.py -> apply_execution_profile_controls -> ReplayBacktestEngine -> save_backtest_artifacts
```

For `dual_output`, the script writes `<base>_strategy_fill/`,
`<base>_realistic_execution/`, and `<base>_execution_comparison.json`.
Run detail reads the child run summary, shows `result.validation.execution_profile`,
and links comparison JSON through
`GET /api/backtest/{run_id}/execution-comparison`, which reads only the matching
`*_execution_comparison.json` artifact.

## Backtest Artifact Generation Flow

```text
ReplayBacktestResult -> backtesting.artifacts.save_backtest_artifacts -> files, DB rows, or both depending on artifact mode and DSN -> routes_backtest.py artifact readers -> frontend charts, tables, and downloads
```

Current: artifact mode is controlled by environment and DSN availability. Do not
edit existing historical artifacts as part of code or docs cleanup.
Caller-controlled artifact IDs are validate-and-reject ASCII path components;
writers and readers resolve each child below the intended artifact root instead
of truncating a supplied path to its basename.

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

## Turtle Research Runner Flow

```text
DB 1D candles -> routes_backtest.py turtle job -> backtesting.turtle_backtest.run_turtle_backtest -> result.json + price/indicator/trades/equity/returns/drawdown CSVs -> frontend result review
```

Turtle is a research-only standalone port of `new_startegy_海龜`; it does not
enter replay, `config/strategies.yaml`, strategy/risk/live gates, or
differential-validation contracts. Sweep requests branch before the technical
`parameter_sweep` harness:

```text
POST /api/backtest/sweep strategy=turtle -> run_turtle_sweep -> results/turtle_sweeps/<sweep_id>/{summary.json,rows.csv,equity_curves.csv?,surface.html?} -> TurtleSweepPanel heatmaps / invest_pct scrub / Plotly surface link
```

Current: the API serves only allow-listed Turtle sweep artifacts. The Plotly
surface HTML loads the vendored static frontend bundle from
`/vendor/plotly.min.js`; `equity_curves.csv` powers the `invest_pct` scrub UI
when the sweep includes that axis.

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

The Backtest Risk tab loads `signals`, `fills`, and `risk-events` together. It
uses the selected chart symbols to show whether sparse trading came from few
strategy signals, risk/drawdown blocking, or execution/fill conversion gaps.

## Progress Panel Flow

```text
config/workstreams.yaml -> routes_progress.py -> GET /api/progress -> frontend/data.js -> frontend/view-progress.js
                         -> allow-listed .md path -> GET /api/progress/file -> browser tab
```

Current: the Progress panel is a read-only operations surface. It does not read
from git, DB, or the network, write repository state, alter strategy/config/gate
behavior, or modify result artifacts. Missing `config/workstreams.yaml` returns
HTTP 200 with an empty `workstreams` list; malformed YAML returns HTTP 200 with
an `error` field so the panel can show an unavailable state.
Progress file reads are limited to existing markdown paths explicitly present in
the workstream config and resolved inside the repository; the repo root is not
mounted as static content. File reads are disabled in the engine app and for a
standalone server bound to a non-loopback host.

## Validation Artifact Flow

```text
saved run artifacts -> validation runner and reference adapters -> validation result directory -> validation API endpoints -> frontend Validation Lab -> promotion review
```

Current: validation views, APIs, and a batch portable signal-validation harness
exist. `make strategy-signal-validation` generates deterministic active-strategy
fixtures and writes validation artifacts under `results/strategy_validation/`.
Validation Lab can also select saved Backtest Runs directly. File-backed runs use
their run directory; DB-only runs read `backtest_artifacts` payloads into a
temporary validation input bundle and write only the new validation evidence under
`results/<run_id>/validation/<validation_id>/`. This is not a backtest artifact
backfill and does not mutate existing result payloads.
`make engine-consistency-smoke` validates the frozen
`tests/fixtures/engine_consistency/` Binance BTC-USDT-SWAP 1H technical-strategy
fixtures against vectorbt and backtrader in no-DB/offline mode. That smoke proves
signal-logic engine consistency only; it is not promotion evidence.
Known gap status must come from `docs/AI_HANDOFF.md`,
`docs/ai_collaboration.md`, and fresh validation artifacts; missing optional
reference-engine dependencies produce SKIP rows and do not satisfy
`portable_validation_gate`.

Run-scoped differential validation CSV artifacts may be indexed in
`backtest_artifact_rows` as `validation/{validation_id}/{artifact_name}` for
faster artifact detail reads. Strategy-validation artifacts stay file-backed
because they are not keyed by `backtest_runs.run_id`.
Run, fixture, strategy, validation and validation-artifact identifiers use the
same reject-not-truncate helper across API, library and CLI entrypoints; invalid
IDs fail before validation evidence is read or written.
