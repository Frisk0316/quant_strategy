---
status: current
type: handoff
owner: human
created: 2026-05-11
last_reviewed: 2026-06-22
expires: none
superseded_by: null
---

> **2026-05-14 architecture shift**: `storage.candle_backend` default flipped to `postgres`; `download_okx_data.py` / `download_binance_data.py` now write parquet + TimescaleDB simultaneously via `scripts/_db_writer.py`. Falls back to parquet when no DSN is reachable. See "Current Change Context" row "DB-primary backtest path".
>
> Historical session records should move to CHANGELOG_AI.md over time.
> Durable bug backlog should move to KNOWN_ISSUES.md over time.
> This file should stay focused on current state and next actions.

# AI Handoff

Cross-session memory for Claude and Codex. **Read this before starting any task. Update this before ending any session.**

---

## Current Goal

2026-06-23 Codex session note (XS momentum universe scaffold): implemented the
local A1/A3/B1-B5 portions of
`docs/superpowers/plans/2026-06-23-xs-momentum-universe.md`. Added
`config/universe.yaml`, point-in-time membership builder/tests, disabled
`xs_momentum` config/model/stub, dollar-neutral long-short target-weight helpers,
crash-regime gross scaling, ADR-0009, Change Manifest
`docs/change_manifests/2026-06-23-xs-momentum-universe.md`, and survivorship
invariant/failure-mode docs. Generated local research artifact
`data/universe/universe_membership.parquet` (ignored by git). A2 remains
unfinished because bulk 1m/funding download plus canonical DB coverage requires
external data/DB work. C1-C3 remain unfinished; C1 is blocked for review because
the plan says positive funding reduces short-leg PnL, while `docs/DOMAIN_RULES.md`
R3.1 says long pays positive funding and vice versa. No research files, live
gates, deployment modes, or existing result artifacts were modified.

2026-06-23 Claude D3 review note (XS momentum scaffold): reviewed the Codex
scaffold above. Verdict — Phase A+B+D1 complete, sound, and honestly documented;
**Phase C (the whole validation) absent → zero edge evidence**; `enabled:false`,
no promotion/live claim permitted. Verified: 9/9 new unit tests pass, doc-impact
gate passes, membership covers 30 symbols with correct point-in-time/survivorship
logic. Resolved the funding-sign open item: the *plan* was wrong, not the code —
R3.1 is canonical (long pays positive, short receives), plan fixed in commit
`5c80cc7`, so **C1 is unblocked**. Extra Phase-C fixes flagged: vol-target gross
is not annualized (currently a no-op) and the crash filter needs the runner to
pass `market_close`. Full review: `tasks/2026-06-23-xs-momentum-d3-review.md`.
⚠️ All XS scaffold is still uncommitted on `fix/ohlcv-exchange-provenance` (which
also holds unrelated `52b4f81`); Codex should commit it with an `AI-Origin: Codex`
trailer before it is lost.

2026-06-23 Claude session note (audience-facing report rewrite, docs-only): the
Validation Lab deck was rebuilt for an internal-team/reviewer audience. Per user
feedback the old deck was too jargon-heavy, mixed Chinese/English mid-sentence,
lacked a purpose/workflow narrative, and over-emphasized "not live-ready".
`scripts/generate_backtest_external_validation_report.py` now produces a 16-slide
deck (10 plain-Chinese main slides: purpose -> workflow -> validation factors
[signal/indicator/trade/pnl/source] -> per-tool function-vs-limit comparison ->
results -> next-step gaps -> conclusion; + 6 technical appendix slides). A new
full methodology document was added: `scripts/generate_validation_methodology_doc.py`
-> `docs/validation_methodology_zh.docx` (requires `python-docx`). No strategy,
risk, config, deployment-gate, or result-artifact changes; all claims stay
anchored to `docs/validation_lab_report_zh.md` and remain advisory-only.

2026-06-22 Codex session note: a user-facing Validation Lab report package was
prepared for a presentation. The package includes
`docs/validation_lab_report_zh.md`,
`docs/backtest_external_validation_report_zh.pptx`,
`scripts/run_validation_lab_signal_order_check.py`, and
`results/validation_lab_signal_order_check_20260622.json`. The BTC-USDT-SWAP
Binance 1H check used MA/EMA 10/200 and MACD 12/26/9 and confirmed
signal-to-order/fill paths for all three strategies. MA/EMA were mostly blocked
after initial fills by the current 500 USD fat-finger max-order-notional cap.
Long-window run-scoped differential-validation attempts for those generated
artifacts did not complete locally, so this evidence must not be cited as fresh
three-engine portable validation or live-readiness evidence.
Follow-up sensitivity rerun requested by the user used
`max_order_notional_usd=250` and `max_pos_pct_equity=1.0`, saved at
`results/validation_lab_signal_order_check_20260622_maxord250_pospct1.json`.
It is still signal-to-order evidence only; no permanent `config/risk.yaml`
change was made. After user approval, RiskGuard reduce-only close orders may now
bypass the single-order fat-finger cap only up to current position notional;
exposure-increasing orders remain capped. The same 250/1.0 rerun now shows MA
orders 5->117 and rejections 112->0, with one
`allowed_reduce_only_bypass:fat_finger_reduce_only` event.
Follow-up verification output is saved at
`results/validation_lab_signal_order_check_20260622_maxord250_pospct1_verify2.json`.
MACD still reports 779 submitted orders but only 13 real fill rows because only
4 distinct order ids ever fill. The fill-model root cause is small residual
close sizing under realistic queue rounding: Binance BTC-USDT-SWAP has
`lotSz/minSz=0.001`, `queue_fill_fraction=0.20`, and after MACD leaves a 0.002
residual long, a touched reduce-only sell can allocate only 0.0004 per bar,
which `_round_fill_size()` rounds to 0. Most later sell orders are replacement
orders cancelled by `cancel_existing`; this is execution-model evidence, not
signal-quality evidence. The 13 fill rows include one terminal-liquidation row;
excluding terminal liquidation, only 3 submitted order ids generated replay L1
fill rows.

Current session goal: finish the user-requested backtest follow-up: make
research-only `fill_all_signals` carry later generated signals through replay
after drawdown stops, expose visible vertical Y scale controls in Price and
indicator panels, and diagnose the default sparse-trading behavior. Work is on
`codex/impl-multi-venue-instrument-specs`. Branch baseline before this task:
ADR-0007 P1 multi-venue instrument specs are locally implemented:
venue specs migration/seed, exchange-aware `ct_val` resolution, exchange-tagged
provenance/source gates, Run Backtest exchange selection, convergence golden
case, and docs/manifest updates. Follow-up implemented: normal Binance/Bybit
USDT-M perps can resolve `ct_val = 1.0` structurally as `exchange_base_unit`;
canonical `1000...` multiplier contracts still require DB specs. Task 4 DB
parity exchange scoping is repaired: postgres canonical candle reads now filter
`source_primary` by the run exchange, and DB parity emits
`canonical_source_primary` so a Binance PASS must prove it compared Binance
candles. 2026-06-18 DB-backed rerun proved source scoping works
(`canonical_source_primary == "binance"`). Follow-up fixed the DB parity input
contract so `price_series.csv` provenance compares timestamped close only; a
direct check matched 192/192 artifact closes to Binance canonical closes with
zero mismatches. Durable PASS evidence now exists at
`results/adr0007_binance_btc_1h_db_pass_20260618/validation/codex_close_only_db_parity_pass_20260618/validation_result.json`
with `db_parity.status == "PASS"`, `canonical_source_primary == "binance"`,
and `ohlcv_source_validation == "db_parity_pass"`. The older
`adr0007_binance_btc_1h_db_pass_20260618_source_provenance` artifact remains a
pre-fix FAIL, carries `SUPERSEDED.md`, and should not be cited as PASS.
2026-06-18 branch consolidation merged `claude/design-multi-venue`
(`4006733`) and `codex/fix-price-chart-universal` (`76dcecc`) into this P1
branch. Preferred integration path is one consolidated P1 PR; Binance promotion
validation and GitHub branch-protection required-check setup stay separate.

2026-06-23 Claude review note: verified Codex's execution-profile + lot/min-size
work (tests pass; scope clean; default profile is idealized `strategy_fill`).
"Signals trade when they appear" holds only under `strategy_fill`; realistic
replay still fills ~0.4% (deferred by user — backtest-first phase). Confirmed the
differential-validation harness is fully implemented and the long-window
vectorbt+backtrader runs that "did not complete locally" on 2026-06-22 now
complete and PASS (ma/ema/macd_crossover, `portable_validation_gate.passed`,
zero actionable mismatch) on the real Binance 1H 20400-bar `strategy_fill` runs —
signal-logic engine-consistency only, `advisory_only`, not promotion evidence.
Wrote Codex task `tasks/2026-06-23-engine-consistency-smoke-task.md` for a fast
offline frozen-fixture smoke (`make engine-consistency-smoke`). Open validation
work: nautilus advisory run, DB-parity with DSN, and (later phase) WF/CPCV for
strategy edge.

