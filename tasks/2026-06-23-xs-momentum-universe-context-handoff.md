# Context Handoff: XS momentum universe scaffold - 2026-06-23

## Goal (one sentence)

Implement the local scaffold for point-in-time universe membership and the
disabled XS momentum research strategy from the 2026-06-23 spec/plan.

## Current state

- Branch: `codex/impl-multi-venue-instrument-specs`.
- Last known good commit / state: branch had pre-existing modified
  `docs/validation_methodology_zh.docx`; this session did not touch it.
- In-progress edits (files): see the paired session handoff and Change Manifest
  `docs/change_manifests/2026-06-23-xs-momentum-universe.md`.
- What works right now: `config/universe.yaml`; point-in-time universe builder
  with local artifact generation; `xs_momentum` disabled config/model/stub;
  explicit replay loading of the no-op stub; dollar-neutral weights;
  vol-normalized scores; weekly target weights with caps; crash-regime gross
  reduction; unit tests and config validation.
- What does not work / unfinished: A2 bulk 1m/funding download and canonical DB
  coverage; C1-C3 vectorized funding-aware backtest, honest scan `n_trials`,
  WF/CPCV/DSR/PSR reports; Claude-owned D2 research files.

## Decisions made (and why)

- `config/instrument_specs.yaml` was not updated for Binance universe candidates
  because ADR-0007 and `docs/DOMAIN_RULES.md` make venue-scoped DB specs the
  promotion-grade authority and the YAML file is an OKX-only fallback.
- `data/universe/` was added to `.gitignore` because generated membership
  parquet is a local research artifact, not source code.
- C1 was not implemented because the plan's short-leg positive-funding
  expectation conflicts with `docs/DOMAIN_RULES.md` R3.1; changing funding sign
  semantics needs explicit human approval and a separate rule-change path.

## Open questions / unverified assumptions

- Should the C1 backtest runner follow current R3.1 funding sign semantics, or
  should the plan/spec be corrected to explicitly change the rule?
- Which exact Binance USDT-perp candidate list should A2 use for the >=25
  symbols with >=12 months parquet plus canonical DB coverage?
- Should the first smoke runner use existing BTC/ETH/SOL/MEME local data after
  the funding sign conflict is resolved?

## Rules in play (preserve verbatim)

- Invariants touched: I20, "Universe membership is point-in-time: no symbol is
  eligible before listing plus warmup, and ended candle history is not
  forward-filled into later eligibility"; I4 funding sign reviewed but unchanged.
- Domain rules touched: R4.1, R4.3, R6.1, R6.3, R7.1, R7.2; R3.1 reviewed.
- Do-not-touch: `research/`, deployment gates, existing result artifacts,
  differential-validation implementation owned by another session.

## Context to load next (the reading list)

- Source of truth: `docs/superpowers/specs/2026-06-23-xs-momentum-universe-design.md`,
  `docs/superpowers/plans/2026-06-23-xs-momentum-universe.md`,
  `docs/DOMAIN_RULES.md`, `docs/ADR/0009-xs-momentum-research-strategy.md`,
  `config/universe.yaml`, `config/strategies.yaml`.
- Owning files / MODULE_BRIEFS: `docs/FEATURE_MAP.md` sections "Point-In-Time
  Universe Membership" and "XS Momentum Research Strategy".
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run

- `python -m pytest tests/unit/test_xs_momentum.py tests/unit/test_universe_membership.py -v` - 9 passed.
- `python scripts/validate_pipeline.py --check-config-only` - PASS
  `config_thresholds` and `strategy_symbol_overlap`.
- `python scripts/docs/check_doc_metadata.py` - passed with 15 pre-existing
  lifecycle metadata warnings.
- `python scripts/docs/check_feature_map_links.py` - passed.
- `python scripts/docs/check_doc_impact.py` with temporary git safe.directory
  env - passed with no impact-matrix violations across 24 changed files.
- `make docs-check` - not run because `make` is not installed in this Windows
  shell; component scripts above were run directly.

## Approvals

- Human approval needed / obtained: needed before funding sign rule changes or
  any live/demo/shadow/promotion claim; not obtained.

## Next action (single, concrete)

- Resolve the R3.1-vs-plan funding sign conflict, then implement
  `backtesting/xs_momentum_backtest.py` with a funding sign regression test.

## Human Learning Notes

The most important gotcha is that the plan itself is not the highest authority
when it conflicts with `docs/DOMAIN_RULES.md`. Here, the funding sign mismatch
is exactly the kind of issue the harness is meant to catch before PnL code is
written.
