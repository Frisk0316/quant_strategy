---
status: current
type: handoff
owner: codex
created: 2026-06-24
last_reviewed: 2026-06-24
expires: none
superseded_by: null
---

# Context Handoff: XS momentum lookahead fix - 2026-06-24

## Goal (one sentence)
Remove the XS momentum daily-to-intraday lookahead leak and rerun review-required
WF/CPCV evidence on leak-free returns.

## Current state
- Branch: `codex/xs-momentum-universe-scaffold`
- Last known good commit / state: pre-existing branch commit `07a5d9c`; this
  session has uncommitted code, test, docs, and result-artifact changes.
- In-progress edits (files): see paired session handoff.
- What works right now: unit regression proves day-D positions do not trade on
  day-D close information; leak-free artifact exists at
  `results/xs_momentum_validation_20260624_leakfix/`.
- What does not work / unfinished: promotion remains blocked because PSR is
  0.7961 (<0.95); vol-target quantity/sizing decision remains separate.

## Decisions made (and why)
- Wrote a new dated artifact directory instead of hand-editing historical JSON
  because the task allowed rerun-or-new-artifact and historical result JSON
  should not be manually rewritten.
- Marked `results/xs_momentum_validation_20260623/` with `SUPERSEDED.md`
  because its `promotion_gate_passed:true` field was generated from leaked
  returns.
- Used direct canonical SQL aggregation for the rerun because the saved validation
  used later-listed/gappy symbols that strict venue-gap loaders reject when
  asked for a full 2024-01-01 start.

## Open questions / unverified assumptions
- Whether the reconstructed validation script should be promoted into a durable
  checked-in rerun script.
- Whether XS momentum should target portfolio volatility instead of median
  single-name volatility remains a Claude/user decision.
- `docs/HYPOTHESIS_LEDGER.md` and `docs/EXPERIMENT_REGISTRY.md` still contain
  E-003 as supported; this task did not permit editing those research/experiment
  records, so a follow-up should supersede that row.

## Rules in play (preserve verbatim)
- Invariants touched: I8 - a fill at bar t uses only data available at or before
  t; I13 - trial count is recorded; I14 - in-sample/idealized output is not
  promotion evidence; I15 - no live/shadow/demo claim without all gates passed
  plus human approval; I20 - universe membership is point-in-time.
- Domain rules touched: R5.3, R6.1, R6.3, R7.1, R7.2.
- Do-not-touch: `research/`, `src/okx_quant/strategies/`,
  `src/okx_quant/signals/`, `src/okx_quant/risk/`,
  `src/okx_quant/portfolio/`, `src/okx_quant/execution/`, `config/`,
  deployment/shadow/demo/live gates, unrelated result artifacts.

## Context to load next (the reading list)
- Source of truth: `AI_CONTEXT.md`, `docs/DOMAIN_RULES.md`,
  `docs/INVARIANTS.md`, `docs/ADR/0009-xs-momentum-research-strategy.md`,
  `tasks/2026-06-24-xs-momentum-phase-c-review.md`,
  `tasks/2026-06-24-xs-momentum-lookahead-fix-task.md`.
- Owning files / MODULE_BRIEFS: `backtesting/xs_momentum_backtest.py`,
  `tests/unit/test_xs_momentum_backtest.py`, `backtesting/walk_forward.py`,
  `backtesting/cpcv.py`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md` for harness rules;
  no XS-specific context pack exists yet.

## Checks run
- `python -m pytest tests/unit/test_xs_momentum_backtest.py::test_daily_close_target_is_not_traded_on_same_day -v` - failed before the fix, passed after the fix.
- `python -m pytest tests/unit/test_xs_momentum_backtest.py tests/unit/test_xs_momentum.py -v` - 12 passed; pytest cache permission warning only.
- `python scripts/docs/check_doc_impact.py` with process-local `safe.directory`
  git config - passed: 10 changed files, no impact-matrix violations.
- Leak-free DB rerun - wrote `results/xs_momentum_validation_20260624_leakfix/` with WF combined OOS Sharpe 0.8825, CPCV overall OOS Sharpe 0.5577, DSR 1.0, PSR 0.7961.

## Approvals
- Human approval needed / obtained: needed before promotion/demo/shadow/live use;
  not obtained.

## Next action (single, concrete)
- Ask Claude to re-review `results/xs_momentum_validation_20260624_leakfix/` and
  decide how to record/supersede the stale HYPOTHESIS_LEDGER and
  EXPERIMENT_REGISTRY entries.

## Human Learning Notes
The old artifact looked impressive because one rebalance day in seven was enough
to trade on same-day close information. The loader also surfaced a useful
workflow lesson: strict venue-gap loaders are right for replay, but review reruns
must preserve the original experiment's later-listing/gappy-symbol handling or
they cannot reproduce the artifact shape.
