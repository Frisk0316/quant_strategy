---
status: current
type: reference
owner: human
created: 2026-06-12
last_reviewed: 2026-06-12
expires: none
superseded_by: null
---

# Failure Modes

Catalogue of known ways this system produces **wrong-but-plausible** results —
the bugs that pass tests and look fine on a chart but corrupt money, risk, or
research conclusions. Every new bug *class* discovered should be added here with
its detection and the invariant/test that now guards it.

This is the inverted view of [[INVARIANTS]]: invariants say what must hold;
failure modes say how it silently breaks.

## Catalogue

| ID | Failure mode | Symptom | Detection / guard | Rule |
|---|---|---|---|---|
| F1 | Missing `ct_val` on SWAP PnL | PnL off by the contract multiplier (e.g. 100x) | I1 PnL tests with ct_val != 1 | R1.1 |
| F2 | Funding sign inverted | Strategy PnL flips sign vs. expectation | I4 funding tests | R3.1 |
| F3 | Funding window too short | Funding income understated, settlement count low | I5 Gate 4 | R3.2 |
| F4 | Lookahead / leakage | In-sample looks great, out-of-sample collapses | I8 oracle tests, review | R5.3, R6.1 |
| F5 | Hidden trial count | Best result is overfit; not reproducible | I13, differential validation | R6.3 |
| F6 | Orphan hedge / phantom position | Open leg after exit; phantom risk | I9 backtesting tests | R5.2 |
| F7 | Terminal position leak | Unrealized PnL excluded; results look better | I10 Gate 1 | R5.2 |
| F8 | Insufficient data coverage | Metrics computed on sparse data | I11 Gate 3 | R6.2 |
| F9 | DB/parquet mismatch | Different results from "same" data | I12 validate-data | R6.2 |
| F10 | Idealized-fill treated as evidence | Promotion on a best-case upper bound | I14, review | R7.1 |
| F11 | No-fill replay | Flat equity curve, run completes "clean" | Gate 2 fill-rate warning | R5.1 |
| F12 | Maker charged taker fees | Costs overstated, edge hidden | I3 fee tests | R2.1 |
| F13 | Stale doc treated as current | Implementing target behavior as if it exists | DOC_LIFECYCLE status check | — |
| F14 | Chat memory as source of truth | Strategy drift, untracked assumption | Read config/research, not memory | — |
| F15 | Artifact OHLC collapsed to close/mid | DB parity compares the right exchange but every OHLC field mismatches canonical candles | Source-provenance `db_parity` with `canonical_source_primary` evidence; artifact vs DB first-row diff | R6.2, R7.2 |

## How to add a failure mode

When a bug is found that is a *new kind* of silent error:

1. Add a row: name, symptom, how it was/should be detected, and the rule it
   violates.
2. If no invariant guards it, add or strengthen one in [[INVARIANTS]] and, if
   possible, a regression test.
3. Note recurring operational failures in `docs/DEBUGGING_RUNBOOK.md` and
   durable backlog in `docs/KNOWN_ISSUES.md`.

Related: [[INVARIANTS]] · [[MENTAL_MODELS]] · [[CRITIQUE_PROTOCOL]] ·
`docs/KNOWN_ISSUES.md`.
