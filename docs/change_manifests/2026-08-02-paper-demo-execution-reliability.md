---
status: current
type: manifest
owner: codex
created: 2026-08-02
last_reviewed: 2026-08-02
expires: none
superseded_by: null
---

# Change Manifest: Paper Demo execution reliability

## Summary

Repair Binance/OKX Demo connectivity and the common OKX order boundary so
paper orders can be authenticated, venue-valid, observed, and cancelled.

## Business rule(s) affected

R5.1, R5.2, R7.2. PnL, fee, funding, sizing thresholds, and promotion rules are
unchanged.

## Trigger area(s) (DOC_IMPACT_MATRIX)

A2 portfolio/execution.

## Files changed

- `src/okx_quant/execution/`, `src/okx_quant/portfolio/portfolio_manager.py` — fixed Demo signing and venue order validation.
- `src/okx_quant/data/market_data_handler.py`, `src/okx_quant/engine.py` — observe Spot fills and use Spot cash mode.
- `scripts/run_*_smoke.py` — bounded Demo order/cancel reliability.
- `tests/unit/` — regressions for clocks, nested results, tick-aligned dual legs, and private subscriptions.

## Behavior delta

- Before: Binance used the legacy Spot Testnet host; signed requests trusted the local clock; OKX invalid tags/prices or nested rejects could break or misstate the lifecycle; Spot fills were not subscribed.
- After: fixed Demo hosts, clock sync, venue-valid OKX inputs, nested result validation, Spot cash mode/fill observation, and bounded place/cancel confirmation.
- Money/risk impact: simulated funds only. No live host was added and no risk or entry threshold changed.

## Source-of-truth updates

- research/strategy_synthesis.md: N/A — strategy assumptions unchanged.
- config/: `config/workstreams.yaml` state only; trading/risk config unchanged.
- ADR: N/A — mechanical paper-execution repair under existing demo-only policy.

## Docs updated (from DOC_IMPACT_MATRIX row)

- [x] `docs/DOMAIN_RULES.md` — reviewed; rules unchanged.
- [x] `docs/INVARIANTS.md` — I60 added.
- [x] `docs/FAILURE_MODES.md` — F63 added.
- [x] `docs/RUNBOOK.md`, `docs/KNOWN_ISSUES.md`, current-state/handoff docs updated.

## Invariants / golden cases

- Invariants checked: I9, I10, I14, I60.
- Golden cases affected: N/A; no accounting formula changed.

## Tests / checks run

- Targeted execution/funding tests: 26 passed.
- Binance Spot and OKX authenticated Demo place/cancel: passed.
- Binance USD-M and OKX private WS authentication: passed; flat USD-M order smoke blocked by design.
- Config and backtest smoke: passed.

## Risks and rollback

- Risks: funding Spot/perp submissions remain non-atomic; Demo results are not live evidence.
- Rollback: revert the listed code/tests/docs; restore the previous Binance Spot host only if intentionally returning to legacy Testnet keys.

## Approval

- Human approval required: yes — obtained from the user's 2026-08-02 request to verify and execute Demo trading/funding strategy plumbing.
