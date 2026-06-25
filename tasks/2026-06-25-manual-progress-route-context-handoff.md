# Context Handoff: Manual Chapters and Standalone Progress Route - 2026-06-25

## Goal (one sentence)
Finish the in-dashboard user manual rewrite and mount the read-only Progress API in the standalone server after Claude/user approval.

## Current state
- Branch: `codex/xs-momentum-universe-scaffold`
- Last known good state: dirty working tree with prior pipeline/data-repair/progress-panel edits preserved.
- In-progress edits (files): `scripts/run_server.py`, `docs/manual/manual.json`, `docs/manual/00-architecture.md` through `docs/manual/80-glossary.md`, `tests/unit/test_routes_manual.py`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`.
- What works right now: manual manifest parses, chapters 00-80 are `written`, manual route tests pass, progress route tests pass, and `scripts.run_server.create_app(...).get('/api/progress')` returns HTTP 200 with no error.
- What does not work / unfinished: `make docs-check` cannot run in this shell because `make` is not installed; direct docs checker scripts were run instead.

## Decisions made (and why)
- Added `/api/progress` to `scripts/run_server.py` because Claude replied "Yes, add it to run_server.py now" and the user passed that approval along.
- Replaced corrupted manual chapters with concise Traditional Chinese content grounded only in existing project docs.
- Fixed the corrupted `tests/unit/test_routes_manual.py` fixture because it blocked validation of the manual route.

## Open questions / unverified assumptions
- None for this follow-up. The manual remains a summary of existing docs, not a new business-rule source.

## Rules in play (preserve verbatim)
- Do-not-touch: `research/`; live/shadow/demo gates; strategy assumptions; result artifacts; unrelated dirty work.
- Business-rule change: none.

## Context to load next (the reading list)
- Source of truth: `docs/DATA_FLOW.md`, `docs/UI_MAP.md`, `docs/FEATURE_MAP.md`, `docs/ai_collaboration.md`, `config/settings.yaml`, `config/strategies.yaml`, `config/risk.yaml`.
- Owning files: manual feature row in `docs/FEATURE_MAP.md`; Progress row in `docs/UI_MAP.md` and `docs/DATA_FLOW.md`.
- Context Pack: `docs/CONTEXT_PACKS/frontend_dashboard.md`.

## Checks run
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_manual_manifest.py tests\unit\test_routes_manual.py -q` -> 4 passed; pytest cache permission warning only.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_routes_progress.py -q` -> 3 passed; pytest cache permission warning only.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -c "from pathlib import Path; from fastapi.testclient import TestClient; from scripts.run_server import create_app; c=TestClient(create_app(Path('results'), Path('frontend'))); r=c.get('/api/progress'); data=r.json(); print(r.status_code, data.get('error'), len(data.get('timeline', [])), len(data.get('branches', [])))"` -> `200 None 60 9`.
- `make docs-check` -> not run; `make` command not found in this Windows shell.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_doc_metadata.py` -> passed with 29 existing warnings.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_feature_map_links.py` -> passed, 141 paths.

## Approvals
- Claude/user approval obtained for adding Progress route to `scripts/run_server.py`.

## Next action (single, concrete)
- Review the combined dirty tree and split commits by topic: pipeline batch/data repair, Progress panel, manual completion/font tweak, and unrelated pre-existing edits.

## Human Learning Notes
The manual route had been blocked by encoding-corrupted test fixture strings, not just missing chapter content. Fixing the reader surface means checking both manifest content and the tiny route smoke tests.
