---
status: current
type: manifest
owner: codex
created: 2026-06-23
last_reviewed: 2026-06-23
expires: none
superseded_by: null
---

# Change Manifest: XS Momentum Universe Scaffold

## Summary

Added the local scaffold for a point-in-time Binance USDT-perp research universe
and disabled XS momentum strategy target-weight construction. This is
research-tier groundwork only; bulk venue data coverage and promotion validation
remain incomplete.

## Business rule(s) affected

R4.1, R4.3, R6.1, R6.3, R7.1, R7.2. R3.1 was reviewed but not changed; C1
funding-accounting implementation is deferred because the plan text conflicts
with the existing funding sign rule.

## Trigger area(s) (DOC_IMPACT_MATRIX)

A1 strategy/signal logic, A2 portfolio/execution accounting, A4
strategy/runtime config, A5 backtesting workflow.

## Files changed

- `.gitignore` - keep generated `data/universe/` artifacts out of git.
- `backtesting/replay.py` - allow explicit loading of the no-op `xs_momentum`
  stub without exposing API/live strategy execution.
- `config/strategies.yaml` - add disabled `xs_momentum` defaults.
- `config/universe.yaml` - add Binance USDT-perp universe rules.
- `docs/ADR/0009-xs-momentum-research-strategy.md` - record strategy-family
  decision and unfinished promotion prerequisites.
- `docs/ADR/README.md` - index ADR-0009.
- `docs/DATA_FLOW.md` - add point-in-time universe membership flow.
- `docs/DOC_IMPACT_MATRIX.md` - include `config/universe.yaml` and survivorship
  docs in relevant rows.
- `docs/FAILURE_MODES.md` - add survivorship-biased universe membership.
- `docs/FEATURE_MAP.md` - add universe membership and XS momentum ownership.
- `docs/INVARIANTS.md` - add point-in-time universe invariant.
- `scripts/build_universe_membership.py` - build deterministic membership
  artifacts from candles.
- `scripts/docs/check_doc_impact.py` - mirror DOC_IMPACT_MATRIX trigger/doc
  updates.
- `src/okx_quant/core/config.py` - add `XSMomentumConfig`.
- `src/okx_quant/portfolio/allocation.py` - add pure dollar-neutral long-short
  weight helper.
- `src/okx_quant/strategies/xs_momentum.py` - add params, score helper, target
  weights, regime scaler, and no-op strategy stub.
- `tests/unit/test_universe_membership.py` - guard no pre-listing eligibility
  and no delisting forward-fill.
- `tests/unit/test_xs_momentum.py` - guard weight construction, scoring,
  target weights, crash scaler, stub loading, and disabled config.

## Behavior delta

- Before: no point-in-time universe artifact builder and no XS momentum strategy
  module/config existed.
- After: local research code can generate a membership artifact and compute
  disabled-by-default XS momentum target weights in tests.
- Money/risk impact: no live, demo, shadow, replay execution, or deployment gate
  behavior changed. Portfolio helper semantics were added but are not wired into
  live execution.

## Source-of-truth updates

- research/strategy_synthesis.md: N/A, Claude-owned D2 task; not touched by
  Codex.
- config/: updated `config/universe.yaml` and `config/strategies.yaml`.
- ADR: ADR-0009 added.

## Docs updated (from DOC_IMPACT_MATRIX row)

- [x] `docs/FEATURE_MAP.md` - updated for universe and XS momentum ownership.
- [x] `docs/DATA_FLOW.md` - updated for universe membership artifact flow.
- [x] `docs/INVARIANTS.md` - added I20.
- [x] `docs/FAILURE_MODES.md` - added F19.
- [x] `docs/DOMAIN_RULES.md` - reviewed; unchanged because no rule text changed.
- [x] `research/strategy_synthesis.md` - intentionally unchanged; Claude-owned
  follow-up D2.
- [x] relevant ADR - ADR-0009 added.

## Invariants / golden cases

- Invariants checked: I4 reviewed, I13 reviewed, I14 reviewed, I15 reviewed,
  I20 added and tested.
- Golden cases affected: N/A, no replay/backtest result contract was added.

## Tests / checks run

- `python -m pytest tests/unit/test_xs_momentum.py tests/unit/test_universe_membership.py -v` - 9 passed.
- `python scripts/validate_pipeline.py --check-config-only` - PASS
  `config_thresholds` and `strategy_symbol_overlap`.

## Risks and rollback

- Risks: target-weight helper is not yet validated through a full backtest;
  generated membership artifact is local parquet research data until DB coverage
  is verified; C1 funding implementation is blocked by a plan-vs-DOMAIN_RULES
  sign conflict.
- Rollback: remove the files listed above and delete the generated local
  `data/universe/universe_membership.parquet` artifact if no longer needed.

## Approval

- Human approval required: yes before any live/demo/shadow/promotion claim or
  before changing R3.1 funding sign semantics. Not obtained in this session.
