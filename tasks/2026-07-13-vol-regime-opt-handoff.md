---
status: current
type: handoff
owner: claude
created: 2026-07-13
last_reviewed: 2026-07-13
expires: none
superseded_by: null
---

# Session Handoff: F-VOL-REGIME-OPT Deribit options vol-regime Stage 1 — 2026-07-13

## Goal (one sentence)

Turn the user's Deribit BTC/ETH "sell premium when vol is super high, buy when
super low" idea into a registered, pre-gridded hypothesis (H-014) with a
Stage-1 probe (E-039) and a staged path whose final target is the two-sided
regime switch (Option C).

## Implementation summary

Literature/data survey (links in the spec); Stage-1 spec written with
design-space expansion; H-014/F-VOL-REGIME-OPT registered (user-ruled new
family vs F-VRP-TIMING); 4-combo grid pre-registered BEFORE the probe; E-039
synthetic-pricing probe ran on Deribit public-API daily DVOL + perp closes
(2021-03→2026-07). Result: regime separation confirmed for the short side
(covered call RICH +2.35%/30d coin BTC vs −0.09% NORMAL; strangle+put-spread
similar), CHEAP-bucket long straddle NEGATIVE on both symbols → C's long leg
stays OFF by default.

## Current state / diff scope

- Branch: `codex/pipeline-batch1-stage3` (tree also carries the other
  session's uncommitted PR #9 repair edits — NOT mine; nothing committed).
- Files added: `docs/superpowers/specs/2026-07-13-f-vol-regime-opt-hypothesis.md`;
  `research/probes/f_vol_regime_opt_probe.py`;
  `results/stage1_probe_20260713_f_vol_regime_opt/` (json + 4 CSVs); this file.
- Files changed: `docs/HYPOTHESIS_LEDGER.md` (H-014 row);
  `docs/EXPERIMENT_REGISTRY.md` (E-039 row + K-budget row);
  `docs/CURRENT_STATE.md`, `docs/AI_HANDOFF.md`, `config/workstreams.yaml`,
  `docs/CHANGELOG_AI.md` (session-end updates). Files deleted: none.

## Business-rule change?

No. Docs/research only. Future Stage-3 engine work (inverse-option coin
accounting) WILL be one: Change Manifest + ADR required, recorded in spec.

## Source-of-truth updates

- research/strategy_synthesis.md: N/A (H-014 enters synthesis only if it
  survives Stage 3). config/: workstreams.yaml mirror only. ADR: none.

## Experiments

- HYPOTHESIS_LEDGER: H-014 (proposed). EXPERIMENT_REGISTRY: E-039
  (completed, 0 trials, no K consumed) + F-VOL-REGIME-OPT K-budget 0/2 row.

## Decisions made (and why)

- New family, not F-VRP-TIMING — user ruling 2026-07-13; same VRP state
  variable but option-premium return source + coin accounting; Stage-3
  quantitative minting check still mandatory; would change on `ASSIGN` (I27).
- Final target = Option C (two-sided switch) — user ruling; put side is a
  spread (inverse-payoff wrong-way risk); long leg OFF by default because
  E-039 shows CHEAP-bucket long straddle is negative-carry.
- Probe used synthetic BS-on-DVOL instead of Tardis CSVs — full option-chain
  days are GB-scale; separation question doesn't need chains. Real-premium
  spot-check deferred to Stage 2 (Tardis first-of-month free CSVs).

## Open questions / unverified assumptions

- Flat-smile bias size (25Δ call IV vs DVOL) — Stage-2 question.
- RICH bucket is thin (≈2–4 non-overlapping cycles); separation is
  mechanism support, not edge evidence.

## Rules in play / do-not-touch

- I13/I23 (honest n_trials, grid pre-registered before probe), I27 (family
  minting), F26-class PIT discipline for any future DB-fed version.
- Do-not-touch: other session's uncommitted PR #9 repair edits; existing
  results/ artifacts; strategy/signal/risk/execution/config gates.

## Checks run

- `python scripts/docs/check_ledger_consistency.py` — passed (15 H, 39 E, 14 K).
- `python scripts/docs/check_doc_metadata.py` — passed, 0 warnings.
- Probe script ran end-to-end; artifacts written.

## Approvals

- Obtained 2026-07-13: new family + Stage-1 probe + C as final target.
- NOT authorized: Stage-3 grid, options engine/adapter work, any promotion.

## Next action (single, concrete)

Codex executes `tasks/2026-07-13-f-vol-regime-opt-stage2-codex-tasks.md`
(T1 Tardis real-premium calibration → E-040, T2 vendor report; T3 not
authorized). Claude is reviewer from 2026-07-13 on (user ruling).

## Human Learning Notes (required)

The probe reproduced the Anchorage finding independently: unfiltered short
premium ≈ 0 over the cycle; the regime filter carries all the value. And the
intuitive "buy vol when it's low" leg loses money even in the cheapest
regime bucket — average VRP > 0 means long vol needs a catalyst, not a level
trigger. Coin-margined puts are the risk concentration: payoff `(K−S)/S`
grows unbounded in a crash while collateral collapses — hence put spreads.
