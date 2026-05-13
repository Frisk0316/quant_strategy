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

Implement position-aware close sizing for pairs trading exit/stop flows after design review.

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
| P2 position-aware close sizing design `(complete; pending review)` | Design pairs trading exit/stop close sizing from ledger positions | PM owns close sizing; implementation must guard to `pairs_trading`, preserve funding carry dual-leg exit behavior, and handle integer-lot float drift |
| P2 shadow calibration test `(complete; pending review)` | Add mirror fill positive routing unit coverage | `ExecutionHandler.on_fill_ws()` now has mock coverage for filled and partially_filled shadow mirror fills routing to `CalibrationLogger.record_fill()` |
| OHLCV rotation `(merged)` | Add Phase 1 OHLCV rotation research/backtest workflow | Vectorised strategy/backtest, CLI, synthetic tests, and XLSX export support added separately from PR14B |
| PR14B `(merged)` | Implement shadow mode parity fixes | `run_shadow.py` now requires `mode=shadow`; shadow primary SimBroker receives instrument specs; broker routing tests added |
| PR14A `(merged)` | Design shadow mode parity plan | `docs/shadow_mode_parity_plan.md` documents current ShadowBroker path, remaining gaps, and PR14B scope |
| PR13 `(merged)` | Implement remaining ADR-0005 replay validation gates | Gate 2 fill-rate warning, Gate 3 data coverage, Gate 4 funding coverage implemented; ADR-0005 moved to Accepted |
| PR12B | Implement replay terminal liquidation | Gate 1 terminal position check implemented via `validation["terminal_positions_closed"]`; replay default closes terminal positions; CLI can opt out; focused regression tests added |
| PR12A | Add replay terminal liquidation design plan | Docs-only design; no replay behavior change |
| PR11 | Add funding carry dual-leg regression tests for signal metadata and PM order alignment | Test-only coverage for long spot + short perp carry behavior |
| PR10B | Add pairs exit/stop hedge close metadata and remove hedge metadata xfail | Strategy metadata only; sizing remains unchanged |
| PR10 | Add pairs trading hedge-close regression coverage | Test-only coverage for linked hedge close behavior |
| PR9 | Add backtest artifact schema regression tests for ADR-0002 frozen fields | Test-only coverage for artifact contract |
| PR8 | Add frontend MIME smoke tests for `.js` and legacy `.jsx` ES modules | Test-only coverage for FastAPI StaticFiles MIME behavior |
| PR7 | Add branch/version management policy and PR template checklist | Governance docs only |

## Known Bugs / Open Issues

1. **Shadow mode parity gap** (resolved in PR14B): `run_shadow.py` requires `mode=shadow`, and shadow primary `SimBroker` receives instrument specs for notional/fee accounting.
2. **SimBroker fill event gap** (P0): `ExecutionHandler.on_order()` expects WebSocket fill, but `SimBroker.submit()` does not emit a simulated fill event — blocks unified backtest/live engine path.
3. **Replay bar-level approximation** (P1): `scripts/run_backtest.py` uses per-bar approximation formulas, not the true `Strategy → Signal → Order → Fill → Ledger` path.
4. **CI gate is minimal**: `.github/workflows/ci.yml` runs ruff fatal-only baseline and unit tests only. This is a temporary baseline until existing lint debt is cleaned up; integration tests still require TimescaleDB planning.
5. **Missing regression tests**:
   - Frontend MIME smoke test exists.
   - Backtest artifact schema regression test exists.
   - Pairs trading hedge-close regression exists; exit/stop hedge metadata implemented.
   - Funding carry dual-leg regression exists.
   - Replay terminal liquidation regression tests exist.
   - Shadow mirror fill positive routing to `CalibrationLogger.record_fill()` is covered by a focused mock unit test for filled and partially_filled mirror updates.
6. **Pairs close sizing gap** (P2): Exit/stop order size is still driven by signal sizing rather than current ledger position. Position-aware close sizing design is documented in `docs/pairs_position_aware_close_sizing_plan.md`; implementation remains next. Funding carry also uses `metadata["action"] == "exit"`, so the implementation must make the close-sizing branch pairs-only unless a separate funding-carry design explicitly expands scope.
7. **ADR-0005 replay validation gates**: Gates 1-4 are implemented and ADR-0005 is Accepted. Gate 1 terminal position check is implemented via `validation["terminal_positions_closed"]`; PR13 added Gate 2 fill-rate warning, Gate 3 data coverage, and Gate 4 funding coverage.

## Do Not Touch (without explicit issue + user approval)

- `src/okx_quant/strategies/` — all strategy implementations
- `src/okx_quant/risk/` — risk guard, drawdown tracker, circuit breaker
- `src/okx_quant/portfolio/` — sizing, position ledger
- `src/okx_quant/execution/broker.py` — SimBroker and execution handler
- `config/risk.yaml` — risk limits
- Any file not listed in the current issue's permitted scope

## Next Steps (in order)

1. **[P2]** Review `docs/pairs_position_aware_close_sizing_plan.md`
2. **[P2]** Implement position-aware close sizing after design review

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
