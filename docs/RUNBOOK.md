---
status: current
type: runbook
owner: human
created: 2026-06-12
last_reviewed: 2026-08-04
expires: none
superseded_by: null
---

# Runbook

This is the normal operation runbook. Use `docs/DEBUGGING_RUNBOOK.md` for
failure-mode diagnosis.

## Setup

```bash
python -m pip install -e ".[dev,backtest]"
```

Optional validation extras may require heavier dependencies:

```bash
python -m pip install -e ".[dev,backtest,validation]"
```

## Local Dev

```bash
python scripts/run_server.py
```

Open the frontend at the server URL, normally `http://localhost:8080`.
This standalone entrypoint includes the backtest/data APIs, Progress panel, and
in-dashboard user manual; it does not start the trading engine. Progress document
links are clickable only on the default loopback bind. A non-loopback bind shows
paths without exposing repository files.

A non-loopback bind also requires both an explicit `--allow-remote` flag and a
non-empty `API_KEY`; backtest, data, and config routes then require
`X-API-Key`, and `/api/docs` is disabled remotely:

```powershell
$env:API_KEY = '<strong-random-value>'
python scripts/run_server.py --host 0.0.0.0 --allow-remote
```

## No-DB Mode

- Leave `DATABASE_URL` unset or point it at an unreachable DSN.
- Use file artifacts and local parquet fallback where available.
- Run lightweight checks:

```bash
make docs-check
make frontend-check
make verify
```

Known gap: no-DB mode cannot prove DB parity or authoritative DB-backed `ct_val`.

## DB Mode

Start TimescaleDB, set `DATABASE_URL`, initialize migrations, then ingest or import
data:

```bash
docker compose -f docker/docker-compose.yml up -d timescaledb
python scripts/market_data/init_db.py
python scripts/market_data/import_parquet_ohlcv.py --bar 1H
python scripts/market_data/import_parquet_funding.py
```

Starting the full Compose stack also waits for the TimescaleDB health check
before starting `okx-quant`. Inside containers, `DATABASE_URL` takes precedence
over the local YAML DSN so the app reaches the `timescaledb` service rather than
container-local `localhost`. A standalone server still requires both a reachable
DB and an explicitly started API process.

For a targeted Binance OHLCV repair, use an exclusive `--end` window:

```bash
python scripts/download_binance_data.py --inst BTC-USDT-SWAP --bar 1H --start 2024-04-29 --end 2024-04-30 --dsn postgresql://user:pass@localhost:5432/quant
```

Use DB mode for integration tests, data validation, source-data checks, and any
promotion-grade evidence.

## Historical Data Download (Parquet)

No API key required. Uses OKX public endpoints.

```bash
python scripts/fetch_okx_data.py \
    --start 2024-01-01 \
    --end   2026-05-01 \
    --bar   1H
```

Downloads:

- `data/ticks/BTC_USDT_SWAP/candles_1H.parquet`
- `data/ticks/ETH_USDT_SWAP/candles_1H.parquet`
- `data/ticks/BTC_USDT_SWAP/funding.parquet`

## Funding-Rate Backfill and Validation

To fetch newer funding-rate rows directly from OKX into TimescaleDB:

```bash
python scripts/market_data/backfill_funding.py \
    --inst BTC-USDT-SWAP \
    --start 2026-04-30 \
    --end   2026-05-06
```

Validate funding coverage for BTC/ETH. Funding intervals are reported from
stored timestamps; pass `--max-gap-hours` only when you want a hard gap gate:

```bash
python scripts/market_data/validate_funding.py \
    --inst BTC-USDT-SWAP \
    --inst ETH-USDT-SWAP \
    --start 2026-01-28 \
    --end   2026-05-06 \
    --max-gap-hours 8
```

## Resumable Multi-Exchange Ingestion

For long-running, resumable backfills, use the checkpointed ingestor. It flushes after
10 requests by default, writes idempotently, stores progress in `ingestion_checkpoints`,
and writes the multi-exchange canonical layer:

- `market_instruments`: one row per exchange-native USDT perpetual instrument
- `market_klines`: `PRIMARY KEY (instrument_id, bar, ts)`
- `market_funding_rates`: `PRIMARY KEY (instrument_id, funding_time)`

```bash
python scripts/market_data/ingest.py \
    --exchange okx \
    --dataset klines_1m \
    --symbols BTC-USDT-SWAP \
    --start 2023-07-01T00:00:00Z \
    --end now \
    --direction backward \
    --flush-every-requests 10
```

```bash
# OKX（必須用 backward）
python scripts/market_data/ingest.py `
    --exchange okx `
    --dataset funding_rate `
    --symbols BTC-USDT-SWAP,ETH-USDT-SWAP `
    --start 2022-03-01T00:00:00Z `
    --end now `
    --direction backward

# Binance
python scripts/market_data/ingest.py `
    --exchange binance `
    --dataset funding_rate `
    --symbols BTCUSDT,ETHUSDT `
    --start 2020-01-01T00:00:00Z `
    --end now `
    --direction backward

# Bybit
python scripts/market_data/ingest.py `
    --exchange bybit `
    --dataset funding_rate `
    --symbols BTCUSDT `
    --start 2020-03-25T00:00:00Z `
    --end now `
    --direction forward
```

Background Docker run:

```bash
docker compose -f docker/docker-compose.yml --profile tools run -d \
    --name okx_btc_1m_backfill ingestor \
    python scripts/market_data/ingest.py \
      --exchange okx \
      --dataset klines_1m \
      --symbols BTC-USDT-SWAP \
      --start 2023-07-01T00:00:00Z \
      --end now \
      --direction backward

docker logs -f okx_btc_1m_backfill
```

Binance and Bybit USDT perpetual examples:

```bash
python scripts/market_data/ingest.py \
    --exchange binance \
    --dataset klines_1m \
    --symbols BTCUSDT,ETHUSDT \
    --start 2020-01-01T00:00:00Z \
    --end now

python scripts/market_data/ingest.py \
    --exchange bybit \
    --dataset funding_rate \
    --symbols BTCUSDT \
    --start 2020-03-25T00:00:00Z \
    --end now
```

Deribit BTC/ETH inverse-perpetual 1m history uses the public TradingView candle
endpoint, native canonical ids, and forward checkpoints. Initial backfill:

```powershell
python scripts\market_data\ingest.py `
    --exchange deribit `
    --dataset klines_1m `
    --symbols BTC-PERPETUAL,ETH-PERPETUAL `
    --start 2024-01-01T00:00:00Z `
    --end now `
    --direction forward
```

Forward top-up uses the same command; the per-symbol checkpoint resumes from
the last successful cursor and idempotent canonical upserts make reruns safe.
Verify the venue scope before using the data:

```sql
SELECT inst_id, source_primary, quality_status, COUNT(*) AS rows,
       MIN(ts) AS first_ts, MAX(ts) AS last_ts
FROM canonical_candles
WHERE inst_id IN ('BTC-PERPETUAL', 'ETH-PERPETUAL')
  AND bar = '1m'
GROUP BY inst_id, source_primary, quality_status;
```

Require `source_primary='deribit'`, no suspect rows, and at least 99% 1m
coverage for the requested window. Never substitute Deribit index-price data.

Check ingestion progress:

```sql
SELECT source, dataset, inst_id, direction, cursor_time, request_count, row_count, status, updated_at
FROM ingestion_checkpoints
ORDER BY updated_at DESC;
```

Query multi-exchange coverage:

```sql
SELECT
  mi.exchange,
  mi.inst_id,
  mi.normalized_symbol,
  COUNT(k.*) AS rows,
  MIN(k.ts) AS first_ts,
  MAX(k.ts) AS last_ts
FROM market_instruments mi
JOIN market_klines k USING (instrument_id)
GROUP BY mi.exchange, mi.inst_id, mi.normalized_symbol
ORDER BY mi.exchange, mi.inst_id;
```

**Symbol format by exchange:**

| Exchange | Format | Example |
| --- | --- | --- |
| OKX | `BASE-QUOTE-SWAP` | `BTC-USDT-SWAP` |
| Binance | `BASEQUOTE` | `BTCUSDT` |
| Bybit | `BASEQUOTE` | `BTCUSDT` |

`--direction forward` paginates oldest→newest; `--direction backward` paginates newest→oldest (default for OKX history endpoint). Both directions are supported for Binance and Bybit.

### H-010 OKX BTC/ETH 1m audit, backfill, and verification

Run the read-only coverage/ROI audit first. It resolves `--dsn`, then
`DATABASE_URL`, then the settings DSN; with none it writes explicit `SKIP`
outputs and makes no DB or network request:

```powershell
python scripts\audit_history_coverage.py `
    --json-out "$env:TEMP\history_coverage_audit.json" `
    --markdown-out "$env:TEMP\history_coverage_audit.md"
```

The exact human/local network command for the frozen H-010 half-open window is:

```powershell
python scripts\market_data\ingest.py `
    --exchange okx `
    --dataset klines_1m `
    --symbols BTC-USDT-SWAP,ETH-USDT-SWAP `
    --start 2024-01-01T00:00:00Z `
    --end 2026-06-17T00:00:00Z `
    --direction backward
```

Do not run that fetch in a network-blocked sandbox. It is checkpointed and
idempotent. When complete raw rows already exist, apply the additive ADR-0014
schema and fixed-scope promotion (the command reruns idempotently):

```powershell
python scripts\promote_okx_canonical_1m.py
```

The no-flag defaults remain `[2024-01-01, 2026-06-17)`. For the separately
authorized 2020-2023 history extension, use ISO dates and then run the exact
same command a second time; both resolved `promoted` counts must stay zero and
the second run's venue counts must also be zero:

```powershell
python scripts\promote_okx_canonical_1m.py `
    --start 2020-01-01 `
    --end 2024-01-01
```

The command compares aggregate raw/resolved timestamp fingerprints before any
write and wraps both symbols in one transaction. A fingerprint mismatch or any
resolved-table change aborts and rolls back the full operation.

Then use this one-shot read-only verifier:

```powershell
python scripts\verify_okx_1m_backfill.py
```

Verify the complete promoted history with:

