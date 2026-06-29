---
status: current
type: handoff
owner: human
created: 2026-06-12
last_reviewed: 2026-06-29
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

- **Backtest UX + late-listing fix (2026-06-29, Claude, user-requested):**
  (1) `backtesting/data_loader.py::_raise_on_venue_gap` now measures venue
  coverage from a symbol's first observed bar (`VENUE_GAP_MIN_COVERAGE = 0.80`),
  so multi-symbol backtests no longer crash on late-listing coins; empty series
  and sub-80% internal gaps still raise, no cross-venue substitution (I19 kept).
  Manifest `docs/change_manifests/2026-06-29-venue-gap-late-listing.md`.
  (2) New `POST /api/backtest/run/cancel/{job_id}` + a Cancel backtest button
  (mirrors fetch-jobs cancel) in `frontend/view-config.js`. (3) Backtest config
  Validation defaults to `None` instead of `Both (WF + CPCV)`. No strategy,
  risk, PnL, funding, config-gate, or deployment behavior changed.

- **C2 funding-carry realism re-cost complete (2026-06-29, Codex):** the C2
  funding-carry family is now refuted/shelved under the realism gate. New
  artifact:
  `results/pipeline_batch2_20260625/c2_funding_carry_realism/summary.json`.
  The rerun kept the original 24-combo grid, added fixed realism costs
  (`fee_bps=2`, two-leg `slippage_bps=3`, `basis_execution_slippage_bps=2`,
  `carry_cost_bps=1` daily), and counted the run as a retry:
  family-cumulative `n_trials=48` (prior 24 + retry 24). Results: WF OOS Sharpe
  -1.5093, CPCV OOS Sharpe -0.2349, DSR 0.0041, PSR 0.4457,
  `statistical_gate_passed:false`, `promotion_gate_passed:false`. Stress windows
  were selected mechanically from trailing 7-day funding APR < 0 or abs(basis z)
  > 3: 154 stress days, stress PnL -0.000786, stress max drawdown -0.000218, and
  4 active/mid-flip days. Realized annualized vol is still only 0.247%, below the
  2% self-check red flag, so the vectorized hedge model remains too calm. No
  live `funding_carry.py`, risk/portfolio/execution, DSR/CPCV/WF harness,
  config gate, demo/shadow/live, research, or old result artifact changed.

- **Pipeline batch 2 checkpoint 1 ready (2026-06-29, Codex):** the requested
  batch order [C3, C2, C1] ran after DB access became available, then stopped
  for Claude evidence review. Artifacts:
  `results/pipeline_batch2_20260625/{c3_sentiment,c2_funding_carry,c1_pairs_ou}/summary.json`
  and `results/pipeline_batch2_20260625/shortlist.md`. C3 Stage-2 FAIL because
  `external_observations.dataset_id='fear_greed_btc'` has event_count 0 over
  2024-01-01 through 2026-06-17; no proxy series was fabricated. C2 Stage-2 PASS
  and Stage-3 fold-refit completed with family n_trials 24, WF OOS Sharpe
  3.5596, CPCV OOS Sharpe 6.8913, DSR/PSR ~1.0, but
  `promotion_gate_passed:false` because portable validation is adapter-required
  and absent. C1 Stage-2 PASS and Stage-3 fold-refit completed with family
  n_trials 24, WF OOS Sharpe -1.2584, CPCV OOS Sharpe -0.9097, DSR 0.0079, PSR
  0.0994, and `promotion_gate_passed:false`. Ledgers append E-023/E-024/E-025
  after the initial blocked-attempt rows; H-006/H-007/H-008 now carry actual
  Stage-2 PASS/FAIL and trial counts. No live strategy behavior, risk/config
  gate, research file, DSR code, or existing result artifact was changed.
  Limitation: C2/C1 skipped Pass A parquet pre-screen because required BTC perp
  candle/funding parquet inputs are missing or incomplete; Pass B DB fold-refit
  completed and is the checkpoint evidence.

