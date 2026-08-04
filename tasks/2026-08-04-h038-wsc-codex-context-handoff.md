---
status: current
type: handoff
owner: codex
created: 2026-08-04
last_reviewed: 2026-08-04
expires: none
superseded_by: null
---

# Context Handoff: H-038 E-094 and WS-C C3/C5/C10 — 2026-08-04

## Goal (one sentence)

Complete the authorized terminal H-038 Stage-2 probe and the three authorized
WS-C order-correctness fixes without changing strategy, deployment, or gates.

## Current state

- Branch: `feature/deribit-moneyness-hypotheses`; pushed baseline `3e7d26f`.
- Last known good state: local H-038 and WS-C task work passes targeted checks,
  full unit tests, Ruff, ledger consistency, strict docs impact, docs check, and
  config check.
- In-progress edits: none for the task; the pre-existing untracked public-status
  handoff is preserved and is not part of this delivery.
- What works: C5 fails closed on rejected/incomplete instrument metadata; C3
  preserves reduce-only and `posSide`; C10 shares maintained `OkxBook` mids.
- What does not work: H-038 stopped at data availability because one required
  SOL minute is absent. No positions, later Stage-2 checks, or Stage 3 exist.

## Decisions made (and why)

- E-094 is a strict data FAIL because 17,271/17,272 is below the frozen 100%
  member-day requirement; a one-minute repair or narrower window would be a
  forbidden gate-chasing rerun.
- Breadth is 1 only as a fail-closed downstream input because the data gate
  prevented an admissible position series; it is not inferred from universe size.
- F-S5 is terminal at K 2/2 regardless of the data-only outcome, per the user-
  authorized task contract.
- OKX top-level response `code` must equal string `"0"`; missing/nonzero codes
  stop broker construction before any order state exists.

## Open questions / unverified assumptions

- Claude should confirm the terminal data-fail interpretation and the separate
  SHA-bound breadth provenance package.
- Claude should confirm hedge-mode `short` reduce-only semantics for the caller-
  supplied `posSide`; net-mode behavior remains covered.

## Rules in play (preserve verbatim)

- Invariants touched: I68 (breadth derived from realized positions, fail closed
  to 1), I69 (complete runtime instrument specs), I70 (reduce-only and matching
  `posSide` reach OKX), I71 (maintained-book mid for deltas).
- Domain rules touched: R1.6, R1.7, R4.2.
- Do-not-touch: `src/okx_quant/strategies/s5_residual_meanrev.py`, all existing
  `results/**`, live/demo/shadow gates, WS-C C1/C2/C4/C6/C7/C8/C9/C11, F2,
  `config/risk.yaml`, and research-owned files.

## Context to load next (the reading list)

- Source of truth: `AI_CONTEXT.md`, `research/strategy_synthesis.md`,
  `docs/DOMAIN_RULES.md`, `docs/INVARIANTS.md`, `docs/HYPOTHESIS_LEDGER.md`,
  `docs/EXPERIMENT_REGISTRY.md`, and the two 2026-08-04 task files.
- Owning files / MODULE_BRIEFS: `docs/FEATURE_MAP.md`,
  `docs/MODULE_BRIEFS/backtesting-engine.md`,
  `docs/MODULE_BRIEFS/portfolio.md`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run

- H-038 probe + registry tests: 24 passed.
- Full unit suite: 1,142 passed, 1 skipped.
- Ruff on changed Python files: passed.
- Ledger consistency: 47 hypotheses, 95 experiments, 39 K-budget families.
- Strict docs impact, docs check, config check, and diff check: passed; docs
  check retained two pre-existing metadata warnings.
- Independent artifact hashes matched both SHA sidecars.

## Approvals

- User explicitly authorized H-038 and WS-C C3/C5/C10 on 2026-08-04.
- No remaining task action requires broader authorization; Claude review and
  any merge/push remain separate decisions.

## Next action (single, concrete)

- Claude reviews the H-038 immutable evidence package and the three WS-C diffs;
  do not rerun H-038 or implement any remaining WS-C/F2 item.

## Human Learning Notes

A nearly complete universe is still incomplete under a 100% frozen gate: the
single missing SOL minute correctly prevented both a backtest and an invented
breadth. At the execution boundary, preserving intent requires checking the
whole path, not only the final broker kwargs; the first review caught that
`OrderManager` had dropped `posSide` before the request was built.
