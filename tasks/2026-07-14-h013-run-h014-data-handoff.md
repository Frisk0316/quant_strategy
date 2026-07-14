---
status: current
type: handoff
owner: claude
created: 2026-07-14
last_reviewed: 2026-07-14
expires: none
superseded_by: null
---

# Session Handoff: H-013 full run + H-014 entry-leg data — 2026-07-14

## Goal (one sentence)

Run H-013 end-to-end and collect H-014's Stage-3 entry-leg data, with nothing
required from the user (user authorization 2026-07-14).

## Implementation summary

H-013: E-038 feasibility PASS, then E-050 Stage-3 on the pre-registered
4-combo grid — statistical fail (WF 0.0543 / CPCV 0.5588 / DSR 0.5999 /
PSR 0.7845, minting MINT 0.051), SHELVED. H-014: collected real traded
premiums for all pre-registered entry legs on the union of grid RICH days
from the free official trade tape — 1,306/1,310 leg-days covered.

## Current state / diff scope

- Added: `research/probes/{h013_vrp_stage3.py,h014_collect_leg_marks.py}`;
  `results/h013_vrp_timing_20260714/`; `results/h014_leg_marks_20260714/`;
  this file. Changed: HYPOTHESIS_LEDGER (H-013), EXPERIMENT_REGISTRY
  (E-038 filled, E-050, K row), CURRENT_STATE, CHANGELOG_AI,
  AI_HANDOFF/workstreams (H-013 closure + H-014 data status). Not committed.

## Business-rule change? / Source-of-truth updates

No. Research/docs only; no ADR/config/gates; synthesis untouched.

## Experiments

- E-038 stage2_complete/pass; E-050 shelved/statistical-fail (4 trials,
  F-VRP-TIMING K 0/2 — original run, no retry entitlement).

## Decisions made (and why)

- "跑 H-013" read as Stage-3 authorization (spec had only Stage-2 approved);
  grid/params kept exactly as pre-registered 2026-07-12 — no extensions.
- H-014 data via trade-tape reconstruction scoped to RICH-union days only
  (~262 day-legs/symbol) instead of a full-tape backfill — free, hours→minutes.
- Traded-VWAP marks accepted as entry premiums (spread-crossing noise ~2-6%
  of mid per E-043); quote-level vendor data demoted to optional robustness.

## Open questions / unverified assumptions

- Collector marks are day-VWAP, not a fixed entry-time snapshot; the Stage-3
  spec must fix an entry convention (e.g., 08:00-nearest trade or day VWAP)
  ex-ante before the options backtest runs.

## Rules in play / do-not-touch

- I13/I23 (pre-registered grid, caller-declared n_trials), I27 (minting),
  F26 (published_at as-of). Untouched: trading core, gates, existing artifacts.

## Checks run

- `check_ledger_consistency.py` — pass (21 H / 51 E / 20 K);
  `check_doc_metadata.py` — pass. H-013 runner reuses the verifier-cleared
  taxonomy003 book/validation path; E-038 zero-Δ frozen-feed check PASS.

## Approvals

- Obtained: run H-013 + collect H-014 data (user 2026-07-14).
- NOT obtained: options-backtest MVP (needs coin-accounting Change Manifest
  + ADR + user sign-off) and H-014 Stage 3 itself.

## Next action (single, concrete)

Claude drafts the coin-margined options-accounting Change Manifest + ADR and
the H-014 Stage-3 spec (entry convention fixed ex-ante, using
`results/h014_leg_marks_20260714/leg_marks.csv`), then asks the user to
sign off before any engine/backtest code.

## Human Learning Notes (required)

Third data-shaped failure mode this week, all the same lesson: the E-041
sample predated hourly DVOL; the first collector run silently picked
instruments that did not exist yet on the signal day (D+30 lands on
daily-expiry instruments created weeks later — `creation_timestamp` filtering
is mandatory when reconstructing historical chains); and `include_old` is
required for aged Deribit trades. Historical-data code must prove the
instrument/series EXISTED at signal time, not merely that the API returns it.
