---
status: current
type: handoff
owner: human
created: 2026-06-12
last_reviewed: 2026-07-12
expires: none
superseded_by: null
---

# Current State

Short present-tense snapshot. History belongs in `docs/CHANGELOG_AI.md`; durable
gaps belong in `docs/KNOWN_ISSUES.md`.

## Repository

- Branch `codex/pipeline-batch1-stage3` at `f1aac94` holds the committed P0
  hardening (`c84f5a1`) plus the zero-delta `origin/main` integration merge
  (`a950025`). PR #9 (documented integration exception, branch → main) is open
  awaiting Codex review; do not force-push.
- Branch `claude/p1-governance-docs` (off `f1aac94`) holds the P1.1/P1.2 work
  below, PR pending Codex review.
- No strategy is promotion/demo/shadow/live ready. Config, accepted ADRs,
  `research/strategy_synthesis.md`, and `docs/ai_collaboration.md` remain the
  authority in the documented order.
- Do not modify research, existing results, strategy/signal/risk/execution
  behavior, DB schema, or deployment gates without a dedicated approved task.

## Completed and usable

- P0.1-P0.3 hardening implemented and Claude-review APPROVED: artifact-ID
  containment, `ct_val` finite-positive `<=1e7`, venue fail-closed. No PnL
  formula or existing artifact changed.
- P0.4 Option B EXECUTED 2026-07-12 (Claude, user-authorized): zero-delta merge,
  integration commit verified (unit 768/1 skip, integration 38, Ruff/docs/
  frontend/config/backtest-smoke pass; api-smoke SKIP no server; validate-data
  FAIL is the pre-existing thin local parquet mirror), PR #9 open.
- P1.1 governance enforcement DONE 2026-07-12 (Claude, Codex review pending):
  `make test-lab` runs the crypto-alpha-lab suite separately and is wired into
  `verify`; A11 ledger validator `scripts/docs/check_ledger_consistency.py` is
  in `docs-check` with unit tests (it found and fixed the missing F-VRP-TIMING
  K-budget row); new dated `tasks/` files (≥2026-07-01) require lifecycle
  frontmatter — checker enforces, 28 July files migrated, 4 templates updated,
  legacy exempt; overview coverage is a documented manual review step in
  `docs/human_overviews/README.md`.
- P1.2 documentation cleanup DONE 2026-07-12: README slimmed 897→101 lines with
  operational detail moved verbatim into `docs/RUNBOOK.md` (521→1237 lines,
  gate wording unchanged); completed 2026-06-25 pipeline/manual plans archived;
  CHANGELOG_AI backfilled with compressed 07-05/07-07/07-11 entries; ADR-0001
  amendment and ADR-0006 status were already fixed by the audit session.
- Turtle research runner, Deribit D1-D5 + R1-R5, manual/Progress routes, and
  daily DVOL backfill (2021-03-24→2026-07-11, gap-free) remain accepted.

## Active / blocked

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

1. Codex reviews/merges PR #9 (P0.4 integration exception).
2. Codex reviews the `claude/p1-governance-docs` PR (P1.1 + P1.2).
3. Codex P1.4 implementation: OKX liquidation unattended mode.
4. Run H-013/E-038 Stage-2 only as a separate task; Stage 3 unauthorized.
5. Pending fact: the user creates the OKX Demo key.

Related: `docs/AI_HANDOFF.md`, `docs/KNOWN_ISSUES.md`,
`config/workstreams.yaml`,
`tasks/2026-07-12-project-diagnosis-followup-tasks.md`.
