---
status: current
type: runbook
owner: human
created: 2026-06-12
last_reviewed: 2026-07-15
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
`bias_report.json`. Do not truncate or edit the journal. No task is registered
by this implementation. A manual cycle leaves no resident process, so stopping
means simply not running another cycle. If the user later approves and creates
a Windows task, the reversible kill switch is:

```powershell
Disable-ScheduledTask -TaskName "quant_h014_deribit_shadow"
# Permanent removal remains a separate human-approved action:
Unregister-ScheduledTask -TaskName "quant_h014_deribit_shadow" -Confirm
```

Eight weeks plus a complete bias report unlock only a live ADR discussion;
live execution still requires R7.2 and a separate explicit user approval.

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
audit first/last timestamps and gaps before using the series in research.

## Scheduled External Ingest (Deribit funding, DVOL, option flow)

Deribit funding, hourly DVOL, and option-flow datasets have historical backfills
plus forward accumulation through `scripts/market_data/ingest_external.py`.
Register these Windows scheduled tasks yourself if the workstation should keep
the datasets fresh; Codex should not register them during implementation:

```powershell
schtasks /Create /TN quant_deribit_funding_ingest /SC HOURLY /MO 1 /TR "cmd /c cd /d C:\quant_strategy && C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\market_data\ingest_external.py --dataset funding_deribit_btc --dataset funding_deribit_eth >> logs\deribit_funding_ingest.log 2>&1" /F
schtasks /Create /TN quant_deribit_dvol_1h_ingest /SC HOURLY /MO 1 /TR "cmd /c cd /d C:\quant_strategy && C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\market_data\ingest_external.py --dataset dvol_deribit_btc_1h --dataset dvol_deribit_eth_1h >> logs\deribit_dvol_1h_ingest.log 2>&1" /F
schtasks /Create /TN quant_deribit_optflow_forward /SC HOURLY /MO 1 /TR "cmd /c cd /d C:\quant_strategy && C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\market_data\ingest_external.py --dataset optflow_deribit_btc --dataset optflow_deribit_eth >> logs\deribit_optflow_forward.log 2>&1" /F
```

Manual run / removal:

```powershell
schtasks /Run /TN quant_deribit_funding_ingest
schtasks /Run /TN quant_deribit_dvol_1h_ingest
schtasks /Run /TN quant_deribit_optflow_forward
schtasks /Delete /TN quant_deribit_funding_ingest /F
schtasks /Delete /TN quant_deribit_dvol_1h_ingest /F
schtasks /Delete /TN quant_deribit_optflow_forward /F
```

The forward option-flow path fetches the recent live window from
`www.deribit.com`; if a task is down for more than the live lookback, rerun the
history backfill script with explicit UTC `--start`/`--end` bounds and
`--resume`. Keep all tasks at hourly cadence or slower to stay within the
project's <=5 req/s Deribit rule.

Daily DVOL (`dvol_deribit_btc`/`dvol_deribit_eth`) is manual-update only by the
2026-07-12 user decision (no scheduled task). Update it with explicit bounds —
Deribit's `get_volatility_index_data` returns 400 when `--start` is passed
without `--end`, and end-of-day exclusive `--end` avoids ingesting today's
partial daily bar:

```powershell
python scripts\market_data\ingest_external.py --dataset dvol_deribit_btc --dataset dvol_deribit_eth --start <last_ingested_date> --end <today>T00:00:00
```

History 2021-03-24 through 2026-07-11 (1,936 rows per symbol, gap-free) was
backfilled 2026-07-12.

## Deribit Option Flow Backfill

Deribit option-flow aggregates use the public history host for backfill and the
`optflow_deribit_btc` / `optflow_deribit_eth` datasets. The script aggregates
hourly inverse-option trades only; USDC-linear instruments are counted as
excluded in `fields.excluded_linear_usdc_count`.

Pilot one month first:

```powershell
python scripts\market_data\backfill_deribit_option_flow.py --start 2024-01-01T00:00:00+00:00 --end 2024-02-01T00:00:00+00:00
```

Proceed to the full run only if the pilot reports per-currency rows in
`[670, 744]`. The full run is checkpointed and resumable:

```powershell
python scripts\market_data\backfill_deribit_option_flow.py --start 2024-01-01T00:00:00+00:00 --end 2026-07-11T00:00:00+00:00 --resume
```

At completion, review the script's JSON coverage summary and list any gaps over
6 hours before using `optflow_deribit_*` in research.

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
/reset    — reset daily loss counter
/help     — list commands
```

### Stream live L2 order book to Parquet

For tick-level microstructure data collection:

```bash
python scripts/stream_orderbook.py --symbol BTC-USDT-SWAP
```

## Engine Dashboard and REST API

The web UI is a React SPA served by the FastAPI engine at **`http://localhost:8080`**.
It starts automatically when the engine runs. No separate server command is needed.
(For the standalone no-engine dashboard, see "Local Dev" above and `docs/UI_MAP.md`.)

### Views

| View | URL path | Description |
| ---- | -------- | ----------- |
| Overview | `/` | Live equity curve, open positions, recent fills |
| Backtest Results | `/results` | All saved runs in `results/`; click to inspect equity curve, trade log, performance stats |
| Walk-Forward | `/walk-forward` | Per-window IS/OOS Sharpe table from the latest replay validation run |
| CPCV | `/cpcv` | CPCV path Sharpes, DSR, PSR for the last validation run |
| Trades | `/trades` | Live trade log with fill_px, fill_sz, fee, strategy |
| Risk | `/risk` | Live: daily loss %, drawdown %, positions per instrument, circuit breaker status |
| Config | `/config` | Read-only view of current `config/` YAML values |

### WebSocket live feed

The dashboard connects to `ws://localhost:8080/api/ws` automatically. Events pushed in real-time:

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