```powershell
python scripts\verify_okx_1m_backfill.py `
    --start 2020-01-01 `
    --end 2026-06-17
```

The verifier reuses `pipeline_stage2_registry.probe_xvenue` over
`[2024-01-01, 2026-06-17)` and exits nonzero unless each symbol has OKX
`coverage_ratio >= 0.95` and Binance/OKX `alignment_ratio >= 0.95`. No alternate
venue may fill a failed leg (I19). It also requires exact raw-to-venue OHLCV
parity and zero OKX rows in the priority-resolved table for this window.

Completed local evidence on 2026-07-17: BTC and ETH each have 1,293,120 raw and
venue-canonical rows, zero mismatches, 1.0 OKX coverage/alignment, and zero
resolved OKX rows. A second promotion changed zero rows. That promotion remains
data-layer evidence only; the separately authorized E-057 commands below create
the later H-010 research verdict. Neither result is promotion or deployment
evidence.

Completed historical extension evidence on 2026-07-18: BTC and ETH each added
2,103,840 venue rows for `[2020-01-01, 2024-01-01)` while changing zero
resolved rows. The final-code rerun changed zero venue and zero resolved rows.
Across `[2020-01-01, 2026-06-17)`, each leg has 3,396,960 raw and venue rows,
zero OHLCV mismatches, 1.0 OKX coverage/alignment, zero missing raw rows, and an
empty `raw_gap_ranges` list. No Binance row filled an OKX gap.
Resolved global counts were identical before and after (`binance/raw`
93,445,900; `deribit/raw` 2,667,850; `okx/raw` 333,723), and two-seed
full-row fingerprints over both historical symbol scopes were also identical.

### H-010 Stage-2 calibration and registered probe

The strategy probe is intentionally two commands. The first command evaluates
one frozen calibration anchor and writes a fresh power-input artifact; it does
not run the four-cell grid or mutate pipeline status:

```powershell
python -m backtesting.xvenue_leadlag_probe `
    --output results\h010_e057_stage2_20260718\h010_power_input.json
```

Then the active caller validates that artifact and its reference hashes before
opening the DB connection:

```powershell
python scripts\run_pipeline_stage2_data_probe.py `
    --candidate xvenue `
    --output-root results\h010_e057_stage2_20260718 `
    --power-input results\h010_e057_stage2_20260718\h010_power_input.json `
    --start 2020-01-01 `
    --end-exclusive 2026-06-17
```

Both commands refuse to treat another venue's funding as OKX funding. Completed
E-057 evidence on 2026-07-18: candle coverage/alignment is 1.0 at 3,396,960
rows per venue/symbol, but exact OKX funding is absent. The one frozen anchor
completed 7,376 episodes and failed cost (median gross 1.3636 bps versus 8.0
bps median round trip). Stage 2 therefore fails with zero grid trials and Stage
3 must not run. Never overwrite either E-057 artifact; choose a new experiment
ID/output directory only after a separately approved ex-ante thesis.

Rollback the data rows only after stopping source-aware consumers:

```sql
-- Roll back only the 2026-07-18 history extension.
DELETE FROM venue_canonical_candles
WHERE source_primary = 'okx'
  AND inst_id IN ('BTC-USDT-SWAP', 'ETH-USDT-SWAP')
  AND bar = '1m'
  AND ts >= '2020-01-01T00:00:00Z'
  AND ts < '2024-01-01T00:00:00Z';
```

The earlier frozen-window rollback remains:

```sql
DELETE FROM venue_canonical_candles
WHERE source_primary = 'okx'
  AND inst_id IN ('BTC-USDT-SWAP', 'ETH-USDT-SWAP')
  AND bar = '1m'
  AND ts >= '2024-01-01T00:00:00Z'
  AND ts < '2026-06-17T00:00:00Z';
```

After code rollback, drop `canonical_candles_by_source` and then
`venue_canonical_candles`. Never delete `raw_candles`, resolved
`canonical_candles`, CAGGs, ledgers, or results for this rollback.

### Stage-2 statistical-power caller inputs

Active registry CLI runs normally require one candidate plus `--breadth`, `--n-obs`,
`--n-trials`, and `--plausible-net-sharpe`; H-010 instead requires the frozen
`--power-input` artifact above. Funding backfill requires the same
four flags unless `--skip-stage2-probe` or `--no-db` makes the probe inactive.
The orchestrator accepts `--power-inputs <json>` where the root object is keyed
by exact `candidate_id`; each value contains those four fields. Values are
ex-ante research assertions and must not be inferred or shared globally across
candidates. Missing fields stop before probe/artifact/status mutation.

## Promote Binance/Bybit Data into canonical_candles

Two parallel database systems exist and are bridged by a `canonical_inst_id` column:

| Layer | Old system (OKX-only) | New system (multi-exchange) |
| --- | --- | --- |
| Identity | `instruments.inst_id TEXT PK` | `market_instruments.instrument_id UUID` |
| K-line storage | `raw_candles (source, inst_id, bar, ts)` | `market_klines (instrument_id, bar, ts)` |
| Strategy-ready | `canonical_candles (inst_id, bar, ts)` ← backtest reads here | promoted via `canonicalize.py` |
| Funding | `funding_rates (source, inst_id, ts)` | `market_funding_rates (instrument_id, funding_time)` |

OKX data is mirror-written to both systems for backward compatibility. Binance/Bybit data lands only in the new `market_*` tables and must be promoted to `canonical_candles` via `canonicalize.py` before backtests can use it.

After ingesting Binance or Bybit data, run this 3-step sequence to make it available to backtests.

**1. Apply the bridge migration (idempotent):**

```bash
python scripts/market_data/init_db.py
```

**2. Set `canonical_inst_id` on the market instrument (once per exchange/symbol pair):**

Connect to TimescaleDB:

```bash
# Find your container name first
docker ps --format '{{.Names}}' | grep timescale

# Open psql (replace docker-timescaledb-1 with your container name)
docker exec -it docker-timescaledb-1 psql -U quant -d okx_quant
```

Then run:

```sql
-- Confirm the row exists
SELECT instrument_id, exchange, inst_id, canonical_inst_id
FROM market_instruments
WHERE exchange = 'binance' AND inst_id = 'BTCUSDT';

-- Set the bridge (BTC-USDT-SWAP must exist in instruments table)
UPDATE market_instruments
SET canonical_inst_id = 'BTC-USDT-SWAP'
WHERE exchange = 'binance' AND inst_id = 'BTCUSDT';
```

Repeat for each symbol and exchange (e.g. `ETHUSDT` → `ETH-USDT-SWAP`).

**3. Run `canonicalize.py` to promote into `canonical_candles`:**

Processes month-by-month and prints per-chunk progress:

```bash
python scripts/market_data/canonicalize.py \
    --canonical-inst BTC-USDT-SWAP \
    --bar 1m \
    --prefer okx,binance,bybit \
    --start 2024-01-01 \
    --end 2026-05-07
```

To canonicalize all instruments in `config/settings.yaml` at once:

```bash
python scripts/market_data/canonicalize.py \
    --all \
    --prefer okx,binance,bybit \
    --start 2024-01-01 \
    --end 2026-05-07
```

**4. Verify the result:**

```sql
-- Row count by source exchange
SELECT source_primary, COUNT(*) AS rows,
       MIN(ts) AS first_ts, MAX(ts) AS last_ts
FROM canonical_candles
WHERE inst_id = 'BTC-USDT-SWAP' AND bar = '1m'
GROUP BY source_primary
ORDER BY first_ts;

-- Spot-check for gaps on any given day (should return 0)
SELECT COUNT(*) AS missing_1m
FROM generate_series(
    '2024-01-01'::timestamptz,
    '2024-01-02'::timestamptz - interval '1 minute',
    interval '1 minute'
) gs(ts)
LEFT JOIN canonical_candles c
    ON c.ts = gs.ts AND c.inst_id = 'BTC-USDT-SWAP' AND c.bar = '1m'
WHERE c.ts IS NULL;
```

After the import succeeds, switch `config/settings.yaml`:

```yaml
storage:
  candle_backend: postgres
```

The database stores exchange-native candles in `raw_candles` and strategy-ready OHLCV in
`canonical_candles`. Higher timeframe views are available for 5m, 15m, and 1H when 1m data
has been backfilled; direct 1H imports are also readable from `canonical_candles`.
Funding-rate history is stored in `funding_rates`, and the backtest/replay loaders use it
when `storage.candle_backend: postgres`.

## Backtest Artifact Fast Reads

Apply migrations through the normal DB initialization path, including
`sql/migrations/0012_backtest_artifact_rows.sql`, before relying on row-backed
artifact reads.

Backfill existing saved runs after the migration:

```bash
python scripts/backfill_backtest_artifact_rows.py --all --verify
```

For a dry run or a small smoke:

```bash
python scripts/backfill_backtest_artifact_rows.py --all --limit-runs 1 --dry-run
python scripts/backfill_backtest_artifact_rows.py --run-id <run_id> --verify
```

Include run-scoped differential validation CSV artifacts when needed:

```bash
python scripts/backfill_backtest_artifact_rows.py --run-id <run_id> --include-validation --verify
```

Benchmark the running API before and after backfill:

```bash
python scripts/benchmark_artifact_reads.py --run-id <run_id> --symbol BTC-USDT-SWAP --output reports/artifact_read_benchmark_after.json
```

The row table is a derived read index. If rows are missing, API endpoints fall
back to existing JSONB/file readers; do not use row-count presence as trading or
promotion evidence.

## Unit Tests

```bash
make test-unit
```

Single module:

```bash
pytest tests/unit/test_strategy_gates.py -v
pytest tests/unit/test_throttles.py -v
```

## Integration Tests

```bash
make test-integration
```

Integration tests may require TimescaleDB and seeded data.

## Lab Tests (crypto-alpha-lab)

```bash
make test-lab
```

Runs `research/crypto-alpha-lab/tests` as a separate pytest invocation so the
lab package's imports never mix with the parent suite. Included in
`make verify` since 2026-07-12.

## Ledger Consistency (A11)

```bash
python scripts/docs/check_ledger_consistency.py
```

