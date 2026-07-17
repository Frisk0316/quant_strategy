---
status: current
type: handoff
owner: claude
created: 2026-07-16
last_reviewed: 2026-07-16
expires: none
superseded_by: null
---

# Handoff: Strategy History Doc + Frontend Iteration View (planning) — 2026-07-16

## Goal (one sentence)

Plan a Codex task set that produces one document recording all past strategies
(logic, ideation source, results, instruments, pipeline architecture) and
surfaces strategy iteration in the frontend Ledger view.

## Implementation summary

Claude planning session only, no code. Scouted the 2026-07-16 Ledger delivery
and both research ledgers, found the existing view lacks logic/source/
instruments/timeline, and wrote a three-task Codex plan reusing the funnel
JSON pipeline and existing Ledger view instead of new routes or views.

## Current state / diff scope

- Branch: `feature/h014-e052-shadow` at `b2eb27e` (pre-existing uncommitted
  Codex Task A/B/C delivery untouched).
- Files added: `tasks/2026-07-16-strategy-history-doc-frontend-codex-tasks.md`,
  this file. Files changed: `docs/CURRENT_STATE.md` (next action 7),
  `docs/AI_HANDOFF.md` (Next steps item 10). Files deleted: none.
- Works now: plan is complete and self-contained. Unfinished: Tasks A/B/C not
  started by Codex.

## Decisions made (and why)

- Extend `view-ledger.js` + funnel JSON schema v2 instead of a new view/route —
  because the funnel script already parses both ledgers and the view/nav exist;
  would change if per-strategy content outgrows an expandable row.
- Hand-authored `docs/STRATEGY_HISTORY.md` (not generated) — because logic
  summaries need judgment and `research/` is Claude-owned, Codex may only read.
- Benchmark/annualized return declared a known gap (`n/a` where unrecorded) —
  because ledgers only record WF/CPCV Sharpe + DSR/PSR; never fabricate.

## Business-rule change? / Source-of-truth updates / Experiments

- Business-rule change: no (observability/docs only; no manifest, no ADR).
- research/strategy_synthesis.md: N/A. config/: N/A (`workstreams.yaml` not
  touched — no milestone status changed). ADR: N/A.
- HYPOTHESIS_LEDGER / EXPERIMENT_REGISTRY entries: none (read-only inputs).

## Rules in play (preserve verbatim)

- Ledgers are authoritative and read-only for Codex in this task set.
- No generated JSON checked into git (funnel-JSON precedent).
- Do-not-touch: `research/**`, `results/**`, `src/okx_quant/{strategies,
  signals,risk,portfolio,execution}/`, `config/risk.yaml`, all gates.

## Tests / checks run

- None (docs/planning only). Verification commands are specified per task:
  docs-check (A), targeted pytest (B), frontend-check (C).

## Context to load next

- `tasks/2026-07-16-strategy-history-doc-frontend-codex-tasks.md` (the plan),
  `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md`,
  `scripts/run_pipeline_funnel_report.py`, `frontend/view-ledger.js`,
  `docs/UI_MAP.md`; pack: none specific.

## Known limitations / risks / open questions

- Registry Setup/Notes are free text; Task B deliberately keeps them raw
  strings — over-parsing is the main scope-creep risk.
- Markdown-serve allow-list file for `STRATEGY_HISTORY.md` was not located;
  Codex must name the file it touches (flagged UNCONFIRMED in the plan).

## Rollback plan

- Delete the two new task files and revert the two doc edits; nothing else
  changed.

## Approvals

- None needed for planning. Codex execution follows the task file; any gate or
  rule change discovered mid-task requires STOP and human/Claude decision.

## Next action (single, concrete) / next recommended task

- Codex executes Task A of
  `tasks/2026-07-16-strategy-history-doc-frontend-codex-tasks.md`.

## Questions for human review

- Confirm the doc name `docs/STRATEGY_HISTORY.md` and that an expandable-row
  detail (vs. a dedicated per-strategy page) matches your "直觀看到迭代" intent.

## Human Learning Notes (required)

- Most of the requested content (source, logic text, instruments, window,
  metrics) already lives in the two ledgers; the gap was presentation, not
  data. The genuinely missing data are benchmark-vs-buy-and-hold and
  annualized return — recording those systematically would need its own
  approved change to the registry conventions.
