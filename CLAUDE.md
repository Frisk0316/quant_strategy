# Claude Code Instructions

@AGENTS.md

`AGENTS.md` carries the shared repo rules (roles, harnesses, file ownership,
verification matrix, hard rules). This file is a ROUTER: per task type it says
what to read, which template to use, and how to verify. Long content lives in
the linked files — never inline it here.

## Context budget (hard caps)

- This file: ≤150 lines, index/routing only.
- This file plus everything it @-imports: ≤500 lines combined.
- Adding a new "always read at session start" file requires explicit user
  approval. If an edit would break a cap, move content into a routed file.
- Why these caps exist: `docs/ai/HARNESS_DIAGNOSIS.md`.

## Claude role (delta on top of AGENTS.md)

- Claude: planning, review, risk analysis, acceptance criteria, docs.
  Codex: implementation of trading core, backtesting workflow, deployment.
- Claude writes code only for docs/review tooling, or when the user explicitly
  assigns an implementation task to Claude.
- Never edit `src/okx_quant/{strategies,signals,risk,portfolio,execution}/` or
  `config/risk.yaml` unless the user explicitly directs it in this session.
- Never claim live/shadow/demo readiness — only gates in
  `docs/ai_collaboration.md` plus explicit user approval can.
- Repo files override chat memory and auto-memory. On conflict, use the
  "Source Of Truth List" in `AI_CONTEXT.md`, then the "Authority Rules" in
  `docs/DOC_LIFECYCLE.md`.
- Precedence between this file and `AGENTS.md`: for Claude-session
  PROCEDURE (session-start reading, session-end handoffs) this file wins —
  it supersedes AGENTS.md's "Mandatory before making changes" reading list
  and its two-file handoff requirement. For shared repo rules (ownership,
  verification matrix, hard rules, harnesses) AGENTS.md wins.

## Session start (exactly this, nothing more)

1. Read `docs/CURRENT_STATE.md`; skim the "next actions" part of
   `docs/AI_HANDOFF.md`.
2. Find your task type in the routing table; read ONLY that row's files.
   Reading any other doc requires a one-line stated reason.
3. Any step needing >300 lines of reading, >5 search rounds, or edits to
   >5 files with a known pattern: dispatch a subagent per
   `docs/ai/MODEL_DISPATCH.md`. The main conversation does not bulk-read.

## Task routing table

| Task type | Read first | Template / protocol | Verify with |
| --- | --- | --- | --- |
| Plan work for Codex | `docs/FEATURE_MAP.md` (owning rows only); `docs/AI_WORKFLOW.md`; relevant `docs/ADR/` | `docs/ai/TASK_TEMPLATES.md` §2 Implementation | binary acceptance criteria in the plan |
| Review a diff/PR | `docs/REVIEW_QUESTIONS.md`, `docs/CRITIQUE_PROTOCOL.md`, `docs/INVARIANTS.md` | `docs/ai/TASK_TEMPLATES.md` §5 Review | review checklist in template |
| Debug a reported bug | `docs/FAILURE_MODES.md`, `docs/GOLDEN_CASES.md` | skill `superpowers:systematic-debugging` | failing case reproduced, then green |
| Business-rule change (PnL/fee/funding/sizing/fills/gates) | `docs/DOMAIN_RULES.md`, `docs/DOC_IMPACT_MATRIX.md` | Change Manifest from `docs/CHANGE_MANIFEST_TEMPLATE.md` | `make docs-impact` |
| Design-heavy / new strategy | `docs/DESIGN_SPACE.md`, `research/strategy_synthesis.md` | `docs/ai/TASK_TEMPLATES.md` §4 Research | user sign-off before build |
| Experiment / backtest run | `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md` | update both ledgers | `make backtest-smoke` |
| Frontend change | `docs/UI_MAP.md` | — | `make frontend-check` |
| Data/ingestion change | `docs/DATA_FLOW.md` | — | `AGENTS.md` "Unit-level Python behavior" row (no dedicated ingestion row exists) |
| Docs/governance only | `docs/DOC_LIFECYCLE.md` | — | `make docs-check` |
| Task type unclear | `docs/CONTEXT_INDEX.md`, relevant `docs/CONTEXT_PACKS/` | ask per `docs/ai/JUDGMENT_RUBRICS.md` §3 | — |

## Operating protocols (read on demand, not up front)

- `docs/ai/MODEL_DISPATCH.md` — who does the work: subagent model/effort
  choice, escalation and downgrade, report contract, fresh-agent verification.
- `docs/ai/JUDGMENT_RUBRICS.md` — when to escalate, when done is done, when to
  stop and ask, wrong-direction signals, quality floor.
- `docs/ai/TASK_TEMPLATES.md` — fill-in dispatch prompts: search,
  implementation, refactor, research, review.
- `docs/ai/MAINTENANCE.md` — which files may be edited freely, where lessons
  are recorded, when to compact.
- `docs/ai/LETTER_TO_FUTURE_SESSIONS.md` — read once before starting a major
  new workstream.

## Session end (single pass, in this order)

1. `docs/CURRENT_STATE.md`: refresh the snapshot; keep the file ≤90 lines.
2. `docs/AI_HANDOFF.md`: update state / do-not-touch / next actions, ≤15 new
   lines; mirror milestone status into `config/workstreams.yaml`.
3. Write ONE file `tasks/YYYY-MM-DD-<topic>-handoff.md` (≤90 lines) covering
   EVERY required field of both `tasks/CONTEXT_HANDOFF_TEMPLATE.md` and
   `tasks/SESSION_HANDOFF_TEMPLATE.md` (fields may be merged, none dropped;
   "n/a" is a valid value), including Human Learning Notes. This single-file
   merge supersedes AGENTS.md's two-file wording for Claude sessions
   (user-approved 2026-07-03).
4. New process lesson? Append to `docs/ai/LESSONS.md` per
   `docs/ai/MAINTENANCE.md`.
5. Move durable history to `docs/CHANGELOG_AI.md`; durable bugs to
   `docs/KNOWN_ISSUES.md`.

If this session has already been compacted/summarized at least once, treat
context as scarce: do steps 1–3 only and note the skipped steps inside the
handoff file.
