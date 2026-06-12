---
status: current
type: runbook
owner: human
created: 2026-06-12
last_reviewed: 2026-06-12
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

## Full Verification

Lightweight, no-DB-oriented verification:

```bash
make verify
```

Full verification, including DB/data-dependent checks:

```bash
make verify-full
```

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
