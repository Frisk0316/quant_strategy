---
status: current
type: handoff
owner: codex
created: 2026-07-17
last_reviewed: 2026-07-17
expires: none
superseded_by: null
---

# Context Handoff: Stage-2 caller repair and OKX canonical promotion — 2026-07-17

## Goal (one sentence)

Ratify the Stage-2 power contract, repair its callers/funnel, and promote the
authorized OKX raw window into a safe source-aware canonical layer without
changing H-010 research evidence or deployment gates.

## Current state

- Branch: `feature/h014-e052-shadow`.
- Last known good code commits: `497c7b7` (A/F1), `d4f23cb` (B audit),
  `bc1a7ba` (C frontend/config), `4aadf4f` (OKX data).
- In-progress edits: shared governance/current-state docs and this handoff are
  intended for the final shared-state commit; unrelated H-021 handoffs remain
  untracked and untouched.
- What works: active Stage-2 callers reject missing candidate inputs; malformed
  funnel artifacts are isolated; source-aware OKX BTC/ETH coverage, alignment,
  and raw parity all pass; promotion rerun changes zero rows.
- Unfinished: Claude review and any separately authorized future H-010 research
  action. No H-010 retry, verdict, Stage 3, or deployment work is in progress.

## Decisions made (and why)

- Ratify the computed `1.7206` reference case, not a universal constant — the
  floor is input-dependent and breadth remains caller-asserted.
- Reject missing power inputs before probe/artifact/status mutation — a caller
  defect must not become terminal candidate evidence.
- Keep resolved `canonical_candles` unchanged and add a venue-keyed layer — an
  in-place identity migration would mix existing CAGGs and block roughly 96
  million rows.
- Use raw rather than `market_klines` for this promotion — frozen Binance ETH is
  incomplete in `market_klines`, while all four raw legs are exact.

## Open questions / unverified assumptions

- BTC/ETH independent-bet breadth is still UNCONFIRMED; correlated bets must be
  undercounted.
- No source-aware 5m/15m/1H CAGG exists; add one only for a separately approved
  consumer with a demonstrated need.

## Rules in play (preserve verbatim)

- Invariants: I19 no cross-venue substitution; I23 family-cumulative trials;
  I45 caller inputs before mutation; I46 artifact isolation; I47 resolved versus
  source-aware identity and exact raw parity.
- Domain rules: R6.2, R6.3, R6.4, R6.5, R7.4.
- Do-not-touch: `research/`, hypothesis/experiment ledgers, existing `results/**`,
  strategy/signal/risk/portfolio/execution logic, and demo/shadow/live gates.

## Context to load next (the reading list)

- Source of truth: user authorization in
  `tasks/2026-07-17-abc-delivery-claude-review.md`; ADR-0013 and ADR-0014.
- Owning files: `backtesting/pipeline_stage2_registry.py`,
  `backtesting/pipeline_orchestrator.py`, `src/okx_quant/data/candle_store.py`,
  `scripts/run_pipeline_funnel_report.py`, and the two 2026-07-17 task specs.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run

- Full unit: `896 passed, 1 skipped`; skip is the existing Windows symlink case.
- Targeted Stage-2: `31 passed`; targeted source-aware data: `45 passed`.
- Ruff, docs metadata/links/ledger/strict impact, config, frontend syntax,
  backtest smoke, and `git diff --check`: PASS.
- Real DB verifier: PASS; each symbol raw=venue=1,293,120, mismatch=0,
  alignment=1.0, resolved OKX=0. Second promotion changed 0 rows.

## Approvals

- Obtained explicitly from the user on 2026-07-17 for scope/floor ratification,
  F1/F2/F3, and OKX data promotion only.

## Next action (single, concrete)

- Claude reviews commits `497c7b7..4aadf4f` plus the final shared-state commit
  against ADR-0013/0014 and confirms no H-010 research claim leaked in.

## Human Learning Notes

`source_primary` was metadata, not part of the old canonical identity; repeated
OKX ingest could never coexist with Binance. The additive layer avoided a
blocking key/CAGG migration. Large source-aware verification scans are CPU/IO
heavy but did not wait on locks; DB-side counts avoided returning 1.29 million
`RETURNING` records to Python.
