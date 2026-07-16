---
status: accepted
type: adr
owner: claude
created: 2026-07-14
last_reviewed: 2026-07-14
expires: none
superseded_by: null
---

# ADR-0011: Deribit Options Shadow-Execution Layer (v1, shadow-only)

## Status

Accepted — 2026-07-14, explicit user authorization in-session ("先授權
deribit 執行層") to start the execution layer in parallel with E-052.
Scope is deliberately SHADOW-ONLY: this ADR authorizes no real order, no
private-key trading permission, no live/demo claim. Real order placement
requires a future ADR plus the R7.2 gate sequence and explicit user approval.

## Context

H-014 (RICH-regime covered call + put spread, coin-denominated) passed the
statistical gate (E-051, user-ratified checkpoint ①); the E-052 second-bear
extension is running. The next R7.2 gate is portable validation: the research
assumptions (t+1 VWAP fills, tranche ladder, R8 accounting) must be checked
against live market reality before any promotion discussion. The platform has
no Deribit execution surface — existing Deribit code is data-only.

## Decision

Build a shadow-execution layer that runs the ratified strategy against LIVE
Deribit public data and journals what it WOULD have done, with zero
order-placement capability in the codebase path it uses.

1. **Production parameters are frozen at the CPCV-selected combo**
   (`ivp_min=85, z_min=0.5`; every E-051 fold selected it). Any change is a
   config-gated event requiring user approval.
2. **Signal engine:** daily job recomputes IVP(365d)/VRP-z(90d) from the
   ingested hourly DVOL (`published_at` as-of, F26) and canonical closes —
   the same definitions as the research series, sourced from the DB.
3. **Intent generator:** on a RICH day, emit tranche intents at t+1 —
   1/30-unit short ~25Δ call + short 25Δ/long 10Δ put spread per symbol,
   nearest-30d expiry among instruments listed at intent time, aggregate cap
   1.0 unit/symbol. R8.3 is enforced in code: any intent set that would leave
   a naked short put is rejected (I39 surface).
4. **Shadow fill model:** at intent time, capture the live order book
   top-of-book; hypothetical fill = hit the bid for sells / lift the ask for
   buys (conservative), fees per R8.4. Also record mid, spread, book depth,
   and the day's later trade VWAP so shadow-vs-research fill bias is
   measurable per leg.
5. **Journal:** append-only JSONL under `results/shadow_h014/` (file-based;
   no DB schema change in v1 — avoids the A6 trigger). Each record carries
   signal inputs, intent, book snapshot, hypothetical fill, and R8 accounting
   fields. Daily mark-to-market and settlement records mirror the research
   runner so the shadow equity curve is directly comparable to E-051/E-052.
6. **Ops:** a single scheduled task (documented in RUNBOOK, registered only
   with user approval per the standing scheduler decision); kill-switch =
   removing the task; no credentials required (public endpoints only).
7. **Exit criteria for v1:** ≥ 8 weeks of shadow journal AND a written
   shadow-vs-research bias report (fill bias per leg, missed-entry rate,
   mark tracking error). Meeting them unlocks the live-execution ADR
   discussion, not live trading itself.

## Consequences

- Portable-validation evidence accrues while E-052 and PR reviews proceed.
- Zero capital, credential, or gate risk in v1; the naked-put prohibition and
  unit cap get their first in-code enforcement, reusable by any later live layer.
- File-based journaling defers DB schema work; if shadow graduates, a proper
  schema lands with the live ADR.
- Implementation ownership: Codex (per AGENTS.md role split), Claude reviews;
  the user may reassign to Claude explicitly.

## Alternatives considered

- Straight-to-demo with real testnet orders: rejected — Deribit test env
  differs materially in liquidity; shadow-on-real-book measures what we
  actually need (fill realism) without credentials.
- DB-schema journal now: rejected for v1 — triggers A6 manifest/ADR work
  before we know the journal shape is right.
- Paper-trading inside the backtest runner: rejected — the point is an
  independent live-data path, not the research code grading itself.