Cross-checks HYPOTHESIS_LEDGER ↔ EXPERIMENT_REGISTRY ID links, family
agreement, and K-budget bounds. Part of `make docs-check` since 2026-07-12.
Artifact existence is NOT machine-checked (see `docs/DOC_IMPACT_MATRIX.md` A11).

## Frontend Static Checks

```bash
make frontend-check
```

This runs JavaScript syntax checks with Node for the static frontend modules.

## API Smoke

Without a running server:

```bash
make api-smoke
```

This exits with an explicit SKIP. To check a live local server:

```bash
API_BASE_URL=http://localhost:8080 make api-smoke
```

If `API_KEY` is set for the server, set the same value in the shell before running
the smoke check.

## Backtest Smoke

```bash
make backtest-smoke
```

Runs a tiny frozen OHLCV fixture through the replay backtest path without a DB,
writes artifacts to a temporary directory, and verifies `result.json`,
`metrics.json`, and `fills.csv`. The fixture uses `strategy_fill` /
`idealized_fill`; it is smoke coverage only and is not promotion evidence.

Strategy Fill replay:

```powershell
python scripts/run_replay_backtest.py --strategy macd_crossover --symbol BTC-USDT-SWAP --exchange binance --bar 1H --strategy-params "{\"fast_span\":12,\"slow_span\":26,\"signal_span\":9}" --execution-profile strategy_fill --save-artifacts --run-id manual_macd_strategy_fill
```

Dual Output replay:

```powershell
python scripts/run_replay_backtest.py --strategy macd_crossover --symbol BTC-USDT-SWAP --exchange binance --bar 1H --strategy-params "{\"fast_span\":12,\"slow_span\":26,\"signal_span\":9}" --execution-profile dual_output --save-artifacts --run-id manual_macd_dual
```

## Replay Backtest CLI Workflow

### Legacy bar-proxy backtest (deprecated)

`scripts/run_backtest.py` is deprecated. The old bar-proxy workflow depended on
order-book market-making proxies that have been removed. Use the replay and
differential-validation steps below for active strategies.

```bash
python scripts/run_backtest.py
```

The command prints a deprecation notice and points to
`scripts/run_replay_backtest.py` and `scripts/run_differential_validation.py`.

### Replay smoke gate (fast infra check)

Runs the event-driven replay engine (actual fill simulation with fees, slippage, partial fills, cancel latency). Smoke defaults: `n_splits=3, k_test=1`.

```bash
python scripts/run_replay_backtest.py \
    --strategy ma_crossover \
    --start 2024-01-01 \
    --end   2024-03-01 \
    --bar   1H \
    --validate both
```

Output is saved under `results/<run_id>/`.

This step verifies that:

- Replay engine runs without errors
- Fill/order counts are non-zero
- Walk-forward OOS Sharpe is positive

### Single-strategy replay backtest

Run the full event-driven stack for any strategy combination:

```bash
# Funding Carry only
python scripts/run_replay_backtest.py \
    --strategy funding_carry \
    --start 2024-01-01 \
    --end   2026-05-01 \
    --bar   1H

# Multiple strategies together
python scripts/run_replay_backtest.py \
    --strategy ma_crossover \
    --strategy funding_carry \
    --start 2024-01-01 \
    --end   2026-05-01
```

Prints orders placed, fill count, Sharpe, MDD, and other metrics.

### Full replay CPCV gate (pre-demo requirement)

Full replay CPCV can be requested through the generic replay CLI for active
strategies. Runtime depends on data range and strategy count.

```bash
python scripts/run_replay_backtest.py \
    --strategy ma_crossover \
    --start  2024-01-01 \
    --end    2026-05-01 \
    --bar    1H \
    --validate both \
    --cpcv-n-splits 6 \
    --cpcv-k-test 2 \
    --wf-is-days 30 \
    --wf-oos-days 7
```

Printed summary:

```text
Replay CPCV  combos=27 paths=15  DSR=0.961  PSR=0.974
Replay WF    windows=32  mean_oos_sharpe=0.847
```

**Gate:** the printed numbers alone authorize nothing. The binding
promotion/demo gates are defined in `docs/ai_collaboration.md` (CPCV with
honest `n_trials` and `DSR >= 0.95` **and** `PSR >= 0.95`, artifact
`validation_status`, idealized-fill exclusion, differential validation,
`ct_val` provenance, explicit user approval). This summary does not replace
them.
The result JSON includes `backtest_execution` showing the fill model parameters used.

Results can be inspected in the dashboard (see "Trading Engine" and
"Engine Dashboard and REST API" below).

## Replay Validation Layers

The three-layer validation gate before any live capital deployment:

```text
Layer 1  scripts/run_replay_backtest.py --validate both     replay WF/CPCV smoke
Layer 2  scripts/run_differential_validation.py             vectorbt/backtrader/nautilus point validation
Layer 3  shadow/demo calibration                            execution/fill parity
```

The replay engine (`backtesting/replay.py`) models:

- **Post-only resting orders** with configurable `order_latency_ms`
- **Post-only rejection** when price crosses the book (order dropped, never retried as taker)
- **Partial fills** via `queue_fill_fraction` (fraction of available book size allocated to local orders)
- **Cancel latency** (`cancel_latency_ms`) — orders can fill after cancel is requested
- **Maker fees** from `BacktestConfig.maker_fee_rate`

All three parameters (`order_latency_ms`, `cancel_latency_ms`, `queue_fill_fraction`) are read from `config/risk.yaml` `backtest:` section and calibrated via the shadow/demo calibration workflow (see "Shadow/Demo Calibration" below).

### CPCV Python API

```python
from backtesting.cpcv import CPCV

cv = CPCV(n_splits=6, k_test=2, embargo_pct=0.02, purge_size=1)
results = cv.evaluate(df, strategy_fn, periods=365*24, n_trials=27)

print(results["dsr"])               # Deflated Sharpe Ratio (corrected for 27 trials)
print(results["psr"])               # Probabilistic Sharpe Ratio
print(results["overall_oos_sharpe"])
print(results["path_sharpes"])      # per-path OOS Sharpe list
```

### Walk-Forward Python API

```python
from backtesting.walk_forward import WalkForward

wf = WalkForward(is_days=30, oos_days=7)
wf_results = wf.evaluate(df, strategy_fn)
print(wf_results[["window", "is_start", "oos_start", "oos_sharpe"]])
```

## Turtle Research Runner Checks

Turtle is DB-backed and 1D-only. It is a research-only standalone runner, not a
replay strategy and not live-readiness evidence.

Core parity/unit check:

```powershell
python -m pytest tests/unit/test_turtle_backtest.py tests/unit/test_routes_backtest_turtle.py -q
```

Manual API single run (requires a running server and DB 1D candles for the
symbol):

```powershell
$body = @{
  strategy = "turtle"; symbols = @("BTC-USDT-SWAP"); bar = "1D";
  start = "2024-01-01"; end = "2024-03-01"; initial_equity = 50000;
  strategy_params = @{ enter_term_sys1 = 20; enter_term_sys2 = 55; leave_term_sys1 = 10; leave_term_sys2 = 20; single_sys_unit_limit = 4; both_sys_unit_limit = 4; invest_pct = 0.01; min_position = 0.0001; fee = 0.003; atr_period = 20 }
} | ConvertTo-Json -Depth 5
Invoke-RestMethod -Method Post -Uri http://localhost:8080/api/backtest/run -ContentType application/json -Body $body
```

Manual sweep payload uses the same `/api/backtest/sweep` endpoint with
`strategy=turtle`; results are written under `results/turtle_sweeps/<sweep_id>/`
and are available via `/api/backtest/sweep/result/{sweep_id}` and
`/api/backtest/sweep/artifact/{sweep_id}/{name}`.

Large Turtle sweeps are batched and resumable. The full four-window reference
grid has 262,080 raw candidates and 115,200 valid combinations, so submit
`max_combinations` at or above the visible valid count; the hard API guardrail
is 200,000 valid combinations, with a 300,000 raw-candidate guardrail to catch
accidental multi-day grids. Reusing the same `sweep_id` resumes from the
existing `rows.csv` checkpoint when the grid and base params match. Cancel a
running sweep with:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8080/api/backtest/sweep/cancel/<job_id>
```

`summary.json` stays small (`top_results`, counts, and artifact names only);
full rows live in `rows.csv`. `/api/backtest/sweep/result/{sweep_id}` only
inlines small 2D/invest artifacts; large CSVs stay behind artifact links.

## H-021 Stage-3 Research Checkpoint (one run only)

This standalone E-056 path is research-only and stops at checkpoint ①. Confirm
the pre-registration commit exists, then run I44 and the full unit suite before
the first and only grid execution:

```powershell
& 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' -m pytest tests\unit\test_h021_inverse_perp_accounting.py -q -p no:cacheprovider
& 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' -m pytest tests\unit -q -p no:cacheprovider
& 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' -m backtesting.xvenue_funding_spread_backtest
```

The run writes a new `results/h021_stage3_<date>/` directory and refuses an
existing `summary.json`; do not delete or overwrite it to retry. After recording
E-056 with family-cumulative `n_trials=12`, generate the checkpoint sidecar:

```powershell
& 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' -m scripts.run_pipeline_checkpoint1_check --summary results\h021_stage3_20260715\summary.json
```

Any missing 8h event, required reference signal, Binance canonical mark, or
native Deribit `source_primary='deribit'` mark is a fail-closed stop. This path
does not authorize an index fallback, retry, promotion, demo, shadow, or live
step.

## Config Validation

```bash
make check-config
```

This runs the existing config-only validation path and should stay lightweight.

## Data Validation

```bash
make validate-data
```

This may require local data files or DB-backed data, depending on configuration and
environment.

## H-014 Deribit Options Shadow (manual only)

ADR-0011 v1 has no credentials and no order method. It reads DB signals, then
uses only Deribit public instruments/order-book/trade/delivery methods. Run one
cycle at or after 08:00 UTC; the process exits after the cycle:

```powershell
python scripts/run_h014_shadow.py
```

The cycle fails closed if either BTC or ETH lacks the exact prior research-day
DVOL/canonical-close pair. Refresh the existing ingestion data first; do not
override the date or frozen `ivp_min=85` / `z_min=0.5` parameters. Build the
ADR-0011 bias report from the append-only journal with:

```powershell
python scripts/run_h014_shadow.py --report
```

Runtime files are `results/shadow_h014/journal.jsonl` and
`bias_report.json`; `journal.jsonl.lock` is the persistent cross-process lock
sidecar. Do not truncate, edit, or remove the journal or its lock while a cycle
may be running. If a UI/manual/scheduled cycle overlaps another, one fails
closed with `another H-014 shadow cycle is already running`.

USER-APPROVED SCHEDULE (2026-07-15, after the review conditions cleared):
`quant_h014_shadow_daily` runs `scripts\run_h014_shadow_task.cmd` daily at
16:10 local (08:10 UTC) — the wrapper tops up DVOL + Binance 1m candles via
`research\probes\h014_daily_shadow_ops.py --no-wait`, runs one cycle, and
refreshes the bias report (log: `logs\h014_shadow_daily.log`). Manage with:

REQUIRED power settings (user-approved 2026-07-29 after the clock stalled for
two weeks): this host runs on battery, and Task Scheduler's defaults refuse a
trigger on battery (`0x800710E0`), kill a running task when power is lost
(`0xC000013A`), and never catch up a missed slot. Any re-registration MUST
re-apply:

```powershell
$s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries -StartWhenAvailable `
  -ExecutionTimeLimit (New-TimeSpan -Hours 2)
Set-ScheduledTask -TaskName quant_h014_shadow_daily -Settings $s
```

