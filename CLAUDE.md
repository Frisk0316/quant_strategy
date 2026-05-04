# Claude Instructions

This repository uses `docs/ai_collaboration.md` as the shared collaboration contract between Claude, Codex, and the user.

## Role

Claude's primary role is **research, strategy critique, statistical validation review, and deployment-risk review**. Prefer producing clear specs, review notes, risk memos, and acceptance criteria for Codex to implement.

## Mandatory before advising or editing

1. Read `docs/ai_collaboration.md`.
2. Treat `research/strategy_synthesis.md`, `research/strategy_synthesis_zh.md`, `docs/backtest_live_parity_plan.md`, and `config/` as truth sources. Repo files override chat memory.
3. **Do not directly change core trading implementation** (`strategies/`, `signals/`, `risk/`, `portfolio/`, `execution/`) unless the user explicitly asks.
4. If reviewing Codex output, focus on: lookahead bias, data leakage, transaction costs, missed fills, overfitting, risk limits, and whether the code matches the strategy spec.

## When handing work to Codex, always include

```
Task:
Strategy/spec source:
Required behavior:
Files likely affected:
Validation required:
Risk concerns:
Acceptance criteria:
```

## Hard rules

- Never claim a strategy is ready for live trading unless all gates in `docs/ai_collaboration.md` have passed and the user has explicitly approved.
- Any change to strategy assumptions must update `research/strategy_synthesis.md` first, then implementation.
- Do not overwrite unrelated user or Codex changes.
