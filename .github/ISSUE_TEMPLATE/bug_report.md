---
name: Bug Report
about: Report a confirmed or suspected bug
labels: bug
---

## Problem

<!-- What is broken? One or two sentences. -->

## Evidence

<!-- Error message, log output, screenshot, or console trace. Paste the actual text — do not paraphrase. -->

```
<paste here>
```

## Suspected Layer

Check the layer(s) most likely responsible:

- [ ] Data (TimescaleDB, ingestion, canonical candles)
- [ ] Strategy (signal generation, entry/exit logic)
- [ ] Portfolio (sizing, position ledger)
- [ ] Execution (broker, order manager, replay execution)
- [ ] Risk (risk guard, drawdown, circuit breaker)
- [ ] API (FastAPI routes, result schema)
- [ ] Frontend (dashboard, charts, module loading)
- [ ] Config (settings.yaml, strategies.yaml, risk.yaml)

## Reproduction

<!-- Exact commands to reproduce. If it requires a DB or specific data, say so. -->

```
<commands here>
```

## Expected Behavior

<!-- What should happen instead? -->

## Scope — Files Permitted to Change

<!-- List only the files that should be touched to fix this bug. -->

-

## Out of Scope — Do Not Touch

<!-- Be explicit. These files must not be modified in this fix. -->

- src/okx_quant/strategies/ (unless this is a strategy bug)
- src/okx_quant/risk/
- config/risk.yaml
- <!-- add others as needed -->

## Acceptance Criteria

- [ ] The described error no longer occurs
- [ ] A regression test is added that would have caught this bug
- [ ] `pytest tests/unit/ -v` passes
- [ ] Replay smoke passes (if execution/backtest layer is affected)
- [ ] `docs/AI_HANDOFF.md` updated

## Additional Constraints

<!-- Anything the fixing AI must not do (e.g., do not change the result schema, do not refactor the broker). -->
