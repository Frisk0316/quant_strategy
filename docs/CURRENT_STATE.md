---
status: current
type: handoff
owner: human
created: 2026-06-12
last_reviewed: 2026-07-27
expires: none
superseded_by: null
---

# Current State

Short present-tense snapshot. History belongs in `docs/CHANGELOG_AI.md`; durable
gaps belong in `docs/KNOWN_ISSUES.md`.

## Repository

- Current working branch: `feature/h014-e052-shadow`. The 2026-07-18 shared
  working tree is now split into five ordered delivery commits at current HEAD;
  use `git log --oneline -5` for exact hashes. The generated funnel JSON remains
  ignored on disk and the stray execution-comparison JSON remains untracked.
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

- Runtime/data reliability repair is complete for the highest-impact paths:
  external coverage groups its approximately 7.4 million observation rows once
  and the real endpoint returns 137 combined rows in 1.704 seconds; Compose
  waits for TimescaleDB health; runtime `DATABASE_URL` wins over the YAML candle
  DSN; and run-list/result-summary DB outages without file fallback return 503
  rather than a plausible empty list or 404. No schema or payload shape changed.
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
- Deribit native hourly HV remains a recent rolling source window. The separate
  `rv30_deribit_{btc,eth}_1h` derived datasets now cover 2021-01-01 through
  2026-07-26 with 48,792 unique rows each, using contiguous Deribit perpetual
  closes and an explicit 720-hour log-return formula. The existing frontend
  fetch queue now exposes BTC/ETH DVOL, native HV, RV30, and current full-chain
  option snapshots without changing strategy or deployment gates.
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
  A local `Research Ops` page can now show this status and run one existing
  public-data shadow cycle; it has no live-mode or order capability.
- Taxonomy_003 Stage-3 COMPLETE 2026-07-14 (user-authorized, Claude solo,
  E-044..E-049, fresh-verifier clean): all six candidates MINT (max corr
  ≤ 0.099) but ALL FAIL the DSR/PSR ≥ 0.95 gate. H-015 optflow refuted;
  H-016 XS-illiquidity shelved (best: WF 0.97, DSR 0.70, PSR 0.80);
  H-017 stablecoin inconclusive; H-018 coinbase-premium refuted;
  H-019 hash-ribbon shelved (breadth-1); H-020 calendar refuted.
- The 2026-07-16 Codex delivery adds ADR-0013 advisory Stage-2 power triage, a
  ledger-derived funnel, a read-only 研究總表 / Ledger view, and a read-only
  history audit with exact H-010 human-run commands. No generated funnel JSON is
  checked in, no network ingest ran, and no strategy/Stage-3/deployment gate
  changed.
- The 2026-07-17 Codex delivery adds `docs/STRATEGY_HISTORY.md` for H-000–H-021
  and E-000–E-056, upgrades the disposable funnel projection to schema v2, and
  adds source/hypothesis/iteration expansion to the Ledger view with a graceful
  schema-v1 hint. The ledgers remain authoritative and unchanged; no generated
  JSON is checked in and no strategy, result, business rule, or gate changed.

- The user ratified the ADR-0013 evaluator scope and computed `1.7206`
  reference case. Active Stage-2 callers now require candidate-specific power
  inputs before probes/artifacts/status changes; malformed artifacts are
  isolated in funnel schema v3. The separately authorized ADR-0014 data task
  promoted closed OKX BTC/ETH 1m raw rows into an additive source-aware layer:
  1,293,120 rows per symbol, raw mismatches 0, coverage/alignment 1.0, resolved
  OKX rows 0, and a second run changed 0 rows. The separately authorized E-057
  task then ran H-010 Stage 2: source-aware candles pass over the extended
  window, but OKX funding is absent and the fixed anchor fails cost at 1.3636
  bps gross versus 8.0 bps median round trip. H-010 is shelved with zero grid
  trials; no Stage 3 or DSR/PSR ran.
- Claude's A1-A3/B1-B4 findings are repaired. Future distinctness contracts
  must have a satisfiable formal/reference overlap; E-057's structural FAIL is
  no longer described as measured evidence. The generic orchestrator refuses
  missing/mismatched H-010 frozen evidence before probing, and funnel schema v3
  reports identity-less artifacts instead of dropping them.

## Active / blocked

- PR #9 follow-up repair is verified: unit `841 passed, 1 skipped`, integration
  `38 passed`, lab `18 passed`, Ruff/docs/config/backtest smoke PASS, and strict
  doc impact from `00c7a51` PASS. The branch is pushed; only the separate PR and
  human review/merge remain pending.
- H-013/F-VRP-TIMING complete 2026-07-14: E-038 PASS; E-050 grid FAILED the
  gate (DSR 0.60/PSR 0.78, MINT 0.051) — shelved, no retry.
- H-009 is shelved after E-063 breadth-restored retry 1: 31 unique assets,
  unchanged four-cell fold-refit grid, WF 1.4778, CPCV 0.9092, DSR 0.8305,
  PSR 0.9166, family-cumulative `n_trials=8`, K 1/2. Checkpoint1 auto fails only
  the statistical threshold; no retune. H-023/F-XS-IDIOVOL stopped at Stage 2
  power (0.5961 plausible net Sharpe < 0.7134 floor), so no Stage 3, trials, or
  retry budget were consumed. `docs/EXPERIMENT_REGISTRY.md` remains the
  authoritative total.
  The 2026-07-26 batch is now correctly classified as a limited two-candidate
  probe: H-023 was its only genuinely new family and H-009 its only
  existing-family iteration. It did not provide full strategy-finding coverage.
  ADR-0016 now defines a complete prompt-triggered round as 10–15
  execution-ready strategies frozen before results, with at least eight
  verified-paper-backed new mechanisms and two eligible existing-strategy
  iterations. This is target authority, not current implementation: today's
  generators lack the minimum/mix validator and unified entry point, literature
  drafts remain `pending_llm`, and unknown/new families without runners stop
  before deterministic evaluation.
  H-012 user-shelved, no retry; F36 cost-lag recorded. H-010 E-057 is shelved at
  Stage 2: 3,396,960 aligned candle rows per venue/symbol pass, but no OKX
  funding exists and 7,376 fixed-anchor episodes capture median 1.3636 bps gross
  versus 8.0 bps cost. All four checks fail; zero grid trials, no Stage 3/DSR.
