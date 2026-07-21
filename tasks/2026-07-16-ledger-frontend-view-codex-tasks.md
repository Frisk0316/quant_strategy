---
status: current
type: task
owner: claude
created: 2026-07-16
last_reviewed: 2026-07-16
expires: 2026-10-16
superseded_by: null
---

# Codex Task C: Read-only Research Ledger frontend view

Claude-authored plan (user-requested 2026-07-16). Codex implements; Claude
reviews. Motivation: per-run backtest artifacts are visible in the Results and
Validation views, and workstream milestones in the Progress panel, but the
aggregate research picture (which hypotheses are supported/testing/refuted/
shelved, their DSR/PSR, and where K was spent) lives only in the markdown
ledgers. Surface it read-only, reusing the funnel JSON from Task A and the
existing markdown-serve route used by Manual/Progress. No new backend data path.

DEPENDS ON Task A (scripts/run_pipeline_funnel_report.py must emit the funnel
JSON this view consumes). Do not start C until A's report artifact exists.

## Filled Implementation template

```text
Task: Add a read-only "Research / Ledger" frontend view aggregating hypothesis
status + the pipeline funnel, with no new backend data source.

Strategy/spec source: docs/HYPOTHESIS_LEDGER.md (canonical status/DSR/PSR),
  Task A funnel JSON; frontend nav pattern in frontend/app.js (progress entry ~L173),
  markdown-serve route already used by Manual/Progress.

Required behavior:
- New nav entry "研究總表 / Ledger" (group: Analysis) rendered by a new
  frontend/view-ledger.js, mirroring how ProgressView/ManualView are wired in app.js.
- The view fetches (a) the Task A funnel JSON and renders a per-family table:
  family_id, hypothesis_id, status, WF/CPCV/DSR/PSR, n_trials, K used,
  data->power->Stage-3->gate funnel counts; and (b) links each row to its ledger
  entry via the EXISTING markdown-serve allow-list route (add HYPOTHESIS_LEDGER.md
  and EXPERIMENT_REGISTRY.md to the configured allow-list ONLY - no new endpoint).
- Read-only: no mutation, no write API, no strategy/param controls. If the funnel
  JSON is absent, render an explicit "run scripts/run_pipeline_funnel_report.py"
  empty state, not a crash.

PERMITTED FILES (only edit these):
- frontend/view-ledger.js                       (new)
- frontend/app.js                               (nav entry + view wiring only)
- frontend/data.js                              (add the fetch path constant if needed)
- <the markdown allow-list config the Manual/Progress route reads>  (add the two ledger paths)
- tests/  (frontend syntax / route test consistent with existing frontend checks)
- docs/UI_MAP.md                                (document the new view + route)

FORBIDDEN (do not touch):
- src/okx_quant/** trading core, config/risk.yaml
- research/, existing results/** artifacts
- docs/HYPOTHESIS_LEDGER.md, EXPERIMENT_REGISTRY.md content (they are DATA here, read-only;
  you may only add their paths to the serve allow-list, not edit their text)
- Any Results/Validation/Backtest view behavior beyond adding the new nav entry

SCOPE LIMIT: one new read-only view + allow-list two markdown files. No new
backend route, no data mutation, no change to existing views' logic.

REQUIRED ON COMPLETION:
- List changed files (git diff --stat).
- Run: make frontend-check (or the repo's frontend syntax/Playwright equivalent);
  paste the output tail. Report SKIP explicitly if Node is unavailable.
- Update docs/UI_MAP.md per the AGENTS.md docs-update matrix.
- Do not commit unless committing was requested.

ACCEPTANCE CRITERIA (binary):
- [ ] New "研究總表 / Ledger" nav entry renders the funnel table from the Task A JSON.
- [ ] Each row deep-links to its ledger entry through the existing markdown-serve route.
- [ ] Absent funnel JSON -> explicit empty state, no console error / crash.
- [ ] View is strictly read-only (no write API call, no mutation control).
- [ ] The markdown allow-list route serves the two ledgers ONLY on the same binds
      as Manual/Progress (no broader exposure).
- [ ] frontend-check passes (or SKIP reported); diff contains only permitted files.

REPORT: changed files, frontend-check tail, the allow-list file actually edited,
anything about the markdown-serve binding left UNCONFIRMED.
```

## Reviewer notes (Claude)

- Ledgers are the source of truth; this view is a projection. On any conflict the
  markdown wins - the view must not become a second, drifting status store.
- Confirm the markdown-serve route's loopback/non-loopback binding rules before
  widening the allow-list (see AI_HANDOFF "Manual/Progress" note); do not expose
  the ledgers on binds where Manual/Progress files are withheld.
- Fresh-verifier check per docs/ai/MODEL_DISPATCH.md.
