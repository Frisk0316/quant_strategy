# Context Handoff: XS Trials And Idea Probe Follow-Up - 2026-06-30

## Goal (one sentence)
Close the F-XS-MOMENTUM family-cumulative `n_trials` inheritance gap and wire
B-half idea enumeration to real Stage-2 data-availability probe results with
taxonomy text as fallback only.

## Current state
- Branch: `codex/xs-momentum-universe-scaffold` working tree with prior
  K-budget/idea-sidecar edits still uncommitted.
- Last known good commit / state: before this follow-up, §7a K-budget fields and
  first taxonomy-only sidecar were already implemented and tested.
- In-progress edits (files): `backtesting/pipeline_checkpoint1.py`,
  `backtesting/pipeline_idea_generator.py`, targeted unit tests, current-state
  docs, `config/workstreams.yaml`, and
  `docs/change_manifests/2026-06-30-xs-trials-and-idea-probe.md`.
- What works right now: `family_registry_from_text()` reads
  F-XS-MOMENTUM as 24 trials and K=2/2; C2 funding-carry remains 48 and K=1/2;
  `enumerate_gaps()` uses supplied Stage-2 `data_availability` PASS/FAIL before
  taxonomy fallback.
- What does not work / unfinished: the generated
  `results/idea_batch_20260630_taxonomy_001/hypothesis_ledger_draft.md` still
  needs Claude/human review before any durable ledger append or Stage 2/3 run.

## Decisions made (and why)
- Did not edit `docs/EXPERIMENT_REGISTRY.md` historical Trials cells - the spec
  forbids changing ledger/registry values in this scope, and E-005 already
  contains the authoritative "at least 24 trials" family-cumulative note.
- Parser honors explicit family-cumulative notes/overrides and otherwise keeps
  the historical max-row fallback - because the registry contains mixed-era rows
  where newer rows already store cumulative values and some refit rows should
  not be double-counted.
- B-half probe consumes Stage-2 `FeasibilityResult` / `FeasibilityCheck` / dict
  results and falls back to taxonomy only when the probe has no answer - because
  the Stage-2 checker remains the authoritative data gate.

## Open questions / unverified assumptions
- Future registry rows must continue to state family-cumulative `n_trials`
  clearly; otherwise parser fallback may preserve a stale max-row value.

## Rules in play (preserve verbatim)
- Invariants touched: I26 - checkpoint summaries must reconcile summary and
  CPCV `n_trials` to `docs/EXPERIMENT_REGISTRY.md`; I27 - automated idea
  ingestion must inherit family status, family-cumulative `n_trials`, and K
  budget rather than minting around prior trials.
- Domain rules touched: R6.3 and R7.4.
- Do-not-touch: `src/okx_quant/strategies/`, `src/okx_quant/signals/`,
  `src/okx_quant/risk/`, `src/okx_quant/portfolio/`,
  `src/okx_quant/execution/`, `config/risk.yaml`, deployment/demo/shadow/live
  gates, research truth files, durable ledger values, existing result artifacts.

## Context to load next (the reading list)
- Source of truth: `AI_CONTEXT.md`, `docs/AI_HANDOFF.md`,
  `docs/CURRENT_STATE.md`, `docs/EXPERIMENT_REGISTRY.md`,
  `docs/HYPOTHESIS_LEDGER.md`.
- Owning files / MODULE_BRIEFS: `docs/FEATURE_MAP.md` section "Strategy
  Research Pipeline Automation".
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/unit/test_pipeline_checkpoint1_check.py tests/unit/test_pipeline_family_minting.py tests/unit/test_pipeline_idea_generator.py -q` - red first: 5 failed; green after fix: 24 passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/unit/test_pipeline_checkpoint1_check.py tests/unit/test_pipeline_family_minting.py tests/unit/test_pipeline_idea_generator.py tests/unit/test_pipeline_feasibility.py tests/unit/test_pipeline_stage2_check.py -q` - 40 passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m ruff check backtesting/pipeline_checkpoint1.py backtesting/pipeline_idea_generator.py tests/unit/test_pipeline_checkpoint1_check.py tests/unit/test_pipeline_family_minting.py tests/unit/test_pipeline_idea_generator.py` - passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_doc_metadata.py` - passed with 32 pre-existing metadata warnings.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_feature_map_links.py` - passed, 166 concrete paths checked.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_human_overview.py` - passed, 2 overviews OK.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\validate_pipeline.py --check-config-only` - passed.
- `check_doc_impact.py --strict` with process-local `safe.directory=C:/quant_strategy` - passed, 17 changed files.
- `make docs-check` - not run; `make` is unavailable in this Windows shell.

## Approvals
- Human approval needed / obtained: no additional approval required for this
  advisory checker/filter wiring; user explicitly requested the two follow-up
  fixes.

## Next action (single, concrete)
- Have Claude/human review
  `results/idea_batch_20260630_taxonomy_001/hypothesis_ledger_draft.md` before
  appending any durable ledger rows or running Stage 2/3.

## Human Learning Notes
The registry is mixed-era: some rows carry per-run grid counts, while newer rows
carry family-cumulative counts. A safe parser cannot blindly sum or blindly max;
future rows should state family-cumulative `n_trials` explicitly.
