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

- Branch/HEAD: `codex/pipeline-batch1-stage3` at `7636dd9`, tracking the matching
  origin branch. The branch was clean at audit start and was 96 commits ahead / 5
  behind `origin/main`; the current tree contains the project-audit repair plus
  the user-approved P0 implementation. Do not discard either scope.
- No strategy is promotion/demo/shadow/live ready. Config, accepted ADRs,
  `research/strategy_synthesis.md`, and `docs/ai_collaboration.md` remain the
  authority in the documented order.
- Do not modify research, existing results, strategy/signal/risk/execution
  behavior, DB schema, or deployment gates unless a dedicated approved task
  explicitly permits it. P0 authorized only artifact containment inside
  differential validation and the shared `ct_val` validation contract; no
  strategy/PnL formula changed.

## Completed and usable

- Turtle standalone research runner, golden parity, UI, and resumable large
  sweeps are implemented. The 2026-07-12 audit restored the fraction-unit UI
  contract; it remains research-only.
- Deribit D1-D5 ingestion/API/frontend work and R1-R5 fixes are accepted. D4
  history is backfilled through 2026-07-10 23:00Z; forward scheduled tasks are
  not registered.
- Funding XS Dispersion H-009/E-031 completed its first cycle and remains
  `testing` after DSR=PSR 0.9346 failed the 0.95 gate.
- OI Positioning H-012/E-037 is user-ratified `shelved`, no retry: WF 0.6034,
  CPCV 0.7240, DSR 0.7220, PSR 0.8484. Hygiene also found F36: positions and
  funding use t+1, but turnover cost is posted on signal day. The immutable
  E-037 artifact remains non-promotion evidence and was not edited.
- Batch 2 C1/C2/C3 and XS Momentum are refuted/shelved. Multi-venue ADR-0007 P1
  and the user-manual content are implemented.
- The standalone local server now exposes the manual; manual frontmatter is
  hidden. Progress document links use an allow-listed contained markdown route
  only on loopback standalone binds; engine/non-loopback views do not expose files.
- P0.1-P0.3 are implemented: artifact identifiers reject unsafe components and
  remain contained under their roots; explicit unknown venues fail with HTTP 400
  while omitted/blank values use the configured primary exchange; the numeric
  `ct_val` guard accepts only finite positive values through `1e7`, with
  provenance still enforced separately by R1.4/I16. PnL formulas and existing
  result artifacts are unchanged.

## Active / blocked

- H-013/F-VRP-TIMING Stage-1 is user-signed-off and remains `proposed`. E-038 is
  reserved-only and absent from the registry until a separately scoped Stage-2
  probe runs; no probe, grid, adapter, or promotion work ran in this task.
- H-010 cross-venue lead/lag is blocked on missing OKX BTC/ETH 1m candles.
- Demo engine mode is blocked by OKX `60005 Invalid apiKey`. Use the standalone
  server for frontend/backtest/data review; never switch to live as a workaround.
- Port `127.0.0.1:8080` is abandoned per the 2026-07-12 user decision (the hung
  user-owned PID 23696 stays untouched); run servers on another port.
- Operations decided 2026-07-12: Deribit schedulers stay unregistered
  (stale accepted, manual RUNBOOK updates only), OKX liquidation collection
  moves to unattended mode (Codex task). Daily DVOL is backfilled and gap-free:
  2021-03-24 through 2026-07-11, 1,936 rows per symbol, daily close matches the
  hourly series; manual-update command is in `docs/RUNBOOK.md`.

## Remaining engineering work from the audit

- P0.1-P0.3 are implemented and Claude-review APPROVED 2026-07-12 with the full
  verification rerun: full unit `768 passed, 1 skipped` (Windows symlink
  privilege), integration `38 passed`, Ruff and `docs-impact --strict` pass.
  The `delete_run` indentation minor is fixed; the symlink regression still
  skips on Windows without privilege and remains active for CI/Linux.
- P0.4 Option B is approved but not executed: merge the five main-only commits
  into the branch, resolve conflicts, use one documented integration-exception
  PR, and run `verify-full` on the integration commit. No force-push.
- Governance follow-ups: separate lab test in `verify`, A11 ledger validator,
  task lifecycle scope, stale README/ADR/overview cleanup.
- The shelved OI research runner has the F36 cost-lag bug class. It is not fixed
  in this task because no retry/reuse is authorized; any future reuse requires a
  code fix, guarding test, new ex-ante rationale, and a new experiment record.

## Next actions, in order

All 2026-07-12 audit decisions are recorded ("Human decisions recorded
2026-07-12" in the follow-up task file): P0.1–P0.3 ratified (P0.2: finite
positive, cap ≤1e7), P0.4 = Option B merge-exception after the P0s, H-012
shelved (F36 turnover-cost-timing logged), H-013 approved, ADR-0001/0006
resolved, P1.4 operations decided.

P0.1–P0.3 are CLOSED: Claude review approved all three on 2026-07-12 and reran
the blocked verification (full unit 768/1 skipped, integration 38, Ruff,
docs-impact strict — all pass).

1. Execute the already-approved P0.4 Option B integration as a separate Git
   task, with `verify-full` on the integration commit.
2. Complete P1.1 governance enforcement and P1.2 documentation cleanup.
3. Run H-013/E-038 Stage-2 only as a separate task; Stage 3 remains unauthorized.
4. Pending fact: the user creates the OKX Demo key.

Related: `docs/AI_HANDOFF.md`, `docs/KNOWN_ISSUES.md`,
`config/workstreams.yaml`.
