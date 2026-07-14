---
status: archived
type: handoff
owner: human
created: 2026-07-07
last_reviewed: 2026-07-07
expires: none
superseded_by: null
---

# Context Handoff: F-OI-POSITIONING Stage-3 Task B - 2026-07-07

## Goal (one sentence)
Complete H-012/F-OI-POSITIONING Task B Stage-3 preflight, research backtest runner, checkpoint artifacts, and documentation without touching live trading code.

## Current state
- Branch: `codex/pipeline-batch1-stage3`.
- Last known good commit / state: dirty working tree with OI Stage-3 implementation and E-037 artifacts; no commit made.
- In-progress edits (files): `backtesting/oi_positioning_backtest.py`, `scripts/run_oi_positioning_checkpoint.py`, registry/contract tests, docs ledgers/handoffs/workstreams, and manifest.
- What works right now: OI contract-count loader excludes suspect rows and never uses `value_num`; no same-day trading leak test passes; Stage-3 runner produced E-037 artifacts.
- What does not work / unfinished: checkpoint1 auto status is FAIL because DSR 0.7220 and PSR 0.8484 are below 0.95; next step is review, not promotion.

## Decisions made (and why)
- Added `backtesting/oi_positioning_backtest.py` as a research-only module patterned after the funding-xs vectorized runner because Task B forbids trading-core changes.
- Used `external_observations.fields.open_interest_contracts` only, with `quality_status='suspect'` excluded, because the Stage-1 spec and Task B explicitly forbid `value_num`.
- Stopped at checkpoint1 after E-037 as required; no retry, adapter, demo, shadow, live, or gate change was made.
- Added `oi_positioning` as adapter-required in `REFERENCE_VALIDATION_CONTRACTS` so portable validation honestly blocks promotion.

## Open questions / unverified assumptions
- Claude/user must review whether H-012 remains `testing`, is refuted, or deserves any ex-ante retry rationale.
- Human review still needs leak-lag spot check, retry-vs-new-family judgment, and portable block reason review from `checkpoint1_auto.json`.

## Rules in play (preserve verbatim)
- Invariants touched: I13/R6.3 family-cumulative `n_trials` must reconcile; I16 ct_val provenance must be authoritative; R7.1 idealized fills cannot be promotion evidence.
- Domain rules touched: R3.1 funding cashflow applied; no rule text changed.
- Do-not-touch: `research/`, existing historical result artifacts outside new F-OI files, trading core under `src/okx_quant/{strategies,signals,risk,portfolio,execution}`, config risk/live/shadow/demo gates.

## Context to load next (the reading list)
- Source of truth: `research/strategy_synthesis.md`, `docs/superpowers/specs/2026-07-04-f-oi-positioning-hypothesis.md`, `docs/backtest_live_parity_plan.md`, `config/`.
- Owning files / MODULE_BRIEFS: `docs/FEATURE_MAP.md`, `docs/DATA_FLOW.md`, `docs/RUNBOOK.md`, `backtesting/oi_positioning_backtest.py`, `scripts/run_oi_positioning_checkpoint.py`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run
- `python -m pytest tests/unit/test_oi_positioning_backtest.py tests/unit/test_pipeline_stage3_registry.py tests/unit/test_pipeline_batch2_contracts.py tests/unit/test_pipeline_batch1_contracts.py tests/unit/test_pipeline_checkpoint1_check.py -q` -> 23 passed.
- `python -m pytest tests/unit/test_differential_validation.py -q` -> 47 passed.
- `python scripts/run_oi_positioning_checkpoint.py` -> wrote `summary.json`, `family_minting*.json`.
- `python -m scripts.run_pipeline_checkpoint1_check --summary results\idea_batch_20260701_taxonomy_002\f_oi_positioning\summary.json --registry docs\EXPERIMENT_REGISTRY.md --output results\idea_batch_20260701_taxonomy_002\f_oi_positioning\checkpoint1_auto.json` -> exit 1 expected; checkpoint status FAIL.
- `python scripts/validate_pipeline.py --check-config-only` -> passed.
- `python -m pytest tests/unit/test_routes_progress.py::test_shipped_workstreams_yaml_is_valid -q` -> 1 passed.
- `python scripts/docs/check_doc_metadata.py` -> passed.
- `python scripts/docs/check_feature_map_links.py` -> passed.
- `python scripts/docs/check_doc_impact.py --strict` with temporary `safe.directory` env -> passed.
- `git diff --check` -> passed; only CRLF normalization warnings.

## Approvals
- Human approval needed / obtained: none for research-only Task B implementation; explicit approval needed before any retry/adapter/demo/shadow/live follow-up.

## Next action (single, concrete)
- Ask Claude/user to review E-037 checkpoint results and decide H-012 verdict/retry policy before any further implementation.

## Human Learning Notes
The first 120-second runner attempts looked like a DB blocker, but the full DB query was simply slow; the full Stage-3 run took about 111 minutes. For future full-window 30+ symbol DB Stage-3 runs, start with a long timeout and avoid interpreting early silence as failure.