- **Strategy research pipeline Stage 2 feasibility automation (2026-06-29,
  Codex):** Stage 2 now has a machine-readable artifact contract and validator.
  New code: `backtesting/pipeline_feasibility.py` and
  `scripts/run_pipeline_stage2_check.py`. The batch-2 runner now writes
  `stage2_feasibility.json` beside each candidate output for PASS, FAIL, and
  data-probe exception paths. Current/target/gap: future Stage 2 runs are
  auditable by JSON before Stage 3; existing on-disk batch artifacts were not
  migrated or regenerated; literature ingestion and background orchestration
  remain outside this patch.

- **CPCV path-return retention + n_trials provenance (2026-06-29, Codex):**
  future `backtesting.cpcv.CPCV.evaluate()` outputs retain raw `path_returns`
  (or `combined_returns` when no path assembly exists), lengths, periods,
  `n_trials_provenance`, and `n_trials_is_floor`. Missing `n_trials` now falls
  back to the observed grid/combo floor and is tagged `grid_size_floor`; explicit
  nonpositive values still set `validation.n_trials_missing`. XS momentum scans
  accept `researched_n_trials` and otherwise tag the family/grid count as a
  floor. `scripts/recheck_dsr.py` recomputes DSR from retained returns and prints
  old-to-new DSR; pipeline checkpoint summaries carry retained CPCV fields with
  `caller_declared` family-cumulative trial provenance. Existing result
  artifacts were not rewritten, so historical summary-only CPCV artifacts remain
  non-recomputable offline.

- **User manual completion (2026-06-25, Codex):** manual chapters
  `00-architecture` through `80-glossary` are now readable Traditional Chinese
  summaries and declared `written` in `docs/manual/manual.json`. The content
  summarizes existing docs only; no research files, strategy behavior, config
  gates, risk rules, deployment behavior, or result artifacts changed.

- **Read-only Progress panel (2026-06-26, Codex):** `/api/progress` and the
  Progress Analysis nav panel now shows curated workstream milestone cards from
  `config/workstreams.yaml`. The route is local/read-only: YAML registry only;
  no git, `STATUS.md`, DB, network, write path, trading-core, config-gate,
  deployment, or result-artifact change. Maintenance contract: update
  `config/workstreams.yaml` alongside `docs/AI_HANDOFF.md`.
- **Pipeline batch 1 Stage 3/refit checkpoint (2026-06-25, Codex):** Binance
  canonical data is complete for S6/S7 over `2024-01-01` through
  `2026-06-16 23:59 UTC`: BTC/ETH perps and BTC/ETH spot each have 1,293,120 1m
  rows with 0 gaps; BTC/ETH perp funding each has 2,694 rows. The defective
  full-sample-select-then-slice harness is superseded by fold-refit validation
  (`backtesting/pipeline_refit.py`, I24/F22). New S5/S6 artifacts are under
  `results/pipeline_batch1_20260625_refit/`: S6 has WF OOS Sharpe 0.0088, CPCV
  OOS Sharpe 0.5422, DSR 0.1963, PSR 0.7387, `statistical_gate_passed:false`;
  do **not** start adapter/ct_val work. S5 reran with ETH factor data but current
  point-in-time membership plus venue-scoped candle coverage produces
  `nonzero_grid_activity:false`, so it is a data-universe artifact, not a
  strategy verdict. S7 was rerun with a non-degenerate finite half-life grid and
  is `shelved_pending_research_review` (WF -0.4359, CPCV -1.1124, DSR/PSR ~0),
  not refuted from the prior all-zero no-trade artifact. No strategy is
  promotion-ready or live/demo/shadow ready.
