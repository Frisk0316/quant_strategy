---
status: current
type: handoff
owner: human
created: 2026-06-12
last_reviewed: 2026-06-17
expires: none
superseded_by: null
---

# Known Issues

Durable backlog for bugs, gaps, and open operational risks. `docs/AI_HANDOFF.md`
may still reference active issues, but long-lived backlog items should move here
over time.

## Governance / Documentation

- `docs/AI_HANDOFF.md` still contains substantial historical session detail. Known
  gap: migrate completed history to `docs/CHANGELOG_AI.md` in a dedicated cleanup
  task.
- Some older Markdown files do not yet include lifecycle metadata. Current
  docs-check warns for older files and hard-fails only for new durable docs.

## Harness

- `make api-smoke` is a real smoke only when `API_BASE_URL` points at a running
  server; otherwise it exits with an explicit SKIP.
- `make backtest-smoke` verifies entrypoints only. Known gap: add a tiny frozen
  no-DB fixture before treating it as replay execution coverage.
- `make verify-full` may require TimescaleDB and seeded data.

## Validation

- Differential-validation unit coverage and the
  `codex_20260616_signal_validation` fixture batch verify source-data validation,
  portable validation gates, signal-point correctness, and active-strategy
  `reference_signals_only` contracts. These fixtures are signal-point evidence,
  not live execution or profitability evidence. CI now runs this fixture batch as
  a regression gate.
- Nautilus remains advisory in v1. Full Nautilus matching-engine parity for
  order/fill/PnL/funding semantics is not implemented.
- The signal-validation runner disables Numba JIT by default for vectorbt fixture
  validation because vectorbt import/JIT initialization can stall on Windows for
  tiny fixture workloads.
- Advisory validation evidence, in-sample backtests, idealized-fill artifacts, and
  DB parity SKIP states are not promotion evidence.
- ADR-0007 P1 closed the registry-only `ct_val` resolution gap for replay by
  adding venue-aware specs, provenance exchange tags, and frontend/API exchange
  selection; Known Issue 20's root cause is closed. Remaining environment gap:
  a fresh DB-backed artifact PASS still needs a reachable seeded DSN. On
  2026-06-18, `DATABASE_URL` was unset, the configured `.env` DSN on port 5432
  refused connections, local PostgreSQL on port 5433 rejected the repo `quant`
  credentials, and Docker Desktop could not be started from this session.
- Source-scoped canonical reads are now a validation boundary: DB parity for
  exchange `<x>` must query `canonical_candles.source_primary = <x>` and emit
  `checks.db_parity.canonical_source_primary == <x>`. If a Binance validation
  run compares OKX-tagged candles or omits this field, fix the candle source
  tagging / DB read path instead of loosening the gate.
- For `price_series.csv`, DB parity is close-only provenance: it compares
  timestamped artifact closes to canonical candle closes after source scoping.
  O/H/L flattening and volume-unit differences are not like-for-like DB parity
  fields; they remain covered by artifact-level structure/data-quality checks.
  Durable DB-backed source-provenance PASS evidence now exists under
  `results/adr0007_binance_btc_1h_db_pass_20260618/validation/codex_close_only_db_parity_pass_20260618/`.
  The older `adr0007_binance_btc_1h_db_pass_20260618_source_provenance`
  artifact still records the pre-fix FAIL, carries `SUPERSEDED.md`, and should
  not be cited as PASS.

## Operations

- Monitoring modules exist, but this map does not prove production alert coverage.
  Treat Telegram/metrics deployment readiness as a separate operational check.
