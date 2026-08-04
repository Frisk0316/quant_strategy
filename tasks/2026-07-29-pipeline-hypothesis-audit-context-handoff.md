---
status: current
type: handoff
owner: codex
created: 2026-07-29
last_reviewed: 2026-07-29
expires: none
superseded_by: null
---

# Context Handoff: Pipeline Hypothesis Audit — 2026-07-29

## Goal (one sentence)
Audit the collaboration model, identify genuinely untested H-0xx hypotheses,
assess pipeline throughput, and run validation only if a safe candidate exists.

## Current state
- Branch: `feature/deribit-moneyness-hypotheses`.
- Last known good state: `ad981c0`; Claude accepted E-069..E-076.
- In-progress edits: this handoff and its paired session handoff only.
- Works: H-030..H-037 have immutable, hash-matching Stage-2 artifacts.
- Unfinished: no untested candidate currently has authorization, sufficient
  data, and a registered deterministic runner at the same time.

## Decisions made (and why)
- No new experiment ran because the ADR-0016 complete-round quota is not met
  and neither H-028 nor H-038 is presently executable.
- Do not use the legacy batch-1 S5 command for H-038: it is not an immutable
  H-038 Stage-2 path and does not implement the repaired-universe contract.
- Keep pipeline execution sequential until profiling identifies execution
  throughput, rather than candidate readiness, as the bottleneck.

## Open questions / unverified assumptions
- H-038 needs explicit authorization and a dedicated Stage-2-only contract.
- Resolve F-S5 trial accounting before H-038: its ledger says cumulative 72,
  while E-009 and E-014 each record 72 trials.
- H-031/H-035, H-033/H-036, and H-037 need separately approved data work
  before their mechanisms can be measured.

## Rules in play (preserve verbatim)
- Invariants: I23 family-cumulative trials; I28 no bare gate-chasing retry;
  I53 result-blind 10-15 / 8 new / 2 iteration manifest; I54 deterministic
  evidence boundary.
- Domain rules: R6.3, R6.8, R6.9, R7.1, R7.2.
- Do not touch: `research/`, existing `results/**`, strategy/risk/execution
  behavior, deployment gates, or the accepted slate artifacts.

## Context to load next (the reading list)
- Source of truth: `docs/HYPOTHESIS_LEDGER.md`,
  `docs/EXPERIMENT_REGISTRY.md`, `docs/ADR/0016-genai-discovery-deterministic-strategy-evaluation.md`.
- Owning files: `docs/FEATURE_MAP.md` "Strategy Research Pipeline Automation";
  `backtesting/pipeline_round.py`, `backtesting/pipeline_orchestrator.py`,
  `backtesting/pipeline_stage2_registry.py`.
- Candidate specs: `docs/superpowers/specs/2026-07-29-event-probe-hypotheses.md`
  and `docs/superpowers/specs/2026-07-29-literature-slate-h032-h037.md`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run
- `scripts/docs/check_ledger_consistency.py` — PASS: 39 hypotheses,
  77 experiments, 33 K-budget families.
- Targeted pipeline tests — PASS: 47 tests.
- Recomputed all eight E-069..E-076 SHA-256 files — all matched; no extra
  Stage-3 files were present.

## Approvals
- No approval was needed for this read-only audit.
- H-038 still needs explicit terminal-retry authorization after its runner and
  trial-accounting contract are reviewable.

## Next action (single, concrete)
- Ask the human whether to authorize an H-038 Stage-2-only registration/runner
  task after first reconciling its family-cumulative trial count.

## Human Learning Notes
`pending` registry rows are append-only history, not a runnable queue. Candidate
readiness is currently limited by data, deterministic contracts, and honest
iteration eligibility—not by CPU parallelism.
