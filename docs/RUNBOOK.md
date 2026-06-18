---
status: current
type: runbook
owner: human
created: 2026-06-12
last_reviewed: 2026-06-17
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

Use DB mode for integration tests, data validation, source-data checks, and any
promotion-grade evidence.

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

Current behavior: verifies entrypoints and reports that a tiny no-DB replay fixture
is still a known gap. It is not full execution coverage.

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

## Source Provenance Validation

Second-stage real-data/source-provenance validation gates an existing
`validation_result.json` or a newly generated differential-validation run. It
requires:

- `source_data_validation.status == "PASS"`
- `source_data_validation.checks.ct_val_provenance.status == "PASS"`
- `source_data_validation.checks.db_parity.status == "PASS"`
- `ohlcv_source_validation == "db_parity_pass"`

Fixture evidence with DB parity `SKIP` fails this gate by design.

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
