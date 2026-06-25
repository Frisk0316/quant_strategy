# Context Handoff: Progress Panel 2026-06-25

## Goal (one sentence)
Add a read-only dashboard panel that shows local git timeline and branch progress
without touching trading behavior.

## Current state
- Branch: `codex/xs-momentum-universe-scaffold`.
- Last known good commit / state: dirty tree already contained pipeline batch 1
  Stage 3 work; Progress panel changes are additive and scoped to permitted
  files.
- In-progress edits (files): `src/okx_quant/api/routes_progress.py`,
  `src/okx_quant/api/server.py`, `frontend/view-progress.js`,
  `frontend/index.html`, `frontend/app.js`, `frontend/data.js`, `STATUS.md`,
  `Makefile`, `tests/unit/test_routes_progress.py`, `docs/UI_MAP.md`,
  `docs/FEATURE_MAP.md`, `docs/DATA_FLOW.md`, `docs/AI_HANDOFF.md`,
  `docs/CURRENT_STATE.md`.
- What works right now: `build_progress_payload(Path.cwd())` returns
  `error=None`, current branch, 60 timeline rows, and 9 branch rows.
- What does not work / unfinished: no browser screenshot was captured; standalone
  `scripts/run_server.py` was not changed because it is outside the task's
  permitted files.

## Decisions made (and why)
- Use direct git subprocess calls with UTF-8 decoding because Windows cp950
  failed on commit text.
- Resolve the repo path before passing `safe.directory` because Git rejects a
  relative `"."` safe directory under the sandbox user.
- Keep `STATUS.md` state values ASCII because emoji/corrupt encoding would make
  the parser brittle.
- Return HTTP 200 with `error` on git failure because the panel is read-only and
  should render an unavailable state instead of breaking the app.

## Open questions / unverified assumptions
- Whether `scripts/run_server.py` should also mount `/api/progress`; not changed
  because it was not in permitted scope.

## Rules in play (preserve verbatim)
- Invariants touched: none.
- Domain rules touched: none.
- Do-not-touch: trading-core (`strategies/`, `signals/`, `risk/`, `portfolio/`,
  `execution/`), config gates, DB schema, deployment gates, existing result
  artifacts, unrelated pipeline Stage 3 changes.

## Context to load next (the reading list)
- Source of truth: task attachment, `AI_CONTEXT.md`, `docs/AI_HANDOFF.md`,
  `docs/UI_MAP.md`, `docs/FEATURE_MAP.md`, `docs/DATA_FLOW.md`.
- Owning files / MODULE_BRIEFS: Progress Panel entry in `docs/FEATURE_MAP.md`.
- Context Pack: no Progress-specific pack exists; `docs/CONTEXT_PACKS/README.md`
  says only harness scaffolding exists.

## Checks run
- `node --check` for all Makefile `FRONTEND_JS` files -> passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_routes_progress.py -q` -> 3 passed; pytest cache warning only.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\smoke\api_smoke.py` -> skipped cleanly because `API_BASE_URL` is unset.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_doc_metadata.py` -> passed with existing warnings.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_feature_map_links.py` -> passed.
- Local HTTP probe: `GET http://127.0.0.1:8090/api/progress` -> `error=None`,
  60 timeline rows, 9 branch rows.

## Approvals
- Human approval needed / obtained: no promotion, demo, shadow, live, or business
  rule approval needed. No commit requested.

## Next action (single, concrete)
- Have the user open the dashboard and inspect the `進度 / Progress` panel.

## Human Learning Notes
The local git API needs explicit UTF-8 decoding and an absolute safe-directory
path on Windows; otherwise commit text or sandbox ownership checks can fail
before the route returns useful progress data.