2026-06-23 Codex follow-up: offline engine-consistency smoke is implemented as
`make engine-consistency-smoke`, with `scripts/run_engine_consistency_smoke.py`
and frozen fixtures under `tests/fixtures/engine_consistency/`. Local run passed
vectorbt+backtrader signal logic for MA/EMA/MACD in 27.581s. Fixture coverage:
MA 2024-01-01T00:00Z to 2024-02-09T23:00Z, 960 bars, 5 signals; EMA
2024-01-01T00:00Z to 2024-02-09T23:00Z, 960 bars, 5 signals; MACD
2024-01-01T00:00Z to 2024-01-05T23:00Z, 120 bars, 5 signals. This remains
signal-logic-only, idealized `strategy_fill` evidence, not promotion/live
evidence. Codex also added `scripts/resample_binance_1h_canonical.py` and seeded
20,400 Binance-sourced BTC-USDT-SWAP 1H canonical rows from existing Binance 1m
canonical rows. The pre-repair MA source-provenance validation with DB parity
enabled failed at
`results/validation_lab_ma_crossover_btc_binance_1h_20260622_maxord250_pospct1_strategyfill/validation/codex_binance_1h_db_parity_20260623/validation_result.json`:
`canonical_source_primary == "binance"`, `artifact_rows=20400`,
`db_rows=20376`, `missing_in_db=24`, `value_mismatches=0`, and
`ohlcv_source_validation == "artifact_warn"`.
Later on 2026-06-23, Codex ran
`scripts/download_binance_data.py --inst BTC-USDT-SWAP --bar 1H --start 2024-04-29 --end 2024-04-30`
against the repo DSN and default `data/ticks` path. The 2024-04-29 Binance 1H
gap is now filled in both local parquet and `canonical_candles`: 24 Binance 1H
rows, local-vs-DB close mismatch count 0. Existing validation-lab artifacts were
generated before this repair; rerunning source provenance on the old MA artifact
now has `db_rows=20400`, `missing_in_db=0`, but `value_mismatches=24`.
Regeneration alone was not enough: Codex 2026-06-23 fixed the structural
source-selection bug so venue-tagged replay loads pass `exchange` into canonical
Postgres candle reads, refuse source-less parquet fallback, and raise explicit
venue gaps. New regenerated MA/EMA/MACD `strategy_fill` runs use suffix
`_venue_scoped_pg_20260623`; their 2024-04-29 00:00 `price_series.close` is the
Binance value `63229.2`. The new MA source-provenance validation passed at
`results/validation_lab_ma_crossover_btc_binance_1h_20260622_venue_scoped_pg_20260623/validation/codex_venue_scoped_pg_db_parity_20260623_pass/validation_result.json`:
`db_parity.status == "PASS"`, `canonical_source_primary == "binance"`,
`artifact_rows=20400`, `db_rows=20400`, `missing_in_db=0`,
`value_mismatches=0`, and `ohlcv_source_validation == "db_parity_pass"`.

## Workstream Sequencing (2026-06-17) — read before parallel sessions

Three workstreams may run across sessions. Ownership of the **ct_val provenance
gate** (`backtesting/differential_validation.py`) is the contended surface.

1. **Multi-venue instrument specs (ADR-0007, P1)** — branch
   `codex/impl-multi-venue-instrument-specs` (plan:
   `docs/superpowers/plans/2026-06-17-multi-venue-instrument-specs-p1.md`,
   design: `claude/design-multi-venue`). **Owns the ct_val provenance gate
   change until merge.** Venue tag + venue-aware resolution are in place.
2. **Backtest-system validation** (source-provenance / differential / signal
   validation). P1 no longer blocks the first DB-backed PASS on the primary
   (Binance) venue. The DB parity input contract is now close-only for replay
   `price_series.csv`; durable evidence passed with
   `checks.db_parity.canonical_source_primary == "binance"`. Non-gate chores
   (branch protection, signal-validation CI, OKX/fixture work) are unblocked.
3. **Universal price chart + progressive load** — implemented on
   `codex/fix-price-chart-universal` (`76dcecc`) and merged into the P1
   integration branch. Independent of 1 and 2; **must not touch**
   `differential_validation.py`.

Rule: only the multi-venue branch edits the ct_val provenance gate until P1
merges. Other sessions coordinate around it, not into it.

## Current Branch

Must be checked with `git branch --show-current` at session start. Observed in
this session: `codex/impl-multi-venue-instrument-specs` after integrating
`claude/design-multi-venue` and `codex/fix-price-chart-universal`.

## Last Known Good Commit

ADR-0007 P1 local state on `codex/impl-multi-venue-instrument-specs`: Tasks 1-6
verified locally; normal Binance/Bybit USDT-M `ct_val` can pass structurally as
`exchange_base_unit`; DB parity now filters canonical candles by run exchange
via `source_primary` and exposes the chosen canonical source in validation
output. Latest code compares artifact close to DB canonical close for
`price_series.csv` DB parity; the saved Binance run's 192 artifact close values
match DB canonical Binance close values exactly under the existing tolerance.
Durable source-provenance output under `results/` passed the source-data gate
with `db_parity.status == "PASS"`,
`canonical_source_primary == "binance"`, and
`ohlcv_source_validation == "db_parity_pass"`.

## System Overview

| Layer | Key files |
|---|---|
| Strategies | `src/okx_quant/strategies/` — active UI/API validation scope: funding_carry, pairs_trading, daily_winner, ohlcv_rotation, ma_crossover, ema_crossover, macd_crossover, fear_greed_sentiment, cme_gap_fill |
| Signals | `src/okx_quant/signals/` |
| Portfolio | `src/okx_quant/portfolio/` — sizing, position ledger |
| Execution | `src/okx_quant/execution/` — broker, replay_execution |
| Risk | `src/okx_quant/risk/` — risk guard, drawdown, circuit breaker |
| Backtesting | `backtesting/` — replay engine, CPCV, walk-forward, artifacts |
| API | `src/okx_quant/api/` — FastAPI server, backtest routes |
| Frontend | `frontend/` — dashboard, backtest viewer, charts |
| Data | TimescaleDB — OHLCV, funding rates, canonical candles |
| Config | `config/settings.yaml`, `config/strategies.yaml`, `config/risk.yaml` |

## Current Change Context

