# Session Handoff: Validation Lab report package — 2026-06-22

## Implementation summary
Prepared a Chinese Validation Lab report package and ran a BTC-USDT-SWAP Binance 1H signal-to-order check for MA 10/200, EMA 10/200, and MACD 12/26/9. The package explains the low-cost external validation architecture, vectorbt/backtrader/Nautilus roles, source-data boundaries, parameter interpretation, limitations, max-order-notional differences, and a no-code beginner strategy-builder plan.
Follow-up risk semantics now allow bounded reduce-only close orders to bypass the single-order fat-finger cap up to current position notional.
Follow-up fill-model diagnosis explains why MACD still had 779 orders but only 13 fill rows under realistic replay: after a partial 0.002 residual long, `queue_fill_fraction=0.20` makes each touched close allocation 0.0004, below Binance `lotSz/minSz=0.001`, so `_round_fill_size()` returns 0 and replacement exit orders keep cancelling without fills.

## Diff scope
- Files added: `docs/validation_lab_report_zh.md`, `docs/backtest_external_validation_report_zh.pptx`, `scripts/run_validation_lab_signal_order_check.py`, `results/validation_lab_signal_order_check_20260622.json`, `tasks/2026-06-22-validation-lab-report-context-handoff.md`, `tasks/2026-06-22-validation-lab-report-session-handoff.md`
- Files changed: `scripts/generate_backtest_external_validation_report.py`, `docs/CURRENT_STATE.md`, `docs/AI_HANDOFF.md`, `docs/CHANGELOG_AI.md`, `docs/FAILURE_MODES.md`
- Files deleted: none

## Business-rule change?
- Yes. The reduce-only fat-finger bypass changed risk semantics; the Change Manifest is `docs/change_manifests/2026-06-22-reduce-only-fat-finger-bypass.md`. The later MACD fill-model audit was documentation/diagnosis only and did not change fill semantics.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A, not touched.
- config/: N/A, not touched.
- ADR: N/A, not added or updated.

## Experiments
- HYPOTHESIS_LEDGER entries: none.
- EXPERIMENT_REGISTRY entries: none.

## Tests / checks run
- `python scripts/run_validation_lab_signal_order_check.py` — passed; generated `results/validation_lab_signal_order_check_20260622.json`.
- `python scripts/run_validation_lab_signal_order_check.py --max-order-notional-usd 250 --max-pos-pct-equity 1 --run-suffix maxord250_pospct1` — passed after bounded reduce-only bypass; generated `results/validation_lab_signal_order_check_20260622_maxord250_pospct1.json`.
- `python scripts/run_validation_lab_signal_order_check.py --max-order-notional-usd 250 --max-pos-pct-equity 1 --run-suffix maxord250_pospct1_verify2` — passed; generated `results/validation_lab_signal_order_check_20260622_maxord250_pospct1_verify2.json`.
- Fill-model audit of the MACD verify2 run — 779 submitted orders, 13 real fill rows, 3 submitted order ids with replay L1 fills plus 1 terminal-liquidation fill id, 776 distinct cancelled order ids; direct `_round_fill_size()` check showed `0.002 * 0.20` rounds to 0 while `0.005 * 0.20` rounds to 0.001.
- `python -m pytest tests/unit/test_risk_guard.py tests/integration/test_replay_engine.py::test_replay_records_allowed_reduce_only_bypass_event -q` — passed, 25 tests.
- `python scripts/run_differential_validation.py --run-id validation_lab_* --engines vectorbt,backtrader,nautilus` — attempted; did not complete locally, stopped without artifact.
- `python scripts/run_differential_validation.py --run-id validation_lab_macd_crossover_btc_binance_1h_20260622 --engines vectorbt` — attempted with and without `NUMBA_DISABLE_JIT=1`; did not complete within 60 seconds, stopped without artifact.
- `python scripts/generate_backtest_external_validation_report.py` — passed; regenerated the PPTX.
- PPTX ZIP smoke — passed; 16 slide XML files present.
- AST parse for `scripts/run_validation_lab_signal_order_check.py` and `scripts/generate_backtest_external_validation_report.py` — passed.
- `python -m pytest tests/unit/test_differential_validation.py -q` — passed, 47 tests; warning that `.pytest_cache` write was denied.
- `make docs-check` — not run because `make` is unavailable in this Windows shell.
- `python scripts/docs/check_doc_metadata.py` — passed with 13 pre-existing metadata warnings.
- `python scripts/docs/check_feature_map_links.py` — passed, 98 concrete paths checked.
- `python scripts/docs/check_doc_impact.py` — exited 0 but reported "no changed files detected"; treat as advisory because `git status` shows changed files.
- `python -m py_compile ...` — not usable because `scripts/__pycache__` write was denied.

## Docs updated
- `docs/validation_lab_report_zh.md`
- `docs/backtest_external_validation_report_zh.pptx`
- `docs/CURRENT_STATE.md`
- `docs/AI_HANDOFF.md`
- `docs/CHANGELOG_AI.md`
- `docs/FAILURE_MODES.md`
- `tasks/2026-06-22-validation-lab-report-context-handoff.md`
- `tasks/2026-06-22-validation-lab-report-session-handoff.md`

## Known limitations / risks
- The BTC/Binance run is signal-to-order evidence, not fresh three-engine portable-validation evidence.
- Long-window differential validation did not complete locally; future work should profile or use a shorter fixture.
- MA/EMA exit attempts were mostly blocked by the 500 USD fat-finger cap; changing that behavior would be a business-rule/risk change requiring explicit approval and manifest work.
- MACD realistic-fill counts are sensitive to queue fraction and exchange lot/min rounding. Treat 779 orders / 13 fill rows as an execution-model finding, not proof that MACD signals rarely touch price.
- The PPTX was smoke-checked as an OpenXML ZIP, not visually inspected in PowerPoint.

## Rollback plan
- Remove the added report/PPT/summary/script/handoff files and revert `scripts/generate_backtest_external_validation_report.py`, `docs/CURRENT_STATE.md`, `docs/AI_HANDOFF.md`, and `docs/CHANGELOG_AI.md`.

## Context Handoff
- See `tasks/2026-06-22-validation-lab-report-context-handoff.md`.

## Questions for human review
- Should reduce-only closes above `max_order_notional_usd` remain fat-finger blocked, or should a separate close-risk policy be designed?
- Should the next validation artifact prioritize short BTC/Binance fixtures or profiling the long-window differential-validation CLI?
- Should the beginner strategy builder live inside the existing config/backtest page or become a separate Strategy Builder view?
- Should realistic replay adopt a calibrated small-order fill policy, or should small residual orders be evaluated only through separate sensitivity runs such as `fill_all_signals`?

## Next recommended task
- Build a short BTC/Binance validation fixture for MA/EMA 10/200 and MACD 12/26/9, then rerun vectorbt/backtrader/Nautilus validation to produce fresh run-scoped `validation_result.json` evidence.

## Human Learning Notes (required)
The useful mental model is three separate questions: did the strategy emit the right signal, did the project turn it into orders/fills under risk rules, and do external engines independently agree on the signal points? This session answered the second question for BTC/Binance and relied on existing fixture evidence for the third; it did not convert the long-window run into promotion evidence. Also separate "price touched" from "fill row exists": queue allocation plus lot/min rounding can make a touched maker order produce zero fill.
