---
status: current
type: handoff
owner: human
created: 2026-06-12
last_reviewed: 2026-07-15
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
- No strategy is promotion/demo/live ready. ADR-0011's manual H-014 shadow-only
  layer is operational, but its 8-week exit gate has not been met. Config,
  accepted ADRs, `research/strategy_synthesis.md`, and
  `docs/ai_collaboration.md` remain the authority in the documented order.
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
- H-014/F-VOL-REGIME-OPT is `supported` on double-passed evidence: E-051
  (2022-05→2026-02, DSR=PSR 0.9845, user-ratified checkpoint ①) and **E-052
  extended-window retry PASS** (2020-05→2026-02 incl. COVID aftermath +
  2021-05 crash + 2022 bear; WF 0.8818, CPCV 1.0098, DSR 0.9746 < PSR 0.9904
  with a REAL multiple-testing penalty, n_trials=8, K 1/2). E-051's
  degenerate-penalty and single-bear caveats are closed; splice-constant
  lookahead disclosed with persisted sensitivity artifact (Jaccard ≥ 0.972).
  Promotion still blocked per R7.2. ADR-0011's shadow-only implementation now
  exists; the next gate is at least 8 valid journal weeks plus the fill-bias,
  missed-entry, and mark-tracking report, followed by human and Claude review.
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
- H-021/F-XVENUE-FUNDING-SPREAD is `inconclusive` after taxonomy_004 E-053/E-054.
  Corrected funding alignment is complete (2,739/2,739 per symbol) and the
  feature-distinctness proxy passes, but Stage 2 fails: Deribit venue-scoped
  perpetual 1m prices are absent and conservative two-leg costs leave no common
  positive BTC/ETH cell. Family proxy n_trials=8, K=0/2. Do not retune or run
  Stage 3 without real Deribit prices/specs and a new ex-ante rationale.
- Demo engine blocked by OKX `60005 Invalid apiKey`; user creates the Demo key
  later. Port 8080 abandoned; use another port.
- Deribit forward schedulers stay unregistered (stale accepted, manual RUNBOOK
  updates). OKX liquidation P1.4 repo support is implemented with an explicit
  Python path and documented S4U/Limited task lifecycle, but the host task still
  reports `Interactive`; Administrator activation and a manual-run check remain.
- F36: the shelved OI runner posts turnover cost on signal day; any reuse needs
  a fix, guarding test, ex-ante rationale, and a new experiment record.
- ADR-0011/H-014 shadow completed its first valid real-DB manual cycle after a
  bounded public-data refresh; both 2026-07-13 signals were `not_rich`. A
  pre-guard smoke's two stale-signal records remain in the append-only audit log
  and are explicitly excluded by the report. No scheduler is registered and no
  private endpoint, credential, or order path exists.

## Next actions, in order

1. Open and review the separate `codex/pipeline-batch1-stage3` follow-up PR;
   human performs the merge.
2. Continue the manual H-014 shadow cycle and obtain Claude's execution/risk
   review. Eight-week counting includes only valid exact-prior-day signals;
   scheduling remains unapproved.
3. From Administrator PowerShell, apply the P1.4 RUNBOOK `/NP` registration;
   verify `S4U`/`Limited`, run the task once, and require result `0`.
4. Pending fact: the user creates the OKX Demo key.
5. Taxonomy_003 and H-013 are closed (all failed the gate); next ideation
   round only with new data families or materially longer history.

Related: `docs/AI_HANDOFF.md`, `docs/KNOWN_ISSUES.md`, `config/workstreams.yaml`,
`tasks/2026-07-12-project-diagnosis-followup-tasks.md`.
