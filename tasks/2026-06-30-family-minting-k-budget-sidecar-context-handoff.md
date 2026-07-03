---
status: current
type: handoff
owner: codex
created: 2026-06-30
last_reviewed: 2026-06-30
expires: none
superseded_by: null
---

# Context Handoff: Family-Minting K-Budget + First Idea Sidecar — 2026-06-30

## Goal (one sentence)
Wire true family retry K-budget reporting into family-minting, then generate the
first taxonomy-only advisory idea sidecar for Claude/human review.

## Current state
- Branch: `codex/pipeline-batch1-stage3`.
- Last known good commit / state: pre-existing dirty workspace with one unrelated
  untracked result artifact `results/ui_funding_carry_55708fee_execution_comparison.json`.
- In-progress edits (files): see paired session handoff.
- What works right now:
  - `family_registry_from_text()` parses `EXPERIMENT_REGISTRY.md` Family K-budget rows.
  - `decide_family_minting()` emits `k_used`, `k_limit`, and `at_k_limit`; `inherited_K` is removed.
  - Direct execution of `scripts/run_pipeline_idea_generator.py` works from repo root.
  - First taxonomy-only sidecar exists at `results/idea_batch_20260630_taxonomy_001/`.
- What does not work / unfinished:
  - `hypothesis_ledger_draft.md` is only a draft; it has not been appended to
    `docs/HYPOTHESIS_LEDGER.md`.
  - The 4 generated candidates are `pending_llm`; no Stage 1 full drafts, Stage 2,
    Stage 3, Pass-A, checkpoint①, or backtest has run.

## Decisions made (and why)
- Parse K-budget in the shared checkpoint registry parser so checkpoint and
  family-minting read one family registry shape.
- Keep `n_trials` and K distinct in output because K is retry attempts and
  `n_trials` is grid/selection combinations.
- Add a direct-script regression for `run_pipeline_idea_generator.py` because the
  user-specified command failed when `backtesting` was not on `sys.path`.
- Write an advisory sidecar only; no durable ledger row or backtest was created.

## Open questions / unverified assumptions
- Claude/human must decide which of the 4 pending candidates deserve full Stage 1 drafts.
- `F-S6-TS-MOMENTUM` appears because it is inconclusive/statistical-fail rather
  than refuted in the taxonomy/ledger logic; Claude should decide whether it is a
  true new twist or should be skipped.

## Rules in play (preserve verbatim)
- Invariants touched: I27 - K budget is read from EXPERIMENT_REGISTRY and must not
  be conflated with family-cumulative `n_trials`; I26 remains advisory-only before
  checkpoint review.
- Domain rules touched: R6.3 and R7.4.
- Do-not-touch: `research/strategy_synthesis.md`, durable ledger values,
  `src/okx_quant/strategies/`, `signals/`, `risk/`, `portfolio/`, `execution/`,
  config gates, deployment/demo/shadow/live gates, and existing result artifacts.

## Context to load next (the reading list)
- Source of truth: `AI_CONTEXT.md`, `docs/CURRENT_STATE.md`,
  `docs/AI_HANDOFF.md`, `docs/EXPERIMENT_REGISTRY.md`,
  `results/idea_batch_20260630_taxonomy_001/hypothesis_ledger_draft.md`.
- Owning files / MODULE_BRIEFS: `docs/FEATURE_MAP.md` → Strategy Research
  Pipeline Automation.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_pipeline_family_minting.py -q` — red first: 3 failed for missing `k_used`; green after fix: 8 passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_pipeline_family_minting.py tests\unit\test_pipeline_checkpoint1_check.py tests\unit\test_pipeline_idea_generator.py -q` — 19 passed, pytest cache warning only.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m ruff check <changed Python files>` — passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_doc_metadata.py` — passed with 32 pre-existing warnings.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_feature_map_links.py` — passed, 166 paths.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_human_overview.py` — passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\validate_pipeline.py --check-config-only` — passed.
- `check_doc_impact.py --strict` with process-local `safe.directory=C:/quant_strategy` — passed.

## Approvals
- Human approval needed / obtained: user approved K-budget wiring and first
  sidecar generation. No approval was obtained for durable ledger append,
  Stage 2/3 execution, backtesting, promotion, demo, shadow, live, or config gate
  changes.

## Next action (single, concrete)
- Claude/human review
  `results/idea_batch_20260630_taxonomy_001/hypothesis_ledger_draft.md` and decide
  which pending candidate(s), if any, should be converted into full Stage 1 drafts.

## Human Learning Notes
The first sidecar showed a useful safety pattern: the generator can produce a
small feasible candidate list without consuming ledger budget, but a CLI path can
still fail even when imported unit tests pass. Direct-script tests are worth
adding for user-facing research harness commands.