16:10 local = 08:10 UTC is the first slot after the frozen 08:00 UTC research-day
boundary; a manual run before 08:00 UTC fail-closes with "H-014 daily cycle must
run at or after 08:00 UTC" — that is correct behavior, not a fault. `Last Result`
is meaningful again since the wrapper now propagates the cycle's exit code.

```powershell
schtasks /Query /TN quant_h014_shadow_daily /FO LIST
schtasks /Run /TN quant_h014_shadow_daily
schtasks /Delete /TN quant_h014_shadow_daily /F   # kill switch
```

Journal event-id dedupe makes an accidental double-run a no-op. A manual
cycle leaves no resident process, so stopping
means simply not running another cycle. If the user later approves and creates
a Windows task, the reversible kill switch is:

```powershell
Disable-ScheduledTask -TaskName "quant_h014_deribit_shadow"
# Permanent removal remains a separate human-approved action:
Unregister-ScheduledTask -TaskName "quant_h014_deribit_shadow" -Confirm
```

Eight weeks plus a complete bias report unlock only a live ADR discussion;
live execution still requires R7.2 and a separate explicit user approval.

### Research Ops frontend

Start the standalone server on loopback, then open `Research Ops` in the left
navigation. Use another port if 8080 is occupied:

```powershell
python scripts/run_server.py --port 8082
```

- `Run one shadow cycle` invokes the exact H-014 manual path above and refreshes
  the journal/bias status. It still has no credentials, private API, or orders.
- `Run research screen` accepts comma-separated H-009 lookback days and
  quantiles. It runs a full-sample sensitivity grid only; every submitted
  combination increments the displayed known family-trial lower bound. The
  Experiment Registry remains authoritative, and the result is not WF/CPCV or
  promotion evidence.
- H-009 request, summary, and error artifacts are written to a new directory
  under `results/h009_parameter_sweeps/`. Do not edit or reuse them as registered
  experiment evidence without completing the experiment-governance workflow.
- Mutation routes return HTTP 403 on the engine app and on non-loopback binds.
  The UI's custom action header also blocks cross-origin form posts. Stopping the
  standalone server disables the UI action surface. No deployment configuration
  is changed by using this page. H-009's in-memory job list resets on restart;
  written artifacts remain.

## Public Research Status Page (GitHub Pages)

This separate static page publishes research progress and H-014 observation
counts only. It contains no equity curve, strategy parameters, signal values,
credentials, live/paper performance, DB connection, or deployment-gate claim.
The `public-status` orphan branch is the publication boundary and must contain
only `index.html`, `status.json`, and `.nojekyll`.

### One-time setup (user-run after merge)

Start from the repository worktree on a clean branch. Create the orphan branch
directly in its own worktree so the main worktree is not cleared or switched:

```powershell
git status --short
git worktree add --orphan -b public-status ..\quant_public_status
New-Item ..\quant_public_status\.nojekyll -ItemType File
python scripts\publish_public_status.py --out ..\quant_public_status\status.json
Copy-Item public_status\index.html ..\quant_public_status\index.html
git -C ..\quant_public_status add .nojekyll index.html status.json
git -C ..\quant_public_status diff --cached --name-only
git -C ..\quant_public_status commit -m "chore: initialize public status"
git -C ..\quant_public_status push -u origin public-status
git -C ..\quant_public_status ls-tree --name-only HEAD
```

The final command must list exactly the three approved files. In GitHub, open
**Settings → Pages**, choose **Deploy from a branch**, then select
`public-status` and `/ (root)`. Do not enable a workflow.

The wrapper defaults `PUBLIC_STATUS_WORKTREE` to `..\quant_public_status` from
the repository root. For another location, set it before registering the task:

```powershell
setx PUBLIC_STATUS_WORKTREE "C:\quant_public_status"
```

Register the daily local refresh after the 16:10 H-014 cycle, then preserve the
same battery/catch-up behavior:

```powershell
schtasks /Create /TN quant_public_status_daily /TR "C:\quant_strategy\scripts\run_public_status_task.cmd" /SC DAILY /ST 16:30 /RU "MAXWEL_FRIEDMAN\woody" /NP /RL LIMITED /F
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries -StartWhenAvailable
Set-ScheduledTask -TaskName quant_public_status_daily -Settings $settings
schtasks /Run /TN quant_public_status_daily
schtasks /Query /TN quant_public_status_daily /V /FO LIST
```

### Daily/manual refresh

The scheduled command runs the local-only generator, copies the page, stages the
orphan worktree, exits without a commit when nothing changed, and otherwise
commits and pushes `public-status`:

```powershell
scripts\run_public_status_task.cmd
```

If an input file is absent, its page section says it is unavailable; the
generator never invents zero values. A malformed input stops the task before
commit/push. A powered-off host misses that day's update, and the page continues
to show its last `generated_at` timestamp.

### Rollback

1. Disable or remove the local task:

   ```powershell
   Disable-ScheduledTask -TaskName quant_public_status_daily
   schtasks /Delete /TN quant_public_status_daily /F
   ```

2. In GitHub **Settings → Pages**, set the source to **None**.
3. Remove the published branch and its local worktree:

   ```powershell
   git push origin --delete public-status
   git worktree remove ..\quant_public_status
   git branch -D public-status
   ```

This removes the served page. It does not modify source inputs under `results/`,
`frontend/`, or `config/`.

## Worklog Page (GitHub Pages + separate public repository)

This independent page publishes AI work-time estimates, commit/task indexes, and
daily portfolio replay snapshots to `Frisk0316/quant_worklog`. It never writes to
the public `public-status` branch or uses its worktree.

### Disclosure decision and privacy boundary

- User decision 2026-08-05: `quant_worklog` is a separate PUBLIC repository, so
  Pages is free (no GitHub Pro needed). The page, the raw JSON, and the full git
  history are publicly browsable and discoverable; the user explicitly accepted
  that work-time and PnL/backtest-metric exposure. To withdraw it later, follow
  Rollback below.
- Never host this content from the `quant_strategy` repository: its single
  Pages slot belongs to the public-status page, whose authorized disclosure
  scope excludes performance data.
- Transcript collection extracts only timestamps and Codex `cwd`; it never emits
  message content, prompts, environment values, or credentials.
- The page must keep its research-replay disclaimer: snapshots are not live or
  paper-trading performance and imply no promotion/deployment gate.

### One-time setup (user-run after merge)

Create the public repository in GitHub first, then clone its empty `main` branch
beside this repository:

```powershell
git clone git@github.com:Frisk0316/quant_worklog.git ..\quant_worklog
python scripts\worklog\collect_ai_sessions.py
python scripts\worklog\publish_worklog_page.py --out-dir ..\quant_worklog
git -C ..\quant_worklog add -A
git -C ..\quant_worklog commit -m "chore: initialize private worklog"
git -C ..\quant_worklog push -u origin main
```

In GitHub **Settings → Pages**, choose **Deploy from a branch**, then `main` and
`/ (root)`. Reconfirm the public-URL risk before saving. Do not create a workflow.

The wrapper defaults `WORKLOG_REPO` to `..\quant_worklog`. To use another clone:

```powershell
setx WORKLOG_REPO "C:\quant_worklog"
```

Register the local daily task after other daily data jobs have completed:

```powershell
schtasks /Create /TN quant_private_worklog_daily /TR "C:\quant_strategy\scripts\worklog\run_worklog_page_task.cmd" /SC DAILY /ST 16:45 /RU "MAXWEL_FRIEDMAN\woody" /NP /RL LIMITED /F
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries -StartWhenAvailable
Set-ScheduledTask -TaskName quant_private_worklog_daily -Settings $settings
schtasks /Run /TN quant_private_worklog_daily
schtasks /Query /TN quant_private_worklog_daily /V /FO LIST
```

The `/RU ... /NP` (S4U) form requires an elevated shell. From a normal shell,
register an Interactive-only task instead (runs only while logged on), and
re-register with the S4U form from Administrator PowerShell later if needed:

```powershell
schtasks /Create /TN quant_private_worklog_daily /TR "C:\quant_strategy\scripts\worklog\run_worklog_page_task.cmd" /SC DAILY /ST 16:45 /F
```

### Daily refresh (artifact reads only — no DB, no replay)

User redirection 2026-08-05: the page tracks the two report strategies (the
options volatility-premium candidate and the funding-rate long/short watch-list
candidate), not the deprecated `strategies.yaml` portfolio. The daily
entrypoint no longer runs any backtest. `snapshot_strategies.py` reads only
frozen research artifacts plus shadow-journal COUNTS (never signal values or
internal tracking codes — a forbidden-key check runs on every build), the
collector gathers timestamp-only sessions, and the publisher assembles the
site and pushes `main`. Work summaries are commit subjects with internal codes
scrubbed; full commit bodies are not published. Previously published
daily/session history is merged in so aged-out transcripts never shrink the
page. A snapshot failure is reported but does not block work-time publication;
a clean staged diff exits without an empty commit.

