---
status: current
type: manifest
owner: codex
created: 2026-07-12
last_reviewed: 2026-07-12
expires: none
superseded_by: null
---

# Change Manifest: Unknown venue fails closed

## Summary

Preserve the configured default when exchange is omitted, but return HTTP 400
for every explicit unknown venue instead of silently substituting Binance.

## Design-space decision

- Keep fallback preserves compatibility but violates R6.4.
- A new enum/registry duplicates the config schema and existing normalizer.
- Chosen: reuse the existing normalizer and argparse `choices`; normalize in
  request validators before background work begins.

## Business rule(s) affected

R6.4 data provenance is restored and made fail-closed.

## Trigger area(s) (DOC_IMPACT_MATRIX)

A7 API. This Manifest is required by the approved P0.3 task because the repair
changes externally observable provenance behavior.

## Files changed

- `src/okx_quant/api/routes_backtest.py` — omitted/config default and unknown 400.
- `scripts/backtest_daily_winner.py` — native CLI choices for the same venues.
- `tests/unit/test_backtest_request_exchange.py` — model, validator and API checks.
- `docs/UI_MAP.md`, `docs/DATA_FLOW.md`, `docs/DOMAIN_RULES.md`,
  `docs/INVARIANTS.md`, `docs/FAILURE_MODES.md` — contract and guard evidence.

## Behavior delta

- Before: an explicit typo could silently select configured/Binance data.
- After: omitted or blank exchange uses `config/settings.yaml` primary exchange;
  supported values normalize to lowercase; every explicit unknown value is 400.
- Money/risk impact: no PnL or sizing formula change; wrong-venue evidence is
  prevented before a run is queued.

## Source-of-truth updates

- research/strategy_synthesis.md: N/A — no strategy assumption changed.
- config/: reviewed unchanged; `StorageConfig.primary_exchange` already limits
  values to the same five supported venues.
- ADR: N/A — this restores ADR-0007/R6.4 behavior rather than changing policy.

## Docs updated (from DOC_IMPACT_MATRIX row)

- [x] `docs/UI_MAP.md` / `docs/DATA_FLOW.md` — request semantics documented.
- [x] `docs/FEATURE_MAP.md` — owning test/CLI recorded.
- [x] `docs/DOMAIN_RULES.md`, `docs/INVARIANTS.md`, `docs/FAILURE_MODES.md` —
  R6.4 confirmed, I33/F31 closed by tests.

## Invariants / golden cases

- Invariants checked: I19, I33.
- Golden cases affected: G-002 unchanged; supported venue loading is unchanged.

## Tests / checks run

- Targeted request/API suite — `43 passed`; final P0 target suite `306 passed,
  1 skipped`. Explicit run and sweep unknown venues fail before queueing.
- Full unit `768 passed, 1 skipped`; integration `38 passed`; full Ruff,
  docs/config/backtest-smoke passed. Details:
  `tasks/2026-07-12-p0-implementation-session-handoff.md`.

## Risks and rollback

- Risks: clients relying on a typo silently becoming Binance now receive 400.
- Rollback: revert normalizer/model/CLI/tests/docs; no artifact migration.

## Approval

- Human approval required: yes — obtained in the user's 2026-07-12 request to
  implement `tasks/2026-07-12-claude-p0-review.md`.