| Commit / PR | Change | Risk |
|---|---|---|
| Backtest execution profiles `(implemented; Codex 2026-06-22)` | `strategy_fill` is the named research-only wrapper around existing fill-all controls, and `dual_output` runs paired `strategy_fill` plus internal `realistic_execution` artifacts with a small comparison JSON. Submitted strategy-order fill metrics now exclude terminal liquidation fills. BTC-USDT-SWAP Binance 1H checks with `max_order_notional_usd=250` and `max_pos_pct_equity=1` passed under Strategy Fill: MA 228/228/228, EMA 252/252/252, MACD 1558/1558/1558 for signal/submitted-order/real-fill counts. Full-period MACD Dual Output wrote `results/validation_lab_macd_btc_binance_1h_20260622_dual_fullperiod_execution_comparison.json`: strategy-fill 1558 submitted fills vs realistic 3 submitted fills plus 1 terminal liquidation fill. Run Detail now shows the execution profile and exposes `GET /api/backtest/{run_id}/execution-comparison` for dual-output comparison JSON. | Research/backtest/API/UI/docs scope only. No strategy logic, live/shadow/demo gates, deployment gates, DB schema, config files, existing result artifacts, or differential-validation tolerances changed. `strategy_fill` and `dual_output` remain idealized/diagnostic and are not promotion or live-readiness evidence. |
| Public WS reconnect-churn fix `(implemented; Claude 2026-06-22)` | `src/okx_quant/data/market_data_handler.py`: a `books` seq-gap/checksum desync no longer re-raises and tears down the whole public connection (which also dropped trades/funding and caused reconnect churn until a clean snapshot landed). `_handle_book_update` now catches the `RuntimeError` and `_resubscribe_book` re-syncs only that instId's `books` channel (discard stale book, `unsubscribe`+`subscribe`) without dropping the socket. Two secondary fixes: demo WS URL keeps `:8443` (`wspap.okx.com:8443`, was stripped to 443) for public+private; `heartbeat_task = None` guard in both `run_public`/`run_private` `finally` blocks prevents an `UnboundLocalError` masking the real error when a subscribe fails before the heartbeat starts. Follow-up (same session): the resubscribe exposed a tight desync/resubscribe loop — a freshly-reset book applied incremental `update`s before its snapshot arrived, failing checksum on an incomplete book every ~100ms. `okx_book.py::handle` now skips updates while `seq is None` (no snapshot baseline yet); the desync log now includes the reason string (seq gap vs checksum). **Confirmed root cause (`scripts/diag_book_checksum.py`):** OKX demo/paper (`wspap`) sends `checksum: 0` on every books snapshot ("not computed"), while live sends a real signed crc32 (diagnostic showed live `server == ours`, demo `server == 0`). The code treated `0` as a real checksum, so the demo book desynced on every snapshot → the whole churn/loop. Final fix: `okx_book.py::handle` skips checksum validation when the field is `0`/absent. The seq-gap/resubscribe/skip-pre-snapshot logic above stays correct for live. New `tests/unit/test_market_data_handler.py` + `test_orderbook.py::{test_update_before_snapshot_is_skipped,test_demo_zero_checksum_is_not_a_mismatch}` cover it; demo run no longer loops. | Live data-path/infra only; backtest does not use WS. `make docs-impact` passes with no violations — `src/okx_quant/data/` is not a business-rule/manifest area, so no Change Manifest required. No strategy/risk/portfolio/execution/PnL/fees/funding/sizing/fills/gates/DB-schema/config/result-artifact changes. `okx_book.py` change is additive (skip pre-snapshot updates); existing `raise`-on-desync for a synced book is unchanged and still unit-tested. An occasional single resubscribe is normal transient-gap recovery; a continuous loop is not — if it persists after this fix the log now shows `checksum mismatch` vs `seq gap` to localize the next step. Reconnect backoff intentionally not added — the `websockets` iterator already backs off on connect failures; revisit only if logs show flapping after this. Not verified against a live OKX socket in this sandbox. |
| Validation Lab DB-only run bridge + run detail review aids `(implemented; Codex 2026-06-22)` | Validation Lab now merges saved Backtest Runs with strategy fixture candidates. Saved runs, including DB-only artifact runs, trigger run-scoped differential validation instead of the strategy fixture endpoint. `routes_backtest.py` materializes DB `backtest_artifacts` payloads into a temporary validation input bundle only for the job, writes validation output under `results/<run_id>/validation/<validation_id>/`, and does not backfill `result.json` into the run directory. Run detail header layout is split so long display names wrap without being covered by chips; Risk events now show top reason/symbol/strategy counts above the table. | API/frontend/test/docs scope only. No strategy logic, risk/portfolio/execution behavior, DB schema, config, existing result artifacts, reference-adapter tolerances, validation gates, or deployment gates changed. DB-only validation still needs the required artifact payloads (`result`, `price_series`, and strategy-required artifacts) and optional reference-engine dependencies; `fill_all_signals` remains research-only evidence. |
| Fill-all signal replay + chart Y zoom + sparse-trading diagnosis `(implemented; Codex 2026-06-22)` | `fill_all_signals` now also lifts max daily loss, soft drawdown, and hard drawdown thresholds in both copied research configs and replay-engine effective limits, then records those effective limits in `result.validation.fill_all_signals_controls`. This fixes the research-only path where later generated signals were still suppressed after a drawdown kill. Local DB diagnosis of `ui_ma_crossover_c9acab8e` (`2026/06/22_ma_crossover_btc_usdt_swap_1000shib_usdt_swap`) found 809 signal rows through 2026-06-11, 90 orders/fills only through 2024-03-11, and a 2024-03-11 `allowed_reduce_only_bypass:drawdown threshold breached` event; the later quiet period is therefore risk-stop/sizing suppression, not missing indicator signals. Price and indicator panels now expose inline vertical Y scale controls, and the Risk tab loads `signals` so it can show signal/fill gaps, top reasons, affected symbols, and research-only fill-all warnings. | Research/backtest/UI/test/docs scope only. No strategy signal logic, live/shadow/demo gates, deployment gates, DB schema, config files, existing result artifacts, differential-validation tolerances, PnL/fee/funding math, or live risk defaults changed. `fill_all_signals` remains idealized research-only evidence and is inadmissible for promotion/live readiness. For realistic runs with late-entry suppression, first lower sizing/risk pressure (`max_order_notional_usd`, `max_pos_pct_equity`, leverage) rather than citing fill-all output. |
| Fast backtest artifact rows `(implemented; DB verification pending; Codex 2026-06-22)` | Option C is implemented as a derived `backtest_artifact_rows` read index. New migration `0012_backtest_artifact_rows.sql`, `backtesting/artifact_rows.py`, row-first API reads, `/api/backtest/{run_id}/summary`, summary-first frontend loading, `scripts/backfill_backtest_artifact_rows.py`, and `scripts/benchmark_artifact_reads.py` are in scope. Existing `result.json`, `backtest_artifacts.payload`, files, strategy logic, PnL, fees, funding, sizing, fills, risk, validation semantics, and deployment gates remain unchanged. A follow-up fix changed row-index dual-write from per-row `executemany` to PostgreSQL bulk COPY after the UI showed new runs lingering at `Stage: Saving replay artifacts` / 85%. | DB migration + read-path/storage-index change only. Old runs require migration plus backfill `--verify` before first-click artifact reads are fast. If row records are missing, API falls back to the current JSONB/file readers. Run-scoped differential validation CSV artifacts can be row-indexed; strategy-validation artifacts remain file-backed because they are not keyed by `backtest_runs.run_id`. Local `DATABASE_URL` was unset, so real DB migration/backfill and API benchmark evidence remain the next task. |
| Backtest chart stuck-loading + width fix `(complete; Codex 2026-06-22)` | `frontend/view-backtest.js` now guards in-flight per-symbol market/indicator fetch results by `runId` instead of cancelling them on every selected-symbol change. This fixes the case where selecting BTC, then adding ADA before BTC returns, left BTC stuck at `loading` forever because the result was discarded and the `loading` status blocked retry. Equity and drawdown charts now use the same fluid chart wrapper width as the price panels. `frontend/data.js` now uses the existing long timeout for `/api/backtest/runs`; local HTTP checks showed the running server can take 3-5s to answer this DB-backed list even though the route's DB/filesystem work is fast, so the old 10s timeout was brittle when the server is busy with WS reconnects or cold requests. Investigation also confirmed `ui_ema_crossover_a986588f` is recorded in local Postgres `backtest_runs` and `backtest_artifacts`; there is no local `results/ui_ema_crossover_a986588f/result.json` because the configured DSN makes artifact mode default to DB. | UI-only plus tests. No strategy logic, risk/portfolio/execution behavior, DB schema, config, result artifacts, deployment gates, or differential-validation files changed. `make frontend-check` could not be run because `make` is unavailable in this Windows sandbox; the equivalent `node --check` commands were run manually. |
| Market Data Coverage queue + delete pair + Binance spec sync `(in progress; Codex 2026-06-22)` | `src/okx_quant/api/routes_data.py` now seeds fetch jobs as `queued`, serializes execution behind one process-local `asyncio.Lock`, exposes `DELETE /api/data/pairs/{inst_id}` to transactionally remove a pair from market/legacy candle and funding tables plus the local parquet mirror, and syncs Binance `exchangeInfo` filters into `venue_instrument_specs` before candle writes. This closes the replay setup gap where downloaded Binance multiplier pairs such as `1000SHIB-USDT-SWAP` still lacked a DB `ct_val` row. `frontend/view-config.js` renders `/fetch/jobs` as a job list, allows stacking fetch submissions, supports per-job cancel, and adds a native-confirm Delete button for OHLCV/funding coverage rows. | Data/API/frontend scope only. No strategy logic, risk/portfolio/execution behavior, DB schema, config, result artifacts, deployment gates, or differential-validation files changed. Delete is irreversible and guarded by UI confirm plus a backend 409 when a non-terminal fetch references the pair. Existing Binance data that was downloaded before this fix may still need a fresh fetch or manual seed to populate `venue_instrument_specs`. Manual DB-backed browser smoke is still pending in this sandbox. |
| Universal price chart + progressive load `(complete; Codex 2026-06-17)` | `frontend/view-backtest.js` now renders one Price + Trade Markers panel per selected symbol, so loaded symbols draw while other symbols are still loading/empty/failed. The base price chart stays strategy-agnostic; MA/EMA/MACD indicator overlay cards remain gated by `isTechnicalRun`. Backend price-series fallback was checked and already reconstructs missing `price_series.csv` rows from `result.json` visual symbols and the candle loader. | UI-only chart behavior. No strategy logic, risk/portfolio/execution behavior, DB schema, result artifacts, deployment gates, or differential-validation gate files changed. Browser-level interaction coverage remains a known gap in `docs/KNOWN_ISSUES.md`. |
| Source provenance validation slice `(in progress; Codex 2026-06-17)` | `scripts/run_source_provenance_validation.py` and `make source-provenance-validation` gate existing or freshly generated `validation_result.json` evidence. The gate requires `source_data_validation.status == PASS`, `ct_val_provenance.status == PASS`, `db_parity.status == PASS`, and `ohlcv_source_validation == db_parity_pass`; DB parity `SKIP` fails by design. | This is DB-backed evidence gating only. It does not alter strategy logic, reference-adapter tolerances, PnL/fill semantics, risk, portfolio, execution, DB schema, deployment gates, existing result artifacts, or Nautilus full execution parity. It still needs a reachable TimescaleDB/Postgres DSN and canonical candles to produce passing real-data evidence. |
| Strategy signal-validation CI gate `(complete; Codex 2026-06-17)` | `.github/workflows/ci.yml` adds a `strategy-signal-validation` job that installs `.[dev,validation]` and runs `make strategy-signal-validation`. `Makefile` now accepts `VALIDATION_RESULTS_DIR`, so CI writes generated validation artifacts to runner temp storage instead of repo `results/`. User agreed this job should be configured as a required branch protection check once pushed. | This is CI/harness wiring only. It does not alter strategy logic, reference-adapter tolerances, PnL/fill semantics, risk, portfolio, execution, DB schema, deployment gates, or existing result artifacts. The job remains fixture signal-point evidence, not real-data parity, execution parity, or live-readiness evidence. |
| Strategy signal-validation harness interface `(complete; Codex 2026-06-16)` | `scripts/run_all_strategy_signal_validation.py` accepts an explicit `--engines` list, sets `NUMBA_DISABLE_JIT=1` by default for vectorbt fixture validation, and can be called through `make strategy-signal-validation` with `VALIDATION_STRATEGIES` / `VALIDATION_ENGINES`. Batch `codex_20260616_signal_validation` produced PASS rows for all active strategies under `results/strategy_validation/`. | This is a harness/interface change only. It does not alter strategy logic, reference-adapter tolerances, PnL/fill semantics, risk, portfolio, execution, or DB schema. New validation artifacts are fixture evidence only: signal-point portability, source-data shape/provenance, portable gate, and Nautilus advisory order/fill replay passed; live execution, PnL parity, fees/slippage, funding settlement, WalkForward/CPCV, and DB-backed real-market evidence remain out of scope. |
| AI Context and Harness `(in progress; docs/harness only)` | Adds `AI_CONTEXT.md`, feature/UI/data/runbook maps, durable AI changelog/known-issues docs, docs-check scripts, smoke placeholders, Makefile harness targets, and Codex prompt templates. | This is governance/harness work only. It must not modify strategy logic, risk/portfolio/execution behavior, DB schema, existing result artifacts, or differential-validation implementation. |
| Differential validation reviewer admissibility `(docs synced by user request; pending Claude review)` | `research/strategy_synthesis.md` Promotion Checklist now states that portable validation applies to all active/declared strategies per `backtesting/differential_validation.py::REFERENCE_VALIDATION_CONTRACTS`, not only `ma_crossover` / `ema_crossover` / `macd_crossover`. Reviewers must inspect `portable_validation_gate`, `signal_point_correctness`, `source_data_validation`, and advisory mismatch counts. Strategies with only advisory replay/export remain blocked for promotion evidence until a proper independent adapter exists or the gate text is explicitly changed by the user. | Codex edited the Claude-owned research checklist only because the user explicitly requested it on 2026-06-12. Claude should review wording, but the stale "non-technical = not_applicable" path is no longer present. |
| Differential validation gate `(implemented in Codex working tree; tested 2026-06-12)` | `docs/ai_collaboration.md` Deployment Gate now treats Differential validation as a repo-wide requirement: every active/declared strategy must declare at least one portable reference path in `REFERENCE_VALIDATION_CONTRACTS`, and promotion evidence must include a fresh `results/<run_id>/validation/<validation_id>/validation_result.json` with `portable_validation_gate.passed == true`. For implemented independent vectorbt/backtrader paths, strict scope is `signal_logic` only (`engines.<engine>.comparison.signal_logic.status == "PASS"` and `actionable_mismatch_count == 0`); PnL / equity / metric mismatches remain advisory but reviewer-admissible. Nautilus v1 remains advisory export/replay unless and until a full reference engine mapping is implemented. **No override**, **retroactive** — existing active-strategy artifacts without current validation fields, without `source_data_validation`, or without `portable_validation_gate.passed == true` fail by default. | 2026-06-12 MACD sanity run `results/strategy_validation/macd_crossover/ui_sweep_macd_rank001_all_engines_validation/validation_result.json` emitted `source_data_validation`, `validation_conclusion`, `portable_validation_gate`, and `signal_point_correctness`. Vectorbt/backtrader/Nautilus signal-point correctness PASS with zero signal mismatches, but the artifact is still **not promotion evidence** because `source_data_validation.status == "FAIL"` from non-authoritative `ct_val` registry provenance. |
| Signal-point correctness scope `(user decision 2026-06-12; docs-only current)` | First-stage external validation target is now explicitly `vectorbt` + `backtrader` + `nautilus` point correctness, not PnL parity. The hard comparison scope should be timestamp/bar, symbol, side, and action/entry-exit under identical data, params, and strategy rules. If all three external systems agree with the project artifact on those points, the project may claim cross-engine confidence in signal generation / timing / side / state transitions. | This does **not** validate order execution, partial/missed fills, queue behavior, fee/slippage/spread, funding settlement, `ct_val` PnL accounting, equity curve, Sharpe, drawdown, or live readiness. Nautilus v1 may support signal-point replay/export evidence, but remains advisory for full matching-engine parity until a true Nautilus engine adapter exists. |
| Order-book market-maker removal `(user decision 2026-06-12; Codex patch tested)` | `as_market_maker`, `obi_market_maker`, and related MM variants are fully removed from active strategy/config/replay/API/UI/portable-validation scope because the project will not maintain order-book data. `src/okx_quant/strategies/as_market_maker.py`, `src/okx_quant/strategies/obi_market_maker.py`, and ASMM-specific replay-validation helpers/CLI are deleted; ASMM parameter scanning / standalone L2 skeleton entrypoints are retired. Remaining active strategies must still satisfy portable validation. | Targeted Python compile, frontend syntax checks, and affected unit/integration tests passed on 2026-06-12. Archive/research docs may retain historical rationale, but reviewers must not treat order-book MM as a pending validation or data-ingest task. |
| `fill_all_signals` admissibility `(complete; commit 7c23791)` | `docs/ai_collaboration.md` Deployment Gate adds an "Idealized fill 排除" row; `research/strategy_synthesis.md` validation-status convention gains an "Idealized-fill exclusion" subsection plus a Promotion Checklist note; `docs/AI_HANDOFF.md` Known Issue 18a codifies the rule. `fill_all_signals` artefacts (including the `ohlcv_rotation` strategy-layer flag) are research-only capacity / execution sensitivity tools and are inadmissible as edge / promotion / live-readiness evidence regardless of `validation_status`. Codex commit `7c23791` wires `idealized_fill: true` through `backtesting/artifacts.py`, `backtesting/cpcv.py`, `backtesting/walk_forward.py`, and surfaces a warning in `routes_backtest.py`. | Enforcement can now check `result.validation.fill_all_signals == true` or `result.validation.idealized_fill == true` programmatically. API responses include `warnings: ["idealized_fill"]` plus a Deployment Gate warning string. No strategy / risk / portfolio / execution code touched in the Codex follow-up. |
| Daily winner normalization + calendar ticks `(complete; Claude conditionally approved; pending human review/commit)` | Daily Winner result payloads now expose `round_trips` plus synthetic BUY/SELL execution rows at read time, so legacy runs such as `ui_daily_winner_e9614719` show buy and sell legs, inferred qty/notional, exit-side PnL, and no auto-generated WF/CPCV when validation is none. Backtest charts use calendar-aware month ticks for multi-month/multi-year ranges. UI labels Daily Winner aggregate cost as `Total Costs` with `(fee+slip)` because the source is combined `cost_rate`, not pure exchange fees. | Validation-only strategy remains non-deployable and not admissible as edge evidence. Synthetic costs are display/accounting aids only; `daily_winner` trades still are not ADR-0002 fills and funding remains not modeled. |
| Validation status convention + results manifest `(docs-only; current)` | Defines five repo-wide `validation_status` labels (`naive_backtest`, `in_sample`, `hold_out`, `walk_forward`, `cpcv`) in `research/strategy_synthesis.md`, links them from the collaboration and backtest-live parity gates, and classifies all 101 current `results/**/*.json` files in `docs/results_validation_manifest.md` without modifying frozen result artifacts. | Conservative default: artifacts without explicit frozen hold-out, WalkForward, CPCV, or documented pre-dataset parameter-freeze proof are `in_sample`; `naive_backtest` and `in_sample` are research records, not OOS evidence or promotion evidence. |
| CME yfinance research proxy + structural fixes + long_only default `(complete; commit 655af31)` | `cme_btc_yfinance` dataset wired via yfinance optional adapter (598 daily rows, 2024-01-01 → 2026-05-19). Stop-loss (`stop_loss_bps_mult=1.5`), dust-bucket exclusion (`min_gap_bps=25`), and shortened hold (`max_hold_days=2`) implemented in `CMEGapFillStrategy` + `analyze_cme_gaps.py`. **Three in-sample runs**: (1) baseline `cme_gap_research.json` = -33.3% / Sharpe -0.52 / MDD -49.2% (109 trades, no stop); (2) post-fix `both` `cme_gap_research_with_stop.json` = -28.1% / Sharpe -0.82 / MDD -37.0% (99 trades, 1.5× stop); (3) post-fix `long_only` default `cme_gap_research_long_only_default.json` = **+7.09%** / Sharpe +0.35 / MDD -14.7% (46 trades, 26 target-fills / 13 stop-losses / 7 timeouts, win 63%, PF 1.24, worst -980 bps). **Route B applied in commit 655af31**: `allow_direction` default flipped to `long_only` in `core/config.py`, `config/strategies.yaml`, `external_features.py`, and `analyze_cme_gaps.py` (functions + CLI). Regression tests `test_cme_gap_fill_default_skips_up_gaps_and_trades_down_gaps` and `test_simulate_reverse_gap_trades_default_excludes_short_side` lock the default. `research/strategy_synthesis.md` Strategy 10 updated. | Research-only proxy; not admissible as deployment evidence. `long_only` default is **regime-fitted to BTC 2024-26**; bear-regime walk-forward remains required before any promotion claim, and failure on that segment must revert the default to "do not deploy". Even on long-only, edge is ~15 bps avg per trade (only ~3 bps above 12 bps round-trip cost) with single -980 bps worst trade — not validated alpha. Deployment still requires an official CME source, bear-regime walk-forward / CPCV pass, and DSR ≥ 0.95. |
| External-feature research baselines doc `(complete; docs-only)` | `research/strategy_synthesis.md` adds Strategy 9 (Crypto F&G long-flat sentiment baseline — `Fear`/`Neutral` are intentional hold states, only `Greed`/`Extreme Greed` trigger exit), Strategy 10 (CME daily weekend-gap research baseline — daily cadence with `publish_lag_days=1`, explicitly not a real-time gap-fill strategy), and a Research Feature Data Caveats section covering DGS10 latest-vintage / non-PIT semantics, F&G label-stability dependency, and the discontinued `CHRIS/CME_BTC1` source. Promotion Checklist extended with ct_val provenance, ADR-0006 reduce-only audit, and an External-Feature Coverage Gate (event_count > 0 for required datasets, stale-rate ≤ 10%, missing-rate ≤ 5%, plus per-dataset vintage / source-stability / label-stability attestations). | Documentation-only; no strategy or risk code touched. Codified caveats only; strategies remain `enabled: false` with `research_only: true` signal metadata. |
| MA/MACD long-flat position fix `(committed 8a4f5f9; follow-up pending commit)` | Technical indicator strategies remain long/flat baselines for research acceptance and parameter tuning. Patch fixes partial-exit state handling, replacement cancellation, long/flat-only ledger close sizing, lot-rounded replay partial fills, and incremental EMA/MACD state matching `ewm(adjust=False)`. Reduce-only risk semantics are scoped to long/flat close orders; fat-finger still blocks reduce-only orders, while allowed reduce-only bypasses for kill/position-limit/daily-stop are logged from `RiskGuard.check()` and written to replay `risk_events` with `allowed_reduce_only_bypass:*`. | Not live-ready. MA/MACD profitability is not established; ct_val gate still blocks promotion when provenance is non-authoritative. Pairs/funding-carry close sizing is intentionally unchanged until P2 design implementation is separately approved. |
| Chart UX overhaul fix-up `(complete; Claude reviewed 2026-05-22)` | Backtest viewer market charts now share one `market` X range across price and indicator panels; reset controls split X vs Y semantics; per-panel Y zoom uses shared `MAX_Y_ZOOM`; drawdown Y zoom anchors at the minimum; MACD sub-panel Y zoom is independent; indicator cards show `warmup_source`; metrics glossary is available from the left nav; artifact indicators default to cold-start strategy-aligned values with `indicator_db_warmup` opt-in and `result.validation.indicator_warmup_sources`. | Claude review accepted the chart/normalization direction with documentation and Daily Winner cost-label follow-up. DB warmup is an opt-in visual aid and can intentionally diverge from cold-start strategy marker timing if enabled. RangeBrush click-outside behavior, binary-search range slicing, and wheel/keyboard zoom remain backlog. |
| Chart zoom + indicator visualization + DB-primary backtest `(complete; pending Codex verification)` | Frontend brush-zoom (now timestamp-domain) across all charts with shared `chartRange` + reset toolbar; per-symbol `IndicatorChart` (price + fast/slow + MACD sub-panel) wired to a new `/api/backtest/{run_id}/indicators` route reading `indicator_series.csv` recomputed at artifact time from `price_series`; download scripts now mirror parquet writes into `raw_candles` + `canonical_candles` via `scripts/_db_writer.py`; canonical writes share `okx_quant.data.canonical_policy` priority `manual > binance > okx > bybit > coinbase/kraken > other`, used by `_db_writer.py`, `CandleStore.canonicalize_from_raw()`, `CandleStore.canonicalize_from_market_klines()`, and `CandleStore.upsert_canonical_candles()`; `routes_backtest._resolve_candle_backend()` + `StorageConfig.candle_backend` default to `postgres` with TCP-probe-based parquet fallback when DSN missing or unreachable; `_to_naive_utc_index` normalises Binance tz-aware vs OKX tz-naive parquet on read; new `config/instrument_specs.yaml` registry + `_resolve_swap_ct_val` writes per-symbol provenance (`db` / `registry` / `hardcoded_btc_eth` / `config_override` / `spot_unit`) into `result.validation.ct_val_sources` with a `ct_val_all_authoritative` boolean for the live/shadow/demo deployment gate | Postgres-by-default may surprise environments without `DATABASE_URL`; fallback is logged but silent in the API. `indicator_series.csv` is additive (does not break ADR-0002 schema). No `src/okx_quant/strategies/` changes. ct_val gate forbids promotion to live unless every symbol's ct_val came from `db`/`config_override`/`spot_unit`; `registry` / `hardcoded_btc_eth` are backtest-only and require explicit reviewer override to ship. |
| P0 web security hardening `(committed fca239f)` | Add API key protection for FastAPI routes/WebSocket, close Swagger UI, add CORS allowlist, and tighten Docker env/port bindings | API clients must send `X-Api-Key` when `API_KEY` is set; standalone `scripts/run_server.py` remains out of scope |
| OHLCV/backtest UI fix `(committed ed283d7, 6d1fd41)` | Fix OHLCV exit code 1, equity scale, drawdown, chart width, background jobs, progress, warm-up transparency, and volume-threshold diagnostics | Frontend + backtest script + routes only; no risk/portfolio code touched |
| P2 position-aware close sizing design `(complete; pending review)` | Design pairs trading exit/stop close sizing from ledger positions | PM owns close sizing; implementation must guard to `pairs_trading`, preserve funding carry dual-leg exit behavior, and handle integer-lot float drift |
| P2 shadow calibration test `(complete; pending review)` | Add mirror fill positive routing unit coverage | `ExecutionHandler.on_fill_ws()` now has mock coverage for filled and partially_filled shadow mirror fills routing to `CalibrationLogger.record_fill()` |
| Daily winner frontend `(complete; pending commit)` | Wire daily_winner into frontend strategy dropdown + Run Backtest UI | `frontend/data.js` adds strategy entry with tag=Validation; `frontend/view-config.js` adds universe checkbox, bar locked to 1D, StrategyParams; `routes_backtest.py` adds daily_winner to allowed set, `_run_daily_winner_job` embeds equity/returns/trades in result.json (no CSV artifacts) |
| OHLCV rotation frontend `(complete; uncommitted)` | Wire ohlcv_rotation into frontend strategy dropdown + Run Backtest UI | `frontend/data.js` adds strategy entry; `frontend/view-config.js` adds universe checkbox, benchmark, rebalance_min, top_k controls; `routes_backtest.py` adds ohlcv_rotation to allowed set, new job + post-process functions, and extra request fields |
| OHLCV rotation `(merged)` | Add Phase 1 OHLCV rotation research/backtest workflow | Vectorised strategy/backtest, CLI, synthetic tests, and XLSX export support added separately from PR14B |
| PR14B `(merged)` | Implement shadow mode parity fixes | `run_shadow.py` now requires `mode=shadow`; shadow primary SimBroker receives instrument specs; broker routing tests added |
| PR14A `(merged)` | Design shadow mode parity plan | `docs/shadow_mode_parity_plan.md` documents current ShadowBroker path, remaining gaps, and PR14B scope |
| PR13 `(merged)` | Implement remaining ADR-0005 replay validation gates | Gate 2 fill-rate warning, Gate 3 data coverage, Gate 4 funding coverage implemented; ADR-0005 moved to Accepted |
| PR12B | Implement replay terminal liquidation | Gate 1 terminal position check implemented via `validation["terminal_positions_closed"]`; replay default closes terminal positions; CLI can opt out; focused regression tests added |
| PR12A | Add replay terminal liquidation design plan | Docs-only design; no replay behavior change |
| PR11 | Add funding carry dual-leg regression tests for signal metadata and PM order alignment | Test-only coverage for long spot + short perp carry behavior |
| PR10B | Add pairs exit/stop hedge close metadata and remove hedge metadata xfail | Strategy metadata only; sizing remains unchanged |
| PR10 | Add pairs trading hedge-close regression coverage | Test-only coverage for linked hedge close behavior |
| PR9 | Add backtest artifact schema regression tests for ADR-0002 frozen fields | Test-only coverage for artifact contract |
| PR8 | Add frontend MIME smoke tests for `.js` and legacy `.jsx` ES modules | Test-only coverage for FastAPI StaticFiles MIME behavior |
| PR7 | Add branch/version management policy and PR template checklist | Governance docs only |

