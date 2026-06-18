---
status: current
type: governance
owner: human
created: 2026-06-12
last_reviewed: 2026-06-12
expires: none
superseded_by: null
---

# AI Context

## Project Summary

`quant_strategy` is an OKX-focused quantitative trading system for research, replay
backtesting, API/frontend review, and staged deployment governance. The current
implementation includes strategy modules, shared portfolio/risk/execution layers,
historical replay backtesting, artifact export, FastAPI routes, a static frontend,
market-data ingestion utilities, and governance documents.

## Primary Human Goal

Build a maintainable workflow where a human can ask Claude and Codex to research,
implement, review, and verify trading-system changes without strategy drift,
untracked assumptions, overwritten work, or accidental live-readiness claims.

## Current Project Stage

- Current: research/backtest/front-end review system with active governance rules.
- Current: replay backtests write file/DB artifacts through the documented artifact
  path, and the frontend can inspect runs, charts, metrics, trades, validation views,
  and market-data coverage.
- Current: `config/` and repo documents, not chat memory, are authoritative for
  runtime settings and strategy assumptions.
- Target: every promotion candidate has reproducible artifacts, walk-forward or CPCV
  evidence, source-data checks, validation gates, demo/shadow history, and explicit
  human approval.
- Known gap: several docs and handoff notes still contain historical detail that
  should migrate gradually to `docs/CHANGELOG_AI.md` and `docs/KNOWN_ISSUES.md`.
- Known gap: lightweight smoke targets exist for harness consistency, but API and
  backtest smoke coverage is not a full end-to-end replay fixture yet.

## Source Of Truth List

Use this order when documents conflict:

1. Current user instruction and explicitly approved task scope.
2. `research/strategy_synthesis.md` for strategy assumptions and research status.
3. `config/` for runtime settings and strategy/risk parameters.
4. `docs/ai_collaboration.md` for gates, AI roles, conflict handling, and completion
   reporting.
5. `docs/DOC_LIFECYCLE.md`, `docs/AI_WORKFLOW.md`, and `docs/BRANCH_VERSIONING.md`
   for documentation, session, and branch governance.
6. Accepted ADRs under `docs/ADR/`.
7. `docs/ARCHITECTURE.md`, `docs/FEATURE_MAP.md`, `docs/UI_MAP.md`,
   `docs/DATA_FLOW.md`, and `docs/RUNBOOK.md` for current architecture and
   operational navigation.
8. `docs/AI_HANDOFF.md` for current state, do-not-touch items, and next actions.

## Human-Maintainability Rule

Every AI change should leave the repository easier for a human to inspect: locate
the owning feature before editing, keep diffs scoped, name authoritative files,
record known gaps instead of inventing implementation status, and provide exact
commands or artifacts that prove what was checked.

## Do Not Do Without Explicit Approval

- Change strategy assumptions or research conclusions.
- Modify `research/` files, except when the user explicitly assigns that task.
- Modify strategy logic in `src/okx_quant/strategies/` or signals in
  `src/okx_quant/signals/`.
- Modify risk, portfolio, execution, sizing, or PnL behavior.
- Modify database schema or migrations.
- Modify existing backtest result artifacts under `results/`.
- Change live, shadow, demo, or deployment-gate policy.
- Treat `naive_backtest`, `in_sample`, idealized-fill, or advisory validation output
  as promotion evidence.
- Touch differential-validation implementation when another session owns that work.
- Reformat or refactor unrelated code.

## Preferred AI Workflow

1. Read this file, `docs/AI_HANDOFF.md`, `docs/AI_WORKFLOW.md`,
   `docs/ai_collaboration.md`, `docs/FEATURE_MAP.md`, and relevant ADRs.
2. Run `git status --short` before editing.
3. Locate the feature and owning files before making a change.
4. State permitted files, forbidden files, required checks, and rollback plan when the
   task has non-trivial blast radius.
5. Implement the smallest scoped change.
6. Run targeted checks first, then the relevant Makefile harness target.
7. Update docs if behavior, workflow, or file ownership changed.
8. Finish with the completion report required by `docs/ai_collaboration.md` and
   `AGENTS.md`.

## Main Risk Areas

- Strategy drift from chat memory or stale docs.
- Lookahead/data leakage and in-sample selection bias.
- `ct_val` provenance and SWAP PnL scaling.
- Funding cashflow sign and settlement timing.
- Replay/live fill mismatch, partial fills, and maker-only semantics.
- DB vs parquet data-source mismatch.
- Frontend/API schema mismatch for charts and artifacts.
- Deployment claims before gates are complete and human approval is recorded.
- Multiple AI sessions editing the same file or ownership area.

## Definition Of Done

A task is done when:

- The diff stays within the approved scope.
- Files added/changed are listed.
- Tests/checks are run, or skipped with a concrete reason.
- Backtest/result artifacts are listed if generated; otherwise state none.
- Known gaps are recorded as gaps, not as completed behavior.
- Deployment readiness is described honestly; no live-readiness claim is made unless
  all gates passed and the user explicitly approved.
