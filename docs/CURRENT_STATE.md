---
status: current
type: handoff
owner: human
created: 2026-06-12
last_reviewed: 2026-07-14
expires: none
superseded_by: null
---

# Current State

Short present-tense snapshot. History belongs in `docs/CHANGELOG_AI.md`; durable
gaps belong in `docs/KNOWN_ISSUES.md`.

## Repository

- PR #9 merged to `main` at `b378e16` (head `00c7a51`). The separate follow-up
  branch `codex/pipeline-batch1-stage3` is pushed through `d046978` and still
  needs a human-reviewed PR. Stacked research branches are also pushed:
  `feature/f-vol-regime-opt-stage2` (`d66f08a`) and
  `feature/taxonomy003-stage3` (`821f761` plus shared state/handoff sync).
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
- P0.4 Option B EXECUTED 2026-07-12: zero-delta merge verified (detail in
  CHANGELOG_AI); PR #9 merged to `main` at `b378e16`, PR head `00c7a51`.
- P1.1 governance enforcement + P1.2 documentation cleanup DONE 2026-07-12:
  test-lab wired into verify, A11 ledger validator in docs-check, lifecycle
  frontmatter enforced under `tasks/`; README slimmed to 101 lines with detail
  in RUNBOOK. Full detail in `docs/CHANGELOG_AI.md` 2026-07-12 entry.
- Turtle research runner, Deribit D1-D5 + R1-R5, manual/Progress routes, and
  daily DVOL backfill (2021-03-24→2026-07-11, gap-free) remain accepted.
- H-014/F-VOL-REGIME-OPT (Deribit inverse-options vol regime): E-039 mechanism
  probe PASSED (short side separates; cheap-bucket long straddle negative →
  long leg OFF); hourly DVOL backfilled 2021→2024 (user-authorized, 46,440
  rows/symbol); **E-043 Stage-2 PASS** — real/synthetic premium ratios all
  ≥ 0.8 on the full 12-pair sample. Stage 3 still blocked: chain history,
  options engine, coin-accounting manifest+ADR, user authorization.
- Taxonomy_003 Stage-3 COMPLETE 2026-07-14 (user-authorized, Claude solo,
  E-044..E-049, fresh-verifier clean): all six candidates MINT (max corr
  ≤ 0.099) but ALL FAIL the DSR/PSR ≥ 0.95 gate. H-015 optflow refuted;
  H-016 XS-illiquidity shelved (best: WF 0.97, DSR 0.70, PSR 0.80);
  H-017 stablecoin inconclusive; H-018 coinbase-premium refuted;
  H-019 hash-ribbon shelved (breadth-1); H-020 calendar refuted.

## Active / blocked

- PR #9 follow-up repair is verified: unit `841 passed, 1 skipped`, integration
  `38 passed`, lab `18 passed`, Ruff/docs/config/backtest smoke PASS, and strict
  doc impact from `00c7a51` PASS. The branch is pushed; only the separate PR and
  human review/merge remain pending.
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
- H-014 next gate: Stage 3 needs option-chain history (vendor decision),
  an options backtest engine (Change Manifest + ADR), and user authorization.

## Next actions, in order

1. Open and review the separate `codex/pipeline-batch1-stage3` follow-up PR;
   human performs the merge.
2. Codex P1.4 implementation: OKX liquidation unattended mode.
3. Run H-013/E-038 Stage-2 only as a separate task; Stage 3 unauthorized.
4. Pending fact: the user creates the OKX Demo key.
5. H-014 is the only live strategy candidate: user decides on option-chain
   data purchase and Stage-3 authorization (engine work needs manifest+ADR).
6. Taxonomy_003 is closed (all six failed the gate); next ideation round
   only with new data families or materially longer history.

Related: `docs/AI_HANDOFF.md`, `docs/KNOWN_ISSUES.md`, `config/workstreams.yaml`,
`tasks/2026-07-12-project-diagnosis-followup-tasks.md`.