## Latest Codex Verification Commands

Chart UX review fix-up + indicator warmup alignment, run on 2026-05-17:

- `node --check frontend/charts.js` - passed
- `node --check frontend/view-backtest.js` - passed
- `node --check frontend/view-glossary.js` - passed
- `node --check frontend/app.js` - passed
- `& 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' -m pytest tests/unit/test_frontend_static_mime.py -v` - 2 passed
- `& 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' -m pytest tests/unit/test_backtesting.py::test_indicator_series_uses_warmup_candles_before_trimming tests/unit/test_backtesting.py::test_indicator_series_trims_leading_rows_when_warmup_missing tests/unit/test_backtesting.py::test_indicator_series_ema_macd_default_cold_start_does_not_fetch_db tests/unit/test_backtesting.py::test_save_artifacts_records_indicator_warmup_sources -v` - 4 passed
- `& 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' -m pytest tests/unit/test_technical_indicator_strategies.py -v` - 5 passed
- `git -c safe.directory=C:/quant_strategy diff --check` - passed

Note: focused indicator artifact tests used explicit pytest node ids because pytest does not expand `::test_indicator_series_*` as a node-id glob. Pytest emitted a non-fatal cache permission warning for `.pytest_cache`.

## Known Bugs / Open Issues

1. **Shadow mode parity gap** (resolved in PR14B): `run_shadow.py` requires `mode=shadow`, and shadow primary `SimBroker` receives instrument specs for notional/fee accounting.
2. **SimBroker fill event gap** (P0): `ExecutionHandler.on_order()` expects WebSocket fill, but `SimBroker.submit()` does not emit a simulated fill event — blocks unified backtest/live engine path.
3. **Replay bar-level approximation** (P1): `scripts/run_backtest.py` uses per-bar approximation formulas, not the true `Strategy → Signal → Order → Fill → Ledger` path.
4. **CI gate is still intentionally lightweight**: `.github/workflows/ci.yml` runs ruff fatal-only baseline, unit tests, docs checks, docs-impact, and the fixture `strategy-signal-validation` batch. Integration tests still require TimescaleDB planning, and fixture signal validation is not real-data parity or execution parity.
5. **Missing regression tests**:
   - Frontend MIME smoke test exists.
   - Backtest artifact schema regression test exists.
   - Pairs trading hedge-close regression exists; exit/stop hedge metadata implemented.
   - Funding carry dual-leg regression exists.
   - Replay terminal liquidation regression tests exist.
   - Shadow mirror fill positive routing to `CalibrationLogger.record_fill()` is covered by a focused mock unit test for filled and partially_filled mirror updates.
