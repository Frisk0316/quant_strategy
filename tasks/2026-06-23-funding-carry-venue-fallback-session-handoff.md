# Session Handoff: Funding Carry Venue Fallback - 2026-06-23

## Implementation summary
Fixed a replay startup crash for Binance `funding_carry`: missing venue-scoped `BTC-USDT` spot candles now fall through to the existing explicit `BTC-USDT-SWAP` fallback in `load_l1_books`, with the same `exchange` preserved.

## Diff scope
- Files added: `docs/change_manifests/2026-06-23-funding-carry-venue-fallback.md`, `tasks/2026-06-23-funding-carry-venue-fallback-context-handoff.md`, `tasks/2026-06-23-funding-carry-venue-fallback-session-handoff.md`
- Files changed: `backtesting/replay.py`, `tests/unit/test_data_loader.py`, `docs/DATA_FLOW.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`
- Files deleted: none

## Business-rule change?
- Yes, A5 backtesting/data provenance surface. Change Manifest at `docs/change_manifests/2026-06-23-funding-carry-venue-fallback.md`; DOC_IMPACT_MATRIX checked for A5.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A, no strategy assumption changed.
- config/: N/A, no runtime parameter changed.
- ADR: N/A, no schema or gate policy changed.

## Experiments
- HYPOTHESIS_LEDGER entries: none.
- EXPERIMENT_REGISTRY entries: none.

## Tests / checks run
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_data_loader.py::test_replay_l1_loader_uses_same_venue_fallback_after_primary_venue_gap -q -p no:cacheprovider` - failed before fix, passed after fix.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_data_loader.py -q -p no:cacheprovider` - 8 passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_doc_metadata.py` - passed with 15 pre-existing warnings.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_feature_map_links.py` - passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_doc_impact.py` - advisory warning remains for unrelated XS momentum strategy file; this fix's A5 warning cleared.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\smoke\backtest_smoke.py` - entrypoints pass; full replay smoke skipped by known fixture gap.
- `git diff --check -- backtesting/replay.py tests/unit/test_data_loader.py docs/DATA_FLOW.md docs/change_manifests/2026-06-23-funding-carry-venue-fallback.md` - passed with line-ending warnings only.

## Docs updated
- `docs/DATA_FLOW.md`
- `docs/AI_HANDOFF.md`
- `docs/CURRENT_STATE.md`
- `docs/change_manifests/2026-06-23-funding-carry-venue-fallback.md`

## Known limitations / risks
- The original real DB replay command was not rerun because the exact command was not provided.
- `make` is unavailable in this shell, so equivalent Python commands were run directly.
- Existing unrelated dirty files remain in the working tree, including XS momentum files.

## Rollback plan
- Revert the `backtesting/replay.py` catch block, the added test, the `docs/DATA_FLOW.md` sentence, this manifest, and the two handoff files.

## Context Handoff
- See `tasks/2026-06-23-funding-carry-venue-fallback-context-handoff.md`.

## Questions for human review
- Should Binance funding-carry spot candles be ingested directly, or is same-venue perp synthetic fallback enough for current research runs?

## Next recommended task
- Rerun the original funding-carry replay command against the local DB, then ingest Binance spot candles if direct spot data is required.

## Human Learning Notes (required)
The stack trace's `BTC-USDT` symbol was the clue: the failure was the funding-carry spot leg, not the perp data repair path that had just been fixed.
