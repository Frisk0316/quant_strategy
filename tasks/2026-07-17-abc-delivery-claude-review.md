---
status: current
type: review
owner: claude
created: 2026-07-17
last_reviewed: 2026-07-17
expires: none
superseded_by: null
---

# Claude Review: Tasks A/B/C delivery (power screen, history audit, ledger view)

Reviewed per docs/REVIEW_QUESTIONS.md + docs/CRITIQUE_PROTOCOL.md. Three
fresh-context verifier agents (one per task) plus a direct DB probe by the
reviewing session. Codex handoff:
`tasks/2026-07-16-power-history-ledger-codex-session-handoff.md`.

## Verdicts

| Task | Verdict | Notes |
| --- | --- | --- |
| A power screen + funnel | APPROVE-WITH-FIXES | math verified; one major caller regression (F1) |
| B history audit + H-010 verify | APPROVE | clean, honest UNCONFIRMED labels, read-only enforced |
| C ledger frontend view | APPROVE | exposure contained to existing loopback allow-list route |

## Key verification evidence

- Power floor: verifier independently re-derived min_detectable_sharpe
  (breadth=1, n_obs=900, n_trials=4 → 1.7206; H-014-like → 0.9785); test
  expectations are non-circular. Triage-only confirmed: no path converts a
  Stage-3 failure to a pass; thresholds <0.95 hard-rejected
  (test_power_thresholds_cannot_relax_below_policy_floor). n_trials =
  max(registry family cumulative, declared), fail-closed if missing.
- Task B: DB connections opened default_transaction_read_only; no network; no
  cross-venue substitution (I19); ingest/verify commands checked against the
  real ingest.py argparse; verify exits 1 at coverage 0.0. Tests 3/3.
- Task C: no new endpoint; allow-list gains exactly the two ledger paths via
  workstreams.yaml links; loopback gating and path containment untouched;
  routes tests 10/10; node --check clean; view is read-only with explicit
  empty state; UI_MAP + UI both state markdown ledgers stay authoritative.
- Reviewer DB probe: market_klines has OKX 1m ≈3.42M/3.40M rows per leg
  spanning 2020-01-01→2026-06/07; canonical_candles OKX 1m = 0 rows.
  H-010's blocker is a raw→canonical identity/consumer gap, NOT missing data.

## Findings requiring action

1. **F1 (major, blocks the next Stage-2 batch, not this merge):**
   `_write_result` now injects statistical_power=FAIL when callers pass no
   power inputs; existing unmodified callers
   `scripts/market_data/backfill_universe_funding.py:247` and
   `scripts/run_pipeline_stage2_data_probe.py` will report stage2 FAIL on
   otherwise-feasible candidates. Direction-safe (fail-closed) and disclosed
   in ADR-0013, but it silently over-rejects. Fix: wire power inputs into
   those callers (or an explicit fail-closed "power inputs required" error
   naming the missing flags) in a follow-up Codex task before any new
   Stage-2 run.
2. **F2 (process, before commit):** the working tree mixes Tasks A/B/C plus
   shared-state edits. Commit in separable units (A core, B scripts+docs,
   C frontend+config, shared state last) so per-task "permitted files only"
   is auditable in history.
3. **F3 (minor):** funnel report crashes with a raw JSONDecodeError on a
   malformed stage2_feasibility.json — fail-closed but ungraceful; record in
   KNOWN_ISSUES or patch to a per-artifact error entry.

## Rulings on Codex's open questions

- 1.7206 floor and breadth contract: **accepted**, with the standing caveat
  that breadth is caller-asserted; BTC/ETH independence is UNCONFIRMED, so
  callers must undercount breadth when correlation is material (a correlated
  pair is closer to breadth 1 than 2).
- pipeline_feasibility.py scope expansion: **ratified** — it is the owning
  evaluator for stage2_status and the expansion is 5 lines, self-disclosed
  in the Change Manifest.
- Legacy Stage-2 writers + orchestrator power inputs: **yes, F1's follow-up
  task should cover them.**
- H-010 next design: prefer a source-aware canonical consumer (or
  market_klines-backed venue-scoped probe) as a SEPARATE user-authorized
  task; no hypothesis retry bundled; I19 still forbids substitution.

## User authorization 2026-07-17

The user authorized all three pending decisions in this session ("都授權"):

1. Ratified the pipeline_feasibility.py scope expansion and accepted the
   1.7206 floor / breadth-counting contract (with the undercount-breadth
   caveat standing).
2. Authorized the F1 caller-regression fix task:
   `tasks/2026-07-17-stage2-power-caller-fix-codex-tasks.md` (includes F2
   commit splitting and F3 graceful funnel errors).
3. Authorized the OKX raw→canonical source-aware promotion task:
   `tasks/2026-07-17-okx-canonical-promotion-codex-tasks.md`. Data promotion
   only — NO hypothesis retry, Stage-1 spec, or H-010 verdict is authorized
   by this sign-off.

## Explicitly NOT approved by this review

No promotion, demo, shadow, or live readiness claim. The power screen is
research triage only. H-010 remains blocked until the canonicalization task
is specced, authorized, and delivered.
