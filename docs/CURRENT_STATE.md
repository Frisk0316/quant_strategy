---
status: current
type: handoff
owner: human
created: 2026-06-12
last_reviewed: 2026-07-13
expires: none
superseded_by: null
---

# Current State

Short present-tense snapshot. History belongs in `docs/CHANGELOG_AI.md`; durable
gaps belong in `docs/KNOWN_ISSUES.md`.

## Repository

- PR #9 is merged to `main` at `b378e16`; its PR head was `00c7a51`. Branch
  `codex/pipeline-batch1-stage3` now has five post-merge review-fix commits
  (`6129f94` through `037b15f`) plus the verified repair work. None of those
  follow-up changes were part of PR #9; they require a separate PR.
- No strategy is promotion/demo/shadow/live ready. Config, accepted ADRs,
  `research/strategy_synthesis.md`, and `docs/ai_collaboration.md` remain the
  authority in the documented order.
- Do not modify research, existing results, strategy/signal/risk/execution
  behavior, DB schema, or deployment gates without a dedicated approved task.

## Completed and usable

- P0.1-P0.3 rules were implemented and Claude-review APPROVED: artifact-ID
  containment, `ct_val` finite-positive `<=1e7`, and venue fail-closed. No PnL
  formula or existing artifact changed. Post-merge DB/registry/caller-spec and
  failed-fill mutation gaps are repaired and covered by fail-closed regressions.
- P0.4 Option B EXECUTED 2026-07-12 (Claude, user-authorized): zero-delta merge,
  integration commit verified (unit 768/1 skip, integration 38, Ruff/docs/
  frontend/config/backtest-smoke pass; api-smoke SKIP no server; validate-data
  FAIL is the pre-existing thin local parquet mirror). PR #9 merged to `main`
  at `b378e16` with PR head `00c7a51`.
- P1.1 governance enforcement DONE 2026-07-12:
  `make test-lab` runs the crypto-alpha-lab suite separately and is wired into
  `verify`; A11 ledger validator `scripts/docs/check_ledger_consistency.py` is
  in `docs-check` with unit tests (it found and fixed the missing F-VRP-TIMING
  K-budget row); every new Markdown file under `tasks/` requires lifecycle
  frontmatter recursively. Only the frozen legacy filename allowlist and the
  four exact task templates are exempt; overview coverage is a documented
  manual review step in `docs/human_overviews/README.md`.
- P1.2 documentation cleanup DONE 2026-07-12: README slimmed 897→101 lines with
  operational detail moved verbatim into `docs/RUNBOOK.md` (521→1237 lines,
  gate wording unchanged); completed 2026-06-25 pipeline/manual plans archived;
  CHANGELOG_AI backfilled with compressed 07-05/07-07/07-11 entries; ADR-0001
  amendment and ADR-0006 status were already fixed by the audit session.
- Turtle research runner, Deribit D1-D5 + R1-R5, manual/Progress routes, and
  daily DVOL backfill (2021-03-24→2026-07-11, gap-free) remain accepted.

## Active / blocked

- PR #9 follow-up repair is verified: unit `841 passed, 1 skipped`, integration
  `38 passed`, lab `18 passed`, Ruff/docs/config/backtest smoke PASS, and strict
  doc impact from `00c7a51` PASS. A separate PR is not yet open.
- H-013/F-VRP-TIMING Stage-1 signed off, `proposed`; E-038 reserved-only until
  a separately scoped Stage-2 probe. Stage 3 unauthorized.
- H-009 stays `testing` (DSR=PSR 0.9346 < 0.95, no gate-chasing retry).
  H-012 user-shelved, no retry; F36 cost-lag recorded. H-010 blocked on OKX
  BTC/ETH 1m backfill.
- Demo engine blocked by OKX `60005 Invalid apiKey`; user creates the Demo key
  later. Port 8080 abandoned; use another port.
- Deribit forward schedulers stay unregistered (stale accepted, manual RUNBOOK
  updates). OKX liquidation unattended mode is an approved Codex task.
- F36: the shelved OI runner posts turnover cost on signal day; any reuse needs
  a fix, guarding test, ex-ante rationale, and a new experiment record.

## Next actions, in order

1. Open and review a separate follow-up PR for the five post-merge commits plus
   the verified repair; human performs the merge.
2. Codex P1.4 implementation: OKX liquidation unattended mode.
3. Run H-013/E-038 Stage-2 only as a separate task; Stage 3 unauthorized.
4. Pending fact: the user creates the OKX Demo key.

Related: `docs/AI_HANDOFF.md`, `docs/KNOWN_ISSUES.md`,
`config/workstreams.yaml`,
`tasks/2026-07-12-project-diagnosis-followup-tasks.md`.