- **Pipeline batch 1 CLOSED + batch 2 pre-registration history (2026-06-25, Claude):**
  Batch 1 [S7, S5, S6] is closed — all three fail the statistical gate under the
  fold-refit harness (see above); none has edge, the gate worked. Do **not** tune
  S5/S6/S7 to chase the gate (mirrors H-002). Batch 2 is pre-registered in this
  historical note and is now superseded by the 2026-06-29 Codex checkpoint above:
  C1 BTC/ETH OU-gated pairs RV (H-006/E-017, F-PAIRS-OU, n_trials=24); C2
  funding carry + basis-z filter (H-007/E-018, F-FUNDING-CARRY, 24); C3 Fear&Greed
  long/flat (H-008/E-019, F-SENTIMENT, 9, `fear_greed_btc` data Stage-2 check
  pending). Run order [C3, C2, C1]; batch id `pipeline_batch2_20260625`. Claude
  writes Stage-1 specs before Codex runs Stage 2->3. T2
  (CPCV raw-path retention + honest n_trials) is implemented for future artifacts;
  follow-up task history is in
  `tasks/2026-06-25-pipeline-batch1-followup-tasks.md`.
- **Strategy Research Pipeline Stage 1 machinery (2026-06-25, Codex):** spec
  `docs/superpowers/specs/2026-06-25-strategy-research-pipeline-design.md` and
  plan `docs/superpowers/plans/2026-06-25-strategy-research-pipeline-stage1.md`
  now have the minimal driver/templates under `docs/superpowers/pipeline/`.
  `scan_xs_momentum` accepts `prior_family_n_trials` and reports
  family-cumulative `n_trials`; the ledgers define family trial accounting and
  I23. The autonomous driver has **not** been run end-to-end; batch 1
  [S7, S5, S6] was run via `scripts/run_pipeline_batch1_checkpoint.py` and is now
  closed (all refuted); batch 2 = [C3, C2, C1] is now at checkpoint 1 per the
  2026-06-29 Codex entry above. No strategy promotion, config, result artifact
  values, or demo/shadow/live gates changed.
- **Results cleanup (2026-06-24, user-approved):** all pre-6/18 `results/`
  artifacts were deleted (scratch runs + cited evidence: `cme_gap_research*`,
  `codex_2026061{2,6}_signal_*`, `results/strategy_validation/`,
  `ui_funding_carry_ac454742`, old PNGs). 6/18+ kept, incl. the adr0007 PASS
  evidence. Consequence: no on-disk strategy-signal-validation evidence remains ??
  re-run `make strategy-signal-validation` before any promotion citation (CI
  regenerates it). `docs/results_validation_manifest.md` rows for deleted files
  are historical only.
- **Latest XS momentum / validation state (2026-06-24, Codex) - DSR fixed,
  portfolio-vol correctness rerun, promotion still blocked:** DSR now uses the
  same per-observation return-series basis as PSR and CPCV no longer treats
  overlapping paths as one independent sample; invariant `DSR <= PSR(0)` is
  guarded by `tests/unit/test_dsr.py` and `tests/unit/test_cpcv.py`. XS momentum
  sizing now targets estimated portfolio book vol with `MAX_GROSS_LEVERAGE=2.0`.
  New artifact: `results/xs_momentum_validation_20260624_portfoliovol/` with
  WF OOS Sharpe 1.2412, CPCV OOS Sharpe 0.6027, DSR 0.7823, PSR 0.8234,
  `n_trials=8`, `n_combinations=15`, `promotion_gate_passed:false`, and
  `status:"review_required"`. PSR remains below 0.95, so there is **no
  promotion support**. `xs_momentum` remains disabled; live/demo/shadow gates
  unchanged.
- **DSR all-strategy recheck (2026-06-24, Codex):** `scripts/recheck_dsr.py`
  scans saved JSON artifacts for DSR fields. Current run found 45 DSR-bearing
  JSON rows: 7 CPCV rows and 38 replay-level single-run diagnostic rows. The
  single-run rows set `dsr == psr` and are not the CPCV multiple-trial DSR
  defect. Daily Winner CPCV was recomputed from saved returns and remains near
  zero DSR. `xs_momentum_validation_20260623` and
  `xs_momentum_validation_20260624_leakfix` have `DSR > PSR(0)` and are
  untrusted. `xs_momentum_validation_20260624_portfoliovol` passes the invariant
  and stays below gate, but raw path returns were not saved, so the audit cannot
  independently recompute it from artifacts alone.

