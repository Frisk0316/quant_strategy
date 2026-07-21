---
status: current
type: handoff
owner: codex
created: 2026-07-21
last_reviewed: 2026-07-21
expires: none
superseded_by: null
---

# Context Handoff: strategy-history / H-010 review fixes — 2026-07-21

## Goal (one sentence)

Hand the five-commit A1–A3/B1–B4 repair and delivery split to Claude for
independent review without changing E-057 or authorizing another probe.

## Current state

- Branch: `feature/h014-e052-shadow`.
- Last known good commits: `5982a7f` H-010/E-057, `b40f15b` OKX history,
  `315b041` Research Ops, and `1ef7b13` review fixes; the shared-state commit
  containing this handoff is the fifth commit at HEAD.
- In-progress edits: none after the shared-state commit. The only expected
  untracked path is
  `results/ui_funding_carry_2a3cdd23_execution_comparison.json` pending the
  user's keep/delete decision. `frontend/research_funnel.json` remains on disk
  but is ignored.
- What works right now: identity-less Stage-2 artifacts are reported; both
  frontend Ledger/Research views are syntax-checked; every registered H-010
  entry path refuses missing or mismatched frozen evidence before probing; and
  future H-010 distinctness contracts must be satisfiable before execution.
- What does not work / unfinished: Claude has not yet reviewed these fixes or
  the five commit boundaries. H-010 remains shelved and no future probe is
  authorized.

## Decisions made (and why)

- E-057 artifacts and outcome remain immutable — B1/B2 were path-contract
  defects gating reuse, not authority to rerun or rewrite the recorded result.
- Future distinctness uses the post-calibration formal candidate window and
  gating references capable of at least 365 common days — the E-057 91-day
  proxy could never satisfy its own threshold.
- Missing generic-path calibration evidence raises before `probe_xvenue` — a
  conditional check would silently bypass funding/cost/distinctness evidence.
- The five commits follow delivery ownership — future registration-before-run
  ordering and rollback are now inspectable in Git.

## Open questions / unverified assumptions

- Claude review of the fixes and per-commit diff boundaries is pending.
- Browser eyeball of the expanded Ledger row and digit checks for the remaining
  13/22 history sections remain inherited UNCONFIRMED items.
- User decision on the stray execution-comparison JSON remains open.

## Rules in play (preserve verbatim)

- Invariants touched: I46 isolates malformed Stage-2 artifacts; I48 requires
  execution-venue funding; I49 requires a structurally satisfiable future
  distinctness overlap before any H-010 probe.
- Domain rules touched: R3.2, R3.4, R6.3, R6.6, R7.4.
- Do-not-touch: `research/` except the explicitly authorized ledger wording;
  existing `results/**`; strategy/signal/risk/portfolio/execution core;
  `config/risk.yaml`; Stage 3, reprobe, retry, promotion, and deployment gates.

## Context to load next (the reading list)

- Source of truth: `tasks/2026-07-18-strategy-history-h010-claude-review.md`,
  `research/strategy_synthesis.md`, `config/`, and
  `docs/change_manifests/2026-07-18-h010-stage2-pipeline.md`.
- Owning files: `backtesting/pipeline_stage2_registry.py`,
  `backtesting/xvenue_leadlag_probe.py`,
  `scripts/run_pipeline_funnel_report.py`, and the matching unit tests.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run

- Red-first B2 regression — failed before the fix because the forbidden probe
  ran without frozen evidence; passed after the guard was added.
- Focused review suites — `23 passed`.
- Broader targeted matrix — `80 passed`.
- Full unit suite — `921 passed, 1 skipped`.
- Ruff, frontend syntax, config, backtest smoke, metadata, links, ledger
  consistency, and strict doc impact — passed; exact tails are in the paired
  session handoff and final task report.
- E-057 file SHA-256 values remain
  `386830A00BFC50CCFC65B9A1EE9A43C8125DA17817D3BB39B56F4568DC939BD3`
  and `5E167003721281082E678A0396FB4D8E48D5D330906FF20D96A9FD5DB6E1000F`.

## Approvals

- Human approval obtained for A1–A3/B1–B5 and the five commits. No approval was
  granted for Stage 3, reprobe, retry, promotion, demo, shadow, or live work.

## Next action (single, concrete)

- Claude reviews `git log --oneline -5`, each commit's `--stat`, the B1/B2
  contract repairs, and the unchanged E-057 hashes.

## Human Learning Notes

Fail-closed results can still hide an unusable contract or an unguarded sibling
entry path. Reviewing whether a gate is mathematically reachable, and checking
every callable entry point, caught defects that ordinary happy-path tests did
not. Committing one delivery at a time also turns ex-ante ordering from a claim
into inspectable evidence.
