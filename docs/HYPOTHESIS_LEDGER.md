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
| H-001 | Cross-venue PnL metrics converge for the same strategy/params when only `ct_val` differs because notional sizing cancels the contract multiplier, modulo venue lot rounding. | ADR-0007 | supported | E-001 | Supported by the deterministic golden test: OKX `ctVal=0.01` and Binance `ctVal=1.0` produce matching `total_return` and `sharpe` within `1e-6`. This is not promotion evidence by itself. |
| H-002 | A dollar-neutral cross-sectional momentum book over a point-in-time top-30 liquid USDT-perp universe earns a positive net-of-cost (fees + slippage + short-leg funding) Sharpe that beats an equal-weight universe basket under walk-forward, surviving DSR ≥ 0.95 and PSR ≥ 0.95. | `research/strategy_synthesis.md` Strategy 11; 2026-06-23 design spec | refuted → shelved | E-002 (planned); E-003 (invalid); E-004; E-005 | Refuted on leak-free, unit-correct evidence: E-003's WF 2.879 / CPCV 1.592 / DSR 1.0 / PSR 0.992 was a lookahead-leak + broken-DSR artifact. E-004 (leak-fixed) PSR 0.7961; E-005 (DSR-fixed + portfolio-vol) DSR 0.7823 / PSR 0.8234 / CPCV OOS Sharpe 0.60 with dispersed, partly-negative groups — both anti-overfit gates fail (<0.95). **2026-06-24 decision (Claude):** shelve as a spec-correct research baseline (`enabled:false`); do **not** tune assumptions to chase the gate (raises honest `n_trials`, deflates DSR). Binding constraints: short OOS track length + weak/unstable edge. See `tasks/2026-06-24-xs-momentum-phase-c-review.md`. |

2026-06-24 correction: H-002 is **refuted under current evidence**. E-003 is
superseded/invalid due to the daily-target lookahead leak and stale
`promotion_gate_passed:true`; E-004 failed PSR after the leak fix; E-005 fixed
DSR and portfolio-vol sizing but still failed promotion gates with DSR 0.7823
and PSR 0.8234.

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
