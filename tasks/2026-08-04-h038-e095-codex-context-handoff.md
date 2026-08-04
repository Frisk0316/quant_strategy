---
status: current
type: handoff
owner: codex
created: 2026-08-04
last_reviewed: 2026-08-04
expires: none
superseded_by: null
---

# Context Handoff: H-038 / E-095 — 2026-08-04

## Goal (one sentence)

Complete the one authorized E-095 rerun with a provenanced 0.95 data gate and close F-S5 at K 2/2.

## Current state

- Branch: `feature/deribit-moneyness-hypotheses`.
- Last known good commit / state: `d7da783`; E-095 edits are uncommitted.
- In-progress edits (files): E-095 code/test, ledgers, state/data-flow/feature/failure-mode docs, workstream text, manifest, two handoffs, and ignored result files under `results/h038_stage2_e095/`.
- What works right now: data PASS at 17,271/17,272; actual-position breadth 5.743875 over 898 daily observations; immutable artifact SHA-256 `40c815834fdbe1f5caadcb1e3a06282eea4b678925dc78cb0bf21e8e4fe9c78f`.
- What does not work / unfinished: E-014 has no dated return series, so distinctness is undefined and fails closed; cost/power were not evaluated. E-095 implementation is complete but uncommitted and awaits review.
- Concurrent unrelated work: private-worklog task/handoff files and their additions to `AI_HANDOFF.md`, `CURRENT_STATE.md`, and `config/workstreams.yaml` appeared during this session and were preserved.

## Decisions made (and why)

- E-095 closes F-S5 as `inconclusive / terminal`, not refuted — because the ordered probe stopped at undefined distinctness before cost or power.
- E-094 stays byte-identical — because it is the immutable contract-error record.
- The 0.95 threshold remains E-095-specific — because the user authorized a one-off correction, not a repository-wide gate policy.

## Open questions / unverified assumptions

- None for execution. Claude should review whether terminal-but-inconclusive wording fully captures the missing E-014 reference evidence.

## Rules in play (preserve verbatim)

- Invariants touched: I11 — data coverage ≥ 80% before a dated replay starts.
- Domain rules touched: R6.2 data/source agreement and explicit provenance; R6.3 honest family-cumulative trial accounting.
- Do-not-touch: `src/okx_quant/strategies/s5_residual_meanrev.py`, research files, existing `results/**`, risk/portfolio/execution, parameters, grid, Stage 3, and deployment gates.

## Context to load next (the reading list)

- Source of truth: `tasks/2026-08-04-h038-e095-rerun-codex-tasks.md`, ADR-0013/0014/0015, `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md`.
- Owning files / MODULE_BRIEFS: `docs/FEATURE_MAP.md`, `backtesting/s5_residual_meanrev_probe.py`, `tests/unit/test_s5_residual_meanrev_probe.py`.
- Context Pack: none exists for H-038; start from `docs/CONTEXT_INDEX.md`.

## Checks run

- Targeted E-095 + registry pytest — 25 passed.
- Ruff — passed.
- Ledger consistency — 47 hypotheses, 96 experiments, 39 K-budget families.
- Config and backtest smoke — passed; smoke uses idealized fill and is not promotion evidence.
- Docs metadata/feature links/strict impact and diff checks — passed; metadata reported two pre-existing warnings.
- E-094 result diff and S5 strategy diff — empty.

## Approvals

- Human approval obtained 2026-08-04 through `tasks/2026-08-04-h038-e095-rerun-codex-tasks.md`.

## Next action (single, concrete)

- Claude reviews the E-095 diff and immutable artifact, especially terminal/inconclusive classification.

## Human Learning Notes

The repaired data really was sufficient: the same 0.999942 coverage produced a position sequence. The next frozen contract boundary was E-014's missing dated returns, so a fail-closed pipeline can still terminate a family without mechanism evidence; ledgers must distinguish terminal budget state from refutation.
