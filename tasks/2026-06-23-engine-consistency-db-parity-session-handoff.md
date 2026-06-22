---
status: current
type: handoff
owner: codex
created: 2026-06-23
last_reviewed: 2026-06-23
expires: none
superseded_by: null
---

# Session Handoff: Engine Consistency Smoke + Binance 1H DB Parity — 2026-06-23

## Implementation summary
Added an offline engine-consistency smoke for MA/EMA/MACD real Binance 1H fixtures and advanced the Binance 1H DB parity task by seeding 20,400 Binance 1H canonical rows, then filling the remaining 2024-04-29 day with direct Binance 1H data. The smoke passes locally in 27.581s; MA and EMA fixtures each cover 960 bars with 5 signals, and MACD covers 120 bars with 5 signals. Existing validation-lab artifacts still need regeneration because they were produced before the data repair.

## Diff scope
- Files added: `scripts/run_engine_consistency_smoke.py`, `scripts/resample_binance_1h_canonical.py`, `tests/unit/test_engine_consistency_smoke.py`, `tests/fixtures/engine_consistency/**`, this handoff pair.
- Files changed: `Makefile`, `docs/RUNBOOK.md`, `docs/FEATURE_MAP.md`, `docs/DATA_FLOW.md`, `docs/KNOWN_ISSUES.md`, `docs/CURRENT_STATE.md`, `docs/AI_HANDOFF.md`, `docs/CHANGELOG_AI.md`.
- Files deleted: none.

## Business-rule change?
- No. The changes add a smoke, a data-population helper, and docs. No PnL/fee/funding/sizing/fill/gate semantics changed.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A.
- config/: N/A.
- ADR: N/A.

## Experiments
- HYPOTHESIS_LEDGER entries: none.
- EXPERIMENT_REGISTRY entries: none.

## Tests / checks run
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_engine_consistency_smoke.py -q` — 2 passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\run_engine_consistency_smoke.py` - PASS in 27.581s.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\resample_binance_1h_canonical.py --dsn postgresql://quant:changeme@localhost:5432/quant --dry-run` — before counts confirmed no Binance 1H rows.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\resample_binance_1h_canonical.py --dsn postgresql://quant:changeme@localhost:5432/quant` — seeded 20,400 rows.
- DB-backed MA source-provenance validation with vectorbt before the targeted day repair - FAIL: `db_parity.status == FAIL`, `canonical_source_primary == "binance"`, `missing_in_db=24`, `value_mismatches=0`.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\download_binance_data.py --inst BTC-USDT-SWAP --bar 1H --start 2024-04-29 --end 2024-04-30 --dsn postgresql://quant:changeme@localhost:5432/quant` - wrote 24 Binance 1H rows to local parquet and DB.
- Local parquet vs DB canonical Binance 1H check for 2024-04-29 - 24 rows, 0 close mismatches.
- DB-backed MA source-provenance validation against the old artifact after filling DB - FAIL: `db_rows=20400`, `missing_in_db=0`, `value_mismatches=24`; old artifact is stale.

## Docs updated
- `docs/RUNBOOK.md`, `docs/FEATURE_MAP.md`, `docs/DATA_FLOW.md`, `docs/KNOWN_ISSUES.md`, `docs/CURRENT_STATE.md`, `docs/AI_HANDOFF.md`, `docs/CHANGELOG_AI.md`.

## Known limitations / risks
- DB parity is not complete for existing validation-lab artifacts. The current evidence is a useful stale-artifact failure, not a PASS.
- The local `python` command resolves to the Windows Store shim in this sandbox; checks used the explicit Python 3.12 path.
- Further DB diagnostics were blocked by the escalation/usage limit after the failed validation run.

## Rollback plan
- Remove the added smoke/helper/test/fixture/handoff files and revert the listed docs/Makefile edits. DB data writes are external state; if rollback is needed, remove the seeded Binance 1H rows for the affected window only after confirming with the user.

## Context Handoff
- See `tasks/2026-06-23-engine-consistency-db-parity-context-handoff.md`.

## Questions for human review
- Should the next pass regenerate only MA first for a quick DB-parity proof, or regenerate MA/EMA/MACD together?
- Should `make engine-consistency-smoke` be wired into CI after this branch is cleaned up?

## Next recommended task
- Regenerate the validation-lab Binance 1H artifacts from repaired data and rerun source-provenance validation to PASS.

## Human Learning Notes (required)
The broad no-Binance-1H-canonical problem and the one-day 2024-04-29 gap are now fixed. The next failure is cleaner: old validation artifacts still contain pre-repair prices.
