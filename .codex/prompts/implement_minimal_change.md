# Implement Minimal Change

Task:

Permitted files:

Forbidden files:

Source of truth:

- `research/strategy_synthesis.md` for strategy assumptions.
- `docs/backtest_live_parity_plan.md` for backtest/live parity.
- `config/` for runtime configuration.
- `docs/ai_collaboration.md` for gates and completion reporting.

Implementation rules:

- Make the smallest change that satisfies the task.
- Do not alter strategy, risk, portfolio, execution, DB schema, deployment gates, or existing result artifacts unless the task explicitly permits it.
- Do not use chat memory to change trading assumptions.
- If docs and code disagree, record a known gap instead of claiming implementation.

Verification:

- Run the narrowest relevant tests first.
- For docs or harness changes, run `make docs-check` and the relevant Makefile target.
- For frontend changes, run `make frontend-check`.
- For backtest behavior changes, run targeted unit tests and a documented smoke/backtest command.

Rollback plan:

- List files to revert.
- Note generated artifacts, if any.