- H-021/F-XVENUE-FUNDING-SPREAD is `refuted` after taxonomy_004 E-056. The
  separately authorized first Stage-3 full-PnL validation used ADR-0012 inverse
  accounting and failed statistical/robustness gates: WF -0.2158, CPCV -0.0375,
  DSR 0.2357, PSR 0.4818, family-cumulative n_trials=12, K=0/2. Stop: no retry,
  retune, promotion, demo, shadow, or live work.
- H-022/F-TAKER-FLOW is `shelved` after the zero-trial E-059 data-gap repair
  reprobe. T1 verifies ETH at 898/898 complete days and
  1,293,120/1,293,120 raw/taker rows, with the retained non-ETH count hash
  unchanged. ADR-0015 alias consumption yields 24,745/24,745 member-days.
  Data, distinctness (0.043660/0.093939), and cost (42.7529 versus 9.9160 bps)
  pass, while power fails at 0.448466 versus the 0.754896 floor. Family trials
  remain 0 and K remains 0/2. Stop with no retune; Stage 3, promotion, and
  deployment remain unauthorized.
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
- Runtime follow-ups remain: F52 needs an explicit engine-dashboard API-key
  contract; remaining per-artifact DB reads should adopt the same outage/absent/
  file-fallback distinction; add a bounded asyncpg pool only after measuring
  post-query-fix connection overhead.

## Next actions, in order

Immediate gate: Claude reviews the ordered E-059 registration, execution, and
outcome-sync commits. Do not retune or rerun H-022; Stage 3 is unauthorized.

1. Claude reviews the five ordered delivery commits and A1-A3/B1-B4 fixes,
   including E-057 byte-hash preservation and per-commit diff stats.
   Claude also reviews E-059's power-fail outcome and the non-gating H-002
   advisory correlation; no F-TAKER-FLOW follow-on is authorized.
2. Open and review the separate `codex/pipeline-batch1-stage3` follow-up PR;
   human performs the merge.
3. Continue the manual H-014 shadow cycle and obtain Claude's execution/risk
   review. Eight-week counting includes only valid exact-prior-day signals;
   scheduling remains unapproved.
4. From Administrator PowerShell, apply the P1.4 RUNBOOK `/NP` registration;
   verify `S4U`/`Limited`, run the task once, and require result `0`.
5. Pending fact: the user creates the OKX Demo key.
6. Before the next completed strategy-finding round, implement ADR-0016 in the
   smallest slices: result-blind manifest plus 8/2/10 executable validation and
   hash-bound resume; joined paper/iteration candidate input with provenance
   deduplication; registered deterministic Stage-2 evaluation for every counted
   candidate; then one reconciled report. Keep execution sequential until
   profiling justifies concurrency. Anything below ten remains incomplete or a
   limited probe. H-009 E-063 and H-023 E-062 are closed; neither passed, and no
   follow-on is authorized without a new ex-ante rationale.
7. Claude review DONE 2026-07-18 and repairs DONE 2026-07-21
   (`tasks/2026-07-18-strategy-history-h010-claude-review.md`): strategy-history
   A/B/C APPROVE-WITH-FINDINGS (minor fixes A1-A3: gitignore funnel JSON,
   frontend-check coverage, missing-ID artifact isolation). H-010/E-057
   APPROVE-WITH-FINDINGS: stage2_fail/shelved outcome stands; B1 (unpassable
   distinctness contract) and B2 (orchestrator bypasses frozen-evidence guard)
   MUST be fixed before any F-XVENUE-LEADLAG reprobe or Stage-2 path reuse.
   A1-A3/B1-B4 are applied and the tree is committed per delivery. Next: Claude
   verifies scope, hashes, tests, and commit ordering; no H-010 path reuse.

8. DONE 2026-07-17: Stage-2 F45/F46 caller/funnel repair and OKX
   raw-to-source-aware-canonical promotion completed under explicit user
   authorization. H-010 ledgers/results were not touched.
9. Measure the repaired UI/API path under normal concurrent run selection, then
   close the remaining per-artifact DB error paths and decide F52 authentication
   before adding retries or a shared connection pool.

Related: `docs/AI_HANDOFF.md`, `docs/KNOWN_ISSUES.md`, `config/workstreams.yaml`,
`tasks/2026-07-12-project-diagnosis-followup-tasks.md`, and
`tasks/2026-07-16-power-history-ledger-codex-context-handoff.md`,
`tasks/2026-07-17-strategy-history-frontend-codex-context-handoff.md`, and
`tasks/2026-07-17-strategy-history-frontend-codex-session-handoff.md`, plus
`tasks/2026-07-18-h010-e057-context-handoff.md` and
`tasks/2026-07-18-h010-e057-session-handoff.md`, plus
`tasks/2026-07-21-db-coverage-performance-context-handoff.md` and
`tasks/2026-07-21-db-coverage-performance-session-handoff.md`.
