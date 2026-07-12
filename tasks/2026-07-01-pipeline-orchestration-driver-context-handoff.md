---
status: archived
type: handoff
owner: human
created: 2026-07-01
last_reviewed: 2026-07-01
expires: none
superseded_by: null
---

# Context Handoff: Pipeline Orchestration Driver Implementation - 2026-07-01

## Goal (one sentence)
Complete Task A from `docs/superpowers/specs/2026-07-01-pipeline-orchestration-driver-design.md`: advisory pipeline orchestrator plus Stage2/Stage3 registries, tests, and required harness docs.

## Current state
- Branch: current working tree at `C:\quant_strategy`; it was already dirty before this task.
- Last known good commit / state: not established in this session; no commit made.
- In-progress edits (files): new orchestrator/registry/CLI/tests plus docs/handoff updates listed in the session handoff.
- What works right now: focused tests pass for `pre_register_batch`, append-only candidate transitions, missing hypothesis ID fail-closed behavior, `NEW` family awaiting status, Stage2 family-keyed registry wrappers, legacy Stage3 `batch_id` guard, and direct execution of `scripts/run_pipeline_stage2_data_probe.py`.
- What does not work / unfinished: no real orchestrator DB run was executed in this session; Task B literature keyword scorer remains unimplemented.

## Decisions made (and why)
- Kept the orchestrator as JSON file IO plus a three-pass status loop, because current batches are capped at <=15 candidates and do not need a scheduler.
- Stopped unknown or `NEW` families at `awaiting_stage2_implementation`, because no family-keyed Stage2 probe exists and auto-backtesting would violate the spec.
- Guarded legacy C1/C2/C3 runners by `batch_id`, because they hardcode `results/pipeline_batch2_20260625/**`.
- Did not update `docs/FEATURE_MAP.md`, because the spec's permitted-file list did not include it; the change manifest records the review.

## Open questions / unverified assumptions
- Whether the next real run should use taxonomy_002 immediately depends on DB availability and a reviewed `--hypothesis-ids` JSON.
- Task B literature keyword scorer remains a separate task.

## Rules in play (preserve verbatim)
- Invariants touched: I29 - append-only orchestrator state, required hypothesis IDs, no silent Stage2/Stage3 advancement for unimplemented families, legacy Stage3 `batch_id` guard, and no writes to durable ledgers.
- Domain rules touched: R6.3, R7.4 enforcement only; rules unchanged.
- Do-not-touch: `src/okx_quant/strategies/`, `signals/`, `risk/`, `portfolio/`, `execution/`, deployment/demo/shadow/live gates, `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md`, existing `results/**` artifacts.

## Context to load next (the reading list)
- Source of truth: `AI_CONTEXT.md`, `docs/CURRENT_STATE.md`, `docs/AI_HANDOFF.md`, `docs/INVARIANTS.md`.
- Owning files / MODULE_BRIEFS: Strategy Research Pipeline Automation in `docs/FEATURE_MAP.md`; `docs/MODULE_BRIEFS/backtesting-engine.md`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.
- Implementation files: `backtesting/pipeline_orchestrator.py`, `backtesting/pipeline_stage2_registry.py`, `backtesting/pipeline_stage3_registry.py`, `scripts/run_pipeline_orchestrator.py`.

## Checks run
- See session handoff for exact commands and results.

## Approvals
- Human approval obtained via current request to complete the task.

## Next action (single, concrete)
- Run the full required verification matrix; if DB is available, run the orchestrator with a reviewed hypothesis-id mapping against taxonomy_002.

## Human Learning Notes
The useful boundary is "registry, not scheduler." A tiny explicit registry gives Codex a safe place to stop when a family is not implemented, while a bigger workflow engine would mostly create new ways to hide the same missing decision.
