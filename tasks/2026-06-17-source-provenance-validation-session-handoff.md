---
status: current
type: handoff
owner: codex
created: 2026-06-17
last_reviewed: 2026-06-17
expires: none
superseded_by: null
---

# Session Handoff: Source Provenance Validation - 2026-06-17

## Implementation summary
Added a minimal source-provenance validation gate that reads existing differential-validation output or runs validation for a saved artifact first, then requires DB-backed OHLCV parity and authoritative `ct_val` evidence. Fixture/no-DB results with DB parity `SKIP` now fail this new gate.

## Diff scope
- Files added: `scripts/run_source_provenance_validation.py`, `tests/unit/test_source_provenance_validation.py`, `tasks/2026-06-17-source-provenance-validation-context-handoff.md`, `tasks/2026-06-17-source-provenance-validation-session-handoff.md`.
- Files changed: `Makefile`, `docs/RUNBOOK.md`, `docs/CURRENT_STATE.md`, `docs/CHANGELOG_AI.md`, `docs/KNOWN_ISSUES.md`, `docs/AI_HANDOFF.md`.
- Files deleted: none.

## Business-rule change?
- No. This is validation harness gating and documentation. It does not change PnL, fee, funding, sizing, fills, strategy assumptions, deployment gates, or DB schema.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A.
- config/: N/A.
- ADR: N/A.

## Experiments
- HYPOTHESIS_LEDGER entries: none.
- EXPERIMENT_REGISTRY entries: none.

## Tests / checks run
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_source_provenance_validation.py -q` - 4 passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_source_provenance_validation.py tests\unit\test_all_strategy_signal_validation.py tests\unit\test_differential_validation.py -q` - 50 passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\run_source_provenance_validation.py --help` - passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_doc_metadata.py` - passed with 11 pre-existing warnings.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_feature_map_links.py` - passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_doc_impact.py` - passed; no changed business-rule files detected.
- `git -c safe.directory=C:/quant_strategy diff --check` - passed with CRLF warnings only.

## Docs updated
- `docs/RUNBOOK.md`, `docs/CURRENT_STATE.md`, `docs/CHANGELOG_AI.md`, `docs/KNOWN_ISSUES.md`, `docs/AI_HANDOFF.md`.

## Known limitations / risks
- No DB-backed PASS artifact was generated in this session.
- The new gate is not wired into CI because it needs a reachable DB DSN and seeded canonical candles.
- This still does not prove Nautilus full execution parity, PnL parity, funding settlement parity, or live readiness.

## Rollback plan
- Revert `scripts/run_source_provenance_validation.py`, `tests/unit/test_source_provenance_validation.py`, the Makefile target, updated docs, and this handoff pair.

## Context Handoff
- See `tasks/2026-06-17-source-provenance-validation-context-handoff.md`.

## Questions for human review
- Which saved run should be used for the first DB-backed source-provenance artifact?

## Next recommended task
- Run the source-provenance gate against a saved run with canonical DB candles and authoritative `ct_val` evidence.

## Human Learning Notes (required)
This step turned the earlier review phrase "real-data/source provenance gap" into a concrete pass/fail interface. It narrows the next task to producing real DB evidence, not designing more validation machinery.