- **Latest XS momentum Phase C state (2026-06-24, Codex) - leak fixed,
  promotion still blocked:** `backtesting/xs_momentum_backtest.py` now shifts
  daily targets one full day before intraday expansion, so day-D positions
  cannot use day-D close information. Regression:
  `tests/unit/test_xs_momentum_backtest.py::test_daily_close_target_is_not_traded_on_same_day`.
  The leaked `results/xs_momentum_validation_20260623/` artifact has
  `SUPERSEDED.md` and remains **INVALID / do not cite** despite its old
  `promotion_gate_passed:true` JSON field. Leak-free rerun:
  `results/xs_momentum_validation_20260624_leakfix/` with 27 loaded symbols,
  `n_trials=8`, `n_combinations=15`, WF combined OOS Sharpe 0.8825, CPCV overall
  OOS Sharpe 0.5577, pre-fix DSR 1.0 (**untrusted; DSR > PSR**), PSR 0.7961,
  `promotion_gate_passed:false`, and `status:"review_required"`. PSR is below
  0.95, so this does **not** support promotion. Vol-target under-leverage remains
  a separate Claude/user decision.

- **XS momentum Phase C review (2026-06-24, Claude) ??LEAK, BLOCK promotion:**
  `backtesting/xs_momentum_backtest.py` has a look-ahead leak ??the day-D target
  weight is built from day-D's own 23:00 close and lagged only one intraday bar,
  so rebalance days are partially traded with hindsight. The committed validation
  artifact `results/xs_momentum_validation_20260623/` (OOS Sharpe 2.4??.1, ~2??%
  vol, `dsr=1.0`, `psr=0.99`, `promotion_gate_passed:true`) is **INVALID /
  superseded ??do not cite as evidence.** D3 fixes (annualized vol-target,
  `market_close` wiring) landed and are tested; funding sign is R3.1-correct;
  vol-target still under-levers ~5? (separate spec-conformance item). Fix +
  re-run: `tasks/2026-06-24-xs-momentum-lookahead-fix-task.md`; review:
  `tasks/2026-06-24-xs-momentum-phase-c-review.md`.
- **XS momentum Phase C research runner (2026-06-23, Codex):** the scaffold is
  committed on `codex/xs-momentum-universe-scaffold` as `07a5d9c`. Phase C adds
  `backtesting/xs_momentum_backtest.py` with R3.1 funding signs, annualized
  vol-target sizing, `market_close` crash-filter wiring, and honest `n_trials`.
  Smoke artifact `results/xs_momentum_db_smoke_20260623.json` is
  `db_smoke_not_promotion`: 22 included symbols, strict venue gap on
  `SOL-USDT-SWAP`, no WF/CPCV or DSR/PSR, and no promotion/live claim.
- **Funding-carry venue fallback fix (2026-06-23, Codex):**
  `backtesting/replay.py::load_l1_books` now preserves the existing explicit
  `BTC-USDT` spot-to-`BTC-USDT-SWAP` fallback for funding-carry synthetic books
  after a primary venue-scoped candle gap. The fallback still uses the same
  `exchange` and does not permit parquet or cross-venue substitution. Manifest:
  `docs/change_manifests/2026-06-23-funding-carry-venue-fallback.md`.
- **Market Data Coverage fast path (2026-06-23, Codex):**
  `/api/data/coverage` now reads OHLCV list rows from `instrument_bars` metadata
  instead of full-scanning `canonical_candles`; the UI shows estimated OHLCV row
  counts with `~` and shows a visible unavailable/error state when the coverage
  request fails instead of implying the DB is empty. Funding coverage provider
  labels now come from `funding_rates.source`, not a hard-coded OKX label. The
  coverage table has local exchange, pair/dataset search, and data-type filters;
  funding export displays fixed `8H` frequency instead of an OHLCV bar.
