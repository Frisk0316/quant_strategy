# Codex Instructions

This repository uses `AI_CONTEXT.md` for project onboarding and `docs/ai_collaboration.md` as the shared collaboration contract between Codex, Claude, and the user.

## Role

Codex is primarily responsible for **implementation, tests, backtesting workflow, config checks, and deployment readiness**. Claude handles research, strategy review, and risk critique.

## Mandatory before making changes

1. Read `AI_CONTEXT.md`.
2. Read `docs/AI_HANDOFF.md`, `docs/AI_WORKFLOW.md`, `docs/ai_collaboration.md`, `docs/DOC_LIFECYCLE.md`, `docs/FEATURE_MAP.md`, and any relevant ADR in `docs/ADR/`.
3. Run `git status --short` to check for existing changes.
4. Do not overwrite unrelated user, Claude, or other Codex-session changes.
5. Treat `research/strategy_synthesis.md`, `docs/backtest_live_parity_plan.md`, and `config/` as truth sources.
6. Locate the owning feature/files before editing; prefer `docs/FEATURE_MAP.md`, `docs/UI_MAP.md`, and `docs/DATA_FLOW.md`.
7. Read `docs/CONTEXT_INDEX.md` to rebuild context from files, not chat history, and load the relevant `docs/CONTEXT_PACKS/` pack for the task.

## Harnesses

Three harnesses govern how work is done. Do not rely on chat history as a source of truth.

### Doc Sync Harness

- `docs/DOMAIN_RULES.md` is the registry of business rules (PnL, fees, funding, sizing, risk, fills, data provenance, gates).
- Every **business-rule change** (any area marked *Manifest? = Yes* in `docs/DOC_IMPACT_MATRIX.md`) must create or update a Change Manifest from `docs/CHANGE_MANIFEST_TEMPLATE.md` and check the impact matrix.
- Every **major rule/policy change** adds an ADR (`docs/ADR/README.md`).
- `make docs-impact` runs `scripts/docs/check_doc_impact.py` (advisory by default, `--strict` for gating).

### Intelligence Harness

- Every **design-heavy task** starts with design-space expansion (`docs/DESIGN_SPACE.md`) and the relevant questions (`docs/QUESTION_BANK.md`, `docs/MENTAL_MODELS.md`).
- Every **experiment** updates `docs/HYPOTHESIS_LEDGER.md` and `docs/EXPERIMENT_REGISTRY.md`.
- Every **new bug class** updates `docs/FAILURE_MODES.md` and, where possible, strengthens `docs/INVARIANTS.md` and a test.
- Reviews use `docs/REVIEW_QUESTIONS.md` and `docs/CRITIQUE_PROTOCOL.md`; correctness anchors live in `docs/INVARIANTS.md` and `docs/GOLDEN_CASES.md`; per-module navigation in `docs/MODULE_BRIEFS/`.

### Context Resilience Harness

- Start from `docs/CONTEXT_INDEX.md`; spend context per `docs/CONTEXT_BUDGET.md`; keep `docs/CURRENT_STATE.md` current.
- Compress per `docs/COMPRESSION_RULES.md` (lossless on rules/decisions/state).
- Every **session ends with a Context Handoff** (`tasks/CONTEXT_HANDOFF_TEMPLATE.md`) plus a Session Handoff (`tasks/SESSION_HANDOFF_TEMPLATE.md`), including **Human Learning Notes**.
- Update `config/workstreams.yaml` whenever you update `docs/AI_HANDOFF.md`, so the Progress panel's per-workstream milestone status stays honest.

## File ownership

| Area | Path |
|------|------|
| Backtesting engine/report | `backtesting/`, `scripts/run_backtest.py`, `scripts/run_replay_backtest.py` |
| Strategy implementation | `src/okx_quant/strategies/`, `src/okx_quant/signals/` |
| Risk and sizing | `src/okx_quant/risk/`, `src/okx_quant/portfolio/` |
| Deployment/config | `config/`, `scripts/run_live.py`, `scripts/run_shadow.py`, `docker/` |