6. **Pairs close sizing gap** (P2): Exit/stop order size is still driven by signal sizing rather than current ledger position. Position-aware close sizing design is documented in `docs/pairs_position_aware_close_sizing_plan.md`; implementation remains next. Funding carry also uses `metadata["action"] == "exit"`, so the implementation must make the close-sizing branch pairs-only unless a separate funding-carry design explicitly expands scope. The MA/MACD long-flat fix deliberately guards its close-sizing branch with `mode == "long_flat"` and does not implement this P2 pairs/funding-carry work.
7. **Order-book MM deleted from active code** (resolved 2026-06-12): Older notes/tests referenced `--strategy as_market_maker` in replay CLI paths. User decision on 2026-06-12 removes MM/order-book strategies from active validation and promotion scope; code/config/tests/scripts now use remaining active strategies instead.
8. **ADR-0005 replay validation gates**: Gates 1-4 are implemented and ADR-0005 is Accepted. Gate 1 terminal position check is implemented via `validation["terminal_positions_closed"]`; PR13 added Gate 2 fill-rate warning, Gate 3 data coverage, and Gate 4 funding coverage.
9. **OHLCV rotation 1m data missing** (data gap, not a code bug): `data/ticks/` only has `candles_1H.parquet` for BTC and ETH; no `candles_1m.parquet` and no SOL data. Running OHLCV rotation at 1m bar will fail at parquet level. Since 2026-05 download scripts also write `canonical_candles` and `routes_backtest` defaults to postgres backend, the DB Coverage panel (`canonical_candles`) is the authoritative source of "what bar/inst is queryable". For parquet-only environments, run `scripts/download_okx_data.py --inst BTC-USDT-SWAP --bar 1m` to populate files.
10. **No-trading for long periods** (multi-cause): For pairs trading, warm-up is 168h (7 days). For OHLCV rotation, regime filter suppresses trading when benchmark is below 240-min EMA. Both are expected behavior. `warmup_bars` and `data_coverage_pct` are now in the OHLCV rotation metrics. UI shows warm-up warning when date range < 3× warm-up time.
11. **Web API public exposure gap** (P0, patch committed): `src/okx_quant/api/server.py` now supports `API_KEY` auth for API routes and WebSocket handshakes, closes `/api/docs`, and applies optional `ALLOWED_ORIGINS`. Full deployment smoke test confirmation is still pending.
12. **Live WS partial-fill remaining-size metadata gap** (P1): Replay fills include `metadata["remaining_sz"]`, but `ExecutionHandler.on_fill_ws()` currently copies order-time metadata and does not derive remaining size from OKX `sz` / `accFillSz`. Long/flat strategies still work if OKX sends a final `state="filled"` update, but the live path should add remaining-size metadata and unit coverage before any promotion.
13. **MA/MACD research baseline doc gap** (P1 docs-only, **still open**): F&G sentiment and CME daily gap baselines are now documented in `research/strategy_synthesis.md` (Strategies 9-10), but the analogous MA/EMA/MACD long-flat baseline section is still missing. Add it as a separate docs-only update covering long/flat execution assumptions, partial-fill semantics, incremental EMA/MACD state, and OOS/WF/CPCV acceptance gates.
14. **External-feature deployment caveats** (P1): Documented in `research/strategy_synthesis.md` as required ADR attestations. (a) **Budget-blocked, not on roadmap**: `CHRIS/CME_BTC1` was discontinued; paid CME alternatives (DataMine, Databento, Polygon) are not provisioned under this project's budget. The strategy's _operating_ signal source is `cme_btc_yfinance` (Yahoo `BTC=F` daily) — research-proxy, never deployment evidence. Trading venue is OKX BTC-USDT-SWAP (crypto/USDT perp), not CME futures itself; this is a cross-venue signal-to-trade setup, not arbitrage on CME. (b) `dgs10` ingest uses latest-vintage upsert and is not point-in-time — any DGS10-conditioned signal must remain `research_only` or move to FRED ALFRED vintage ingest. **Resolved in code**: `fear_greed_btc` label-stability — `FearGreedSentimentParams` now ships a `validate_extreme_fear_label` allow-list validator plus numeric `extreme_fear_threshold` / `exit_value_threshold` fallbacks driven off `value_num`; promotion ADR can attest against this implementation rather than treating it as an open blocker.
15. **Cross-strategy single-period selection-bias prohibition** (P1, normative, applies retroactively): Any `results/*.json` or `results/**/*.json` artifact with `validation_status: in_sample` or `validation_status: naive_backtest` is prohibited from being cited as edge evidence, used as a promotion basis, or used to satisfy the `docs/ai_collaboration.md` Deployment Gate stage `Historical backtest`, regardless of how strong total_return / Sharpe / PF / win-rate appears. Such use is **不得** and shall not pass review. The Deployment Gate stage `Walk-forward 或 CPCV` must be satisfied by an artifact with `validation_status: walk_forward` or `validation_status: cpcv`; CPCV must pass DSR >= 0.95 and PSR >= 0.95. `n_trials` must be reported honestly and must include all grid-sweep variants, manually adjusted versions, and trial variants discussed in chat / issues / commits even if no result file was retained; hidden trials count toward N. Future promotion artifacts using `backtesting/cpcv.py::CPCV.evaluate()` must provide `n_trials` explicitly and may not rely on a fallback default. This rule is retroactive: every current `results/**/*.json` artifact and every prior chat conclusion about "strategy performance" must be re-evaluated under this prohibition. Illustrative `cme_gap_fill` example, preserving the original warning: Route B was applied in commit `655af31` (2026-05-19), flipping `allow_direction` from `both` to `long_only` because up-gaps (short BTC) were -3,799 bps vs down-gaps +803 bps on the post-fix yfinance proxy run. Default re-run `results/cme_gap_research_long_only_default.json` reports total_return +7.09%, Sharpe +0.35, MDD -14.7% over 46 trades. Because this was a three-round manually tuned single-period backtest, its `validation_status` is `in_sample`, and the +7.09% number is not edge evidence. **Route B is still explicitly regime-fitted to BTC 2024-26; bear-regime walk-forward remains required before any promotion claim.** If `long_only` fails on a bear or sideways segment in the walk-forward, the default must revert to "do not deploy" and the strategy retired. Even on `long_only`, edge is only ~3 bps above round-trip cost — not validated alpha. The three `results/cme_gap_research*.json` artifacts are classified `in_sample` in `docs/results_validation_manifest.md`.
16. **In-sample envelope methodology lesson** (P2 process note): Claude's earlier estimate that a 1.5× stop would flip the CME gap-fill run from -3,187 to +3,308 bps was wrong because it only re-priced existing timeout exits and assumed target-fill trades were unchanged. The real bar-by-bar simulator triggered stop-loss on intra-trade adverse high/low excursions and converted 35/82 fills into stop-loss losses. Any future "what-if" stop / target replacement estimate on this style of strategy must walk every bar of every trade, not just re-cap existing exit reasons. Apply this lesson to MA/MACD baseline and any other long/flat exit-replacement review.
17. **Analyzer ↔ replay measurement divergence on `cme_gap_fill`** (P1 documentation only, no code change planned): `analyze_cme_gaps.simulate_reverse_gap_trades` uses each OKX bar's `high`/`low` to detect target / stop touches; the replay engine feeds the strategy a single L1 book event per bar synthesised from the bar `close` (`_synthetic_l1_from_candles`), so `_target_touched` / `_stop_loss_touched` only see the close mid. On 1H bars (intra-bar range 20-100 bps) many analyzer `target_fill` trades become replay `timeout` — replay is systematically more negative on the same gap signal. Secondary divergence: funding (perp), maker queue/partial-fill mechanics, entry-price reference (bar open vs close mid), broker-modelled fees vs flat 12 bps. **Interpretation rule**: analyzer JSON is an upper bound under idealised execution; replay artefact is a coarse close-mid lower bound. Neither is admissible as deployment evidence in isolation. Closing the gap requires either bar-high/low events in replay (changes strategy semantics; separate research item) or shadow trading for ground truth.
18a. **Idealized-fill artefacts are not live-readiness evidence** (P1, normative, applies retroactively): Any `results/**/*.json` artefact with `result.validation.fill_all_signals == true` or `result.validation.idealized_fill == true` is **not OOS evidence, not edge evidence, and not promotion evidence**, regardless of `validation_status`. Codex commit `7c23791` writes `idealized_fill` in artefacts and propagates it through CPCV / WalkForward aggregate validation blocks, so this exclusion is now enforceable programmatically. `fill_all_signals` is a research-only capacity / execution sensitivity tool — it raises `max_order_notional_usd` to 1e12, `max_pos_pct_equity` to 1e6, `stale_quote_pct` to 1e6, `max_daily_loss_pct` to 1e6, `soft_drawdown_pct` to 1e6, and `hard_drawdown_pct` above those soft stops, sets `queue_fill_fraction = 1.0`, zeroes latency, switches replay to `fill_all_on_submit`, and (for `ohlcv_rotation`) bypasses `top_k`, `rank_exit_buffer`, and `max_position_weight`. WF / CPCV layered on top of idealized fills measures only signal-side fit, not execution-reachable PnL, so the Deployment Gate Idealized-fill exclusion row in `docs/ai_collaboration.md` rejects such artefacts even at `validation_status: walk_forward` / `cpcv`. Allowed use cases are strictly: (a) PnL / capacity upper-bound estimation; (b) detecting whether the realistic-fill backtest is execution-bound vs. signal-bound. Reviewers must reject any promotion ADR, edge claim, or `docs/AI_HANDOFF.md` "ready for live" assertion that cites a `fill_all_signals` artefact.

