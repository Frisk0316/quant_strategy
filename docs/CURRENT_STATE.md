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

- **Current goal:** Validation Lab report package and Backtest execution
  profiles are prepared for the 2026-06-22 presentation while Option C fast
  backtest artifact-read work remains the broader active branch context. A
  2026-06-23 Claude docs-only pass rebuilt the deck for an internal-team
  audience (plain Chinese; purpose -> workflow -> validation factors -> per-tool
  function-vs-limit comparison; 10 main + 6 appendix slides) and added a full
  methodology document `docs/validation_methodology_zh.docx` via
  `scripts/generate_validation_methodology_doc.py` (needs `python-docx`).
- **Current branch:** `codex/impl-multi-venue-instrument-specs`.
- **Backtest execution profiles:** Implementation is complete from
  `docs/superpowers/specs/2026-06-22-backtest-execution-profiles-design.md`.
  User-facing choices are `Strategy Fill` and `Dual Output`; live/demo/shadow
  gates remain unchanged and Strategy Fill is idealized research evidence only.
  BTC-USDT-SWAP Binance 1H checks with `max_order_notional_usd=250` and
  `max_pos_pct_equity=1` pass signal-to-order under Strategy Fill; full-period
  MACD Dual Output shows the realistic maker path still has only 3 submitted
  strategy-order fills and 1 terminal liquidation fill. Run Detail now shows
  the execution profile and links dual-output comparison JSON through the
  backtest API.
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
  rejects the repo `quant` credentials. **2026-06-23 DB parity state:** Claude's
  probe found no binance-sourced BTC-USDT-SWAP 1H canonical rows; Codex then
  resampled Binance 1m canonical rows into 20,400 Binance 1H rows and filled the
  remaining 2024-04-29 one-day gap with direct Binance 1H data through
  `download_binance_data.py`. Local parquet and DB canonical Binance 1H rows now
  match for 2024-04-29 (24 rows, 0 close mismatches). Existing validation-lab
  artifacts were generated before that repair and still fail DB parity with 24
  value mismatches, so regenerate/revalidate them before citing a current
  DB-backed Binance 1H PASS. Any `fill_all_signals` run remains
  idealized research-only evidence and must not be cited for live readiness. The
  2026-06-22 long-window BTC/Binance differential-validation attempts for the
  generated MA/EMA/MACD runs did not complete locally; cite the result only as
  signal-to-order evidence, not as fresh three-engine portable validation.
  The reduce-only fat-finger bypass depends on callers passing correct current
  position notional into `RiskGuard.check()`. Low fill counts in realistic
  replay can be execution-model artifacts, especially when queue allocation
  rounds below venue lot/min size; check distinct filled order ids, cancellation
  logs, and `queue_fill_fraction` before interpreting strategy signal quality.

- **Engine-consistency evidence (2026-06-23, Claude):** the long-window
  vectorbt+backtrader differential validation that "did not complete locally" on
  2026-06-22 now completes and PASSES. On the real Binance BTC-USDT-SWAP 1H
  (20400-bar) `strategy_fill` runs, ma/ema/macd_crossover each report
  `portable_validation_gate.passed == true` with vectorbt AND backtrader
  `signal_logic == PASS`, `actionable_mismatch_count == 0`. Artifacts:
  `results/validation_lab_{ma,ema,macd}_crossover_btc_binance_1h_20260622_maxord250_pospct1_strategyfill/validation/claude_engine_consistency_20260623/validation_result.json`.
  This is signal-logic engine-consistency only: `admissibility == advisory_only`,
  `promotion_gate_evidence == false`, `ohlcv_source_validation == artifact_pass_db_skipped`
  (no DSN → DB parity skipped), and the runs are idealized `strategy_fill`. Not
  promotion/live evidence. Measured runtime: vectorbt ~125s/run; backtrader is the
  bottleneck, so the long-window batch is impractical as an inline check — see the
  `tasks/2026-06-23-engine-consistency-smoke-task.md` Codex task for a fast offline
  frozen-fixture smoke (`make engine-consistency-smoke`).
- **Engine-consistency smoke (2026-06-23, Codex):** an offline frozen-fixture
  smoke now exists at `make engine-consistency-smoke`, backed by
  `tests/fixtures/engine_consistency/` and
  `scripts/run_engine_consistency_smoke.py`. Local run passed vectorbt+backtrader
  signal logic in 27.581s. Fixture coverage: MA and EMA each use
  2024-01-01T00:00Z through 2024-02-09T23:00Z (960 hourly bars, 5 signals);
  MACD uses 2024-01-01T00:00Z through 2024-01-05T23:00Z (120 hourly bars,
  5 signals). This is signal-logic-only, idealized `strategy_fill` evidence,
  not promotion/live-readiness evidence.
- **Binance 1H DB parity (2026-06-23, Codex):** `scripts/resample_binance_1h_canonical.py`
  seeded 20,400 Binance-sourced BTC-USDT-SWAP 1H canonical rows from Binance 1m
  canonical data for 2024-01-01 through 2026-04-30T23:00. A follow-up
  `download_binance_data.py --bar 1H --start 2024-04-29 --end 2024-04-30`
  run replaced the remaining OKX-backed 2024-04-29 day with Binance 1H data in
  both `data/ticks/BTC_USDT_SWAP/candles_1H.parquet` and `canonical_candles`.
  Local-vs-DB check: 24 rows, 0 close mismatches. Existing validation-lab
  artifacts still need regeneration because old MA source provenance now has
  `db_rows=20400`, `missing_in_db=0`, but `value_mismatches=24`.
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
- For the Validation Lab report follow-up: long-window vectorbt+backtrader
  signal-logic consistency for MA/EMA 10/200 and MACD 12/26/9 now PASSES, and a
  repeatable offline smoke exists at `make engine-consistency-smoke`. Remaining:
  (a) nautilus is advisory and was not run in the 2026-06-23 batch; (b) DB parity
  needs regenerated validation-lab artifacts after the 2024-04-29 Binance data
  repair.
- Decide whether realistic replay needs an explicit small-order fill policy
  before using MACD realistic-fill counts as strategy evidence.

## How to update

Overwrite the snapshot whenever it goes stale; do not append history. Move
completed detail to `docs/CHANGELOG_AI.md` and durable gaps to
`docs/KNOWN_ISSUES.md`.

Related: `docs/AI_HANDOFF.md` and [[CONTEXT_INDEX]] and [[CONTEXT_BUDGET]].
