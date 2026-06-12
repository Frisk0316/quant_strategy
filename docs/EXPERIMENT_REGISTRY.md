---
status: current
type: reference
owner: human
created: 2026-06-12
last_reviewed: 2026-06-12
expires: none
superseded_by: null
---

# Experiment Registry

Append-only log of experiments and research runs. Its job is to make results
**reproducible** and to keep an honest **trial count** (R6.3): every search over
parameters or strategies is a trial that inflates the best observed result.

Every experiment must link a hypothesis in [[HYPOTHESIS_LEDGER]]. Do not delete
rows — supersede them. A refuted or disappointing result is as valuable as a
positive one and must stay in the log.

## Registry

| ID | Date | Hypothesis | Setup (data range, config, seed) | Trials | Artifact / run_id | Outcome | Notes |
|---|---|---|---|---|---|---|---|
| E-000 | 2026-06-12 | H-000 | _example: BTC-SWAP 1H, config/strategies.yaml@<sha>, seed=0_ | 1 | _results/<run_id>_ | template | replace; do not delete |

## Required fields

- **Setup** must be enough to reproduce: instrument, date range, config
  reference (path + commit or hash), seed, and data source (DB vs parquet).
- **Trials** is the cumulative count of parameter/strategy combinations searched
  to produce this result. Hidden trials are a leakage bug (I13).
- **Artifact** points to the reproducible output (a `results/` run_id or file).
  Idealized-fill / in-sample artifacts must be labelled as such (R7.1).
- **Outcome** states the measured result and whether it supported the hypothesis.

## Rules

- Append, never rewrite. To correct an entry, add a new row and note "supersedes
  E-NNN".
- An experiment with no reproducible artifact is anecdote, not evidence.
- Promotion requires walk-forward / CPCV evidence and the
  `docs/ai_collaboration.md` gates, not a single positive row here.

Related: [[HYPOTHESIS_LEDGER]] · [[GOLDEN_CASES]] · `research/strategy_synthesis.md`.
