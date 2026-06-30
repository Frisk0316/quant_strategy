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
- Frontend backtest-chart behavior is still mostly covered by syntax/static
  checks plus API artifact tests. Known gap: add a browser-level interaction test
  before treating progressive multi-symbol chart loading as fully guarded.

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
- Pipeline batch 1's `ETH-USDT-SWAP` data blocker was resolved on 2026-06-25:
  Binance `ETH-USDT-SWAP` canonical 1m OHLCV now covers 2024-01-01 through
  2026-06-16 23:59 UTC with 1,293,120 rows and 0 gaps, and Binance funding has
  2,694 rows. The remaining gap is validation quality, not data availability:
  S6 did not re-earn the statistical gate on the fold-refit harness, so portable
  validation adapters and authoritative ct_val evidence must not start for S6.
  S7 is shelved after a non-degenerate half-life rerun. S5 has a separate
  point-in-time universe/canonical coverage mismatch: the current membership
  artifact plus strict venue-scoped complete-window candle coverage produces
  `nonzero_grid_activity:false`, so the S5 refit summary is a data-universe
  artifact rather than a strategy verdict.

- **Family-minting checker K vs n_trials (resolved 2026-06-30):** the initial
  `backtesting/pipeline_family_minting.py` set `inherited_K = inherited_n_trials`
  because no retry-count source existed. The checker now reads the
  `docs/EXPERIMENT_REGISTRY.md` *Family K-budget* table and reports real
  `k_used`, `k_limit`, and `at_k_limit`; `n_trials` and K are no longer
  conflated. Remaining operational caveat: the K-budget table is human-maintained
  checkpoint①#9 state, so stale table values still need human review.

- **XS family-cumulative n_trials inheritance (resolved 2026-06-30):** the
  shared `family_registry_from_text()` parser previously took the largest raw
  `Trials` cell, so F-XS-MOMENTUM inherited 8 from E-003/E-004/E-005 even though
  the ledger/registry notes state the family has 24 trials before future retry.
  The parser now honors explicit family-cumulative row text/overrides (including
  the XS "at least 24 trials" note and newer `family-cumulative n_trials=...`
  rows), so checkpoint① and family-minting inherit XS as 24 while C2 remains 48.
  Remaining operational caveat: future registry rows should continue to state
  the family-cumulative value clearly; otherwise the parser falls back to the
  historical max-row interpretation.

- **B-half data availability probe stub (resolved 2026-06-30):** the initial
  idea-generator B-half accepted `data_availability_probe` but discarded it and
  filtered only by taxonomy text. `enumerate_gaps()` now consumes supplied
  Stage-2 `pipeline_feasibility.py` data-availability results and uses taxonomy
  text only when the probe has no answer. This remains an advisory pre-backtest
  filter; Stage 2 is still the authoritative fail-closed gate before Stage 3.

## Operations

- Monitoring modules exist, but this map does not prove production alert coverage.
  Treat Telegram/metrics deployment readiness as a separate operational check.
