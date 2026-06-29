# Session Handoff: Manual Chapters and Standalone Progress Route - 2026-06-25

## Implementation summary
Completed the in-dashboard manual rewrite from architecture through glossary, fixed the manual manifest and route test fixture, and confirmed the standalone `scripts/run_server.py` app serves the already-built read-only Progress API.

## Diff scope
- Files added: `tasks/2026-06-25-manual-progress-route-context-handoff.md`, `tasks/2026-06-25-manual-progress-route-session-handoff.md`.
- Files changed: `scripts/run_server.py`, `docs/manual/manual.json`, `docs/manual/00-architecture.md`, `docs/manual/10-backtest-validation.md`, `docs/manual/20-strategies.md`, `docs/manual/30-risk-limits.md`, `docs/manual/40-data-pipeline.md`, `docs/manual/50-deployment-gates.md`, `docs/manual/60-frontend-views.md`, `docs/manual/70-config-files.md`, `docs/manual/80-glossary.md`, `tests/unit/test_routes_manual.py`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`.
- Files deleted: none.

## Business-rule change?
- No. Manual text summarizes existing rules only; no Change Manifest needed for this follow-up.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A.
- config/: N/A.
- ADR: N/A.

## Experiments
- HYPOTHESIS_LEDGER entries: none.
- EXPERIMENT_REGISTRY entries: none.

## Tests / checks run
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_manual_manifest.py tests\unit\test_routes_manual.py -q` -> 4 passed; pytest cache permission warning only.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_routes_progress.py -q` -> 3 passed; pytest cache permission warning only.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -c "from pathlib import Path; from fastapi.testclient import TestClient; from scripts.run_server import create_app; c=TestClient(create_app(Path('results'), Path('frontend'))); r=c.get('/api/progress'); data=r.json(); print(r.status_code, data.get('error'), len(data.get('timeline', [])), len(data.get('branches', [])))"` -> `200 None 60 9`.
- `make docs-check` -> not run; `make` command not found in this Windows shell.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_doc_metadata.py` -> passed with 29 existing warnings.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_feature_map_links.py` -> passed, 141 paths.

## Docs updated
- `docs/manual/manual.json`
- `docs/manual/00-architecture.md`
- `docs/manual/10-backtest-validation.md`
- `docs/manual/20-strategies.md`
- `docs/manual/30-risk-limits.md`
- `docs/manual/40-data-pipeline.md`
- `docs/manual/50-deployment-gates.md`
- `docs/manual/60-frontend-views.md`
- `docs/manual/70-config-files.md`
- `docs/manual/80-glossary.md`
- `docs/AI_HANDOFF.md`
- `docs/CURRENT_STATE.md`

## Known limitations / risks
- Existing manual chapters 00-80 were rewritten; no known unreadable manual chapter remains in this pass.
- `make docs-check` could not run because `make` is unavailable.

## Rollback plan
- Revert this follow-up by restoring the changed manual files, `tests/unit/test_routes_manual.py`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, and removing the two handoff files. Remove the `make_progress_router` include from `scripts/run_server.py` only if the standalone Progress endpoint is no longer desired.

## Context Handoff
- See tasks/2026-06-25-manual-progress-route-context-handoff.md.

## Questions for human review
- Should chapters 00-30 be re-encoded/re-written in the same readable Traditional Chinese style in a separate docs-only pass?

## Next recommended task
- Split the current dirty tree into topic commits so the manual/progress UI work does not get mixed with pipeline batch and market-data repair changes.

## Human Learning Notes (required)
The manual backlog was ready to finish after the Progress panel; the hidden blocker was corrupted fixture text in `test_routes_manual.py`, which made validation fail before content quality could even be assessed.
