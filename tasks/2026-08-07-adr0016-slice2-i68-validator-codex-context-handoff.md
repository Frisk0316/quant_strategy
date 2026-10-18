---
status: current
type: handoff
owner: codex
created: 2026-08-07
last_reviewed: 2026-08-07
expires: none
superseded_by: null
---

# Context Handoff: ADR-0016 slice 2 I68 validator — 2026-08-07

## Goal (one sentence)
Make ADR-0016 sealing enforce I68 and provide one hash-bound sequential
seal/execute/reconcile command without running a real round.

## Current state
- Branch: `claude/ops-dsn-fix-and-db-backup` (shared dirty worktree).
- Last known good commit / state: `df4e75d`; this delivery is uncommitted.
- In-progress edits: `backtesting/pipeline_round.py`,
  `backtesting/pipeline_orchestrator.py`, `scripts/run_pipeline_orchestrator.py`,
  their two unit tests, I68 verification, the ADR-0016 Change Manifest,
  `docs/AI_HANDOFF.md`, `docs/CHANGELOG_AI.md`, and `config/workstreams.yaml`.
- What works right now: synthetic I68 validation, sealing, ordered execution,
  atomic per-candidate resume, manifest mutation refusal, and reconciliation.
- What does not work / unfinished: the phase-3 `signal_ref` runner registry is
  intentionally empty, so no real complete round can seal or run.

## Decisions made (and why)
- Reused the existing round manifest and orchestrator modules because a new
  workflow framework would add no contract coverage.
- Kept DB locators allow-listed and runner execution sequential because the
  task forbids generated SQL/code and concurrency is not justified.
- Missing or invalid breadth provenance records breadth 1 but also makes the
  candidate uncounted, preserving both I68's fail-closed value and quota rule.

## Open questions / unverified assumptions
- Phase 3 must define reviewed `signal_ref` runners before any real round.
- Phase 2 literature identity and enough candidate supply remain absent.

## Rules in play (preserve verbatim)
- I68: every counted candidate needs DB-confirmed dataset numbers, positive
  gross/cost bps with gross provenance, and artifact-derived breadth; missing
  breadth fails closed to 1 and the candidate does not count.
- Domain rules: R6.8 and R9.5; no ratio gate was added.
- Do not touch: strategy/signal/risk/portfolio/execution, research, existing
  results, ledgers, differential validation, or deployment gates.

## Context to load next (the reading list)
- Source of truth: ADR-0016, I68, the slice-2 task, and the existing Change
  Manifest.
- Owning files: `backtesting/pipeline_round.py`,
  `backtesting/pipeline_orchestrator.py`, `scripts/run_pipeline_orchestrator.py`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run
- Targeted pytest — 23 passed; cache-write permission warning only.
- Targeted Ruff — passed.
- Docs metadata, feature links, and ledger consistency — passed.
- Doc impact advisory — exit 0 with the expected A5 warning because the task
  forbids edits to DATA_FLOW/FEATURE_MAP/GOLDEN_CASES; review recorded in the
  Change Manifest.
- Config validation — passed.

## Approvals
- Infrastructure build approved by the user through the assigned task. A real
  round remains a separate approval.

## Next action (single, concrete)
- Claude reviews the slice-2 diff against the binary acceptance list.

## Human Learning Notes
Hash-bound resume needs a checkpoint after each candidate, not just a sealed
manifest: otherwise a process interruption would make the command rerun
already completed candidates. The empty runner registry is an intentional
honesty boundary, not an unfinished workaround.
