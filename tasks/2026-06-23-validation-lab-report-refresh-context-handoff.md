# Context Handoff: Validation Lab report refresh — 2026-06-23

## Goal (one sentence)
Fold Claude's 2026-06-23 validation progress into the existing Chinese Validation Lab Markdown/PPTX report without changing strategy, risk, config, deployment gates, or result artifacts.

## Current state
- Branch: `codex/impl-multi-venue-instrument-specs`
- Last known good commit / state: `148fb09`; working tree already had unrelated pre-existing implementation/docs/result changes before this report refresh.
- In-progress edits (files): `docs/validation_lab_report_zh.md`, `scripts/generate_backtest_external_validation_report.py`, `docs/backtest_external_validation_report_zh.pptx`, this context handoff, and the paired session handoff.
- What works right now: the Markdown report now includes collaboration scope, 2026-06-22 signal-to-order evidence, 250/1.0 risk sensitivity, MACD dual-output comparison, Claude 2026-06-23 long-window vectorbt/backtrader signal-logic PASS evidence, DB parity gap, and offline engine-consistency smoke progress. The PPTX regenerates successfully with 18 slides and contains the new Claude/smoke/DB parity sections.
- What does not work / unfinished: `make docs-check` is unavailable in this Windows shell; equivalent Python docs checks were run instead. DB parity for current Binance 1H validation-lab runs remains SKIP because current DB lacks Binance-sourced 1H canonical rows. Nautilus full matching-engine parity remains unfinished.

## Decisions made (and why)
- Updated the existing report generator rather than hand-editing PPTX XML because the repo already owns the deck through `scripts/generate_backtest_external_validation_report.py`.
- Added exactly two new PPTX slides for Claude validation evidence and remaining gaps/smoke progress because the old deck already covered architecture and signal-to-order results.
- Kept all new wording advisory-only because Claude's long-window validation used `strategy_fill`, had `promotion_gate_evidence = false`, skipped DB parity, and selected vectorbt/backtrader only.
- Did not update `research/`, strategy logic, risk, config, deployment gates, or existing result artifacts because this task was report packaging only.

## Open questions / unverified assumptions
- Whether Binance 1H canonical rows should be re-seeded from source API or resampled from Binance 1m canonical rows before rerunning DB parity.
- Whether the offline engine-consistency smoke target should become a required CI/docs check after its current untracked implementation is reviewed.
- Whether Nautilus full parity should be revived soon or deferred until order-book/L2-L3 data work is approved.

## Rules in play (preserve verbatim)
- Invariants touched: none changed. Referenced validation/promotion boundaries only.
- Domain rules touched: none changed. Referenced data provenance and validation-gate rules only.
- Do-not-touch: `research/`, strategy implementation, signals, risk, portfolio, execution, config, deployment gates, differential-validation implementation, and existing backtest result artifacts.

## Context to load next (the reading list)
- Source of truth: `AI_CONTEXT.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `docs/ai_collaboration.md`, `docs/backtest_live_parity_plan.md`.
- Owning files / MODULE_BRIEFS: `docs/FEATURE_MAP.md`, `docs/UI_MAP.md`, `docs/DATA_FLOW.md`, `scripts/generate_backtest_external_validation_report.py`, `docs/validation_lab_report_zh.md`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.
- Evidence files: `results/validation_lab_signal_order_check_20260622.json`, `results/validation_lab_signal_order_check_20260622_maxord250_pospct1.json`, `results/validation_lab_macd_btc_binance_1h_20260622_dual_fullperiod_execution_comparison.json`, and `results/validation_lab_{ma,ema,macd}_crossover_btc_binance_1h_20260622_maxord250_pospct1_strategyfill/validation/claude_engine_consistency_20260623/validation_result.json`.

## Checks run
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\generate_backtest_external_validation_report.py` — passed; wrote `docs/backtest_external_validation_report_zh.pptx` at 51,239 bytes.
- PPTX zip/package smoke using Python `zipfile` — passed; found 18 slide XML files and confirmed slide XML contains `Claude 2026-06-23`, `Offline smoke`, and `DB parity data gap`.
- `make docs-check` — failed because `make` is unavailable in this Windows shell.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_doc_metadata.py` — passed with 14 pre-existing lifecycle metadata warnings.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_feature_map_links.py` — passed; 102 concrete paths checked.

## Approvals
- Human approval needed / obtained: no deployment, risk, business-rule, or artifact-migration approval requested or obtained. This report refresh does not claim live readiness.

## Next action (single, concrete)
- Review and merge the report package only after confirming the unrelated pre-existing working-tree changes belong to their owning sessions.

## Human Learning Notes
The key distinction is "portable signal logic" versus "promotion evidence." Claude's 2026-06-23 runs materially improve confidence that MA/EMA/MACD signal timing is portable across vectorbt/backtrader on the long Binance 1H `strategy_fill` artifacts, but the result is still advisory-only because DB parity is skipped, Nautilus was not selected, and idealized-fill artifacts do not validate realistic execution or live readiness.
