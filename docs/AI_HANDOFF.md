# AI Handoff

Cross-session memory for Claude and Codex. **Read this before starting any task. Update this before ending any session.**

---

## Current Goal

Establish AI governance infrastructure: workflow docs, issue templates, CI skeleton, and regression tests for highest-risk PnL and execution logic.

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

## Recent Changes (last 5 sessions)

| Commit / PR | Change | Risk |
|---|---|---|
| PR3 `(current)` | Fix PR1/PR2 doc consistency: funding sign, ADR-0005 status, MIME `.js`, templates | Docs only + one-line server.py fix |
| `389939a` fix | Route `DATABASE_URL` through `cfg` so local backtest scripts write to DB | `config.py` + `artifacts.py` only |
| PR2 `b58ad3e` | Add `ARCHITECTURE.md` and `ADR/0001–0005` | Some ADRs describe target behavior not yet fully implemented |
| PR1 `55b9d67` | Add AI workflow, handoff, debugging runbook, PR/issue templates, `.gitignore` fixes | Governance docs only |
| `cb022c5` | Add TradesView, CompareView, RiskView to frontend | Frontend regression risk if component imports break |

## Known Bugs / Open Issues

1. **Shadow mode mismatch** (P0): `scripts/run_shadow.py` claims SimBroker vs OKX demo comparison, but engine only instantiates SimBroker in shadow mode. No true comparison happens.
2. **SimBroker fill event gap** (P0): `ExecutionHandler.on_order()` expects WebSocket fill, but `SimBroker.submit()` does not emit a simulated fill event — blocks unified backtest/live engine path.
3. **Replay bar-level approximation** (P1): `scripts/run_backtest.py` uses per-bar approximation formulas, not the true `Strategy → Signal → Order → Fill → Ledger` path.
4. **No CI gate**: No `.github/workflows/` — no automated test enforcement on PRs.
5. **Missing regression tests**: No tests for ct_val PnL, funding carry dual leg alignment, pairs trading hedge close, or replay terminal liquidation.
6. **ADR / implementation mismatch** (P0 docs): ADR-0005 validation gates are proposed, not yet enforced by replay engine. Terminal liquidation, fill-rate warning, and data coverage gate need implementation (PR10–11).

## Do Not Touch (without explicit issue + user approval)

- `src/okx_quant/strategies/` — all strategy implementations
- `src/okx_quant/risk/` — risk guard, drawdown tracker, circuit breaker
- `src/okx_quant/portfolio/` — sizing, position ledger
- `src/okx_quant/execution/broker.py` — SimBroker and execution handler
- `config/risk.yaml` — risk limits
- Any file not listed in the current issue's permitted scope

## Next Steps (in order)

1. **[Done]** PR1 — AI governance docs, GitHub templates, `.gitignore` fixes
2. **[Done]** PR2 — `ARCHITECTURE.md`, `ADR/0001–0005`
3. **[Done]** PR3 — Fix PR1/PR2 doc consistency (funding sign, ADR-0005 status, MIME `.js`, templates)
4. **[PR4]** CI skeleton: `.github/workflows/ci.yml` with ruff + pytest unit gate
5. **[PR5]** Regression test: SWAP `ct_val` PnL — `tests/unit/test_position_pnl_accounting.py`
6. **[PR6]** Regression test: frontend MIME smoke — `tests/unit/test_frontend_static_mime.py`
7. **[PR7]** Regression test: backtest artifact schema — `tests/unit/test_backtest_artifact_schema.py`
8. **[PR8]** Regression test: pairs trading hedge close — `tests/unit/test_pairs_trading_hedge_close.py`
9. **[PR9]** Regression test: funding carry dual leg — `tests/unit/test_funding_carry_dual_leg.py`
10. **[PR10A]** Design: terminal liquidation plan — `docs/replay_terminal_liquidation_plan.md`
11. **[PR10B]** Implementation: terminal liquidation in `backtesting/replay.py`
12. **[PR11]** Replay validation gates implementation (ADR-0005 → Accepted)
13. **[PR12A]** Design: shadow mode parity plan — `docs/shadow_mode_parity_plan.md`
14. **[PR12B]** Implementation: shadow mode SimBroker vs OKX demo gap fix

## Open Questions

- Should `AI_WORKFLOW.md` content eventually be merged back into `ai_collaboration.md`, or kept separate permanently?
- Which commit is the last confirmed clean state for integration tests (requires DB)?
- Is `config/risk.yaml` the authoritative risk limit file or is there per-strategy risk config in `strategies.yaml`?

## Session Handoff Checklist

Before ending a session, confirm:

- [ ] Changed files listed
- [ ] Tests run (or reason stated why not)
- [ ] `AI_HANDOFF.md` updated (Known Bugs, Next Steps, Recent Changes)
- [ ] Commit has `AI-Origin:` trailer
- [ ] Issue acceptance criteria met or partial progress noted
