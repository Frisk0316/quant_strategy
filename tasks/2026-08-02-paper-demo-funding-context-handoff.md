---
status: current
type: handoff
owner: codex
created: 2026-08-02
last_reviewed: 2026-08-02
expires: none
superseded_by: null
---

# Context Handoff: Paper Demo funding execution — 2026-08-02

## Goal (one sentence)

Verify that the user-supplied Binance and OKX Demo credentials cannot route to
real funds, complete bounded Demo trades, and exercise the funding-carry and
future strategy-test paths without changing strategy assumptions.

## Current state

- Branch: `feature/deribit-moneyness-hypotheses`.
- Last known good commit / state: pre-task HEAD `1de87c8`; task changes remain uncommitted.
- In-progress edits (files): Binance/OKX execution clients and smokes, common OKX broker/portfolio/data-handler/engine paths, targeted tests, governance/runbook/current-state docs.
- What works right now: Binance Spot Demo place/cancel/no-open-order; Binance USD-M Demo auth with flat-account no-exposure block; OKX Demo REST place/cancel and private WS subscriptions; current funding decision; dual-leg replay/test workflow.
- What does not work / unfinished: Spot/perp funding orders are not atomic across legs; no live/promotion claim is allowed.

## Decisions made (and why)

- Binance Spot is fixed to `demo-api.binance.com`, not legacy `testnet.binance.vision`, because unified Demo keys are environment-specific.
- USD-M may fall back to the unified Demo key, while explicit `BINANCE_FUTURES_*` values retain precedence.
- The live 12% funding entry gate was preserved; current 0.229% APR correctly produced no order.
- No forced real Demo funding position was opened because lowering the gate would change the strategy assumption; synthetic/replay dual-leg tests cover the entry path.

## Open questions / unverified assumptions

- What compensating/reconciliation policy should close the non-atomic Spot/perp execution gap? Claude/human review required before promotion work.

## Rules in play (preserve verbatim)

- Invariants touched: I60 — paper clients are fixed to non-production hosts; signed time, venue formats, nested results, and both fill channels must pass before calling a lifecycle successful.
- Domain rules touched: R5.1, R5.2, R7.2.
- Do-not-touch: `research/`; funding thresholds; risk limits; live/shadow/demo gates; Deribit H-014 Phase-2 activation.

## Context to load next (the reading list)

- Source of truth: `config/settings.yaml`, `config/strategies.yaml`, `config/risk.yaml`, `research/strategy_synthesis.md`, ADR-0017/0018.
- Owning files / MODULE_BRIEFS: `docs/FEATURE_MAP.md`; execution, portfolio, market-data, and deployment/config owners.
- Context Pack: no deployment-specific pack exists; start from `docs/CONTEXT_INDEX.md` and `docs/CONTEXT_PACKS/README.md`.

## Checks run

- Authenticated Binance Spot Demo and OKX Demo place/cancel — passed.
- Binance USD-M Demo and OKX private WS authentication — passed; USD-M order leg blocked safely on a flat account.
- Targeted funding/execution tests — passed.
- Config, backtest smoke, Ruff, docs impact, docs metadata/link/ledger checks — passed; two pre-existing metadata warnings remain.

## Approvals

- Human approval obtained in the 2026-08-02 request to verify and execute Demo trading/funding strategy plumbing.
- No approval exists for live funds, strategy promotion, funding threshold changes, or Deribit Phase 2.

## Next action (single, concrete)

- Claude reviews the funding-carry non-atomic cross-leg boundary and recommends the smallest fail-safe reconciliation contract before any sustained Demo strategy run.

## Human Learning Notes

Binance unified Demo and legacy Spot Testnet keys are not interchangeable. A
successful authenticated balance read is weaker than a place/cancel/no-residual
round trip, and a valid low funding rate should produce no trade rather than a
forced demonstration position.
