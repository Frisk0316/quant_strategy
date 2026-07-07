---
status: draft
type: design
owner: claude
created: 2026-07-04
last_reviewed: 2026-07-04
expires: none
superseded_by: null
---

# H-009 Retry-1 Pre-registration (F-FUNDING-XS-DISPERSION)

User-approved retry decision 2026-07-04. This document is the **ex-ante
rationale** required by the standing H-009 constraint ("no chase-the-gate
retry"): it is written before inspecting E-031's per-combo results (this
session read only the aggregate WF/CPCV/DSR numbers in the ledger and
registry, never `summary.json` per-combo rows), and the rationale below is a
statistical-power argument, not a parameter change motivated by the miss.

## Ex-ante rationale (what changes, and why it is legitimate)

**Breadth restoration: 28 → 32 symbols.** E-031 ran on 28 of the 32
point-in-time-eligible symbols only because 4 symbols (`CC-USDT-SWAP`,
`FIL-USDT-SWAP`, `M-USDT-SWAP`, `SHIB-USDT-SWAP`) had zero funding history —
they were outside the original 22-symbol backfill union (E-030 notes). This
was a **data-completeness gap, not a design choice**: the Stage-1 spec's
universe definition is the full PIT top-30 universe, and breadth is this
family's explicit statistical-power lever
(`docs/superpowers/specs/2026-07-03-statistical-power-gates.md`). Retry-1
backfills funding for the 4 symbols and reruns the identical grid on the
spec-intended universe.

**What does NOT change:** window (2024-01-01 → 2026-06-17), grid
(`L ∈ [7,14]`, `Q ∈ [0.20,0.30]`, 4 combos), rebalance frequency, vol-target,
quantile construction, funding accounting, harness (fold-refit WF/CPCV,
N=6/k=2/embargo=2%/purge=1), leak test, retained `path_returns`. No parameter
is added, removed, or re-ranged.

## Trial and K accounting (binding)

- Family cumulative `n_trials`: 4 (E-031) + 4 (this grid) = **8**. The
  Stage-3 runner must declare `n_trials=8`.
- K budget: this retry burns **K 1/2** for `F-FUNDING-XS-DISPERSION`,
  regardless of outcome.
- Honest expectation, stated up front: at `n_trials=8` the DSR bar is
  *higher* than E-031 faced at 4. The retry passes only if the 4 restored
  symbols genuinely add cross-sectional edge/power; if DSR/PSR land below
  0.95 again, the outcome analysis must not be used to construct a rationale
  for retry-2 — a second retry needs its own independent ex-ante rationale
  and burns the final K.

## Decision rule (pre-committed)

- DSR ≥ 0.95 and PSR ≥ 0.95, other checkpoint① checks green → proceed to
  Claude review for promotion-track discussion (still no live claim).
- Any gate below threshold → H-009 goes to `refuted / shelved` unless the
  user explicitly rules otherwise at review; no immediate retry-2.

## Scope

Docs-only pre-registration, Claude-authored. Execution is Codex's per
`tasks/2026-07-04-h009-retry1-codex-plan.md`. No gate, trading-core, or
config change.