The funding strategy's per-rebalance long/short notional table renders once
`holdings.json` exists — produced by
`tasks/2026-08-05-funding-ls-holdings-log-codex-tasks.md` (weekly rebalance by
design). These are reporting snapshots, not validation or promotion evidence.

```powershell
scripts\worklog\run_worklog_page_task.cmd
```

For the Pages-disabled local option, serve the clone on loopback so browser
`fetch` can read the JSON files, then open the printed local address:

```powershell
python -m http.server 8000 --bind 127.0.0.1 --directory ..\quant_worklog
```

Known limits: a powered-off host misses that day's refresh; transcript event
gaps approximate active time rather than a clock; Codex sessions from other
machines are absent; uncommitted/unwritten AI conversation content is excluded
by design.

### Rollback

1. Stop and remove the scheduled task:

   ```powershell
   Disable-ScheduledTask -TaskName quant_private_worklog_daily
   schtasks /Delete /TN quant_private_worklog_daily /F
   ```

2. In GitHub **Settings → Pages**, set the source to **None**.
3. Delete `Frisk0316/quant_worklog` (or make it private) if the generated
   history should be withdrawn; note that already-crawled public copies cannot
   be recalled. Retain it with Pages disabled for local-only use if preferred.
4. Remove the local clone only if its generated history is no longer needed.

These steps do not remove source transcripts or backtest artifacts from this
repository.

## H-014 Deribit Options Live Layer (implemented, disabled)

ADR-0017's private client and adapter exist for review and testnet plumbing,
but `config/risk.yaml` keeps `h014_live.enabled: false`. There is no runner,
scheduled task, `config/settings.yaml` mode change, or activation in this
delivery. Missing credentials fail startup if the adapter is explicitly
enabled; the disabled path constructs no private client and continues appending
the supplied ADR-0011 shadow journal record.

The additive config values are USD notional/loss limits, a fractional drawdown
threshold, testnet/live host selection, and bounded maker repricing. V1 counts
one proposed tranche as `tranche_units * signal spot` for the per-symbol and
aggregate notional checks; activation review must confirm those caps and the
caller-supplied risk snapshot against the approved capital limit.

Run the mocked, no-network plumbing checks:

```powershell
python -m pytest tests/unit/test_deribit_private_client.py tests/unit/test_h014_live_adapter.py -v
python scripts/h014_live_panic.py --dry-run
```

After the user supplies a trade-scoped **testnet** key, the read-only
authenticated plumbing check below verifies auth, account-summary, and option
position calls without placing an order or changing `enabled`:

```powershell
python -c "from okx_quant.execution.deribit_live.private_client import DeribitPrivateClient as C; c=C.from_env(env='test'); print(c.get_account_summary('BTC')); print(c.get_positions('BTC')); c.close()"
```

### Binance and OKX Demo connectivity

These are manual, unscheduled connectivity smokes, not strategy promotion
evidence. Binance uses the unified Demo Trading key in
`BINANCE_API_KEY`/`BINANCE_SECRET`; optional `BINANCE_FUTURES_*` values override
it for USD-M. OKX uses only `OKX_DEMO_API_KEY`/`OKX_DEMO_SECRET`/
`OKX_DEMO_PASSPHRASE` and requires `config/settings.yaml` `system.mode: demo`.
The live-labeled `OKX_API_KEY`/`OKX_SECRET`/`OKX_PASSPHRASE` names are never
read by this smoke.

```powershell
python scripts/run_binance_testnet_smoke.py --venue spot     # demo-api.binance.com
python scripts/run_binance_testnet_smoke.py --venue futures  # demo-fapi.binance.com
python scripts/run_okx_demo_smoke.py                         # demo balance + place/cancel
```

The Binance futures leg only reduces an existing non-zero one-way position —
it reports `blocked` rather than opening new exposure on a flat/hedge account.

The Binance clients synchronize venue time before signed requests. Spot places
and cancels one resting Demo order. The futures leg never opens exposure on a
flat account. OKX uses simulated-trading routing, a venue-valid resting price,
and confirms nested order/cancel result codes.

Funding-carry validation must preserve the configured APR gate. Run the
targeted dual-leg replay and execution checks; a current rate below the 12% APR
threshold correctly produces no signal and must not be forced by lowering the
threshold:

```powershell
python -m pytest tests/unit/test_execution_flow.py tests/unit/test_backtesting.py tests/integration/test_signal_strategy_integration.py -k funding_carry -q
python scripts/smoke/backtest_smoke.py
```

The demo funding pair is not atomic across legs. Do not interpret connectivity,
synthetic dual-leg tests, or Demo fills as live/deployment readiness.

Runtime order events are append-only in
`results/live_h014/orders.jsonl`; the persistent sidecar lock is
`orders.jsonl.lock`. Placement, rejection, risk-stop, and adapter-failure
events use the existing Telegram environment variables when configured;
otherwise the approved fallback is log-only with a code TODO. The separately
operated ADR-0011 shadow scheduled task retains its existing Windows toasts.

Panic dry-run makes no network call and writes no state. The actual panic
command first persists reduce-only state, then attempts option-order
cancellation for both BTC and ETH even if one cancellation fails:

```powershell
python scripts/h014_live_panic.py --dry-run
# ONLY during an approved testnet/live incident with scoped credentials:
python scripts/h014_live_panic.py
```

`results/live_h014/reduce_only.flag` is intentionally persistent. Do not remove
it or re-enable entries without human review of the incident and risk state.

Activation remains a later, separate approval in this exact order:

1. Meet ADR-0011's at-least-eight-valid-weeks shadow exit and complete the bias
   report.
2. Obtain Claude and human review of that report.
3. Pass every R7.2 / `docs/ai_collaboration.md` deployment gate, including the
   H-014 portable differential-validation gate.
4. Obtain a separate explicit user approval naming the capital cap.
5. Only then review an `enabled` flip and any scheduler registration as their
   own deployment change.

## Scheduled External Ingest (OKX liquidation)

OKX's public liquidation-orders REST endpoint only retains a few hours of
events (measured 2026-07-03: BTC ~14h, ETH ~5h at the 1,600-row cap), so
`liq_okx_btc` / `liq_okx_eth` forward accumulation runs as a Windows scheduled
task every 2 hours. P1.4's unattended mode uses the same `woody` account with
an S4U (`/NP`) logon and `LIMITED` run level; it stores no password and does not
grant SYSTEM or administrator privileges. Run this once from an Administrator
PowerShell to create or replace the previous Interactive-only task:

```powershell
schtasks /Create /TN quant_liq_okx_ingest /TR "C:\quant_strategy\scripts\market_data\run_liq_ingest_task.cmd" /SC HOURLY /MO 2 /ST 00:05 /RU "MAXWEL_FRIEDMAN\woody" /NP /RL LIMITED /F
(Get-ScheduledTask -TaskName "quant_liq_okx_ingest").Principal | Format-List UserId,LogonType,RunLevel
# Expected: woody / S4U / Limited
```

The wrapper pins the verified Python 3.12 executable because an S4U session
must not depend on an interactive PATH. Update that path if Python is moved.
S4U has no delegated network credentials; this task needs only public HTTPS,
the local repository, and the configured localhost TimescaleDB.

Manual run, status, and permanent removal:

```powershell
schtasks /Run /TN quant_liq_okx_ingest
Get-ScheduledTaskInfo -TaskName "quant_liq_okx_ingest" | Format-List LastRunTime,LastTaskResult,NextRunTime,NumberOfMissedRuns
schtasks /Delete /TN quant_liq_okx_ingest /F
```

Rollback to the former logged-on-only behavior, if needed:

```powershell
schtasks /Create /TN quant_liq_okx_ingest /TR "C:\quant_strategy\scripts\market_data\run_liq_ingest_task.cmd" /SC HOURLY /MO 2 /ST 00:05 /RU "MAXWEL_FRIEDMAN\woody" /IT /RL LIMITED /F
```

The ingest is an idempotent upsert with `fail_on_empty_fetch`; gaps appear if
the machine or DB is off for longer than the retention window — check the log
and `external_observations` first/last timestamps when auditing coverage.

## FRED Macro And Research-Only Gold Ingest

Add `FRED_API_KEY=<key>` to `.env`; never commit the real key. The ingest
client reads `FRED_API_KEY` from the process environment, so use
`python-dotenv` to load the repository `.env` for the command:

```powershell
python -m dotenv -f .env run -- python scripts\market_data\ingest_external.py --dataset dgs2 --start 2026-01-01 --dry-run
python -m dotenv -f .env run -- python scripts\market_data\ingest_external.py --dataset dgs2 --start 2026-01-01 --end 2026-01-10
python -m dotenv -f .env run -- python scripts\market_data\ingest_external.py --dataset vixcls --dataset dtwexbgs --dataset dgs2 --dataset gold_yfinance --start 2020-01-01T00:00:00Z --end <UTC_TODAY>T00:00:00Z
```

`vixcls`, `dtwexbgs`, and `dgs2` are FRED business-daily series with
`publish_lag_days: 1`; verify every stored FRED row has
`published_at > observed_at`. `gold_yfinance` is Yahoo/yfinance `GC=F`, an
unofficial continuous COMEX futures proxy used because FRED no longer provides
the intended gold series. It is research-only, may contain roll/adjustment
artefacts, and must not be presented as the paper's gold input or as promotion
evidence.

## Scheduled External Ingest (Deribit option surface)

Deribit option-surface OI/IV snapshots are live-only and cannot be backfilled.
History for `optsurf_deribit_btc` / `optsurf_deribit_eth` starts at the first
successful snapshot. Codex provides the script; the user registers the Windows
scheduled task:

```powershell
schtasks /Create /TN quant_deribit_options_snapshot /SC HOURLY /MO 1 /TR "cmd /c cd /d C:\quant_strategy && C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\market_data\snapshot_deribit_options.py >> logs\deribit_options_snapshot.log 2>&1" /F
```

Manual run / removal:

