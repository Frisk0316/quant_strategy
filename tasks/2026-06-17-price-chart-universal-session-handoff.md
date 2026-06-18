---
status: current
type: handoff
owner: codex
created: 2026-06-17
last_reviewed: 2026-06-17
expires: none
superseded_by: null
---

# Session Handoff: Universal Price Chart - 2026-06-17

## Implementation summary
Changed the Backtest Price + Trade Markers card from one global loading branch to one panel per selected symbol. Price fetch failures now mark that symbol as `error`, marker fetch failures still degrade to no markers, and empty price responses show a per-symbol empty state.

## Diff scope
- Files added: `tasks/2026-06-17-price-chart-universal-context-handoff.md`, `tasks/2026-06-17-price-chart-universal-session-handoff.md`.
- Files changed: `frontend/view-backtest.js`, `docs/UI_MAP.md`, `docs/KNOWN_ISSUES.md`, `docs/AI_HANDOFF.md`.
- Files deleted: none.

## Business-rule change?
- No. No Change Manifest or DOC_IMPACT business-rule rows required.

## Source-of-truth updates
- `research/strategy_synthesis.md`: N/A.
- `config/`: N/A.
- ADR: N/A.

## Experiments
- HYPOTHESIS_LEDGER entries: none.
- EXPERIMENT_REGISTRY entries: none.

## Tests / checks run
- Static RED check: failed before edit with `global price-card loading gate is still present`; passed after edit.
- `node --check frontend\view-backtest.js` - passed.
- Direct `make frontend-check` equivalent: `node --check` passed for `frontend/data.js`, `frontend/charts.js`, `frontend/view-config.js`, `frontend/view-backtest.js`, `frontend/view-results.js`, `frontend/view-validation.js`, `frontend/view-trades.js`, `frontend/view-glossary.js`, and `frontend/app.js`.
- `make frontend-check` - not run; `make` is unavailable in this Windows shell.
- `python -m pytest ...` - not usable through the default `python` launcher in this sandbox; reran with the explicit Python 3.12 path.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_frontend_static_mime.py tests\unit\test_backtest_visual_fallbacks.py -v` - 13 passed, 1 `.pytest_cache` permission warning.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_doc_metadata.py` - passed with 12 pre-existing lifecycle metadata warnings.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_feature_map_links.py` - passed.
- `git diff --check -- frontend/view-backtest.js docs/UI_MAP.md docs/KNOWN_ISSUES.md docs/AI_HANDOFF.md` - passed with CRLF conversion warnings.

## Docs updated
- `docs/UI_MAP.md`: documented strategy-agnostic price panels and technical-only indicator overlays.
- `docs/KNOWN_ISSUES.md`: recorded missing browser-level interaction coverage for progressive chart loading.
- `docs/AI_HANDOFF.md`: recorded this UI-only workstream result.

## Known limitations / risks
- No browser-level automated test was added because the repo has no Preact/browser interaction harness for this view.
- Existing unrelated staged/unstaged multi-venue files were present before this branch and must stay out of this commit.

## Rollback plan
- Revert the task commit; no data migration or artifact cleanup is required.

## Context Handoff
- See `tasks/2026-06-17-price-chart-universal-context-handoff.md`.

## Questions for human review
- Should a tiny browser smoke harness be added later for Backtest chart interactions?

## Next recommended task
- Add one browser-level regression for selecting multiple symbols once a frontend test harness exists.

## Human Learning Notes (required)
The backend fallback already covered older non-technical runs. The visible freeze came from the UI summary/loading branch, so the smallest fix was to stop treating selected symbols as one shared loading unit.
