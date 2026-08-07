---
status: current
type: handoff
owner: codex
created: 2026-08-07
last_reviewed: 2026-08-07
expires: none
superseded_by: null
---

# Context Handoff: ADR-0016 phase 3 round runners — 2026-08-07

## Goal (one sentence)
Bind sealed round candidates to existing Stage-2 probes without changing probe
logic, while preserving a fail-loud, resume-safe Stage-3 authorization boundary.

## Current state
- Branch: current user worktree; no branch operation performed.
- Last known good state: targeted phase-3 matrix passes; both live registries are empty.
- In-progress edits: none after final verification.
- What works right now: reviewed-list adapter, breadth recomputation, live min/max
  range validation, Stage-2 checkpoint/authorization halt, and authorized resume.
- What does not work / unfinished: no candidate has a reviewed binding; literature
  identity and the remaining candidate admission/family rulings still block a real round.

## Decisions made (and why)
- Keep Stage-2 and Stage-3 registries separate and empty — because Stage-3
  authorization is candidate-specific and must never inherit a family wildcard.
- Support one allow-listed realized-position breadth formula with a recorded
  field/window — because arbitrary formula evaluation would violate the GenAI boundary.

## Open questions / unverified assumptions
- Claude should confirm future admission packets emit the supported aligned
  realized-position series shape and exact reviewed runner names.

## Rules in play (preserve verbatim)
- Invariants touched: I53 Stage 3 remains pass-only; I54 deterministic code owns
  evidence; I68 breadth is derived from realized positions, never declared.
- Domain rules touched: R6.8 and R6.9 enforcement only; semantics unchanged.
- Do-not-touch: `research/`, existing `results/**`, probes, strategy/risk/
  portfolio/execution modules, and every deployment gate.

## Context to load next (the reading list)
- Source of truth: `docs/ADR/0016-genai-discovery-deterministic-strategy-evaluation.md`.
- Owning files: `backtesting/pipeline_round_runners.py`,
  `backtesting/pipeline_orchestrator.py`, `backtesting/pipeline_round.py`.
- Context Pack: none specific exists; start from `docs/CONTEXT_INDEX.md`.

## Checks run
- Targeted pytest including Stage-2 registry — 46 passed.
- Targeted Ruff — passed.
- Docs metadata/links/ledger and config validation — passed.
- Doc-impact advisory — exit 0 with the expected A5 documentation warning.
- `git diff --check` — passed; line-ending conversion warnings only.

## Approvals
- Infrastructure implementation authorized by the current task; no real round,
  Stage 3, experiment, or deployment authorization was used.

## Next action (single, concrete)
- Claude reviews the phase-3 diff and the future admission-packet binding shape.

## Human Learning Notes
A SHA-256 proves which artifact was referenced, not that a declared number is
true; recomputation belongs immediately before the shared execution boundary.
