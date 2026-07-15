---
status: current
type: handoff
owner: codex
created: 2026-07-15
last_reviewed: 2026-07-15
expires: none
superseded_by: null
---

# Context Handoff: taxonomy_004 cross-venue funding Stage 2 — 2026-07-15

## Goal (one sentence)

Inventory locally runnable strategies, then use the existing research pipeline
to generate and honestly test one new data-backed candidate without retrying a
failed family or claiming an incomplete proxy is a backtest.

## Current state

- Branch: `feature/h014-e052-shadow`; observed HEAD before final verification:
  `87d38d7`.
- Last known good state: targeted pipeline/probe suite and Makefile-equivalent
  docs/config/backtest checks pass; see the paired session handoff.
- In-progress edits: C4 probe/registry/tests, taxonomy and Stage-1 specs,
  H-021/E-053/E-054 governance rows, F41-I43 guards, feature/data maps, shared
  state/changelog/workstream entries, manifest, and this handoff pair.
- Concurrent edits not owned here: H-014 shadow, liquidation unattended task,
  config/risk/domain/runbook changes and their handoffs/fixtures. They were
  preserved and must not be rolled back with this task.
- What works right now: taxonomy_004 idea generator selects exactly
  `F-XVENUE-FUNDING-SPREAD`; the registered DB-backed Stage-2 probe aligns
  2,739/2,739 funding events per symbol after bounded F41 correction, computes
  provisional feature distinctness, and correctly gross-normalizes both legs,
  t+1 funding, turnover, and base/stress costs.
- What does not work / unfinished: Stage 2 is `FAIL`. Deribit venue-scoped
  perpetual 1m price coverage is 0%, conservative costs have no common positive
  BTC/ETH cell, and no Stage-3/full-PnL runner exists or is authorized.

## Decisions made (and why)

- Selected only C4 — its research prerequisite is now satisfied; taxonomy_003
  candidates and H-009 cannot be gate-chased.
- Used a dual-perp convergence expression — a Binance-only leg would replace
  the claimed cross-venue mechanism with price beta.
- Counted E-053=4 and E-054=4, cumulative n_trials=8 — both four-cell outcome
  surfaces were inspected even though E-053 is invalid.
- Kept K=0/2 — registry policy says planned/data-blocked/Stage-2-failed rows do
  not consume K.
- Preserved E-053 and copied E-054 to an immutable snapshot — existing result
  evidence was not overwritten; would change only under an explicit artifact
  migration.
- Stopped at Stage 2 — would change only after real Deribit perp prices,
  reviewed inverse-contract/fee specs, and a new ex-ante rationale exist.

## Open questions / unverified assumptions

- Whether free/licensed historical Deribit perpetual mark/OHLC can be obtained
  with point-in-time provenance and sufficient coverage.
- Whether a config-owned, reviewed Deribit/Binance taker+slippage schedule would
  support any frozen cell; the current conservative stress fails on BTC.
- H-021 is `inconclusive`, not supported or refuted; feature-level correlations
  are not a final family-minting verdict.

## Rules in play (preserve verbatim)

- R2.1: "Maker and taker fees are distinct; a maker-only strategy must not be
  charged taker fees in backtest or live accounting."
- R3.1: "Funding cashflow sign convention: a long pays positive funding and
  receives negative funding (and vice versa). Sign errors invert strategy PnL."
- R6.1: "No lookahead bias or feature leakage in research or replay."
- R6.3: "Trial count must be tracked; hidden trials inflate selection bias."
- R7.1: advisory output is not promotion evidence; R7.2 requires every gate and
  explicit human approval.
- I41: <=1 second settlement-boundary canonicalization only; larger offsets
  fail closed. I42: undefined correlation is never zero. I43: missing funding
  intervals cannot be compressed into a false t+1 transition.
- Do-not-touch: `research/`, existing result artifacts, live/demo/shadow gates,
  strategy/risk/portfolio/execution code, and concurrent H-014/liquidation work.

## Context to load next (the reading list)

- Source of truth: `research/deribit_data_strategy_research.md` C4 (read-only),
  `docs/HYPOTHESIS_LEDGER.md` H-021, `docs/EXPERIMENT_REGISTRY.md` E-053/E-054.
- Owning files: `backtesting/xvenue_funding_spread_probe.py`,
  `backtesting/pipeline_stage2_registry.py`, and
  `tests/unit/test_xvenue_funding_spread_probe.py`.
- Design/evidence: `docs/superpowers/specs/2026-07-15-mechanism-taxonomy-004.md`,
  `docs/superpowers/specs/2026-07-15-f-xvenue-funding-spread-hypothesis.md`,
  `results/idea_batch_20260715_taxonomy_004/e054_reprobe_advisory.json`.
- Context Pack: no task-specific pack exists; use
  `docs/CONTEXT_PACKS/harness-scaffolding.md` plus the backtest module brief.

## Checks run

- `python -m pytest ...pipeline/probe... -q -p no:cacheprovider` — 49 passed.
- Idea generator — selected 1/1 C4 candidate after the intentional partial-data
  taxonomy classification.
- Orchestrator first run — Stage-2 FAIL, E-053 later invalidated by F41.
- Orchestrator `--reprobe` — corrected coverage; Stage-2 still FAIL on price
  availability and conservative cost.
- Makefile-equivalent docs metadata, feature links, ledger consistency,
  strict docs-impact, config validation, Ruff, and backtest smoke — passed.
  `make` itself is unavailable.

## Approvals

- User authorized this new pipeline ideation/test round.
- No approval exists for data purchase/network backfill, Stage 3, an accounting
  ADR, config changes, shadow/demo/live, or promotion.

## Next action (single, concrete)

- Stop. Ask Claude/human to decide whether authoritative Deribit perpetual price
  acquisition is worth opening as a separate data task; do not retune C4.

## Human Learning Notes

Provider settlement timestamps can be economically identical while differing
by milliseconds; exact equality created a convincing 65% coverage artifact.
More importantly, a two-leg pair with gross=1 earns only half the raw funding
spread because each leg is 0.5 NAV. Missing either factor can turn a blocked
candidate into a false pass. The corrected proxy is mildly promising only under
cheap repo-default costs and too fragile under conservative costs, so acquiring
full price data should be a deliberate decision, not an automatic next step.
