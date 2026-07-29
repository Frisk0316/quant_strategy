---
status: current
type: handoff
owner: codex
created: 2026-07-29
last_reviewed: 2026-07-29
expires: none
superseded_by: null
---

# Context Handoff: H-024..H-027 moneyness/vol limited probe — 2026-07-29

## Goal (one sentence)

Execute the four user-authorized probes in frozen order only after every I49
distinctness reference satisfies the global dated-overlap contract.

## Current state

- Branch: `feature/deribit-moneyness-hypotheses`
- Last known good commit / state: registration commit `4c84a18`
- In-progress edits: closeout docs and this handoff only
- What works right now: four registry entries, shared feature/probe code,
  fail-closed global I49 pre-flight, and targeted tests
- What does not work / unfinished: E-025/F-PAIRS-OU has no dated return series,
  so the pre-flight stops before DB access and no candidate has executed

## Decisions made (and why)

- Treat the E-025 condition as a contract error, not a candidate failure,
  because I49 requires structural feasibility before any probe starts.
- Do not fabricate dates from CPCV path order or substitute another reference,
  because either action would change the signed-off distinctness contract.
- Do not add experiment rows or consume trials/K, because no probe executed.

## Open questions / unverified assumptions

- Claude must identify or authorize the canonical dated E-025/F-PAIRS-OU
  reference, or explicitly amend the I49 contract.

## Rules in play (preserve verbatim)

- I49: every distinctness reference must have at least 65 common dated days
  before any H-024..H-027 probe runs.
- Candidate order: H-024, H-025, H-027, H-026.
- A Stage-2 four-check failure stops that candidate; Stage 3 is pass-only.
- H-026 uses family-cumulative `n_trials=8`; K is consumed only if Stage 3 runs.
- Do not touch `research/`, existing result artifacts, deployment gates, or
  differential-validation implementation.

## Context to load next (the reading list)

- Source of truth:
  `docs/superpowers/specs/2026-07-28-deribit-moneyness-vol-probe-hypotheses.md`
  and `tasks/2026-07-28-moneyness-vol-probe-codex-tasks.md`
- Owning files: `backtesting/moneyness_vol_probe.py`,
  `backtesting/pipeline_stage2_registry.py`,
  `docs/MODULE_BRIEFS/backtesting-engine.md`
- Context Pack: no task-specific pack exists; use
  `docs/CONTEXT_PACKS/harness-scaffolding.md`

## Checks run

- `python -m pytest tests/unit/test_moneyness_vol_probe.py -v` — 5 passed
- Probe plus registry unit tests — 20 passed
- Targeted Ruff — passed
- Whole-batch pre-flight — expected I49 `ValueError` before DB access
- Docs metadata, feature-map links, ledger consistency, config validation, and
  advisory docs-impact checks — passed (two pre-existing metadata warnings)
- Backtest smoke — passed; idealized fixture is not promotion evidence
- `git diff --check` — passed with line-ending warnings only

## Approvals

- User approval to execute the frozen limited probe was obtained.
- No approval exists to alter I49, substitute a reference, retune, activate
  trading, or run Stage 3 after a Stage-2 failure.

## Next action (single, concrete)

- Claude supplies or authorizes the dated E-025 reference; then rerun the
  whole-batch pre-flight before any DB connection.

## Human Learning Notes

CPCV `path_returns` are ordered performance samples, not a dated daily-return
series. Without explicit dates they cannot support a common-day correlation
gate, even when their sample count is large.