Do **not** modify `research/` files — that is Claude's ownership area.

## Locate-before-edit rule

Before editing, identify:

- User-facing behavior or harness surface being changed.
- Owning frontend/API/backtesting/data/config/docs files.
- Files explicitly permitted for this task.
- Files forbidden for this task.
- Tests or Makefile targets that verify the change.
- Rollback path for the files you will touch.

If a document and implementation disagree, record it as a current/target/known-gap distinction. Do not claim target behavior is implemented.

## Standard verification matrix

| Change type | Minimum checks |
| --- | --- |
| Docs/governance only | `make docs-check` |
| Business-rule change (PnL/fee/funding/sizing/fills/gates) | `make docs-impact` plus a Change Manifest, on top of the change's normal tests |
| Frontend static/UI | `make frontend-check` plus targeted API/unit tests if data shape changed |
| Config/harness | `make check-config`, `make docs-check` when docs changed |
| Unit-level Python behavior | `make test-unit` or narrower pytest command |
| Backtest workflow | Targeted pytest plus `make backtest-smoke`; full replay only when fixture/data is available |
| API smoke | `make api-smoke`; set `API_BASE_URL` to test a running server |
| Full local verification | `make verify` for light no-DB checks; `make verify-full` when TimescaleDB/data are available |

Do not treat placeholder smoke output as full coverage. If a check skips because the environment lacks DB, server, data, Node, or optional validation dependencies, report that explicitly.

## Docs update matrix

| If you change | Also review/update |
| --- | --- |
| Feature ownership, files, or user-facing behavior | `docs/FEATURE_MAP.md` |
| Frontend navigation, chart behavior, or API calls | `docs/UI_MAP.md` |
| Ingestion, artifact, API, or validation data paths | `docs/DATA_FLOW.md` |
| Setup, smoke, test, rollback, or verification commands | `docs/RUNBOOK.md` |
| Current state, do-not-touch list, or next actions | `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md` |
| Durable AI history | `docs/CHANGELOG_AI.md` |
| Durable bug/gap backlog | `docs/KNOWN_ISSUES.md` |
| A business rule (PnL/fee/funding/sizing/fills/gates) | `docs/DOMAIN_RULES.md`, `docs/INVARIANTS.md`, a Change Manifest, and `docs/DOC_IMPACT_MATRIX.md` rows |
| A new bug class | `docs/FAILURE_MODES.md` (and the guarding invariant/test) |
| Strategy/system assumptions via an experiment | `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md` |

## When finishing a task, always report

```
Implementation summary:
Diff scope:
Files added:
Files changed:
Assumptions made:
Tests/checks run:
Backtest/result artifacts:
Docs updated:
Known limitations:
Risks:
Rollback plan:
Questions for Claude review:
Next recommended task:
Deployment readiness:
```

## Hard rules

- Never claim a strategy is ready for live trading unless all gates in `docs/ai_collaboration.md` have passed and the user has explicitly approved.
- Never change strategy assumptions based on chat memory — only from `research/strategy_synthesis.md` or explicit user instruction.
- Do not skip tests and claim deployable.
- Only modify files within the scope of the current task.
- Do not modify existing backtest result artifacts unless the user explicitly asks for artifact migration.
- Do not change live, shadow, demo, or deployment gates without explicit user approval.
- Do not touch differential-validation implementation when another session owns that work; document only the boundary/gap if needed.
- Every non-trivial task starts with locate-before-edit; every design-heavy task starts with design-space expansion (`docs/DESIGN_SPACE.md`).
- Every business-rule change creates/updates a Change Manifest and checks `docs/DOC_IMPACT_MATRIX.md`; every major rule change adds an ADR.
- Every experiment updates `docs/HYPOTHESIS_LEDGER.md` and `docs/EXPERIMENT_REGISTRY.md`; every new bug class updates `docs/FAILURE_MODES.md`.
- Every session ends with a Context Handoff (`tasks/CONTEXT_HANDOFF_TEMPLATE.md`) including Human Learning Notes. Do not rely on chat history as source of truth.
