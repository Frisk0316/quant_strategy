---
status: current
type: reference
owner: human
created: 2026-06-12
last_reviewed: 2026-06-12
expires: none
superseded_by: null
---

# Hypothesis Ledger

Tracks **testable claims** — about strategy edge, system behavior, or a design
decision's premise — from statement to resolution. The point is to make beliefs
explicit and falsifiable so the system does not accumulate untested assumptions.

Every experiment must reference a hypothesis here, and every hypothesis that is
tested must link the experiment in [[EXPERIMENT_REGISTRY]].

## Lifecycle

`proposed` → `testing` → (`supported` | `refuted` | `inconclusive`) → optionally
`retired`.

A `supported` hypothesis is still not promotion evidence on its own; promotion
needs the gates in `docs/ai_collaboration.md`.

## Ledger

| ID | Hypothesis (falsifiable) | Source | Status | Experiment(s) | Resolution / notes |
|---|---|---|---|---|---|
| H-000 | _example: "Funding-carry edge on BTC-SWAP survives fees+funding over a full settlement window."_ | DESIGN_SPACE | proposed | — | template row; replace |
| H-001 | Cross-venue PnL metrics converge when only `ct_val` differs because notional sizing cancels the contract multiplier, modulo venue lot rounding. | ADR-0007 | supported | E-001 | Supported by the deterministic golden test: OKX `ctVal=0.01` and Binance `ctVal=1.0` produce matching `total_return` and `sharpe` within `1e-6`. This is not promotion evidence by itself. |

## How to add an entry

1. State the hypothesis so it can be **refuted** by evidence ("X improves Y by
   ≥ Z under condition C"), not as an aspiration.
2. Record where it came from (design decision, review question, observed
   anomaly).
3. When you run a test, set status `testing` and link the
   [[EXPERIMENT_REGISTRY]] entry.
4. On resolution, record the outcome and what it implies for
   [[DOMAIN_RULES]] / [[INVARIANTS]] / [[DESIGN_SPACE]].

Related: [[EXPERIMENT_REGISTRY]] · [[DESIGN_SPACE]] · [[QUESTION_BANK]].
