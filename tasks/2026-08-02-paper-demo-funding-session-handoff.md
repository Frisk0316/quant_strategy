---
status: current
type: handoff
owner: codex
created: 2026-08-02
last_reviewed: 2026-08-02
expires: none
superseded_by: null
---

# Session Handoff: Paper Demo funding execution — 2026-08-02

## Implementation summary

Moved Binance Spot to the official unified Demo host, synchronized signed
client clocks, reused the unified key safely for USD-M, repaired OKX Demo order
format/result handling, and completed authenticated Demo smokes. Funding-carry
now queues tick-aligned SWAP and cash-Spot legs with both fill channels visible;
current-rate evaluation respected the unchanged APR threshold.

## Diff scope

- Files added: OKX smoke unit test, Change Manifest, Context Handoff, Session Handoff.
- Files changed: bounded smoke scripts; Binance clients; OKX broker; portfolio manager; market-data handler; engine; targeted tests; runbook/governance/current-state/workstream docs.
- Files deleted: none.

## Business-rule change?

- Yes, A2 execution boundary behavior. Change Manifest at `docs/change_manifests/2026-08-02-paper-demo-execution-reliability.md`; DOC_IMPACT_MATRIX row A2 checked. No accounting formula, funding threshold, risk limit, or promotion gate changed.

## Source-of-truth updates

- research/strategy_synthesis.md: N/A; not modified.
- config/: `config/workstreams.yaml` status only; trading/risk config unchanged.
- ADR: N/A; no major policy change.

## Experiments

- HYPOTHESIS_LEDGER entries: none.
- EXPERIMENT_REGISTRY entries: none.

## Tests / checks run

- Targeted funding/execution tests: passed.
- Authenticated Binance Spot and OKX Demo place/cancel: passed.
- Binance USD-M and OKX private WS auth: passed; flat USD-M exposure blocked.
- Current OKX BTC funding decision: 0.229% APR versus 12% gate, no signal.
- Backtest/config/Ruff/docs checks: passed; `make` itself unavailable on this Windows host, so its underlying Python targets ran directly.

## Docs updated

- Change Manifest, RUNBOOK, INVARIANTS I60, FAILURE_MODES F63, KNOWN_ISSUES, CHANGELOG_AI, AI_HANDOFF, CURRENT_STATE, and workstream status.

## Known limitations / risks

- Funding Spot/perp venue submissions remain non-atomic; one leg may fill while the other rejects.
- Demo/test evidence does not establish profitability, promotion, or live readiness.
- No actual funding entry occurred because the current rate was below the unchanged gate.

## Rollback plan

- Revert the task's code/tests/docs. Return to the legacy Binance Spot host only when intentionally using a separate legacy Testnet key.

## Context Handoff

- See `tasks/2026-08-02-paper-demo-funding-context-handoff.md`.

## Questions for human review

- Should Claude specify a compensating cancel/hedge reconciliation contract before a sustained funding-carry Demo run?

## Next recommended task

- Design and review the smallest fail-safe cross-leg reconciliation behavior, then add one bounded Demo integration test without changing the 12% entry gate.

## Human Learning Notes (required)

The main blockers were environment identity and venue boundary details, not the
credentials themselves: unified Binance Demo has a different Spot host, OKX
rejects non-alphanumeric tags, and nested response codes/fill-channel coverage
must be checked. A no-signal result is the correct successful strategy outcome
when current funding is below threshold.
