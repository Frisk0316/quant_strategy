---
status: current
type: handoff
owner: codex
created: 2026-06-25
last_reviewed: 2026-06-25
expires: none
superseded_by: null
---

# Context Handoff: Strategy Research Pipeline Stage 1 - 2026-06-25

## Goal (one sentence)

Implement the minimal Stage 1 pipeline machinery and enforce
family-cumulative `n_trials` for candidate scans.

## Current state

- Branch: current working tree at `C:\quant_strategy`; git safe.directory must be
  passed as `C:/quant_strategy` for reliable git-backed checks.
- Last known good state: `pytest tests/unit/test_xs_momentum_backtest.py -v`
  passed; doc-impact passed with process-local safe.directory.
- In-progress edits (files): see paired session handoff.
- What works right now: `scan_xs_momentum(..., prior_family_n_trials=N)` reports
  `N + len(grid)` in rows and attrs; Stage 1 driver/templates and ledgers record
  family trial accounting.
- What does not work / unfinished: the pipeline has not been run on [S7, S5, S6];
  no candidate shortlist or evidence artifact exists.

## Decisions made (and why)

- Keep Stage 1 manual-ledger based because the plan explicitly deferred JSON
  state and evidence validators to Stage 2.
- Use `docs/FEATURE_MAP.md` as the required A5 doc-impact companion because the
  code change is backtesting behavior, not a data-flow change.

## Open questions / unverified assumptions

- Whether Stage 2 should add a machine-readable validator for family cumulative
  `n_trials`; currently manual review plus I23 guards it.

## Rules in play (preserve verbatim)

- Invariants touched: I13 trial count recorded; I21 `DSR <= PSR(0)` basis; I23
  candidate CPCV `n_trials` must be at least the family-cumulative trial count
  recorded in `docs/EXPERIMENT_REGISTRY.md`.
- Domain rules touched: R6.3, R7.4.
- Do-not-touch: `src/okx_quant/strategies/`, `signals/`, `risk/`,
  `portfolio/`, `execution/`, config gates, `backtesting/cpcv.py`,
  `analytics/dsr.py`, and result artifact values.

## Context to load next (the reading list)

- Source of truth: `AI_CONTEXT.md`, `docs/AI_HANDOFF.md`,
  `docs/CURRENT_STATE.md`, `research/strategy_synthesis.md`.
- Owning files: `docs/FEATURE_MAP.md` XS Momentum Research Strategy section.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run

- `pytest tests/unit/test_xs_momentum_backtest.py -v` - 5 passed, 1 pytest cache
  warning.
- `python scripts/docs/check_doc_impact.py` - failed because PATH `python.exe`
  cannot execute in this sandbox.
- `GIT_CONFIG_COUNT=1 ... python scripts/docs/check_doc_impact.py` with Python
  3.12 absolute path - passed, 17 changed files, no impact-matrix violations.
- `git -c safe.directory=C:/quant_strategy diff --check` - exit 0, line-ending
  warnings only.

## Approvals

- Human approval needed / obtained: approval still required before running or
  publishing any candidate; not obtained in this session.

## Next action (single, concrete)

- Review the diff, then run the Stage 1 driver on [S7, S5, S6] only if the user
  explicitly asks to start the first batch.

## Human Learning Notes

Family `n_trials` is not a result-local number anymore. The ledger is the source
of truth for future CPCV deflation, and old XS momentum `n_trials=8` artifacts
remain historical/non-promotion evidence rather than values to mutate.