18. **Pending CME gap-fill exit-throttle + timestamp-normalisation commit** (P1): Uncommitted diff against `src/okx_quant/strategies/external_features.py` adds `_ActiveGap.exit_requested` to suppress duplicate exit signals while an exit order is pending (regression test `test_cme_gap_fill_does_not_repeat_exit_signal_while_exit_order_pending`). A separate uncommitted change in `backtesting/replay.py::_to_ms_int` + `backtesting/data_loader.py::_timestamp_to_ms` normalises multi-precision timestamps (s/ms/us/ns) in the L1 book loader and feature loader, with tests in `test_external_data.py` and `test_external_feature_strategies.py`. These should be split into two commits — exit-throttle is the alignment fix for the analyzer baseline; timestamp normalisation is an unrelated robustness fix.

19. **Differential validation gate field shape and misread defense** (P1, normative, applies retroactively; broadened by user 2026-06-12): `docs/ai_collaboration.md` Deployment Gate requires each active/declared strategy to declare at least one portable reference-validation path in `backtesting/differential_validation.py::REFERENCE_VALIDATION_CONTRACTS`. User decision on 2026-06-12: first-stage validation should aim for signal-point correctness across all three external systems (`vectorbt`, `backtrader`, `nautilus`) where supported; the hard comparison is timestamp/bar, symbol, side, and action/entry-exit, while PnL/fill/metric parity remains out of hard scope. A strategy can satisfy promotion-grade portable evidence only with at least one independent reference engine result, currently `reference_signals_only`, whose strict `signal_logic` comparison is `PASS` with `actionable_mismatch_count == 0`; advisory-only replay/export must not set `portable_validation_gate.passed == true`. Codex working tree now emits scoped comparison summaries (`signal_logic`, `trade_execution`, `pnl_semantics`, `metrics`) plus per-scope actionable/downstream mismatch counts. `reference_signals_only` means the external adapter independently recomputes the expected signal stream from portable artifacts such as `price_series.csv`, `funding_rates.csv`, `external_observations.csv`, or `target_weights.csv`, then compares signal timing/side/target fields against the project artifact; it does **not** replay the project's own signals as proof, and it does **not** validate trade fills, queue behavior, funding settlement, PnL, equity, or metric realism. No override path exists — FAIL is hard-block; any exclusion requires explicit user approval and a corresponding update to the gate text in `docs/ai_collaboration.md`. Misread defense: gate PASS under `reference_signals_only` validates signal-logic portability only; reviewers may cite nonzero advisory `actionable_mismatch_counts` as promotion ADR rejection or deferral evidence even when the signal-logic gate passes.

