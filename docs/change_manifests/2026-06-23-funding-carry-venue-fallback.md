---
status: current
type: manifest
owner: codex
created: 2026-06-23
last_reviewed: 2026-06-23
expires: none
superseded_by: null
---

# Change Manifest: Funding Carry Venue Fallback

## Summary
Funding-carry replay can again use the existing explicit spot-to-perp synthetic
book fallback when the spot venue-scoped candle series is missing. The fallback
still queries the same venue and does not allow parquet or cross-venue data.

## Business rule(s) affected
R6.4, restored documented venue-scoped provenance behavior.

## Trigger area(s) (DOC_IMPACT_MATRIX)
A5 backtesting.

## Files changed
- `backtesting/replay.py` - allow explicit fallback after a primary venue gap.
- `tests/unit/test_data_loader.py` - regression coverage for same-venue fallback.
- `docs/change_manifests/2026-06-23-funding-carry-venue-fallback.md` - this manifest.

## Behavior delta
- Before: `funding_carry` failed on missing Binance `BTC-USDT` 1H candles before
  trying its explicit `BTC-USDT-SWAP` fallback.
- After: that specific primary venue gap can fall through to the explicit fallback,
  which is still loaded with `exchange='binance'`.
- Money/risk impact: none to PnL, fees, funding sign, sizing, or risk limits.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A - no strategy assumption changed.
- config/: N/A - no runtime parameter changed.
- ADR: N/A - restores ADR-0007/R6.4 behavior; no policy or schema change.

## Docs updated (from DOC_IMPACT_MATRIX row)
- [x] `docs/DATA_FLOW.md` - updated to document explicit same-venue perp fallback for funding-carry spot synthetic books.
- [x] `docs/FEATURE_MAP.md` - reviewed; ownership/tests already point to backtesting/data loader.
- [x] `docs/GOLDEN_CASES.md` - reviewed; G-002 remains unchanged.
- [x] ADR-0002/0005 - reviewed by scope; no result schema or validation gate change.

## Invariants / golden cases
- Invariants checked: I19.
- Golden cases affected: G-002 unchanged.

## Tests / checks run
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_data_loader.py::test_replay_l1_loader_uses_same_venue_fallback_after_primary_venue_gap -q -p no:cacheprovider` - passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_data_loader.py -q -p no:cacheprovider` - passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_doc_metadata.py` - passed with 15 pre-existing metadata warnings.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_feature_map_links.py` - passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_doc_impact.py` - advisory warning remains for unrelated `src/okx_quant/strategies/xs_momentum.py`; A5 warning for this fix cleared.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\smoke\backtest_smoke.py` - entrypoints pass; full replay smoke skipped because the tiny no-DB fixture is a known gap.
- `git diff --check -- backtesting/replay.py tests/unit/test_data_loader.py docs/DATA_FLOW.md docs/change_manifests/2026-06-23-funding-carry-venue-fallback.md` - passed with line-ending warnings only.

## Risks and rollback
- Risks: a future unrelated venue-gap `ValueError` with the same message prefix could fall through only when an explicit fallback is configured.
- Rollback: revert the `backtesting/replay.py` catch block, the regression test, and this manifest.

## Approval
- Human approval required: no - bug fix restores existing documented fallback without changing gates or business-rule policy.
