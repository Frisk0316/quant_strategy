---
status: current
type: manifest
owner: codex
created: 2026-06-22
last_reviewed: 2026-06-22
expires: none
superseded_by: null
---

# Change Manifest: Backtest Execution Profiles

## Summary
Backtest runs now separate idealized strategy research from realistic maker-execution stress through named execution profiles. The realistic replay path remains available internally and idealized artifacts are explicitly marked as research-only evidence.

## Business rule(s) affected
R5 fill/execution semantics and R7 promotion-evidence admissibility.

## Trigger area(s) (DOC_IMPACT_MATRIX)
A2 portfolio/execution, A5 backtesting, A8 API/UI behavior, A9 validation/reporting.

## Files changed
- `backtesting/research_controls.py` - profile names and profile-to-config controls.
- `backtesting/replay.py` - submitted-fill metrics exclude terminal liquidation.
- `scripts/run_replay_backtest.py` - profile CLI and dual-output orchestration.
- `scripts/run_validation_lab_signal_order_check.py` - profile-aware report runner.
- `src/okx_quant/api/routes_backtest.py` - public profile field and job status.
- `frontend/view-config.js` - Strategy Fill / Dual Output picker.
- `frontend/view-backtest.js` - run-detail execution profile display and comparison JSON link.
- `tests/` - profile, metric, CLI, and API guards.
- `docs/` - rule, invariant, runbook, UI/data-flow, and gate wording.

## Behavior delta
- Before: Replay results could mix strategy signal quality with maker queue, cancel, lot/min rounding, and terminal liquidation effects unless users knew the low-level `fill_all_signals` switch.
- After: Users select `Strategy Fill` for signal-to-position research or `Dual Output` for paired strategy-vs-realistic diagnostics.
- Money/risk impact: `strategy_fill` may increase research PnL and fill rate because execution caps and queue constraints are intentionally bypassed. Those artifacts are marked `idealized_fill` and are not promotion evidence.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A - no strategy assumption changed.
- config/: N/A - live, shadow, demo, and default config files are unchanged.
- ADR: N/A - additive profile metadata and API/UI naming do not replace an existing ADR.

## Docs updated (from DOC_IMPACT_MATRIX row)
- [x] `docs/DOMAIN_RULES.md` - execution profile semantics.
- [x] `docs/INVARIANTS.md` - idealized-fill and terminal-liquidation metric invariants.
- [x] `docs/FEATURE_MAP.md` - backtest entrypoint ownership.
- [x] `docs/UI_MAP.md` - two-choice execution profile picker.
- [x] `docs/DATA_FLOW.md` - dual-output artifact flow.
- [x] `docs/RUNBOOK.md` - CLI examples.
- [x] `docs/ai_collaboration.md` - promotion evidence caveat.

## Invariants / golden cases
- Invariants checked: I14, I17, I18.
- Golden cases affected: BTC-USDT-SWAP Binance 1H Validation Lab signal-order checks.

## Tests / checks run
- `python -m pytest tests/unit/test_parameter_sweep.py tests/unit/test_backtesting.py tests/unit/test_backtest_request_exchange.py tests/integration/test_api_endpoints.py -q` - 78 passed.
- `node --check frontend/view-config.js` - passed.
- `python scripts/docs/check_doc_metadata.py` - passed with 14 pre-existing lifecycle metadata warnings.
- `python scripts/docs/check_feature_map_links.py` - passed.
- `python scripts/docs/check_doc_impact.py` - passed; advisory script reported no changed files to verify in this local state.
- `git diff --check` - passed with CRLF normalization warnings only.
- `python scripts/run_validation_lab_signal_order_check.py --max-order-notional-usd 250 --max-pos-pct-equity 1 --run-suffix maxord250_pospct1_strategyfill --execution-profile strategy_fill` - passed; wrote `results/validation_lab_signal_order_check_20260622_maxord250_pospct1_strategyfill.json`.
- `python scripts/run_replay_backtest.py ... --execution-profile dual_output --run-id validation_lab_macd_btc_binance_1h_20260622_dual_fullperiod` - passed through a temporary local wrapper to avoid PowerShell JSON quoting; wrote `results/validation_lab_macd_btc_binance_1h_20260622_dual_fullperiod_execution_comparison.json`.
- `python -m pytest tests/unit/test_backtest_visual_fallbacks.py::test_run_detail_displays_execution_profile_and_comparison_link tests/unit/test_backtest_visual_fallbacks.py::test_execution_comparison_endpoint_infers_dual_output_file -q` - passed.
- `node --check frontend/view-backtest.js` - passed.

## Validation evidence
- Strategy Fill, BTC-USDT-SWAP Binance 1H, 2024-01-01 to 2026-04-30, `max_order_notional_usd=250`, `max_pos_pct_equity=1`:
  - MA 10/200: 228 signals, 228 submitted orders, 228 real fills, 0 rejections.
  - EMA 10/200: 252 signals, 252 submitted orders, 252 real fills, 0 rejections.
  - MACD 12/26/9: 1558 signals, 1558 submitted orders, 1558 real fills, 0 rejections.
- Full-period MACD Dual Output:
  - `strategy_fill`: 1558 submitted orders, 1558 submitted-order fills, fill rate 1.0.
  - `realistic_execution`: 779 submitted orders, 3 submitted-order fills, 1 terminal liquidation fill, fill rate 0.003851.

## Risks and rollback
- Risks: Users may still read idealized Strategy Fill output as tradable evidence; Dual Output doubles replay runtime.
- Rollback: Revert the implementation commit and remove this manifest/docs wording. Historical artifacts are not migrated.

## Approval
- Human approval required: yes - design approved in chat on 2026-06-22.
