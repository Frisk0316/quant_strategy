# Context Handoff: Validation Lab report package — 2026-06-22

## Goal (one sentence)
Prepare a Chinese report and PowerPoint for the Validation Lab presentation and verify BTC-USDT-SWAP Binance 1H MA/EMA/MACD signal-to-order behavior.

## Current state
- Branch: `codex/impl-multi-venue-instrument-specs`
- Last known good commit / state: branch already contained ADR-0007 P1, Validation Lab saved-run support, and fast artifact-read work; this session did not change trading logic.
- In-progress edits (files): `docs/validation_lab_report_zh.md`, `docs/backtest_external_validation_report_zh.pptx`, `scripts/generate_backtest_external_validation_report.py`, `scripts/run_validation_lab_signal_order_check.py`, `results/validation_lab_signal_order_check_20260622.json`, `docs/CURRENT_STATE.md`, `docs/AI_HANDOFF.md`, `docs/CHANGELOG_AI.md`, this handoff, and the paired session handoff.
- What works right now: report/PPT are generated; PPTX ZIP/OpenXML smoke passed with 16 slides; BTC-USDT-SWAP Binance 1H signal-to-order summary exists for MA 10/200, EMA 10/200, and MACD 12/26/9. Reduce-only close orders may bypass single-order fat-finger only up to current position notional.
- What does not work / unfinished: long-window run-scoped differential validation for the generated MA/EMA/MACD artifacts did not complete locally, even for MACD + vectorbt with `NUMBA_DISABLE_JIT=1`; do not cite it as fresh three-engine validation evidence. MACD realistic-fill counts are also execution-model constrained: with `queue_fill_fraction=0.20` and Binance `lotSz/minSz=0.001`, a residual 0.002 reduce-only close allocates 0.0004 per touch and rounds to zero, so many touched exit orders have no fill rows.

## Decisions made (and why)
- Wrote a detailed Markdown report plus a concise PPT deck because the user needs both presentation material and a complete evidence-backed reference.
- Kept the BTC/Binance check as signal-to-order evidence, not promotion evidence, because source/provenance, portable signal quorum, WF/CPCV, and shadow/demo gates were not all run.
- Reused the existing standard-library PPTX generator rather than introducing `python-pptx`, because the repo already had a no-extra-dependency report generator.

## Open questions / unverified assumptions
- Whether the long-window differential-validation stall is vectorbt import/JIT, artifact comparison volume, CSV write cost, or another adapter bottleneck needs profiling.
- Whether MA/EMA exit orders above 500 USD should continue to be fat-finger blocked, or whether reduce-only close logic needs a separate explicit user-approved rule change.
- Whether the beginner strategy builder should be a new frontend view or integrated into the existing config/backtest view.

## Rules in play (preserve verbatim)
- Invariants touched: I6 max order caps; I12 DB source parity; I14 no idealized/in-sample promotion; I16 venue-scoped `ct_val` provenance.
- Domain rules touched: R1 contract value and instrument specs; R4 sizing/risk; R5 fills/execution; R6 data provenance; R7 validation/promotion gates.
- Do-not-touch: `research/`, strategy logic, signals, risk, portfolio, execution, PnL/fee/funding behavior, deployment gates, existing backtest result artifacts not created by this session.

