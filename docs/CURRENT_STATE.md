---
status: current
type: handoff
owner: human
created: 2026-06-12
last_reviewed: 2026-06-22
expires: none
superseded_by: null
---

# Current State

A small, always-current snapshot a session can trust on a cold start. Keep this
**short** and **present-tense** - it is not a changelog (history goes to
`docs/CHANGELOG_AI.md`) and not a backlog (gaps go to `docs/KNOWN_ISSUES.md`).

This file complements `docs/AI_HANDOFF.md`: `AI_HANDOFF.md` is the working
handoff between sessions; this is the one-screen "where are we" that
[[CONTEXT_BUDGET]] marks must-load.

## Snapshot

- **Current goal:** Validation Lab report package is prepared for the
  2026-06-22 presentation while Option C fast backtest artifact-read work remains
  the broader active branch context.
- **Current branch:** `codex/impl-multi-venue-instrument-specs`.
- **Last known good state:** The branch contains P1 merge commits `d649701`
  (Claude design/changelog) and `10d631f` (price chart) on top of the ADR-0007
  implementation. No existing result artifacts were modified.
- **Current working state:** Local ADR-0007 P1 closeout is implemented.
  `db_parity` reports `canonical_source_primary`, scopes canonical reads to the
  run exchange, and compares timestamped `close` only for `price_series.csv`
  provenance. A direct 2026-06-18 check of the saved Binance run matched 192/192
  artifact closes to DB canonical Binance closes with zero mismatches. Durable
  source-provenance evidence lives at
  `results/adr0007_binance_btc_1h_db_pass_20260618/validation/codex_close_only_db_parity_pass_20260618/validation_result.json`
  and passes `ct_val_provenance`, `db_parity`, and `ohlcv_source_validation`.
  Price chart panels now render progressively per selected symbol, with
  technical overlays still gated to MA/EMA/MACD; in-flight per-symbol chart
  fetches are guarded by `runId`, so changing selected symbols no longer leaves
  an earlier symbol stuck at `loading`. Equity and drawdown charts use the same
  fluid width as price panels. The Backtest run list uses the frontend's long
  timeout because the running local server has shown 3-5s HTTP responses for
  `/api/backtest/runs` while WS reconnects are noisy. The run
  `ui_ema_crossover_a986588f` is present in local Postgres `backtest_runs` and
  `backtest_artifacts`; it has no local `results/<run_id>/result.json` because
  the configured DSN makes artifact mode default to DB. Validation Lab now merges
  saved Backtest Runs into its candidate selector and runs saved records through
  run-scoped differential validation; DB-only runs are materialized to a temporary
  input bundle for validation output under `results/<run_id>/validation/` without
  backfilling `result.json`. Research-only `fill_all_signals` replay now also
  lifts daily-loss and drawdown stops, records the effective thresholds in
  `result.validation.fill_all_signals_controls`, and keeps later generated
  strategy signals flowing through submitted orders/fills for signal-side
  sensitivity checks. Backtest Price and technical indicator panels expose
  visible vertical Y scale controls, and the Risk tab loads signal rows to show
  signal-to-fill gaps for sparse-trading diagnosis. Market Data Coverage now
  queues fetch jobs sequentially in the API, renders the fetch job list in the
  frontend, exposes a guarded whole-pair delete path for OHLCV/funding pairs,
  and syncs Binance exchangeInfo-derived specs into `venue_instrument_specs` so
  fetched multiplier contracts such as `1000SHIB-USDT-SWAP` can resolve DB
  `ct_val`. Fast artifact-read work now adds migration 0012, a derived
  `backtest_artifact_rows` table, row-first chart/table API reads, a lightweight
  `/api/backtest/{run_id}/summary` endpoint, summary-first frontend selection,
  and backfill/benchmark scripts. The row table is disposable derived data; old
  runs need `scripts/backfill_backtest_artifact_rows.py --all --verify` after
  migration before their first-click artifact reads use the fast path. A
  2026-06-22 Validation Lab report package now exists at
  `docs/validation_lab_report_zh.md` and
  `docs/backtest_external_validation_report_zh.pptx`; it includes a
  BTC-USDT-SWAP Binance 1H signal-to-order check summary at
  `results/validation_lab_signal_order_check_20260622.json`. A follow-up
  sensitivity rerun with `max_order_notional_usd=250` and
  `max_pos_pct_equity=1.0` is saved at
  `results/validation_lab_signal_order_check_20260622_maxord250_pospct1.json`.
  Reduce-only close orders may now bypass the single-order fat-finger cap only
  up to current position notional; exposure-increasing orders remain capped. A
  second verification rerun with the same 250/1.0 risk overrides is saved at
  `results/validation_lab_signal_order_check_20260622_maxord250_pospct1_verify2.json`.
  MACD still has sparse real fills because realistic replay uses
  `queue_fill_fraction=0.20` plus Binance `lotSz/minSz=0.001`; after MACD leaves
  a 0.002 BTC-USDT-SWAP residual long, each reduce-only sell can allocate only
  0.0004 per touch and rounds to zero, so orders can be submitted/cancelled
  without fill rows until terminal liquidation. The MACD 13 fill rows include
  one terminal-liquidation row; excluding terminal liquidation, only 3 submitted
  order ids generated real replay fill rows.
