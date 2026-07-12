---
status: archived
type: handoff
owner: codex
created: 2026-06-30
last_reviewed: 2026-06-30
expires: none
superseded_by: null
---

# Context Handoff: Family-Minting Checker - 2026-06-30

## Goal (one sentence)
Implement `mechanism-taxonomy.md` §7 so automatic idea ingestion cannot mint a fresh family budget when a candidate signal is too close to an existing family.

## Current state
- Branch: current workspace branch with pre-existing dirty C2/C3/checkpoint docs and artifacts.
- Last known good commit / state: not changed by this handoff.
- In-progress edits (files): family-minting checker, CLI, tests, I27, manifest, AI handoff/current state/workstream docs.
- What works right now: `decide_family_minting()` reads caller-supplied candidate/reference signals plus `docs/EXPERIMENT_REGISTRY.md`, computes pairwise-complete absolute correlation, and returns ASSIGN/MINT/NEEDS_HUMAN/SKIP_RECOMMENDED.
- What does not work / unfinished: no idea-generation driver, no literature corpus ingestion, and no automatic reference-signal fetcher; callers must supply reference signals.

## Decisions made (and why)
- Used stdlib Pearson correlation on lists or dict-shaped series; no pandas/numpy dependency is needed for this pure checker.
- Reused `backtesting.pipeline_checkpoint1.family_registry_from_text()` for family trial/status lookup instead of writing a second registry parser.
- `inherited_K` currently mirrors inherited family cumulative trials because the ledger has no separate machine-readable K field.
- CLI always exits 0 for valid advisory decisions; SKIP_RECOMMENDED/NEEDS_HUMAN are not automatic discard gates.

## Open questions / unverified assumptions
- Whether the next implementation should use `docs/superpowers/specs/2026-06-30-idea-generator-frontend-design.md` §6 before literature corpus work.
- Whether the ledger should eventually add a separate explicit K field instead of reusing cumulative trials as the machine-readable proxy.

## Rules in play (preserve verbatim)
- Invariants touched: I27 - high-correlation candidates must ASSIGN/SKIP instead of MINT.
- Domain rules touched: R6.3 and R7.4.
- Do-not-touch: `research/**`, strategy/signals/risk/portfolio/execution, CPCV/WF/differential/replay/DSR internals, config gates, ledger values, existing `results/**`.

## Context to load next (the reading list)
- Source of truth: `AI_CONTEXT.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `docs/EXPERIMENT_REGISTRY.md`, `docs/INVARIANTS.md`.
- Owning files / MODULE_BRIEFS: `docs/FEATURE_MAP.md` Pipeline Batch / research-pipeline entries.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_pipeline_family_minting.py -q` -> 6 passed, pytest cache warning only.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_pipeline_family_minting.py tests\unit\test_pipeline_checkpoint1_check.py -q` -> 11 passed, pytest cache warning only.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_doc_metadata.py` -> passed with 32 pre-existing metadata warnings.
- `check_doc_impact.py` via Python plus process-local `safe.directory=C:/quant_strategy` -> passed.
- `make docs-check` / `make docs-impact` -> unavailable in this Windows shell.

## Approvals
- Human approval needed / obtained: no approval for promotion, deployment, config gates, strategy changes, or result artifact mutation was requested or obtained.

## Next action (single, concrete)
Hand the next session to the idea-generator front-end / literature corpus lane.

## Human Learning Notes
The family-minting guard is only as good as the reference signals supplied by the future ingestion driver. The safe default is advisory: suspicious relabels are blocked from MINT, but humans still decide true mechanism novelty.
