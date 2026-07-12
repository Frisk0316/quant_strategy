---
status: current
type: handoff
owner: human
created: 2026-07-03
last_reviewed: 2026-07-03
expires: none
superseded_by: null
---

# Session + Context Handoff: AI harness governance install — 2026-07-03

Combined handoff per new CLAUDE.md session-end step 3.

## Goal (one sentence)

Convert one-off Fable 5 judgment into durable, small-model-executable
governance files (user's explicit meta-task; no trading work).

## Implementation summary

Measured harness waste (~3,000 lines session-start reading; 7-surface
session-end fan-out; self-verification), then rewrote CLAUDE.md as a
routing table with budget caps and created the docs/ai/ protocol set plus
two pinned subagents. Adversarial fresh-context review found 11 issues;
10 fixed, 1 waived (cosmetic).

## Diff scope

- Files added: docs/ai/{HARNESS_DIAGNOSIS,MODEL_DISPATCH,JUDGMENT_RUBRICS,
  TASK_TEMPLATES,MAINTENANCE,LESSONS,LETTER_TO_FUTURE_SESSIONS}.md,
  docs/ai/CLAUDE_md_backup_2026-07-03.txt, .claude/agents/{scout,verifier}.md,
  this handoff. Auto-memory: project_ai_governance_system.md + MEMORY.md line.
- Files changed: CLAUDE.md (full rewrite; backup above).
- Files deleted: none.

## Current state

- Branch: codex/pipeline-batch1-stage3 (this session's files uncommitted;
  tree also carries another session's uncommitted turtle/funding edits).
- Works now: routing table live in CLAUDE.md; scout/verifier agents load
  next session; docs-check passes 0 warnings.
- Unfinished: docs/AI_HANDOFF.md / CURRENT_STATE.md / workstreams.yaml not
  updated (see Decisions); nothing committed.
- Context to load next: CLAUDE.md routing table only; pack n/a.

## Docs updated

- CLAUDE.md (rewrite), docs/ai/* (new), this handoff. FEATURE_MAP / UI_MAP /
  DATA_FLOW / RUNBOOK rows: n/a (no feature, UI, data-path, or command
  behavior changed).

## Business-rule change / source-of-truth / experiments

No business-rule change (governance/docs only) — no Change Manifest.
research/, config/, ADR, HYPOTHESIS_LEDGER, EXPERIMENT_REGISTRY: n/a.

## Decisions made (and why)

- Shared rules live only in AGENTS.md (duplication drifts); CLAUDE.md
  keeps the `@AGENTS.md` import while under the 500-line cap.
- Two session-end handoffs merged into ONE file (diagnosed leak #2) —
  user approved 2026-07-03, cap raised to ≤90 lines.
- New files in docs/ai/, not docs/ root (41 files there already).
- AI_HANDOFF.md / CURRENT_STATE.md / workstreams.yaml NOT updated: they
  carry another session's uncommitted edits; editing risks clobbering.

## Checks run

- docs-check scripts (metadata + feature-map links): pass, 0 warnings.
- Adversarial fresh-context review (paths, conflicts, model facts,
  read-back): 10 findings fixed, re-verified.

## Rules in play / do-not-touch

- Trading-core paths and config/risk.yaml untouched. Working tree carries
  ANOTHER session's uncommitted turtle/funding edits — do not commit this
  session's files mixed with those.

## Open questions / approvals needed

- Approved 2026-07-03: handoff merge; handoff cap ≤90. Committing these
  files is assigned to Codex (nothing committed by this session).
- UNCONFIRMED: Fable→Opus reroute quota accounting (official docs silent).

## Next action (single, concrete)

Once the turtle-session edits are merged: add a one-line pointer to this
system in docs/AI_HANDOFF.md and mirror workstreams.yaml.

## Human Learning Notes (required)

The harness's own ceremony was the top token consumer — ~3,000 lines of
mandated reading per session, each line individually reasonable. Process
debt accretes exactly like code debt and needs the same explicit deletion
budget. Second: what survives model downgrades is structure (routing,
binary acceptance criteria, fresh-context verification), not cleverness —
so invest there, not in longer instructions.
