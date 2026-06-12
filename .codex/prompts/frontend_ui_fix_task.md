# Frontend UI Fix Task

Read first:

- `AI_CONTEXT.md`
- `docs/UI_MAP.md`
- `docs/FEATURE_MAP.md`
- `docs/DEBUGGING_RUNBOOK.md`
- `docs/ADR/0004-frontend-module-loading.md`

Permitted by default:

- `frontend/`
- Frontend-facing route transforms in `src/okx_quant/api/routes_backtest.py` only when explicitly needed.
- Targeted frontend tests under `tests/unit/`.

Forbidden without explicit approval:

- Strategy logic, risk, portfolio, execution, DB schema, deployment gates, and existing result artifacts.
- Validation engine changes when another session owns differential validation.

Workflow:

1. Reproduce or locate the UI surface.
2. Trace API calls through `frontend/data.js`.
3. Change the smallest relevant component.
4. Run `make frontend-check` and targeted tests.
5. Update `docs/UI_MAP.md` or `docs/FEATURE_MAP.md` if the mapping changed.

Required handoff:

- Visible behavior changed.
- Files changed.
- Checks run.
- Remaining browser/manual verification risk.