20. **Source-data gate FAIL is caused by ct_val provenance, not DB parity** (P0, Claude review 2026-06-11): Audited all 21 `results/**/validation_result.json`. Only 1 artifact ([`results/ui_sweep_macd_crossover_5fca174a_rank_001/validation/codex_progress_stage_check`](../results/ui_sweep_macd_crossover_5fca174a_rank_001/validation/codex_progress_stage_check/validation_result.json)) actually ran the `source_data_validation` block; it is `status: FAIL` driven **solely** by `checks.ct_val_provenance.status == "FAIL"` ("not authoritative for all SWAP symbols"). `checks.db_parity` is `SKIP` and **structurally cannot fail the gate** — the aggregator at `backtesting/differential_validation.py:675-681` only escalates on FAIL/WARN, never SKIP. The other 20 artifacts carry `ohlcv_source_validation: deferred` with **no `source_data_validation` block at all** — the gate is implemented but not wired into the standard artifact-emission path, so it is unenforced for 20/21 artifacts. Root cause of the ct_val FAIL: the run had neither a reachable DB `instruments.contract_value` nor a caller-supplied `config_override`, so `ReplayBacktestEngine._resolve_swap_ct_val` fell back to `registry` (`config/instrument_specs.yaml`), which is non-authoritative for live gating. **Decision: ct_val provenance is the next blocking patch priority; DB parity is NOT** — DB parity stays opt-in `SKIP` and is promoted to blocking per-strategy only at demo/shadow time, once `canonical_candles` is populated for the symbols/bars under test and a DSN is wired into the validation/CI environment (blocked today by the data gap in Known Issue 9). Secondary hardening flagged: `_validate_ct_val_provenance` (`differential_validation.py:1213-1218`) returns `WARN` when provenance is _missing entirely_ but `FAIL` when present-but-non-authoritative — "missing" should be tightened to `FAIL` to match the hard deployment gate in `docs/ai_collaboration.md:203-212`, otherwise omitting provenance is easier to pass than supplying a non-authoritative value.

## Do Not Touch (without explicit issue + user approval)

- `src/okx_quant/strategies/` — all strategy implementations
- `src/okx_quant/risk/` — risk guard, drawdown tracker, circuit breaker
- `src/okx_quant/portfolio/` — sizing, position ledger
- `src/okx_quant/execution/broker.py` — SimBroker and execution handler
- `config/risk.yaml` — risk limits
- Any file not listed in the current issue's permitted scope

## Next Steps (in order)

