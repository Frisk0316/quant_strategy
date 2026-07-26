---
status: current
type: handoff
owner: codex
created: 2026-07-26
last_reviewed: 2026-07-26
expires: none
superseded_by: null
---

# Context Handoff: H-022/E-059 taker-flow Stage 2 — 2026-07-26

## Goal (one sentence)

Verify the completed ETH raw repair, run the preregistered frozen E-059
data-gap repair probe with ADR-0015 alias consumption, and stop without
retuning or Stage 3 on any failed check.

## Current state

- Branch: `feature/h014-e052-shadow`.
- Last known good commit / state: `592b757` preregisters E-059 before
  `049d136` wires the alias and commits the immutable result.
- In-progress edits (files): E-059 outcome/state/handoff synchronization only;
  unrelated pre-existing runtime/API changes remain unstaged and must not be
  overwritten.
- What works right now: ETH is complete at 898/898 UTC member-days and
  1,293,120/1,293,120 exact raw/taker rows. E-059 passes data, distinctness,
  and cost.
- What does not work / unfinished: statistical power fails at plausible net
  Sharpe 0.448466 below the 0.754896 floor. H-022 is shelved; Claude review is
  pending.

## Decisions made (and why)

- Set H-022 to `shelved`, not `testing` — because E-059 failed one of four
  frozen Stage-2 checks.
- Preserve trials at 0 and K at 0/2 — because no Stage-3 grid ran.
- Do not retune or rerun — because the authorized task requires an honest stop
  on any E-059 failure.

## Open questions / unverified assumptions

- Claude should review whether the fall from E-058 power 0.780894 to E-059
  0.448466 is the expected consequence of complete ETH plus economic-asset
  alias consumption; the artifact itself is deterministic and internally
  consistent.
- H-002 remains advisory only at absolute correlation 0.421862.

## Rules in play (preserve verbatim)

- R6.3: family-cumulative trials cannot be hidden or reset.
- R6.6: gating-reference overlap and correlation thresholds are declared
  ex ante.
- R6.7 / I50: membership bytes are immutable; alias collapse is
  exchange-scoped, order-preserving, consumer-time, post-selection, and cannot
  refill rank N+1.
- Do-not-touch: `research/`; membership parquet; E-058 bytes; existing result
  artifacts; trading core; `config/risk.yaml`; Stage 3; deployment gates;
  unrelated working-tree changes.

## Context to load next (the reading list)

- Source of truth:
  `tasks/2026-07-24-e058-repair-e059-codex-tasks.md`,
  `tasks/2026-07-24-e058-claude-review.md`,
  `docs/ADR/0015-consumer-time-economic-asset-aliases.md`,
  `docs/EXPERIMENT_REGISTRY.md`, and `docs/HYPOTHESIS_LEDGER.md`.
- Owning files / MODULE_BRIEFS: `backtesting/taker_flow_probe.py`,
  `backtesting/universe_aliases.py`, and
  `backtesting/pipeline_stage2_registry.py`.
- Context Pack: start from `docs/CONTEXT_INDEX.md`; no narrower task pack
  exists.

## Checks run

- T1 read-only year/day/raw/taker query — 2024 366/366 and 527,040 rows;
  2025 365/365 and 525,600; 2026 167/167 and 240,480; total 898/898 and
  1,293,120.
- `python -m pytest tests/unit/test_universe_aliases.py
  tests/unit/test_taker_flow_probe.py
  tests/unit/test_pipeline_stage2_registry.py -q --tb=short
  -p no:cacheprovider` — 29 passed.
- `python -m pytest tests/unit/ -q --tb=short -p no:cacheprovider` —
  956 passed, 1 skipped.
- Full Ruff, docs metadata/feature-map/ledger, strict doc impact, config, and
  backtest smoke — passed.
- Membership SHA-256:
  `9822810321262e76a65bccf18a519ac2f61f05f986bd13b730c0cb3d9e1657c5`.
- E-058 SHA-256:
  `a61f58c0c2ea8b539b6cb0896abde6cd50e1154a7bbd59794db11f3b7a275a10`.
- E-059 SHA-256:
  `0eefc5531d075202aa688ae052e9d159c6b7f2d494b76ccd0080dea9c352acee`.

## Approvals

- Human approval obtained for T1/T2 and the conditional E-059 reprobe.
- No approval exists for retuning, Stage 3, promotion, demo, shadow, or live.

## Next action (single, concrete)

- Claude reviews the ordered E-059 commits, four-check deltas versus E-058,
  artifact hash, and the disclosed execution-harness overlap.

## Human Learning Notes

Docker Desktop had stopped, so the existing TimescaleDB volume had to be
started before verification. A host `Start-Process` invocation ran detached
even though its PID was not surfaced to the sandbox; a later identical
foreground invocation reached the immutable writer after the detached run and
was rejected with `FileExistsError`. The first artifact is intact and the
second invocation changed no bytes. Use a yielded long-running execution cell,
not detached host processes, for future multi-minute probes.
