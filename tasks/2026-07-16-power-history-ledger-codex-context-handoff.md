---
status: current
type: handoff
owner: codex
created: 2026-07-16
last_reviewed: 2026-07-16
expires: none
superseded_by: null
---

# Context Handoff: Power Triage, History Audit, and Ledger View — 2026-07-16

## Goal (one sentence)

Deliver Tasks A/B/C as advisory, read-only pipeline improvements without changing
research assumptions, Stage-3/deployment gates, trading core, or stored results.

## Current state

- Branch: `feature/h014-e052-shadow`.
- Last known good commit / state: `b2eb27e` plus the uncommitted Task A/B/C
  working tree; the three Claude-authored task specs were pre-existing untracked
  inputs and were not edited.
- In-progress edits: none in implementation; all requested code/docs are present
  and verified. The working tree remains uncommitted by user instruction.
- What works right now: registry-scoped power triage, schema-v1 funnel CLI,
  read-only history audit, fail-closed H-010 verifier, static 研究總表 / Ledger
  view, loopback-only ledger links, and explicit missing-JSON state.
- What does not work / unfinished: H-010 still fails at zero canonical OKX
  coverage; the current canonical identity/source priority cannot retain Binance
  and OKX at the same `(inst_id, bar, ts)`. Real browser rendering was not run
  because Playwright is absent and third-party npm execution was rejected.

## Decisions made (and why)

- Keep the power check registry-scoped and legacy artifact reads compatible —
  because the task permitted registry wiring and forbids artifact migration;
  broaden only if all Stage-2 writers are explicitly placed in scope.
- Label low-level `n_trials` as `caller_declared`; only the registry-context path
  labels it `max_registry_actual_and_ex_ante_declared_cumulative` — because provenance must
  reflect the actual authority used.
- Generate `frontend/research_funnel.json` only on demand and do not check it in
  — because the Markdown ledgers are authoritative and a committed projection
  would drift.
- Do not run the prepared OKX network ingest — because Task B is audit/command
  prep only, and existing raw rows show that ingestion alone cannot repair the
  canonical consumer boundary.
- ADR-0013 records the triage decision and limits because DOC_IMPACT A9 requires
  an ADR even though no promotion/deployment policy changes.

## Open questions / unverified assumptions

- Independent-bet breadth is caller-supplied. Treating BTC/ETH as breadth 2 is
  UNCONFIRMED; the H-014-like fixture passes at 2 and fails at 1.
- Venue plausible-earliest dates in the history ranking are UNCONFIRMED planning
  assumptions; late listings can overstate a dataset's history gap.
- Claude should decide whether a future H-010 task changes canonical identity or
  moves the probe to the multi-venue `market_klines` consumer.

## Rules in play (preserve verbatim)

- I19: “A venue-tagged run loads candles only from that venue's
  provenance-tagged canonical series; source-less parquet or another venue
  cannot substitute missing bars.”
- I23: “Candidate CPCV and Stage-2 power-screen `n_trials` must use at least the
  family-cumulative trial count recorded in `docs/EXPERIMENT_REGISTRY.md`; a
  per-run or caller-declared smaller count alone is a violation.”
- R6.3: “Trial count must be tracked; hidden trials inflate selection bias.
  Stage-2 statistical-power triage must use the family-cumulative `n_trials`
  recorded in `docs/EXPERIMENT_REGISTRY.md`; missing accounting fails closed.”
- R7.2: “No live / shadow / demo readiness claim is valid unless every gate in
  `docs/ai_collaboration.md` passes and the human explicitly approves.”
- F44: a single-source canonical identity must not be treated as simultaneous
  multi-venue storage; keep the cross-venue verifier fail closed.
- Do-not-touch: `research/`, existing `results/**`, strategy/signal/risk/
  portfolio/execution code, `config/risk.yaml`, Stage-3 grids/gates, and
  live/demo/shadow/deployment gates.

## Context to load next (the reading list)

- Source of truth: `research/strategy_synthesis.md`,
  `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md`, `config/`, and the
  three `tasks/2026-07-16-*-codex-tasks.md` specifications.
- Owning files: `backtesting/pipeline_power_screen.py`,
  `backtesting/pipeline_stage2_registry.py`,
  `scripts/run_pipeline_funnel_report.py`,
  `scripts/audit_history_coverage.py`, `scripts/verify_okx_1m_backfill.py`, and
  `frontend/view-ledger.js`.
- Governance: `docs/ADR/0013-stage2-statistical-power-triage.md`,
  `docs/change_manifests/2026-07-16-stage2-power-screen.md`,
  `docs/DOMAIN_RULES.md`, `docs/INVARIANTS.md`, `docs/DATA_FLOW.md`,
  `docs/UI_MAP.md`, and `docs/RUNBOOK.md`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run

- Cross-module pytest matrices — `82 passed`, plus 7 Stage-2 data-probe and 10
  legacy batch-2 compatibility tests.
- Targeted Ruff — PASS; all frontend syntax files including the new view — PASS.
- Docs metadata, Feature Map links, ledger consistency, strict doc impact — PASS.
- Config validation and frozen no-DB backtest smoke — PASS.
- Real funnel projection — schema 1, 22 ledger/registry families/candidates,
  6 data-feasible, 18 Stage-3 runs, 1 gate pass, K spent 7.
- Real read-only history audit — COMPLETE, 68 canonical + 46 external datasets.
- Real H-010 verifier — expected FAIL/exit 1: both OKX legs 0 rows, coverage and
  alignment 0.0 against the 0.95 thresholds.
- Loopback HTTP smoke — root 200; absent funnel 404; generated funnel 200; two
  allowed ledgers 200; unlisted file 404; generated JSON then removed.
- Playwright — SKIP: package absent; sandbox rejected third-party npm execution.

## Approvals

- Human approval obtained through the explicit 2026-07-16 `/goal` request for
  Tasks A/B/C. No approval was requested or inferred for ingest, retry,
  canonical schema/consumer changes, Stage 3, or deployment.

## Next action (single, concrete)

- Claude reviews the actual diff, especially power provenance/breadth and the
  H-010 canonical-boundary finding, using a fresh verifier.

## Human Learning Notes

The task's rough “about 1.9” example is 1.720600 under the repository's exact
one-tailed PSR/DSR equations; the independent SciPy inversion agrees with the
implementation. More importantly, H-010 is not currently a simple missing-data
problem: venue-native rows already exist in multi-venue storage, while the
canonical identity chooses one source. Re-running the same ingest cannot make a
two-venue canonical join possible. Keep projections disposable, provenance
literal, and treat any schema/consumer repair as a separate design decision.
