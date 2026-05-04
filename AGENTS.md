# Codex Instructions

This repository uses `docs/ai_collaboration.md` as the shared collaboration contract between Codex, Claude, and the user.

## Role

Codex is primarily responsible for **implementation, tests, backtesting workflow, config checks, and deployment readiness**. Claude handles research, strategy review, and risk critique.

## Mandatory before making changes

1. Read `docs/ai_collaboration.md`.
2. Run `git status --short` to check for existing changes.
3. Do not overwrite unrelated user or Claude changes.
4. Treat `research/strategy_synthesis.md`, `docs/backtest_live_parity_plan.md`, and `config/` as truth sources.

## File ownership

| Area | Path |
|------|------|
| Backtesting engine/report | `backtesting/`, `scripts/run_backtest.py`, `scripts/run_replay_backtest.py` |
| Strategy implementation | `src/okx_quant/strategies/`, `src/okx_quant/signals/` |
| Risk and sizing | `src/okx_quant/risk/`, `src/okx_quant/portfolio/` |
| Deployment/config | `config/`, `scripts/run_live.py`, `scripts/run_shadow.py`, `docker/` |

Do **not** modify `research/` files — that is Claude's ownership area.

## When finishing a task, always report

```
Implementation summary:
Diff scope:
Assumptions made:
Tests/checks run:
Backtest/result artifacts:
Questions for Claude review:
Deployment readiness:
```

## Hard rules

- Never claim a strategy is ready for live trading unless all gates in `docs/ai_collaboration.md` have passed and the user has explicitly approved.
- Never change strategy assumptions based on chat memory — only from `research/strategy_synthesis.md` or explicit user instruction.
- Do not skip tests and claim deployable.
- Only modify files within the scope of the current task.