- **Active risks:** The older checked-in validation artifact
  `adr0007_binance_btc_1h_db_pass_20260618_source_provenance` still records the
  pre-fix FAIL and now carries `SUPERSEDED.md`; cite the new
  `codex_close_only_db_parity_pass_20260618` artifact for PASS evidence. Port
  5432 repo DSN is currently reachable; local PostgreSQL on port 5433 still
  rejects the repo `quant` credentials. Any `fill_all_signals` run remains
  idealized research-only evidence and must not be cited for live readiness. The
  2026-06-22 long-window BTC/Binance differential-validation attempts for the
  generated MA/EMA/MACD runs did not complete locally; cite the result only as
  signal-to-order evidence, not as fresh three-engine portable validation.
  The reduce-only fat-finger bypass depends on callers passing correct current
  position notional into `RiskGuard.check()`. Low fill counts in realistic
  replay can be execution-model artifacts, especially when queue allocation
  rounds below venue lot/min size; check distinct filled order ids, cancellation
  logs, and `queue_fill_fraction` before interpreting strategy signal quality.
- **Do-not-touch:** trading-core (`strategies/`, `signals/`, `risk/`,
  `portfolio/`, `execution/`), PnL/fee/funding behavior, deployment gates,
  existing result artifacts, and API/frontend behavior outside the approved
  artifact fast-read and Market Data Coverage queue/delete scopes. Do not add DB
  schema changes beyond approved migrations 0011 and 0012 in this branch.

## Next steps

- Apply migration 0012, run artifact-row backfill with `--verify`, and capture a
  benchmark report against a running API when a DB-backed environment is
  available.
- Manually smoke the Market Data Coverage queue/delete flow against a DB-backed
  server before relying on it operationally.
- For Binance symbols downloaded before the spec-sync fix, rerun a fetch or seed
  `venue_instrument_specs` before replaying multiplier contracts such as
  `1000SHIB-USDT-SWAP`.
- Open/review one consolidated PR from `codex/impl-multi-venue-instrument-specs`
  to `main` after the active implementation branch is ready.
- Keep Binance promotion work (signal quorum + WF/CPCV) and branch-protection
  required-check configuration as separate tasks.
- For the Validation Lab report follow-up, create a short BTC/Binance fixture or
  profile `scripts/run_differential_validation.py` before claiming long-window
  three-engine validation for MA/EMA 10/200 or MACD 12/26/9.
- Decide whether realistic replay needs an explicit small-order fill policy
  before using MACD realistic-fill counts as strategy evidence.

## How to update

Overwrite the snapshot whenever it goes stale; do not append history. Move
completed detail to `docs/CHANGELOG_AI.md` and durable gaps to
`docs/KNOWN_ISSUES.md`.

Related: `docs/AI_HANDOFF.md` and [[CONTEXT_INDEX]] and [[CONTEXT_BUDGET]].
