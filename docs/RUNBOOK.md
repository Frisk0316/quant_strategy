---
status: current
type: runbook
owner: human
created: 2026-06-12
last_reviewed: 2026-07-11
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

## Integration Tests

```bash
make test-integration
```

Integration tests may require TimescaleDB and seeded data.

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

## Scheduled External Ingest (OKX liquidation)

OKX's public liquidation-orders REST endpoint only retains a few hours of
events (measured 2026-07-03: BTC ~14h, ETH ~5h at the 1,600-row cap), so
`liq_okx_btc` / `liq_okx_eth` forward accumulation runs as a Windows scheduled
task every 2 hours (user-approved 2026-07-03):

```text
Task name : quant_liq_okx_ingest  (schtasks, Interactive only — runs while logged on)
Wrapper   : scripts/market_data/run_liq_ingest_task.cmd
Log       : logs/liq_okx_ingest.log (gitignored)
Manual run: schtasks /Run /TN quant_liq_okx_ingest
Remove    : schtasks /Delete /TN quant_liq_okx_ingest /F
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
