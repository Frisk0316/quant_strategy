# crypto-alpha-lab Agent Instructions

This subproject is research-only. It exists to systematize alpha discovery for
the parent `quant_strategy` backtesting framework without modifying that
framework during early research.

## Scope

- Work only inside `research/crypto-alpha-lab/` unless the user explicitly asks
  for a parent-repo change.
- Do not implement live trading.
- Do not add real exchange API clients.
- Do not add API keys, secrets, credentials, or account state.
- Do not import parent live trading modules.
- Treat output as research artifacts, not deployment approval.

## Truth Sources

If this lab conflicts with the parent repo, use the parent repo truth sources:

- `research/strategy_synthesis.md`
- `docs/backtest_live_parity_plan.md`
- `config/`
- `docs/ai_collaboration.md`

The existing parent research files describe current strategy assumptions. This
lab creates a separate, systematic pipeline for finding and scoring future
alphas that may later be adapted to the backtesting architecture.

## Required Review Points

Every alpha candidate should make these assumptions explicit:

- Paper or source reference.
- Signal definition.
- Required data.
- Time horizon.
- Transaction-cost handling.
- Lookahead and leakage risks.
- Overfit and multiple-testing risks.
- Compatibility with the parent backtest artifact contract.

## Phase Boundaries

Phase 1 is skeleton only:

- interfaces,
- schemas,
- tests,
- documentation,
- no live trading,
- no exchange API.

Future phases may add ingestion, scoring workflow, candidate registries, and
backtest config exporters after review.
