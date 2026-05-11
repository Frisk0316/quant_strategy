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

| Commit | Change | Risk |
|---|---|---|
| `cb022c5` | Add TradesView, CompareView, RiskView to frontend | Frontend regression risk if component imports break |
| `48b7321` | Add validation options for backtests, enhance replay validation | Replay result schema may have changed |
| `50849e6` | Add backtest viewer with API server and DB integration | API route/schema dependency with frontend |
| `725e9aa` | SQL scripts for mirroring funding rates and canonicalizing market data | Data pipeline dependency for replay tests |
| `b1926bd` | Enhance funding rate ingestion and diagnostics SQL | Funding carry backtest depends on this data |

## Known Bugs / Open Issues

1. **Shadow mode mismatch** (P0): `scripts/run_shadow.py` claims SimBroker vs OKX demo comparison, but engine only instantiates SimBroker in shadow mode. No true comparison happens.
2. **SimBroker fill event gap** (P0): `ExecutionHandler.on_order()` expects WebSocket fill, but `SimBroker.submit()` does not emit a simulated fill event — blocks unified backtest/live engine path.
3. **Replay bar-level approximation** (P1): `scripts/run_backtest.py` uses per-bar approximation formulas, not the true `Strategy → Signal → Order → Fill → Ledger` path.
4. **No CI gate**: No `.github/workflows/` — no automated test enforcement on PRs.
5. **Missing regression tests**: No tests for ct_val PnL, funding carry dual leg alignment, pairs trading hedge close, or replay terminal liquidation.

## Do Not Touch (without explicit issue + user approval)

- `src/okx_quant/strategies/` — all strategy implementations
- `src/okx_quant/risk/` — risk guard, drawdown tracker, circuit breaker
- `src/okx_quant/portfolio/` — sizing, position ledger
- `src/okx_quant/execution/broker.py` — SimBroker and execution handler
- `config/risk.yaml` — risk limits
- Any file not listed in the current issue's permitted scope

## Next Steps (in order)

1. **[Done — this session]** Create governance docs and GitHub templates (PR 1)
2. **[PR 2]** Write `docs/ARCHITECTURE.md` and `docs/ADR/` after full source read
3. **[PR 3]** Create `.github/workflows/ci.yml` with ruff + pytest unit gate
4. **[PR 4]** Add regression test: SWAP `ct_val` PnL (highest risk)
5. **[PR 5]** Add regression test: pairs trading hedge close
6. **[PR 6]** Add regression test: replay terminal liquidation
7. **[PR 7]** Fix shadow mode SimBroker vs OKX demo gap (P0)

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
