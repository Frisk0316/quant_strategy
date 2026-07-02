---
status: current
type: handoff
owner: human
created: 2026-06-12
last_reviewed: 2026-06-29
expires: none
superseded_by: null
---

# Known Issues

Durable backlog for bugs, gaps, and open operational risks. `docs/AI_HANDOFF.md`
may still reference active issues, but long-lived backlog items should move here
over time.

## Harness

- `make api-smoke` is a real smoke only when `API_BASE_URL` points at a running
  server; otherwise it exits with an explicit SKIP.
- `make backtest-smoke` uses a tiny frozen no-DB replay fixture. It is smoke
  coverage only; full replay/data-provenance coverage and promotion evidence
  still require the normal validation gates.
- `make verify-full` may require TimescaleDB and seeded data.
- Frontend backtest-chart behavior is still mostly covered by syntax/static
  checks plus API artifact tests. Known gap: add a browser-level interaction test
  before treating progressive multi-symbol chart loading as fully guarded.
- The crypto-alpha-lab (`research/crypto-alpha-lab/`) is a **separate Python
  package**; its tests must run as their own step (`pip install -e
  research/crypto-alpha-lab` then `python -m pytest
  research/crypto-alpha-lab/tests -p no:cacheprovider`). Collecting them in the
  same `pytest` invocation as `tests/unit/` fails with
  `ImportError: crypto_alpha_lab`. CI now runs the parent and lab suites as
  separate steps.

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
- `scripts/recheck_dsr.py` is the current audit for DSR-bearing JSON artifacts.
  The 2026-06-24 run found 7 CPCV rows and 38 replay-level single-run diagnostic
  rows. `xs_momentum_validation_20260623` and
  `xs_momentum_validation_20260624_leakfix` have stored CPCV DSR values that
  violate `DSR <= PSR(0)` and must not be cited. Daily Winner CPCV was
  recomputed from saved returns and remains non-passing. The portfolio-vol XS
  artifact has a fixed, non-passing DSR/PSR pair, but only summary/path Sharpe
  fields were saved. As of 2026-06-29, future CPCV outputs retain raw path
  returns, or combined returns when path assembly is unavailable, so
  `scripts/recheck_dsr.py` can recompute DSR from saved artifacts; historical
  artifacts were not backfilled and remain summary-only.
- A fresh DB-backed artifact PASS still needs a reachable seeded DSN. On
  2026-06-18, `DATABASE_URL` was unset, the configured `.env` DSN on port 5432
  refused connections, local PostgreSQL on port 5433 rejected the repo `quant`
  credentials, and Docker Desktop could not be started from that session.
- Source-scoped canonical reads are now a validation boundary: DB parity for
  exchange `<x>` must query `canonical_candles.source_primary = <x>` and emit
  `checks.db_parity.canonical_source_primary == <x>`. If a Binance validation
  run compares OKX-tagged candles or omits this field, fix the candle source
  tagging / DB read path instead of loosening the gate.
- For `price_series.csv`, DB parity is close-only provenance: it compares
  timestamped artifact closes to canonical candle closes after source scoping.
  O/H/L flattening and volume-unit differences are not like-for-like DB parity
  fields; they remain covered by artifact-level structure/data-quality checks. A
  2026-06-23 Codex reseed created 20,400 Binance-sourced 1H canonical rows for
  `BTC-USDT-SWAP` from Binance 1m canonical data, then a targeted
  `download_binance_data.py --bar 1H --start 2024-04-29 --end 2024-04-30`
  repaired the remaining one-day gap. Local parquet and DB canonical Binance 1H
  closes now match for 2024-04-29 (24 rows, 0 mismatches). Existing
  validation-lab artifacts from before the repair still fail DB parity with 24
  close mismatches; rerun/regenerate those artifacts before citing a current
  DB-backed Binance 1H PASS. The older
  `adr0007_binance_btc_1h_db_pass_20260618_source_provenance` artifact still
  records the pre-fix FAIL, carries `SUPERSEDED.md`, and should not be cited as
  PASS.
- Pipeline batch 1's remaining gap is validation quality, not ETH data
  availability: S6 did not re-earn the statistical gate on the fold-refit
  harness, so portable validation adapters and authoritative ct_val evidence
  must not start for S6. S7 is shelved after a non-degenerate half-life rerun.
  S5 has a separate point-in-time universe/canonical coverage mismatch: the
  current membership artifact plus strict venue-scoped complete-window candle
  coverage produces `nonzero_grid_activity:false`, so the S5 refit summary is a
  data-universe artifact rather than a strategy verdict.

## Operations

- Monitoring modules exist, but this map does not prove production alert coverage.
  Treat Telegram/metrics deployment readiness as a separate operational check.
