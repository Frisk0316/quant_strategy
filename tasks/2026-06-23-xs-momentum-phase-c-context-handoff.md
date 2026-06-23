# Context Handoff: XS Momentum Phase C Research Runner - 2026-06-23

## Goal (one sentence)
Implement the first XS momentum Phase C research runner with corrected funding
signs, annualized volatility targeting, crash-filter proxy wiring, and a
DB-backed smoke artifact.

## Current state
- Branch: `codex/xs-momentum-universe-scaffold`.
- Last known good commit / state: scaffold committed as `07a5d9c` with
  `AI-Origin: Codex`; Phase C code/tests/docs are the active follow-up.
- In-progress edits (files): `backtesting/xs_momentum_backtest.py`,
  `src/okx_quant/strategies/xs_momentum.py`,
  `tests/unit/test_xs_momentum.py`,
  `tests/unit/test_xs_momentum_backtest.py`, Phase C docs/handoffs.
- What works right now: focused XS tests pass; DB smoke artifact exists at
  `results/xs_momentum_db_smoke_20260623.json`.
- What does not work / unfinished: artifact is not promotion-grade; WF/CPCV,
  DSR/PSR, >=25-symbol >=12-month venue-scoped coverage, and human review remain
  unfinished.

## Decisions made (and why)
- Funding cashflow uses `-(position * funding_rate)` because R3.1 is canonical:
  long pays positive funding, short receives positive funding.
- Vol-target gross uses annualized realized volatility because
  `vol_target_annual` is annual by name/config and daily volatility made the cap
  effectively a no-op.
- `market_close` is optional on the research runner because crash filtering needs
  a market proxy, but the smoke artifact disabled the proxy after ETH zeroed
  exposure across the window.
- The DB smoke artifact stays local/uncommitted because it is not a frozen
  golden case or promotion artifact.

## Open questions / unverified assumptions
- Which market proxy should govern the XS crash filter for promotion-grade runs:
  BTC, ETH, equal-weight market, or a venue-native index?
- Whether enough canonical Binance 1m/funding coverage can be backfilled to
  reach >=25 symbols for >=12 months without venue gaps.
- How to integrate this runner into WF/CPCV plus DSR/PSR without reusing hidden
  trials as selection evidence.

## Rules in play (preserve verbatim)
- Invariants touched: I4 "Funding sign: long pays positive funding, receives
  negative"; I13 "Trial count is recorded; no hidden trials in selection"; I14
  "`naive_backtest` / `in_sample` / idealized output never used as promotion
  evidence"; I15 "No live/shadow/demo claim without all gates passed + human
  approval"; I20 point-in-time universe membership.
- Domain rules touched: R3.1, R4.1, R4.3, R6.2, R6.3, R7.1, R7.2.
- Do-not-touch: `research/`, existing historical result artifacts, live/demo/
  shadow gates, differential-validation implementation unless explicitly tasked.

## Context to load next (the reading list)
- Source of truth: `docs/superpowers/specs/2026-06-23-xs-momentum-universe-design.md`,
  `docs/superpowers/plans/2026-06-23-xs-momentum-universe.md`,
  `docs/DOMAIN_RULES.md`, `docs/INVARIANTS.md`,
  `docs/ADR/0009-xs-momentum-research-strategy.md`.
- Owning files / MODULE_BRIEFS: `docs/FEATURE_MAP.md`, `docs/DATA_FLOW.md`,
  `backtesting/xs_momentum_backtest.py`,
  `src/okx_quant/strategies/xs_momentum.py`.
- Context Pack: `docs/CONTEXT_PACKS/` relevant backtesting/validation pack if
  present; otherwise start from `docs/CONTEXT_INDEX.md`.

## Checks run
- `python -m pytest tests/unit/test_xs_momentum.py tests/unit/test_xs_momentum_backtest.py tests/unit/test_universe_membership.py -v` - 13 passed; `.pytest_cache` permission warning only.
- `python scripts/validate_pipeline.py --check-config-only` - PASS
  `config_thresholds` and `strategy_symbol_overlap`.
- `python scripts/docs/check_feature_map_links.py` - passed.
- `python scripts/docs/check_doc_metadata.py` - passed with existing metadata
  warnings.
- `python scripts/docs/check_doc_impact.py` with one-command Git safe.directory
  env - passed, 19 changed files, no impact-matrix violations.

## Approvals
- Human approval needed / obtained: needed before any promotion/demo/shadow/live
  claim; not obtained.

## Next action (single, concrete)
- Decide the market proxy and then run XS WF/CPCV plus DSR/PSR once canonical DB
  coverage reaches the promotion threshold.

## Human Learning Notes
The plan-vs-rule funding conflict is resolved in favor of `DOMAIN_RULES`: do not
let a strategy plan override accounting signs. Also, a crash proxy can be wired
correctly while still being unusable for a given artifact if the proxy choice
zeroes exposure; proxy selection is part of validation, not plumbing.
