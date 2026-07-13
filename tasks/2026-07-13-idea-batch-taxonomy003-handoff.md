---
status: current
type: handoff
owner: claude
created: 2026-07-13
last_reviewed: 2026-07-13
expires: none
superseded_by: null
---

# Session Handoff: Idea batch taxonomy_003 + H-015 Stage 1/2 — 2026-07-13

## Goal (one sentence)

Run a new strategy-ideation round end-to-end (Claude solo, user-instructed,
no Codex): idea batch, own data downloads/probes, top-pick Stage-1 spec and
registration.

## Implementation summary

Generated `results/idea_batch_20260713_taxonomy_003/idea_batch.json`
(6 candidates ranked, 4 skipped-blocked, schema-conforming) from the
mechanism-taxonomy frontier + literature; ran availability-only probes
(`feasibility.json`, script `research/probes/idea_batch_20260713_feasibility.py`)
against the DB (optflow, Amihud breadth) and three free external sources
(DefiLlama, Coinbase, blockchain.info) — all pass. Registered top pick
H-015/F-OPTFLOW-POSITIONING with a pre-registered 4-combo grid and E-042
Stage-2 data probe (PASS, 0 trials, no K).

## Current state / diff scope

- Branch `codex/pipeline-batch1-stage3`; nothing committed (tree also holds
  other sessions' uncommitted edits — do not mix).
- Files added: `docs/superpowers/specs/2026-07-13-f-optflow-positioning-hypothesis.md`;
  `research/probes/idea_batch_20260713_feasibility.py`;
  `results/idea_batch_20260713_taxonomy_003/{idea_batch.json,feasibility.json}`;
  this file. Files changed: HYPOTHESIS_LEDGER (H-015), EXPERIMENT_REGISTRY
  (E-042 + K row), CURRENT_STATE (P1.1/P1.2 compressed to fit ≤90),
  AI_HANDOFF item 7, workstreams.yaml (pipeline stream), CHANGELOG_AI.

## Business-rule change? / Source-of-truth updates

No. Research/docs only. strategy_synthesis.md untouched (candidates enter it
only after surviving Stage 3). No ADR, no config gates.

## Experiments

- HYPOTHESIS_LEDGER: H-015 (proposed). EXPERIMENT_REGISTRY: E-042
  (stage2_partial / data_availability_pass) + F-OPTFLOW-POSITIONING K 0/2.

## Decisions made (and why)

- Top pick = optflow imbalance: data already ingested and verified (D4),
  mechanism pre-reserved as its own family by the Deribit research doc §3 C2,
  smallest distance from probe to Stage-3. Would change if minting returns
  ASSIGN vs F-FUNDING-XS-DISPERSION / F-OI-POSITIONING (I27).
- Direction fixed ex-ante: follow put-flow extremes to flat (Pan-Poteshman
  informed-flow), not fade; two-sided variant rejected to keep the grid at 4.
- Probes measure availability ONLY (coverage/staleness/labeling/frozen-feed);
  no signal metrics computed — keeps I13 clean before user ratification.

## Open questions / unverified assumptions

- Crypto option flow may be hedging-dominated rather than informed —
  exactly what Stage 3 falsifies. Shape caveat vs refuted F-SENTIMENT is in
  the spec; minting check mandatory.

## Rules in play / do-not-touch

- I13 (no hidden trials), I27 (minting fold), F26 (published_at as-of),
  R3.1 funding cashflow at Stage 3. Do-not-touch: other sessions'
  uncommitted PR #9 / E-041 edits; existing results/ artifacts.

## Checks run

- `check_ledger_consistency.py` — pass (16 H / 42 E / 15 K).
- `check_doc_metadata.py` — pass, 0 warnings. Probe script ran end-to-end.

## Approvals

- Obtained: user instruction 2026-07-13 to run this round Claude-solo incl.
  data downloads. NOT yet obtained: ratification of the batch ranking;
  authorization to run the H-015 Stage-3 grid.

## Next action (single, concrete)

User ratifies the taxonomy_003 ranking; on sign-off Claude implements the
H-015 Stage-3 runner (patterned on `backtesting/oi_positioning_backtest.py`)
through checkpoint ①.

## Human Learning Notes (required)

The best new candidate was already sitting in our own warehouse: D4 option-flow
data ingested a week ago fits the reserved C2 mechanism with 99.99% coverage,
while every externally-sourced candidate (stablecoin, Coinbase premium,
on-chain) needs new ingestion first. Checking data ranges BEFORE fixing a
sample design is now twice-learned (E-041 failed closed because its 2022
sample predates hourly-DVOL coverage — my T1-R spec missed it).