```powershell
schtasks /Run /TN quant_deribit_options_snapshot
schtasks /Delete /TN quant_deribit_options_snapshot /F
```

The snapshot writes one row per currency per run into `external_observations`;
new snapshots retain the complete current listed chain in `raw_payload`, sorted
by expiry, strike, and option type. Audit first/last timestamps and gaps before
using the series in research; past full chains cannot be reconstructed from this
live endpoint.

## H-039 Cross-venue Options IV Forward Snapshot

The H-039 collector writes the current OKX, Bybit, and Deribit BTC/ETH
constant-maturity option-IV rows. It interpolates total variance between the
two valid expiries bracketing 30 days, explicitly labels nearest-expiry
fallback, and stores the full normalized active chain. It cannot reconstruct
hours before scheduler activation.
TimescaleDB must be running before the first manual snapshot:

```powershell
python scripts\market_data\snapshot_xvenue_options.py
```

The command stores the current snapshot first, then returns a non-zero
`snapshot gap alert` if the prior successful bucket is more than 1.5 hours
away. Inspect `logs\xvenue_options_snapshot.log` and DB coverage after any
alert; do not fill the missing hour with a proxy.

Codex provides the wrapper, but the user registers and owns the least-privilege
Windows task:

```powershell
schtasks /Create /TN quant_xvenue_options_iv /TR "C:\quant_strategy\scripts\market_data\run_xvenue_options_snapshot_task.cmd" /SC HOURLY /MO 1 /ST 00:15 /RL LIMITED /F
schtasks /Run /TN quant_xvenue_options_iv
schtasks /Query /TN quant_xvenue_options_iv /V /FO LIST
```

Verify `Last Run Result: 0`, the six `xvenue_opt_iv_*` datasets advancing by one UTC
hour, and no gap alert in the log. Remove the task without deleting stored
observations:

```powershell
schtasks /Delete /TN quant_xvenue_options_iv /F
```

Scheduler registration starts forward accumulation; Stage 2 remains blocked
until at least 270 honest daily observations exist.

## CFTC COT and Cboe Historical Backfill

Run the six CFTC futures-only histories and the four current Cboe volatility
histories after TimescaleDB is healthy:

```powershell
python scripts\market_data\ingest_external.py --dataset cot_cme_btc --dataset cot_cme_eth --dataset cot_es --dataset cot_ust10y --dataset cot_usd_index --dataset cot_gold --start 2006-01-01
python scripts\market_data\ingest_external.py --dataset cboe_vix9d --dataset cboe_vix --dataset cboe_vix3m --dataset cboe_vix6m --start 1990-01-01
```

Every COT row must have `published_at >= observed_at + 2 days`; the reference
date is usually Tuesday but can be another weekday in holiday weeks. Cboe rows
must have `published_at = observed_at + 1 day`.

The only official CSV tried for total put/call history is:

```text
https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/totalpc.csv
```

Cboe documents this archive as 2006-11-01 through 2019-10-04. It can be loaded
once with the command below, but it is discontinued and must not be registered
as a current daily scheduler or replaced by scraping the Daily Market
Statistics page:

```powershell
python scripts\market_data\ingest_external.py --dataset cboe_pcr_total --start 2006-11-01 --end 2019-10-04
```

## Scheduled External Ingest (Deribit funding, volatility, option flow)

Deribit funding, hourly DVOL, rolling historical volatility, and option-flow
datasets use `scripts/market_data/ingest_external.py`. Historical volatility is
forward-accumulated because its public endpoint exposes only a recent window.
Register these Windows scheduled tasks yourself if the workstation should keep
the datasets fresh; Codex should not register them during implementation:

```powershell
schtasks /Create /TN quant_deribit_funding_ingest /SC HOURLY /MO 1 /TR "cmd /c cd /d C:\quant_strategy && C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\market_data\ingest_external.py --dataset funding_deribit_btc --dataset funding_deribit_eth >> logs\deribit_funding_ingest.log 2>&1" /F
schtasks /Create /TN quant_deribit_dvol_1h_ingest /SC HOURLY /MO 1 /TR "cmd /c cd /d C:\quant_strategy && C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\market_data\ingest_external.py --dataset dvol_deribit_btc_1h --dataset dvol_deribit_eth_1h >> logs\deribit_dvol_1h_ingest.log 2>&1" /F
schtasks /Create /TN quant_deribit_hv_ingest /SC HOURLY /MO 1 /TR "cmd /c cd /d C:\quant_strategy && C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\market_data\ingest_external.py --dataset hv_deribit_btc_1h --dataset hv_deribit_eth_1h >> logs\deribit_hv_ingest.log 2>&1" /F
schtasks /Create /TN quant_deribit_optflow_forward /SC HOURLY /MO 1 /TR "cmd /c cd /d C:\quant_strategy && C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\market_data\ingest_external.py --dataset optflow_deribit_btc --dataset optflow_deribit_eth >> logs\deribit_optflow_forward.log 2>&1" /F
```

Manual run / removal:

```powershell
schtasks /Run /TN quant_deribit_funding_ingest
schtasks /Run /TN quant_deribit_dvol_1h_ingest
schtasks /Run /TN quant_deribit_hv_ingest
schtasks /Run /TN quant_deribit_optflow_forward
schtasks /Delete /TN quant_deribit_funding_ingest /F
schtasks /Delete /TN quant_deribit_dvol_1h_ingest /F
schtasks /Delete /TN quant_deribit_hv_ingest /F
schtasks /Delete /TN quant_deribit_optflow_forward /F
```

The forward option-flow path fetches the recent live window from
`www.deribit.com`; if a task is down for more than the live lookback, rerun the
history backfill script with explicit UTC `--start`/`--end` bounds and
`--resume`. If the history and live windows do not yet overlap, rerun the
explicit missing interval without `--resume` after the history host catches up.
Keep all tasks at hourly cadence or slower to stay within the project's <=5
req/s Deribit rule.

Manual historical-volatility refresh:

```powershell
python scripts\market_data\ingest_external.py --dataset hv_deribit_btc_1h --dataset hv_deribit_eth_1h
```

`--start`/`--end` only filter the rolling response locally; they cannot request
older historical-volatility rows from Deribit.

For a reproducible series extending to 2021, use the separate derived RV30
datasets. They use contiguous hourly Deribit perpetual closes, not Deribit's
native HV endpoint or adaptively downsampled index-chart history:

```powershell
python scripts\market_data\ingest_external.py --dataset rv30_deribit_btc_1h --dataset rv30_deribit_eth_1h --start 2021-01-01T00:00:00Z --end <UTC_END>
```

The Market Data Coverage panel exposes the same refresh under Exchange =
`Deribit`; search BTC/ETH and submit the hourly job. It also refreshes DVOL,
native rolling HV, and the current option-chain snapshot.

Daily DVOL (`dvol_deribit_btc`/`dvol_deribit_eth`) is manual-update only by the
2026-07-12 user decision (no scheduled task). Update it with explicit bounds —
Deribit's `get_volatility_index_data` returns 400 when `--start` is passed
without `--end`, and end-of-day exclusive `--end` avoids ingesting today's
partial daily bar:

```powershell
python scripts\market_data\ingest_external.py --dataset dvol_deribit_btc --dataset dvol_deribit_eth --start <last_ingested_date> --end <today>T00:00:00
```

History 2021-03-24 through 2026-07-25 (1,950 rows per symbol) was current after
the manual 2026-07-26 top-up.

## Deribit Option Flow Backfill

Deribit option-flow aggregates use the public history host for backfill and the
`optflow_deribit_btc` / `optflow_deribit_eth` datasets. The script aggregates
hourly inverse-option trades only; USDC-linear instruments are counted as
excluded in `fields.excluded_linear_usdc_count`. Each hourly
`raw_payload.sample` retains the full inverse tape with `trade_id`; row keys
and aggregate fields stay unchanged.

Pilot one month first:

```powershell
python scripts\market_data\backfill_deribit_option_flow.py --start 2024-01-01T00:00:00+00:00 --end 2024-02-01T00:00:00+00:00
```

Proceed to the full run only if the pilot reports per-currency rows in
`[670, 744]`. Run the full enrichment one calendar month at a time and retry a
failed month once:

```powershell
python scripts\market_data\backfill_deribit_option_flow.py --start <MONTH_START> --end <NEXT_MONTH_OR_LAST_COMPLETE_UTC_HOUR> --chunk-days 1
```

At completion, require retained-trade count to equal `fields.trade_count` on
sampled hours, review the script's JSON coverage summary, list gaps over 6
hours, and measure the `external_observations` hypertable size delta before
using `optflow_deribit_*` in research.

## Strategy Signal Validation

First-stage portable validation builds deterministic signal-point fixtures for
active strategies and validates them against the selected reference engines:

```bash
python -m pip install -e ".[dev,validation]"
make strategy-signal-validation
```

To run a smaller slice:

```bash
make strategy-signal-validation VALIDATION_STRATEGIES=ma_crossover VALIDATION_ENGINES=vectorbt,backtrader
```

Outputs are written under `results/strategy_validation/` plus a batch summary JSON
by default. Use `VALIDATION_RESULTS_DIR` to keep generated artifacts outside the
repo workspace:

```bash
make strategy-signal-validation VALIDATION_RESULTS_DIR=/tmp/strategy_validation
```

`source_data_validation` can pass in no-DB fixture mode because the generated
fixtures mark `ct_val` as `config_override`; real promotion evidence still needs
the relevant deployment gates. If `vectorbt` or `backtrader` is missing, those
engines skip and `portable_validation_gate.passed` remains false. The batch runner
sets `NUMBA_DISABLE_JIT=1` by default when `vectorbt` is selected because the
fixture workloads are tiny and this avoids vectorbt import/JIT stalls on Windows.

## Engine Consistency Smoke

Fast offline signal-logic smoke for real Binance BTC-USDT-SWAP 1H fixtures:

```bash
make engine-consistency-smoke
```

Equivalent direct command:

```bash
python scripts/run_engine_consistency_smoke.py
```

