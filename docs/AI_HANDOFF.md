---
status: current
type: handoff
owner: human
created: 2026-05-11
last_reviewed: 2026-05-11
expires: none
superseded_by: null
---

# AI Handoff

Cross-session memory for Claude and Codex. **Read this before starting any task. Update this before ending any session.**

---

## Current Goal

Establish AI governance infrastructure: branch/version management, CI skeleton, and regression tests for highest-risk PnL and execution logic.

## Current Branch

`main`

## Last Known Good Commit

`cb022c5` — Add TradesView, CompareView, and RiskView components  
_(Status: tests/unit pass locally; integration tests require TimescaleDB — not confirmed clean in CI)_

## System Overview

| Layer | Key files |
|---|---|
| Strategies | `src/okx_quant/strategies/` — funding_carry, pairs_trading, as_market_maker, obi_market_maker |
| Signals | `src/okx_quant/signals/` |
| Portfolio | `src/okx_quant/portfolio/` — sizing, position ledger |
| Execution | `src/okx_quant/execution/` — broker, replay_execution |
| Risk | `src/okx_quant/risk/` — risk guard, drawdown, circuit breaker |
| Backtesting | `backtesting/` — replay engine, CPCV, walk-forward, artifacts |
| API | `src/okx_quant/api/` — FastAPI server, backtest routes |
| Frontend | `frontend/` — dashboard, backtest viewer, charts |
| Data | TimescaleDB — OHLCV, funding rates, canonical candles |
| Config | `config/settings.yaml`, `config/strategies.yaml`, `config/risk.yaml` |

## Current Change Context

| Commit / PR | Change | Risk |
|---|---|---|
| PR7 `(current)` | Add branch/version management policy and PR template checklist | Governance docs only |
| PR6 | Add SWAP `ct_val` PnL regression tests for unrealized, notional, and realized PnL | Test-only coverage for portfolio accounting |

## Known Bugs / Open Issues

1. **Shadow mode mismatch** (P0): `scripts/run_shadow.py` claims SimBroker vs OKX demo comparison, but engine only instantiates SimBroker in shadow mode. No true comparison happens.
2. **SimBroker fill event gap** (P0): `ExecutionHandler.on_order()` expects WebSocket fill, but `SimBroker.submit()` does not emit a simulated fill event — blocks unified backtest/live engine path.
3. **Replay bar-level approximation** (P1): `scripts/run_backtest.py` uses per-bar approximation formulas, not the true `Strategy → Signal → Order → Fill → Ledger` path.
4. **CI gate is minimal**: `.github/workflows/ci.yml` runs ruff fatal-only baseline and unit tests only. This is a temporary baseline until existing lint debt is cleaned up; integration tests still require TimescaleDB planning.
5. **Missing regression tests**: No tests for frontend MIME, funding carry dual leg alignment, pairs trading hedge close, or replay terminal liquidation.
6. **ADR / implementation mismatch** (P0 docs): ADR-0005 validation gates are proposed, not yet enforced by replay engine. Terminal liquidation, fill-rate warning, and data coverage gate need implementation (PR12–13).

## Do Not Touch (without explicit issue + user approval)

- `src/okx_quant/strategies/` — all strategy implementations
- `src/okx_quant/risk/` — risk guard, drawdown tracker, circuit breaker
- `src/okx_quant/portfolio/` — sizing, position ledger
- `src/okx_quant/execution/broker.py` — SimBroker and execution handler
- `config/risk.yaml` — risk limits
- Any file not listed in the current issue's permitted scope

## Next Steps (in order)

1. **[PR8]** Regression test: frontend MIME smoke — `tests/unit/test_frontend_static_mime.py`
2. **[PR9]** Regression test: backtest artifact schema — `tests/unit/test_backtest_artifact_schema.py`
3. **[PR10]** Regression test: pairs trading hedge close — `tests/unit/test_pairs_trading_hedge_close.py`
4. **[PR11]** Regression test: funding carry dual leg — `tests/unit/test_funding_carry_dual_leg.py`
5. **[PR12A]** Design: terminal liquidation plan — `docs/replay_terminal_liquidation_plan.md`
6. **[PR12B]** Implementation: terminal liquidation in `backtesting/replay.py`
7. **[PR13]** Replay validation gates implementation (ADR-0005 → Accepted)
8. **[PR14A]** Design: shadow mode parity plan — `docs/shadow_mode_parity_plan.md`
9. **[PR14B]** Implementation: shadow mode SimBroker vs OKX demo gap fix

## Documentation Cleanup Next Step

After PR4 is merged, classify existing Markdown files with lifecycle metadata in a dedicated docs-only cleanup PR. Do not change strategy assumptions or implementation behavior during that cleanup.

## Open Questions

- Should `AI_WORKFLOW.md` content eventually be merged back into `ai_collaboration.md`, or kept separate permanently?
- Which commit is the last confirmed clean state for integration tests (requires DB)?
- Is `config/risk.yaml` the authoritative risk limit file or is there per-strategy risk config in `strategies.yaml`?

## Session Handoff Checklist

Before ending a session, confirm:

- [ ] Changed files listed
- [ ] Tests run (or reason stated why not)
- [ ] `AI_HANDOFF.md` updated (Known Bugs, Next Steps, Current Change Context)
- [ ] Commit has `AI-Origin:` trailer
- [ ] Issue acceptance criteria met or partial progress noted
