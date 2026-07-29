---
status: current
type: handoff
owner: claude
created: 2026-07-29
last_reviewed: 2026-07-29
expires: none
superseded_by: null
---

# Handoff: shadow-clock repair + ADR-0016 literature slate — 2026-07-29

Merged Context+Session handoff (user-approved single-file format).

## Goal (one sentence)
Get the H-014 shadow evidence clock actually running, and build the
literature-backed candidate slate ADR-0016 needs before a complete round.

## Implementation summary
Two threads. (1) The shadow clock had been stalled since 2026-07-15; the
recorded cause ("machine off") was wrong. Root cause: Task Scheduler power
conditions refused every trigger on battery and never caught up. Settings
flipped with user approval; the wrapper's exit-code masking (introduced
2026-07-28 with the toast notifications) fixed; a second blocker then surfaced
— `canonical_candles` ran 14 days behind `market_klines` because the daily ops
script ingested but never promoted — fixed by a manual catch-up plus a
permanent canonicalize step. The 16:10 scheduled run now completes unattended
and the journal carries 2026-07-29. (2) Literature research produced eight
verified-paper-backed new mechanisms (H-030…H-037) plus an eligibility audit
of every K-remaining family, yielding exactly one legitimate existing-strategy
iteration (H-038).

## Current state / diff scope
- Branch: `feature/deribit-moneyness-hypotheses` (stacked on PR #17).
- Commits this session: `df04f92` scheduler+exit-code repair; `7e18edb`
  canonicalize step; `2c16f8a` H-030/H-031; `5667ed1` slate pipeline notes;
  `3d1d22e` H-032…H-037; `2d2e1b2` iteration audit + H-038; plus this
  session-end sync.
- Works now: shadow task runs unattended on battery, catches up missed slots,
  reports honest exit codes; journal advancing.
- Unfinished: no Stage-2 probe module exists for any of H-030…H-038.

## Decisions made (and why)
- Flipped three scheduler power settings (user-approved) — without them the
  job could never run on this host; would revert only if the machine stops
  being battery-powered and the settings caused unwanted wakeups.
- Registered eight mechanisms but explicitly did NOT manufacture a second
  iteration — I28 forbids bare reruns of statistically-failed families, and
  every K-remaining family except F-S5 falls in that class.
- Recorded four screened-out mechanisms (IV-skew→returns is refuted by its own
  literature; max-pain has no rigorous study; stablecoin flows need on-chain
  data we lack; overnight seasonality is cost-dominated) so they are not
  re-proposed.

## Rules in play (preserve verbatim)
- I28: refuted/shelved/inconclusive families need an explicit twist, never a
  bare rerun. I53: below 10–15/8/2 a slate is a `limited_probe`.
- H-038 would consume F-S5 K → 2/2, i.e. **terminal for that family**.
- No promotion/live/demo claim; R7.2 untouched. ADR-0011 exit clock restarts
  2026-07-29; missed days are permanently unrecoverable.

## Open questions / unverified assumptions
- Whether a second eligible iteration can ever appear without waiting for
  blocked data (OKX funding) or a new-mechanism failure that yields a twist.
- H-030's distinctness vs shelved F-TAKER-FLOW is the decisive unknown; if it
  fails, the "boundary timing, not flow level" mechanism claim is false.

## Checks run
- `check_ledger_consistency.py` — passed (39 hypotheses, 69 experiments,
  35 K-budget families)
- `check_doc_metadata.py` — passed (2 pre-existing warnings)
- Shadow: `schtasks /Query` Last Run 16:10:02, Last Result 0; journal
  event_dates now include 2026-07-29
- Canonical candles verified to 2026-07-29 08:05 for BTC and ETH

## Approvals
- Obtained: scheduler settings change; "補齊到八個" for the slate.
- Needed: authorization to execute any of H-030…H-038 (H-038 especially, it
  is terminal for F-S5).

## Next action (single, concrete)
Write the Stage-2 probe modules (ADR-0016 phase 3) for the registered slate,
starting with H-030 — it is the only candidate whose event count plausibly
clears the power floor that killed H-024…H-029 and H-029/E-068.

## Human Learning Notes
- The two-week shadow stall was a settings bug that had been mis-attributed to
  the user. Before blaming an operator for a missed automation, read the job's
  configuration and result codes — see the new entry in `docs/ai/LESSONS.md`.
- Fixing one layer exposed the next (scheduler → canonicalize gap). "It runs
  now" is not "it works now" until the end-to-end artifact appears.
- Research produced a genuinely useful *negative*: the IV-skew→returns idea is
  refuted in its own literature, so a probe was avoided entirely.
- Honest arithmetic beats a full checklist: the round is 9 of 10–15 and stays
  a `limited_probe` until a real second iteration exists.

## Skipped session-end steps
CURRENT_STATE.md was not rewritten this session (it stands at ~220 lines vs
its 90-line cap; a dedicated compaction pass moving history to CHANGELOG_AI is
still owed). AI_HANDOFF, workstreams, KNOWN_ISSUES, RUNBOOK, and LESSONS were
all updated.