This validates frozen `tests/fixtures/engine_consistency/` runs for
`ma_crossover`, `ema_crossover`, and `macd_crossover` against vectorbt and
backtrader. It forces no-DB/offline mode and requires each strategy fixture to
have at least three signal rows. Passing output is signal-logic engine
consistency only; the fixtures are `strategy_fill`/idealized-fill and are not
edge, promotion, or live-readiness evidence.

## Source Provenance Validation

Second-stage real-data/source-provenance validation gates an existing
`validation_result.json` or a newly generated differential-validation run. It
requires:

- `source_data_validation.status == "PASS"`
- `source_data_validation.checks.ct_val_provenance.status == "PASS"`
- `source_data_validation.checks.db_parity.status == "PASS"`
- `ohlcv_source_validation == "db_parity_pass"`

Fixture evidence with DB parity `SKIP` fails this gate by design. For
`price_series.csv`, DB parity compares timestamped `close` values against
canonical candle close values; O/H/L and volume are checked separately as
artifact structure, not as like-for-like DB provenance fields.

To gate an existing validation result:

```bash
python scripts/run_source_provenance_validation.py --validation-result results/<run_id>/validation/<validation_id>/validation_result.json
make source-provenance-validation SOURCE_PROVENANCE_ARGS="--validation-result results/<run_id>/validation/<validation_id>/validation_result.json"
```

To generate and gate fresh evidence for a saved run, enable DB parity and provide
a reachable TimescaleDB/Postgres DSN:

```bash
DIFF_VALIDATION_ENABLE_DB_PARITY=1 \
DIFF_VALIDATION_DB_DSN=postgresql://user:pass@localhost:5432/quant \
python scripts/run_source_provenance_validation.py --run-id <run_id> --validation-id <validation_id>
```

PowerShell equivalent:

```powershell
$env:DIFF_VALIDATION_ENABLE_DB_PARITY = "1"
$env:DIFF_VALIDATION_DB_DSN = "postgresql://user:pass@localhost:5432/quant"
python scripts/run_source_provenance_validation.py --run-id <run_id> --validation-id <validation_id>
```

ADR-0007 Binance DB-backed PASS flow:

```powershell
$env:DATABASE_URL = "postgresql://user:pass@localhost:5432/quant"
psql $env:DATABASE_URL -f sql/migrations/0011_venue_instrument_specs.sql
psql $env:DATABASE_URL -f sql/seed_venue_instrument_specs.sql

python scripts/run_replay_backtest.py --strategy ma_crossover --symbol BTC-USDT-SWAP --bar 1H --exchange binance --run-id <run_id>

$env:DIFF_VALIDATION_ENABLE_DB_PARITY = "1"
$env:DIFF_VALIDATION_DB_DSN = $env:DATABASE_URL
python scripts/run_source_provenance_validation.py --run-id <run_id> --engines vectorbt,backtrader --validation-id <validation_id>
```

Required evidence for that milestone:

- `source_data_validation.status == "PASS"`
- `source_data_validation.checks.ct_val_provenance.status == "PASS"`
- `source_data_validation.checks.db_parity.status == "PASS"`
- `source_data_validation.checks.db_parity.canonical_source_primary == "binance"`
- `ohlcv_source_validation == "db_parity_pass"`
- `result.validation.exchange == "binance"`
- `ct_val_sources["BTC-USDT-SWAP"].source` is `exchange_base_unit` or `db`

If `db_parity` has no rows or compares another source, fix the
`canonical_candles.source_primary` data/source tagging. Do not relax the gate.

This gate does not prove Nautilus full execution parity, PnL parity, or live
readiness.

To reseed Binance BTC-USDT-SWAP 1H canonical candles from already-ingested
Binance 1m canonical rows:

```powershell
python scripts/resample_binance_1h_canonical.py --dsn postgresql://user:pass@localhost:5432/quant --start 2024-01-01 --end 2026-05-01
```

Then rerun source provenance validation:

```powershell
$env:NUMBA_DISABLE_JIT = "1"
$env:DIFF_VALIDATION_ENABLE_DB_PARITY = "1"
$env:DIFF_VALIDATION_DB_DSN = "postgresql://user:pass@localhost:5432/quant"
python scripts/run_source_provenance_validation.py --run-id <run_id> --engines vectorbt --validation-id <validation_id>
```

## Windows without make

From the repository root, run any supported Makefile-equivalent target through
[`scripts/verify.ps1`](../scripts/verify.ps1). The script prints every command
before running it and exits nonzero as soon as a command fails:

```powershell
pwsh scripts/verify.ps1 -Target <target>
```

If PowerShell 7 is not installed, the same script also runs under the built-in
Windows PowerShell:

```powershell
powershell.exe -NoProfile -File scripts/verify.ps1 -Target <target>
```

`PYTHON`, `PYTEST`, `RUFF`, and `NODE` environment variables override the same
tool defaults as the Makefile. The target mappings are:

| Target | Equivalent command or ordered target sequence |
| --- | --- |
| `test-unit` | `pytest tests/unit/ -v --tb=short` |
| `test-lab` | `pytest research/crypto-alpha-lab/tests -q -p no:cacheprovider` |
| `test-integration` | `pytest tests/integration/ -v --tb=short` |
| `check-config` | `python scripts/validate_pipeline.py --check-config-only` |
| `lint` | `ruff check src/ tests/ backtesting/ scripts/` |
| `docs-check` | `python scripts/docs/check_doc_metadata.py`<br>`python scripts/docs/check_feature_map_links.py`<br>`python scripts/docs/check_ledger_consistency.py` |
| `docs-impact` | `python scripts/docs/check_doc_impact.py` |
| `frontend-check` | Run `node --check` separately for `frontend/data.js`, `tweaks-panel.js`, `charts.js`, `view-config.js`, `view-backtest.js`, `view-results.js`, `view-validation.js`, `view-trades.js`, `view-glossary.js`, `view-manual.js`, `view-progress.js`, `view-ledger.js`, `view-research.js`, and `app.js`. |
| `api-smoke` | `python scripts/smoke/api_smoke.py` |
| `backtest-smoke` | `python scripts/smoke/backtest_smoke.py` |
| `verify` | `lint` → `docs-check` → `frontend-check` → `check-config` → `test-unit` → `test-lab` → `api-smoke` → `backtest-smoke` |
| `verify-full` | The complete `verify` sequence above → `test-integration` → `python scripts/validate_pipeline.py --data-dir data/ticks --inst BTC-USDT-SWAP` |

The parent unit suite and the lab suite intentionally remain separate pytest
invocations so the lab package imports do not enter the parent suite.

## Full Verification

Lightweight, no-DB-oriented verification:

```bash
make verify
```

Full verification, including DB/data-dependent checks:

```bash
make verify-full
```

Doc Sync Harness check (business-rule changes must carry a Change Manifest and
the docs listed in `docs/DOC_IMPACT_MATRIX.md`):

```bash
make docs-impact                              # advisory: warnings, exit 0
DOC_IMPACT_BASE=origin/main python scripts/docs/check_doc_impact.py --strict   # enforce
```

CI runs `docs-impact` strict on pull requests (`.github/workflows/ci.yml`,
`docs` job) and advisory on push to `main`. CI also runs the active-strategy
fixture signal-validation batch in the `strategy-signal-validation` job, writing
validation artifacts to runner temp storage.

## Shadow/Demo Calibration

Replay backtest accuracy depends on three parameters that must be measured from real exchange behavior:

| Parameter | Measures | Config key |
| --------- | -------- | ---------- |
| `queue_fill_fraction` | What fraction of available book size our orders actually fill | `backtest.queue_fill_fraction` |
| `order_latency_ms` | Mean time from order submit to first WS fill confirmation | `backtest.order_latency_ms` |
| `cancel_latency_ms` | P95 time from cancel request to WS cancel confirmation | `backtest.cancel_latency_ms` |

### How calibration data is collected

When the engine runs in `demo` or `shadow` mode, a `CalibrationLogger` is automatically started. It writes a JSONL event file per session to `results/calibration/`:

```text
results/calibration/
  calib_20260504T120000.jsonl    ← raw events (submit / fill / cancel)
  summary_20260504T120000.json   ← per-session stats (written on shutdown)
```

Each JSONL line is one of:

- `{"type": "submit", "cl_ord_id": "m_...", "order_px": ..., "submit_ts": ...}`
- `{"type": "fill",   "cl_ord_id": "m_...", "fill_px": ..., "latency_ms": ..., "slippage_bps": ...}`
- `{"type": "cancel_request", ...}` / `{"type": "cancel_ack", "cancel_latency_ms": ...}`

### Step-by-step calibration workflow

**1. Run the engine in demo mode for at least 1–2 weeks:**

```bash
# config/settings.yaml: system.mode = demo
python -m okx_quant.engine
```

**2. Check collected data and preview suggested config:**

```bash
python scripts/run_calibration_apply.py --dir results/calibration
```

Output example:

```text
Loading 14 calibration file(s)...
  calib_20260504T120000.jsonl: 847 events
  ...

=== Calibration Statistics ===
  Submitted orders    : 1240
  Filled orders       : 684
  Fill rate           : 0.5516  → queue_fill_fraction
  Mean order latency  : 312.4 ms  → order_latency_ms
  P95 order latency   : 891.0 ms
  Mean cancel latency : 187.3 ms
  P95 cancel latency  : 543.0 ms  → cancel_latency_ms
  Mean slippage       : 0.31 bps  (informational)
  P95 slippage        : 1.12 bps  (informational)

=== Suggested config/risk.yaml backtest section ===
backtest:
  queue_fill_fraction: 0.5516
  order_latency_ms: 312
  cancel_latency_ms: 543
```

**3. Apply the values to config:**

```bash
python scripts/run_calibration_apply.py --dir results/calibration --apply
```

This writes the suggested values into the `backtest:` section of `config/risk.yaml`.

**4. Re-run full replay CPCV with calibrated parameters** (see "Full replay CPCV gate" above).

`--min-fills` (default 10) guards against applying with too few data points:

```bash
# Require at least 50 fills before applying
python scripts/run_calibration_apply.py --apply --min-fills 50
```

## Live Deployment Gates

