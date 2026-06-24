---
status: current
type: handoff
owner: codex
created: 2026-06-24
last_reviewed: 2026-06-24
expires: none
superseded_by: null
---

# Context Handoff: DSR Harness + XS Portfolio Vol - 2026-06-24

## Goal (one sentence)

Fix the CPCV/DSR validation-harness defect and make XS momentum sizing target
portfolio book vol without changing promotion/live gates.

## Current state

- Branch: `codex/xs-momentum-universe-scaffold`.
- Last known good commit / state: pre-existing worktree already contained the
  XS lookahead fix changes from the prior Codex pass.
- In-progress edits: DSR/CPCV code, XS sizing, unit tests, manifests, docs, and
  the new local artifact `results/xs_momentum_validation_20260624_portfoliovol/`.
- What works right now: targeted DSR/CPCV and XS tests pass; doc-impact script
  passes; portfolio-vol artifact exists.
- What does not work / unfinished: `make docs-impact` cannot run because `make`
  is unavailable in this Windows shell; no Git commit was created.

## Decisions made (and why)

- DSR uses per-observation Sharpe from the exact return series because
  `sqrt(T-1)` is a per-observation sample-size term.
- CPCV computes DSR over non-overlapping path returns instead of concatenating
  overlapping paths because duplicated OOS observations inflated confidence.
- Missing `n_trials` now emits `dsr=0.0` and `validation.n_trials_missing`
  because a fake fallback trial count is worse than no DSR.
- XS momentum uses diagonal estimated book vol plus `MAX_GROSS_LEVERAGE=2.0`
  because it is the smallest portfolio-vol estimate available from existing
  weights and constituent vol.

## Open questions / unverified assumptions

- The diagonal book-vol estimate ignores covariance; use covariance only if
  reviewer requires tighter realized-vol targeting.
- The portfolio-vol rerun changed WF Sharpe more than a pure scalar would;
  likely cap/name-cap/cost/funding effects. Promotion remains blocked.

## Rules in play (preserve verbatim)

- Invariants touched: I13 trial count honesty; I21 `DSR <= PSR(0)`; I22 XS
  portfolio-vol gross sizing and max-gross cap.
- Domain rules touched: R4.4, R6.3, R7.1, R7.2, R7.3, R7.4.
- Do-not-touch: `research/`, live/demo/shadow/deployment gates, risk/portfolio/
  execution layers, existing result artifacts.

## Context to load next (the reading list)

- Source of truth: `AI_CONTEXT.md`, `docs/DOMAIN_RULES.md`, `docs/INVARIANTS.md`,
  `docs/FAILURE_MODES.md`, ADR-0009, the two 2026-06-24 task files.
- Owning files / MODULE_BRIEFS: `backtesting/cpcv.py`,
  `src/okx_quant/analytics/dsr.py`, `src/okx_quant/strategies/xs_momentum.py`,
  `backtesting/xs_momentum_backtest.py`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run

- `pytest tests/unit/test_dsr.py tests/unit/test_cpcv.py -v` - 3 passed.
- `pytest tests/unit/test_xs_momentum.py tests/unit/test_xs_momentum_backtest.py -v` - 12 passed.
- `pytest tests/unit/test_dsr.py tests/unit/test_cpcv.py tests/unit/test_backtesting.py tests/unit/test_parameter_sweep.py -v` - 70 passed.
- `python scripts/docs/check_doc_impact.py` with process-local `safe.directory` - passed.
- `make docs-impact` - not run; `make` command unavailable.

## Approvals

- Human approval needed / obtained: needed before any promotion/demo/shadow/live
  interpretation; not obtained.

## Next action (single, concrete)

- Ask Claude to review the DSR basis fix and portfolio-vol rerun, especially the
  non-flat WF Sharpe delta and whether diagonal book-vol is sufficient.

## Human Learning Notes

DSR is easy to overstate when annualized ratios meet per-bar sample counts. Also,
"vol targeting is scale only" is only exactly true before caps, costs, and
funding; a correctness rerun can still move Sharpe a bit without changing the
promotion verdict.
