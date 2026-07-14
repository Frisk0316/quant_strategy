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

- P0.1-P0.3 rules implemented and Claude-APPROVED (artifact-ID containment,
  `ct_val` validator, venue fail-closed); post-merge gaps repaired with
  fail-closed regressions. No PnL formula or existing artifact changed.
- P0.4 Option B EXECUTED 2026-07-12: zero-delta merge verified (detail in
  CHANGELOG_AI); PR #9 merged to `main` at `b378e16`, PR head `00c7a51`.
- P1.1 governance + P1.2 docs cleanup DONE 2026-07-12 (test-lab in verify,
  A11 validator in docs-check, tasks/ frontmatter enforced, README slimmed);
  detail in the CHANGELOG_AI 2026-07-12 entry.
- Turtle research runner, Deribit D1-D5 + R1-R5, manual/Progress routes, and
  daily DVOL backfill (2021-03-24→2026-07-11, gap-free) remain accepted.
- H-014/F-VOL-REGIME-OPT: **E-051 Stage-3 PASSED the statistical gate — the
  first in this project** (WF 1.3049, CPCV 1.1326, DSR = PSR 0.9845 ≥ 0.95,
  minting MINT 0.074; 2022-05→2026-02; real trade-tape entries/marks,
  official delivery settlement, ADR-0010/R8/I39 accounting, golden tests
  green; adversarial fresh-verifier verdict PASS-STANDS). Honest caveats
  recorded: thin margin with degenerate-zero DSR penalty (all CPCV folds
  picked the same combo); one bear cycle in window. Status `testing` pending
  checkpoint-① human review; promotion still blocked per R7.2 (portable
  validation absent, user approval required).
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
- H-013/F-VRP-TIMING complete 2026-07-14: E-038 PASS; E-050 grid FAILED the
  gate (DSR 0.60/PSR 0.78, MINT 0.051) — shelved, no retry.
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
3. Pending fact: the user creates the OKX Demo key.
4. H-014 checkpoint-① human review: user ratifies (or rejects) the E-051
   statistical pass with its recorded caveats; promotion work stays blocked
   per R7.2 regardless until all `docs/ai_collaboration.md` gates pass.
5. Taxonomy_003 and H-013 are closed (all failed the gate); next ideation
   round only with new data families or materially longer history.

Related: `docs/AI_HANDOFF.md`, `docs/KNOWN_ISSUES.md`, `config/workstreams.yaml`,
`tasks/2026-07-12-project-diagnosis-followup-tasks.md`.