## Context to load next (the reading list)
- Source of truth: `AI_CONTEXT.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `docs/ai_collaboration.md`, `docs/DOMAIN_RULES.md`, `docs/INVARIANTS.md`.
- Owning files / MODULE_BRIEFS: `docs/FEATURE_MAP.md`, `docs/UI_MAP.md`, `docs/DATA_FLOW.md`, `backtesting/differential_validation.py`, `scripts/run_differential_validation.py`, `src/okx_quant/portfolio/portfolio_manager.py`, `src/okx_quant/risk/risk_guard.py`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run
- `python scripts/run_validation_lab_signal_order_check.py` — completed; generated `results/validation_lab_signal_order_check_20260622.json`; terminal output was large before logging was reduced.
- `python scripts/run_validation_lab_signal_order_check.py --max-order-notional-usd 250 --max-pos-pct-equity 1 --run-suffix maxord250_pospct1` — completed after bounded reduce-only bypass; generated `results/validation_lab_signal_order_check_20260622_maxord250_pospct1.json`.
- `python scripts/run_validation_lab_signal_order_check.py --max-order-notional-usd 250 --max-pos-pct-equity 1 --run-suffix maxord250_pospct1_verify2` — completed; generated `results/validation_lab_signal_order_check_20260622_maxord250_pospct1_verify2.json`.
- Fill-model audit of `results/validation_lab_macd_crossover_btc_binance_1h_20260622_maxord250_pospct1_verify2`: 779 orders, 13 real fill rows, 3 submitted order ids with replay L1 fills plus 1 terminal-liquidation fill id, and 776 distinct cancelled order ids. `_round_fill_size()` check confirmed `0.002 * 0.20 -> 0.0` while `0.005 * 0.20 -> 0.001`.
- `python -m pytest tests/unit/test_risk_guard.py tests/integration/test_replay_engine.py::test_replay_records_allowed_reduce_only_bypass_event -q` — passed, 25 tests.
- `python scripts/run_differential_validation.py --run-id validation_lab_* --engines vectorbt,backtrader,nautilus` — attempted in parallel; no artifacts after more than two minutes; stopped.
- `python scripts/run_differential_validation.py --run-id validation_lab_macd_crossover_btc_binance_1h_20260622 --engines vectorbt` — attempted with and without `NUMBA_DISABLE_JIT=1`; no artifact after 60 seconds; stopped.
- `python scripts/generate_backtest_external_validation_report.py` — passed; wrote `docs/backtest_external_validation_report_zh.pptx`.
- PPTX ZIP smoke — passed; 16 slide XML files and `ppt/presentation.xml` present.
- AST parse for edited scripts — passed.
- `python -m pytest tests/unit/test_differential_validation.py -q` — passed, 47 tests; pytest cache write warning due permission.
- `make docs-check` — not run; `make` is unavailable in this Windows shell.
- `python scripts/docs/check_doc_metadata.py` — passed with 13 pre-existing metadata warnings.
- `python scripts/docs/check_feature_map_links.py` — passed, 98 concrete paths checked.
- `python scripts/docs/check_doc_impact.py` — exited 0 but reported "no changed files detected"; treat as advisory because `git status` shows changed files.
- `python -m py_compile ...` — not usable; writing `scripts/__pycache__` failed with permission denied.

## Approvals
- Human approval needed / obtained: no live/deployment approval requested or obtained. No business-rule change was made.

## Next action (single, concrete)
- Profile `scripts/run_differential_validation.py` on a short BTC/Binance fixture and produce a fresh three-engine validation artifact for MA/EMA 10/200 and MACD 12/26/9 before making any stronger validation claim.

## Human Learning Notes
Validation Lab evidence has layers. Fixture three-engine signal validation already proves the harness can pass MA/EMA/MACD signal-point checks, but the new BTC/Binance long-window signal-to-order run only proves the project can turn those signals into orders/fills/rejections under its own risk/execution path. MA/EMA rejections are a useful teaching example: external signal parity and project risk realization are different questions. MACD's 779 orders versus 13 fill rows teaches a second layer: realistic maker replay can be dominated by queue allocation and exchange lot/min rounding, so order count is not fill reachability.

Backtest execution profiles make that split explicit: `Strategy Fill` asks whether signals perform after becoming positions, `realistic_execution` asks how much survives current maker replay assumptions, and `dual_output` compares the two. Passing Strategy Fill or Dual Output is diagnostic, not live-readiness approval.

## 2026-06-22 Addendum: Backtest execution profiles implemented
- Implemented `strategy_fill`, internal `realistic_execution`, and public `dual_output` execution profiles across replay CLI, Validation Lab signal-order script, API request/job status, and frontend config UI.
- Added submitted-order fill metrics that exclude terminal liquidation rows: `submitted_order_fill_count` and `terminal_liquidation_fill_count`.
- New Change Manifest: `docs/change_manifests/2026-06-22-backtest-execution-profiles.md`.
- New BTC-USDT-SWAP Binance 1H Strategy Fill evidence with `max_order_notional_usd=250`, `max_pos_pct_equity=1`: `results/validation_lab_signal_order_check_20260622_maxord250_pospct1_strategyfill.json`.
- Strategy Fill counts: MA 10/200 = 228 signals / 228 submitted / 228 fills; EMA 10/200 = 252 / 252 / 252; MACD 12/26/9 = 1558 / 1558 / 1558; all had 0 rejections.
- Full-period MACD Dual Output comparison: `results/validation_lab_macd_btc_binance_1h_20260622_dual_fullperiod_execution_comparison.json`.
- Full-period MACD Dual Output result: `strategy_fill` had 1558 submitted-order fills; `realistic_execution` had 779 submitted orders, 3 submitted-order fills, 13 real fill rows, and 1 terminal liquidation fill.
- Run Detail now shows execution profile metadata and links dual-output comparison JSON through `GET /api/backtest/{run_id}/execution-comparison`.
- Verification added: 78 targeted unit/integration tests passed, `node --check frontend/view-config.js` passed, doc metadata/link/impact checks passed with existing advisory warnings.