The **authoritative** gate definition is the Deployment Gates section of
`docs/ai_collaboration.md` (walk-forward/CPCV with honest `n_trials`,
`DSR >= 0.95` and `PSR >= 0.95`, idealized-fill exclusion, differential
validation, `ct_val` source check, replay/shadow evidence, and explicit user
approval at each stage). The engine-level operational checklist below is a
subset and never overrides it. The deprecated bar-proxy backtest is NOT a
gate and must not be cited as promotion evidence.

**Engine-level operational checklist before `system.mode: live`:**

| Step | Requirement |
| ---- | ----------- |
| Replay CPCV (full) | passing per `docs/ai_collaboration.md` (DSR and PSR ≥ 0.95, honest n_trials) with calibrated fill model |
| Demo trading | ≥ 4 weeks, calibration data collected, user-approved |
| Shadow mode | ≥ 2 weeks, sim PnL tracks demo PnL within tolerance |
| Human approval | Explicit sign-off required — engine will not self-promote |

```bash
# Run live (only after all gates pass)
python scripts/run_live.py
```

These gates operate together with the deployment gates in
`docs/ai_collaboration.md`; nothing here relaxes those. No strategy currently
meets these gates.

**Risk limits (hard-coded, cannot be overridden at runtime):**

| Level | Threshold | Action |
| ----- | --------- | ------ |
| Max order notional | $500 | RiskGuard rejects order |
| Daily loss | 5% | Halt all strategies |
| Soft drawdown | 10% | Size multiplier → 0.5× |
| Hard drawdown | 15% | Close all positions, kill switch |
| Max leverage | 3× | RiskGuard rejects order |

## Trading Engine

### Start in each mode

```bash
# Demo: paper trading against live OKX demo environment
# config/settings.yaml: system.mode = demo
python -m okx_quant.engine

# Shadow: SimBroker (primary) + OKXBroker demo (mirror) run in parallel
# config/settings.yaml: system.mode = shadow
python -m okx_quant.engine

# Live: real trading
# config/settings.yaml: system.mode = live
python -m okx_quant.engine

# Or use the mode-specific entry scripts:
python scripts/run_demo.py
python scripts/run_shadow.py
python scripts/run_live.py
```

The engine starts the FastAPI server on port 8080 automatically. Entering
demo/shadow/live requires the gates above plus explicit user approval.

### Telegram kill switch (optional)

If `TELEGRAM_TOKEN` and `TELEGRAM_CHAT_ID` are set in `.env`:

```text
/status   — current mode, equity, drawdown
/kill     — trigger hard stop and halt engine
/reset confirm — reset RiskGuard after explicit confirmation
/help     — list commands
```

Commands are accepted only from the configured `TELEGRAM_CHAT_ID`; updates
from every other chat are ignored.

### Continuously collect public OKX market data

`quant_okx_market_data` starts at Windows boot and runs the credential-free public
collector continuously. It reads OKX books, public trades, and funding-rate
updates for BTC/ETH Spot and SWAP; it does not load `.env`, construct a broker,
or expose an order path. Chunked Parquet files land under
`data/ticks/<instrument>/` as `ob_ticks_*`, `trades_*`, and `funding_*`.

The task runs as `woody` / `S4U` / `Limited` without storing a password, may
start and continue on battery, catches up after a missed boot trigger, has no
execution-time limit, and retries unexpected failures after one minute. The
collector stops cleanly before free space falls below 10 GiB; storage retention
remains manual. Run the registration script once through a UAC-approved
Administrator PowerShell:

```powershell
Start-Process powershell -Verb RunAs -Wait -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File C:\quant_strategy\scripts\market_data\register_okx_market_data_task.ps1'
```

```powershell
Get-ScheduledTask -TaskName quant_okx_market_data | Format-List TaskName,State
Get-ScheduledTaskInfo -TaskName quant_okx_market_data | Format-List LastRunTime,LastTaskResult
Get-Content logs\okx_market_data_collector.log -Tail 30

# Manual bounded smoke, in minutes:
python scripts\stream_orderbook.py --duration 0.15 --symbols BTC-USDT-SWAP BTC-USDT ETH-USDT-SWAP ETH-USDT

# Reversible stop / restart:
Stop-ScheduledTask -TaskName quant_okx_market_data
Start-ScheduledTask -TaskName quant_okx_market_data
Disable-ScheduledTask -TaskName quant_okx_market_data

# Permanent removal only when intended:
Unregister-ScheduledTask -TaskName quant_okx_market_data -Confirm
```

`LastTaskResult = 267009` (`0x41301`) means the continuous task is currently
running. Check remaining disk space periodically:

```powershell
python -c "import shutil; print(round(shutil.disk_usage('C:/quant_strategy').free / 2**30, 1), 'GiB free')"
```

## Engine Dashboard and REST API

The web UI is a Preact/htm SPA served by the FastAPI engine at **`http://localhost:8080`**.
It starts automatically when the engine runs. No separate server command is needed.
(For the standalone no-engine dashboard, see "Local Dev" above and `docs/UI_MAP.md`.)
The engine API defaults to loopback. A non-loopback `API_HOST` fails startup
unless `API_KEY` is set. Compose additionally binds the host port to
`127.0.0.1` and requires `API_KEY`, `TIMESCALE_PASSWORD`, and
`GRAFANA_PASSWORD` during interpolation.

### Views

The left navigation changes the Preact component's internal `view` state and
renders the selected panel in the same document. These views do not have URL
routes; the browser location is used only to derive the WebSocket host.

### WebSocket live feed

The dashboard connects to the current host at `/api/ws` automatically (for
example, `ws://localhost:8080/api/ws`). Events pushed in real-time:

- `FILL` — every fill with inst_id, side, fill_px, fill_sz, fee, strategy
- `RISK_SNAPSHOT` — equity, drawdown, daily_loss_pct, positions every 2 seconds
- `RISK` — circuit breaker trips and hard stop events

### REST API

The same endpoints the frontend calls are also available for scripting:

```bash
# List all saved backtest runs
curl http://localhost:8080/api/backtest/runs

# Fetch a specific run's full result.json
curl http://localhost:8080/api/backtest/<run_id>

# Live engine status
curl http://localhost:8080/api/live/status

# Current positions
curl http://localhost:8080/api/live/positions

# Recent trades (last 200)
curl http://localhost:8080/api/live/trades?limit=200

# Live risk metrics
curl http://localhost:8080/api/live/risk
```

API docs (Swagger UI): `http://localhost:8080/api/docs`

## Configuration Reference

### Credentials (only needed for live/demo/shadow modes)

```bash
cp .env.example .env
# Edit .env:
#   OKX_API_KEY=...
#   OKX_SECRET=...
#   OKX_PASSPHRASE=...
#   OKX_DEMO_API_KEY=...        (OKX Demo smoke only)
#   OKX_DEMO_SECRET=...
#   OKX_DEMO_PASSPHRASE=...
#   API_KEY=...                 (dashboard API / Compose)
#   GRAFANA_PASSWORD=...        (Compose)
#   TELEGRAM_TOKEN=...      (optional — for alerts and kill switch)
#   TELEGRAM_CHAT_ID=...    (optional)
```

### Config files

| File | What to set |
| ---- | ----------- |
| `config/settings.yaml` | `system.mode` (demo/shadow/live), `symbols`, `equity_usd` |
| `config/strategies.yaml` | Per-strategy parameters for active/research strategies |
| `config/risk.yaml` | Hard risk limits and `backtest:` execution parameters |

### `config/settings.yaml`

```yaml
system:
  mode: demo             # demo | shadow | live
  symbols:
    - BTC-USDT-SWAP
    - ETH-USDT-SWAP
  spot_symbols:
    - BTC-USDT
  equity_usd: 5000.0
  log_level: INFO
  json_logs: false
```

### `config/strategies.yaml` (example active strategy params)

```yaml
ma_crossover:
  enabled: true
  symbols:
    - BTC-USDT-SWAP
  fast_window: 20
  slow_window: 50
```

### `config/risk.yaml` (backtest section)

```yaml
risk:
  max_order_notional_usd: 500.0
  max_daily_loss_pct: 0.05
  soft_drawdown_pct: 0.10
  hard_drawdown_pct: 0.15
  max_leverage: 3.0

backtest:
  order_latency_ms: 0       # updated by run_calibration_apply.py
  cancel_latency_ms: 200    # updated by run_calibration_apply.py
  queue_fill_fraction: 0.20 # updated by run_calibration_apply.py
```

## Engine Implementation Notes

- **Clock sync**: REST calls sync OKX server time every 5 minutes to avoid error 50102 (>30s drift).
- **Post-only hard rule**: Error 51026 is logged and dropped; never retried as taker. This preserves maker-only execution semantics in both backtest and live.
- **Contract value guard**: `validate_ct_val()` accepts only finite `0 < ct_val <= 1e7` and raises `ValueError` otherwise (ADR-0003 amendment, 2026-07-12). This is a corruption guard; venue-matched provenance is enforced separately (R1.4/I16).
- **WS reconnect**: `CircuitBreaker` tracks reconnect count; halts strategies if threshold exceeded within the rolling window.
- **OKX book CRC32**: `OkxBook` stores raw string tuples for exact CRC32 validation. Sequence gaps or checksum mismatches raise `RuntimeError` → reconnect.
- **Feed storage**: Tick data written to Parquet by default; TimescaleDB backend available via `storage.backend: timescaledb` in `settings.yaml`.
- **Pairs trading**: Kalman filter updates hedge ratio online each tick. OU half-life must be < 48h for entry. `max_hedge_uncertainty: 10.0` prevents entry when Kalman variance is high.

## Rollback

For scoped docs/harness changes:

1. Review `git status --short`.
2. Revert only files touched by the current task.
3. Do not reset or overwrite unrelated user, Claude, or other Codex-session changes.
4. Re-run the narrow check for the reverted area.

## Common Environment Notes

- `DATABASE_URL` enables DB-backed data and artifacts.
- `BACKTEST_ARTIFACT_MODE` controls whether artifacts write to files, DB, or both.
- `API_BASE_URL` enables API smoke checks against a running server.
- `API_KEY` is required by API smoke when the server requires authenticated calls.
- Node is required for `make frontend-check`.
- Differential-validation dependencies are optional and should not be pulled into
  lightweight verification unless the task is explicitly about validation.