- **Current goal:** A 2026-06-23 Codex pass implemented the local A1/A3/B1-B5
  scaffold for XS momentum and point-in-time universe membership from
  `docs/superpowers/plans/2026-06-23-xs-momentum-universe.md`. The work is
  research-tier only: `xs_momentum` is disabled by default, `on_market()` is
  a no-op, the generated `data/universe/universe_membership.parquet` artifact
  is local/ignored, and no live/demo/shadow or promotion readiness claim exists.
  A2 bulk 1m/funding plus canonical DB coverage remains unfinished. C1-C3 remain
  unfinished; C1 needs review because the plan's short-leg positive-funding
  sign expectation conflicts with `docs/DOMAIN_RULES.md` R3.1.
- **D3 review (2026-06-23, Claude):** scaffold A/B/D1 verified sound (9/9 tests,
  doc-impact gate pass, 30-symbol point-in-time membership correct); Phase C
  absent ??no edge evidence; not promotion/live. Funding-sign conflict resolved ??
  the plan was wrong (R3.1 stands: short receives positive funding), plan fixed in
  `5c80cc7`, so C1 is unblocked. Phase-C to-fix: annualize the vol-target
  (currently a no-op) and wire `market_close` into the crash filter. XS scaffold
  remains uncommitted on `fix/ohlcv-exchange-provenance`. Detail:
  `tasks/2026-06-23-xs-momentum-d3-review.md`.
- **Previous goal:** Validation Lab report package and Backtest execution
  profiles are prepared for the 2026-06-22 presentation while Option C fast
  backtest artifact-read work remains the broader active branch context. A
  2026-06-23 Claude docs-only pass rebuilt the deck for an internal-team
  audience (plain Chinese; purpose -> workflow -> validation factors -> per-tool
  function-vs-limit comparison; 10 main + 6 appendix slides) and added a full
  methodology document `docs/validation_methodology_zh.docx` via
  `scripts/generate_validation_methodology_doc.py` (needs `python-docx`).
- **Current branch:** `codex/xs-momentum-universe-scaffold`.
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
  value mismatches. Codex then fixed the structural source-selection bug so
  venue-tagged replay reads Binance-scoped canonical Postgres candles instead of
  source-less parquet; regenerated MA/EMA/MACD runs with suffix
  `_venue_scoped_pg_20260623` now have the Binance 2024-04-29 close `63229.2`,
  and the MA source-provenance validation passes DB parity over 20,400 rows with
  0 mismatches. Any `fill_all_signals` run remains
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
  (no DSN ??DB parity skipped), and the runs are idealized `strategy_fill`. Not
  promotion/live evidence. Measured runtime: vectorbt ~125s/run; backtrader is the
  bottleneck, so the long-window batch is impractical as an inline check ??see the
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
  Local-vs-DB check: 24 rows, 0 close mismatches. Regeneration alone was not
  enough because replay had been reading source-unscoped candles; the
  venue-scoped source fix now forces canonical Postgres with
  `source_primary=binance`, refuses parquet fallback for venue-tagged candle
  loads, and raises explicit venue gaps. New MA DB parity evidence:
  `results/validation_lab_ma_crossover_btc_binance_1h_20260622_venue_scoped_pg_20260623/validation/codex_venue_scoped_pg_db_parity_20260623_pass/validation_result.json`
  has `canonical_source_primary == "binance"`, `artifact_rows=20400`,
  `db_rows=20400`, `value_mismatches=0`, and
  `ohlcv_source_validation == "db_parity_pass"`.
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
  (a) nautilus is advisory and was not run in the 2026-06-23 batch; (b) broader
  promotion evidence still needs WF/CPCV and realistic-execution review. The MA
  source-data DB parity leg is now reproduced on the venue-scoped regenerated run.
- Decide whether realistic replay needs an explicit small-order fill policy
  before using MACD realistic-fill counts as strategy evidence.

## How to update

Overwrite the snapshot whenever it goes stale; do not append history. Move
completed detail to `docs/CHANGELOG_AI.md` and durable gaps to
`docs/KNOWN_ISSUES.md`.

Related: `docs/AI_HANDOFF.md` and [[CONTEXT_INDEX]] and [[CONTEXT_BUDGET]].