0. **[P0 - fixture signal validation passed and is now CI-wired; broader correctness still blocked by real-data/execution evidence]** SWAP ct_val provenance gate is stricter in `backtesting/differential_validation.py`: missing provenance is `FAIL`, and validation artifacts emit `source_data_validation`, `validation_conclusion`, and `portable_validation_gate`. `scripts/run_all_strategy_signal_validation.py` generated deterministic active-strategy fixtures with explicit `config_override` ct_val provenance. Batch `codex_20260616_signal_validation` passed for all active strategies: `source_data_validation == PASS`, `portable_validation_gate.passed == true`, `signal_point_correctness.passed == true`, and `nautilus_order_fill_parity.status == "PASS"`. CI runs the fixture batch via `make strategy-signal-validation`; DB parity remains out of scope and opt-in `SKIP` until a DSN/data fixture is ready. This batch is not live-readiness evidence.
0c. **[P0 - source-provenance slice implemented; current Binance DB-backed MA PASS reproduced after venue-scoped source fix]** `scripts/run_source_provenance_validation.py` gates existing or freshly generated differential-validation results for real-data/source provenance. It fails fixture evidence with DB parity `SKIP` and requires `db_parity_pass`. The older `results/adr0007_binance_btc_1h_db_pass_20260618/validation/codex_close_only_db_parity_pass_20260618/validation_result.json` PASS should not be treated as a standing current-DB PASS until reproduced. A 2026-06-23 Codex reseed plus a targeted Binance download filled the 2024-04-29 one-day gap in local parquet and DB canonical 1H data, but regeneration alone was insufficient because replay had not been passing the run exchange into canonical candle reads. Codex fixed that structural source-selection bug and regenerated MA/EMA/MACD with suffix `_venue_scoped_pg_20260623`; the MA source-provenance artifact `codex_venue_scoped_pg_db_parity_20260623_pass` now has `db_parity.status == PASS`, `canonical_source_primary == binance`, and 0 mismatches over 20,400 rows. Nautilus matching-engine/PnL/funding parity stays later unless the user explicitly reprioritizes it.
0a. **[P0 — research checklist synced by explicit user request; pending Claude review]** `research/strategy_synthesis.md` Promotion Checklist no longer frames Differential validation as MA/EMA/MACD-only. It points reviewers to `REFERENCE_VALIDATION_CONTRACTS` for all active/declared strategies, requires `portable_validation_gate.passed == true` for promotion evidence, explains `reference_signals_only` versus advisory replay/export, and preserves advisory mismatch review authority.
0b. **[P1 - unit-tested; pending real dependency-backed artifact review]** Differential-validation output includes `signal_point_correctness`, a three-engine (`vectorbt` / `backtrader` / `nautilus`) point-correctness matrix with PASS/FAIL, mismatch counts, examples, and advisory differences. Frontend `view-validation.js` renders this matrix; PnL/fill/metric differences remain advisory and Nautilus remains advisory for full execution/PnL parity.
1. **[P0]** Claude re-review MA/MACD long-flat position fix follow-up, especially live/replay reduce-only bypass audit logging and ADR-0006.
2. **[P0 — DONE 2026-05-22]** Claude re-reviewed Chart UX overhaul / Daily Winner normalization follow-up; remaining accepted changes were documentation alignment and Daily Winner cost labeling.
3. **[P0]** Remaining DB-primary backend verification from prior handoff: end-to-end SOL download + backtest, DSN-invalid fallback path, and grep for stray `--backend parquet` outside fallback/tests.
4. **[P0]** Run deployment smoke tests for API key auth, CORS, WebSocket auth, and Docker port bindings before any public AWS deployment.
5. **[P1]** Add live WS remaining-size metadata from OKX `sz` / `accFillSz` and unit coverage before any MA/MACD promotion.
6. **[P1]** Claude docs-only update: add MA/EMA/MACD long-flat baseline section to `research/strategy_synthesis.md` (F&G + CME daily baselines and external-feature data caveats already added in this session).
6a. **[P3 — budget-blocked, no current plan]** Replace `CHRIS/CME_BTC1` adapter target with a maintained official CME BTC futures source (paid: DataMine, Databento, Polygon, or equivalent). Not on the active roadmap — this project trades OKX crypto/USDT pairs and uses CME only as a _signal_; the yfinance proxy (`cme_btc_yfinance`) is the operating signal source under budget. Re-open at P1 only if/when budget approves a paid feed; until then, all CME-gap research stays on the yfinance proxy and must be labelled accordingly.
6c. **[P1 — DONE 2026-05-19, commit `655af31`]** Codex flipped `CMEGapFillParams.allow_direction` default from `both` to `long_only` (Route B). Touched `core/config.py`, `config/strategies.yaml`, `external_features.py`, `analyze_cme_gaps.py` (functions + CLI), plus regression tests `test_cme_gap_fill_default_skips_up_gaps_and_trades_down_gaps` and `test_simulate_reverse_gap_trades_default_excludes_short_side`. Re-run `results/cme_gap_research_long_only_default.json` confirms `allow_direction="long_only"` and total_return = +7.09% on the yfinance proxy. `research/strategy_synthesis.md` Strategy 10 and Current Change Context updated.
6d. **[P1]** Bear-regime walk-forward / CPCV for `cme_gap_fill` on the `cme_btc_yfinance` proxy (since the official CME source is budget-blocked per 6a). Identify bear / sideways segments inside the available proxy window (e.g. extended drawdown stretches in 2024-2025) and run walk-forward separately on those. If `long_only` fails on any such segment, revert default to "do not deploy" and mark the strategy retired in Strategy 10. Any promotion ADR opened on the proxy alone must explicitly attest to the signal-source fidelity gap and require post-promotion monitoring against any future official feed. Until 6d completes, no promotion claim may cite the +7.09% proxy number as evidence — it is regime-fitted to BTC 2024-26.
6e. **[P1]** Codex follow-up: write `validation_status` field into `result.json` via `backtesting/artifacts.py` (separate issue, will touch ADR-0002 frozen schema — requires user approval).
6f. **[P1]** Codex follow-up: make `backtesting/cpcv.py::CPCV.evaluate()` require explicit `n_trials` (remove the `None` fallback), and add an equivalent trials-reporting parameter to `WalkForward.evaluate()`; separate issue because it will touch `backtesting/`.
6b. **[P1]** F&G label allow-list validator + numeric `value_num` thresholds are now in place (`FearGreedSentimentParams.validate_extreme_fear_label`, `extreme_fear_threshold`, `exit_value_threshold`). Remaining work for F&G promotion ADR is the Neutral/Fear hold-through DSR validation, not the validator itself.
7. **[P1]** Download 1m candle data for BTC-USDT-SWAP, ETH-USDT-SWAP, SOL-USDT-SWAP to enable 1m OHLCV rotation backtests (now routes through DB on download).
8. **[P2]** Review `docs/pairs_position_aware_close_sizing_plan.md`.
9. **[P2]** Implement position-aware close sizing after design review.
10. **[P1 — DONE 2026-05-25, commit `7c23791`]** Codex follow-up for `fill_all_signals` admissibility (Option B of 2026-05-25 Claude review): wired `idealized_fill: true` into `result.validation` via `backtesting/artifacts.py`, propagated through `backtesting/cpcv.py::CPCV.evaluate()` and `backtesting/walk_forward.py::WalkForward.evaluate()` outputs, and surfaced a warning in `src/okx_quant/api/routes_backtest.py` response payloads when the flag is true. Regression coverage added for: (a) single replay with `fill_all_signals=True` writing `idealized_fill: true` in `result.validation`; (b) CPCV / WalkForward aggregate propagation; (c) API response `warnings: ["idealized_fill"]`. No strategy / risk / portfolio / execution changes in the Codex follow-up.

11. **[P1 - implemented and dependency-backed fixture batch generated]** Differential-validation comparator emits scoped `signal_logic`, `trade_execution`, `pnl_semantics`, and `metrics` summaries with `actionable_mismatch_count` and `downstream_mismatch_count`; the gate reads strict `signal_logic` only for independent reference roles. `tests/unit/test_differential_validation.py` passes locally, and batch `codex_20260616_signal_validation` produced all-strategy three-engine fixture artifacts. Indicator-series bar-by-bar comparison remains out of scope; do not loosen tolerances or add Nautilus full adapter code without a new approved issue.

## Documentation Cleanup Next Step

After the consolidated P1 PR is merged, classify existing Markdown files with
lifecycle metadata in a dedicated docs-only cleanup PR. Do not change strategy
assumptions or implementation behavior during that cleanup.

## Open Questions

- Should `AI_WORKFLOW.md` content eventually be merged back into `ai_collaboration.md`, or kept separate permanently?
- Which commit is the last confirmed clean state for integration tests (requires DB)?
- Is `config/risk.yaml` the authoritative risk limit file or is there per-strategy risk config in `strategies.yaml`?

## Session Handoff Checklist

Before ending a session, confirm:

- [ ] Changed files listed
- [ ] Tests run (or reason stated why not)
- [ ] `AI_HANDOFF.md` updated (Known Bugs, Next Steps, Current Change Context)
- [ ] Commit has `AI-Origin:` trailer
- [ ] Issue acceptance criteria met or partial progress noted
