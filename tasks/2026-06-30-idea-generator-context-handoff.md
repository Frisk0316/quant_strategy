# Context Handoff: Idea Generator B §6 + A §6b - 2026-06-30

## Goal (one sentence)
Implement the full-auto idea-generator front end: deterministic taxonomy
enumeration/ranking/registration plus crypto-alpha-lab paper-to-candidate-to-parent
draft automation.

## Current state
- Branch: `codex/pipeline-batch1-stage3`
- Last known good commit / state: working tree was already dirty before this task.
- In-progress edits (files): see session handoff for exact files added/changed.
- What works right now:
  - `backtesting.pipeline_idea_generator` enumerates taxonomy gaps, skips
    refuted/shelved and data-blocked families, ranks deterministically, caps at
    15, writes `idea_batch.json` and `hypothesis_ledger_draft.md`.
  - `scripts/run_pipeline_idea_generator.py` drives the parent generator.
  - `crypto_alpha_lab.pipeline` parses keyless arXiv metadata, validates
    supplied paper scores, promotes high-priority scores into research-only
    `AlphaCandidate` records, and writes dated weekly screen files.
  - `crypto_alpha_lab.adapters.to_parent_stage1_draft` converts lab candidates
    into parent Stage 1 draft dicts.
- What does not work / unfinished:
  - No real corpus fetch was run in this sandbox.
  - No generated draft was appended to `docs/HYPOTHESIS_LEDGER.md`; human review is still required.
  - Non-arXiv/free-academic source connectors are not implemented.

## Decisions made (and why)
- Use stdlib-only parsing/fetching/writing because the task is a pre-backtest
  sidecar and does not need a new framework.
- Write advisory sidecars instead of durable ledger rows because Stage 1 still
  requires human review.
- Treat A-half drafts as `source=A_literature` inside candidates and
  batch-level `source=mixed` when the parent merge hook is used, so downstream
  review can see the route clearly.
- Reject prompt inputs containing market series or fold-boundary keys because
  the ingestion spec requires an anti-leakage data firewall.

## Open questions / unverified assumptions
- Which exact public/free corpus sources beyond arXiv should be enabled first.
- Whether the first real `idea_batch.json` should be generated from the current
  mechanism taxonomy only or also from a fresh weekly lab screen.

## Rules in play (preserve verbatim)
- Invariants touched: I13/I14/I15/I26/I27 remain in force; no new invariant was added.
- Domain rules touched: R6.1, R6.3, R7.1, R7.4 reviewed; no rule semantics changed.
- Do-not-touch: strategy/signals/risk/portfolio/execution, deployment gates,
  `research/strategy_synthesis.md`, durable ledger values, existing `results/**`
  artifacts, and differential-validation implementation.

## Context to load next (the reading list)
- Source of truth: `docs/superpowers/specs/2026-06-30-idea-generator-frontend-design.md`,
  `docs/superpowers/specs/2026-06-30-mechanism-taxonomy.md`,
  `docs/EXPERIMENT_REGISTRY.md`, `research/crypto-alpha-lab/README.md`.
- Owning files / MODULE_BRIEFS: `docs/FEATURE_MAP.md`, `docs/DATA_FLOW.md`,
  `docs/superpowers/pipeline/stage1-hypothesis.md`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run
- `python -m pytest tests\unit\test_pipeline_idea_generator.py -q` - 5 passed.
- `(lab) python -m pytest tests\test_pipeline_adapters.py -q -p no:cacheprovider` - 4 passed.
- `(lab) python -m pytest -q -p no:cacheprovider` - 12 passed.
- `python -m ruff check <new idea-generator/lab files>` - passed.
- `python scripts\docs\check_doc_metadata.py` - passed with 32 pre-existing warnings.
- `python scripts\docs\check_feature_map_links.py` - passed, 154 concrete paths checked.
- `check_doc_impact.py --strict` with process-local `safe.directory` - passed, 43 changed files.
- `git diff --check` - passed; only CRLF conversion warnings were printed.
- `python scripts\validate_pipeline.py --check-config-only` - passed.
- `make docs-check` - not available in this Windows shell.

## Approvals
- Human approval needed / obtained: approval still needed before any sidecar draft is appended to the durable hypothesis ledger or backtested.

## Next action (single, concrete)
- Run the first real parent `idea_batch.json` sidecar from the current taxonomy
  and/or a fresh lab weekly screen, then send `hypothesis_ledger_draft.md` to
  Claude/human review.

## Human Learning Notes
The key safety move is keeping idea generation pre-backtest and sidecar-only:
automation can draft candidates, but it must not silently consume family budget,
append ledger rows, or see validation/fold data while inventing ideas.
