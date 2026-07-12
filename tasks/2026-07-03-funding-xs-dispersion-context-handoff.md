---
status: current
type: handoff
owner: human
created: 2026-07-03
last_reviewed: 2026-07-03
expires: none
superseded_by: null
---

# Context Handoff: Funding XS Dispersion Stage 3 Checkpoint - 2026-07-03

## Goal (one sentence)

Run F-FUNDING-XS-DISPERSION family-minting distinctness, execute the
`xs_momentum_backtest.py`-style Stage-3 4-combo grid, and stop at checkpoint 1.

## Current state

- Branch: `codex/pipeline-batch1-stage3`.
- Last known good commit / state: working tree already had unrelated Turtle
  platform edits before this task; this task avoided those files.
- In-progress edits (files): `backtesting/funding_xs_dispersion_backtest.py`,
  `scripts/run_funding_xs_dispersion_checkpoint.py`,
  `backtesting/pipeline_stage3_registry.py`,
  `tests/unit/test_funding_xs_dispersion_backtest.py`,
  `tests/unit/test_pipeline_stage3_registry.py`,
  `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md`,
  `docs/FEATURE_MAP.md`,
  `docs/change_manifests/2026-07-03-funding-xs-dispersion-stage3.md`,
  and this handoff pair.
- What works right now: family minting writes sidecars and returns provisional
  `MINT`; Stage-3 runs 4 combos on 28 Stage-2-good Binance USDT perps; summary
  and checkpoint1 sidecars are written.
- What does not work / unfinished: checkpoint1 auto status is `FAIL` because
  DSR/PSR are 0.9345841204456411, below the 0.95 threshold. Portable validation
  remains adapter-required/absent. Claude/human review is still required.

## Decisions made (and why)

- Reused XS momentum target-weight construction and fold-refit helpers because
  this task asked to implement funding-xs Stage 3 through the existing
  `xs_momentum_backtest.py` pattern and stop at checkpoint 1.
- Loaded DB-backed daily closes via the last canonical 1m close per day because
  per-symbol 1m loading was too slow for checkpoint work and did not add
  evidence needed for a daily rebalance grid.
- Avoided `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, and
  `config/workstreams.yaml` because a concurrent Turtle platform session already
  had dirty changes there.

## Open questions / unverified assumptions

- H-009 remains `testing`: checkpoint1 statistical gate failed, but Claude/human
  still needs to decide whether provisional `MINT` has enough mechanism novelty
  versus the refuted F-FUNDING-CARRY family, and whether to shelve/refute.
- Portable validation block reason is honest but unreviewed by a human.

## Rules in play (preserve verbatim)

- Invariants touched: I13 hidden trials, I23 family-cumulative `n_trials`, I27
  family minting and K-budget separation.
- Domain rules touched: R3.1 funding sign convention, R6.1 leakage, R6.3 honest
  `n_trials`, R7.1 idealized-fill exclusion, R7.4 validation status.
- Do-not-touch: `research/`, live/shadow/demo gates, strategy/risk/portfolio/
  execution/config gate behavior, differential-validation implementation, and
  Turtle platform files from the concurrent session.

## Context to load next (the reading list)

- Source of truth: `research/strategy_synthesis.md`,
  `docs/superpowers/specs/2026-07-04-f-funding-xs-dispersion-hypothesis.md`,
  `docs/HYPOTHESIS_LEDGER.md` H-009, `docs/EXPERIMENT_REGISTRY.md` E-031.
- Owning files / MODULE_BRIEFS: `docs/FEATURE_MAP.md` section "Funding XS
  Dispersion Research Candidate"; `backtesting/funding_xs_dispersion_backtest.py`;
  `scripts/run_funding_xs_dispersion_checkpoint.py`.
- Context Pack: `docs/CONTEXT_PACKS/research_pipeline.md` if available; otherwise
  rebuild from `docs/CONTEXT_INDEX.md` and the files above.

## Checks run

- `python -m pytest tests\unit\test_funding_xs_dispersion_backtest.py tests\unit\test_pipeline_stage3_registry.py tests\unit\test_pipeline_checkpoint1_check.py -q` - 15 passed, pytest cache permission warning only.
- `python scripts\run_funding_xs_dispersion_checkpoint.py` - completed DB-backed
  family-minting plus 4-combo Stage-3 run.
- `python -m scripts.run_pipeline_checkpoint1_check --summary results\idea_batch_20260701_taxonomy_002\f_funding_xs_dispersion\summary.json --output results\idea_batch_20260701_taxonomy_002\f_funding_xs_dispersion\checkpoint1_auto.json` - expected FAIL at checkpoint 1 due DSR/PSR < 0.95.
- `python scripts\docs\check_doc_metadata.py` - passed.
- `python scripts\docs\check_feature_map_links.py` - failed on unrelated
  concurrent Turtle feature-map text referencing missing `surface.html`; not
  modified to avoid cross-session conflict.
- `python scripts\docs\check_doc_impact.py --strict` with temporary
  safe.directory env - passed.

## Approvals

- Human approval needed before any strategy promotion, retry, demo, shadow, live,
  or config-gate work. Not requested or obtained.

## Next action (single, concrete)

- Ask Claude to review E-031/checkpoint1 sidecars and decide verdict:
  shelve/refute H-009 as statistical-fail, or explicitly authorize a new scoped
  realism/retry task.

## Human Learning Notes

The family-minting checker can pass distinctness while checkpoint1 still stops
the work: distinct mechanism is not the same as deployable edge. Updating the
registry before rerunning checkpoint1 matters because trial reconciliation is a
first-class gate, independent of DSR/PSR.
