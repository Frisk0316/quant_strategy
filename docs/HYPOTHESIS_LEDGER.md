---
status: current
type: reference
owner: human
created: 2026-06-12
last_reviewed: 2026-06-25
expires: none
superseded_by: null
---

# Hypothesis Ledger

Tracks **testable claims** about strategy edge, system behavior, or a design
decision's premise from statement to resolution. The point is to make beliefs
explicit and falsifiable so the system does not accumulate untested assumptions.

Every experiment must reference a hypothesis here, and every hypothesis that is
tested must link the experiment in [[EXPERIMENT_REGISTRY]].

## Lifecycle

`proposed` -> `testing` -> (`supported` | `refuted` | `inconclusive`) ->
optionally `retired`.

A `supported` hypothesis is still not promotion evidence on its own; promotion
needs the gates in `docs/ai_collaboration.md`.

## Family Trial Accounting

Each hypothesis belongs to a family. `family_cumulative_n_trials` is the count
the next CPCV run for that family must use: the prior family total plus the
current run's grid size. The detailed rows live in [[EXPERIMENT_REGISTRY]].

## Ledger

| ID | Family ID | Family cumulative n_trials | Hypothesis (falsifiable) | Source | Status | Experiment(s) | Resolution / notes |
|---|---|---:|---|---|---|---|---|
| H-000 | F-000 | 0 | _example: "Funding-carry edge on BTC-SWAP survives fees+funding over a full settlement window."_ | DESIGN_SPACE | proposed | - | template row; replace |
| H-001 | F-001 | 1 | Cross-venue PnL metrics converge for the same strategy/params when only `ct_val` differs because notional sizing cancels the contract multiplier, modulo venue lot rounding. | ADR-0007 | supported | E-001 | Supported by the deterministic golden test: OKX `ctVal=0.01` and Binance `ctVal=1.0` produce matching `total_return` and `sharpe` within `1e-6`. This is not promotion evidence by itself. |
| H-002 | F-XS-MOMENTUM | 24 | A dollar-neutral cross-sectional momentum book over a point-in-time top-30 liquid USDT-perp universe earns a positive net-of-cost (fees + slippage + short-leg funding) Sharpe that beats an equal-weight universe basket under walk-forward, surviving DSR >= 0.95 and PSR >= 0.95. | `research/strategy_synthesis.md` Strategy 11; 2026-06-23 design spec | refuted / shelved | E-002 (planned); E-003 (invalid); E-004; E-005 | Refuted on leak-free, unit-correct evidence: E-003's WF 2.879 / CPCV 1.592 / DSR 1.0 / PSR 0.992 was a lookahead-leak + broken-DSR artifact. E-004 (leak-fixed) PSR 0.7961; E-005 (DSR-fixed + portfolio-vol) DSR 0.7823 / PSR 0.8234 / CPCV OOS Sharpe 0.60 with dispersed, partly-negative groups - both anti-overfit gates fail (<0.95). Under the 2026-06-25 family-cumulative convention, F-XS-MOMENTUM has at least 24 trials from E-003/E-004/E-005 before any future retry. **2026-06-24 decision (Claude):** shelve as a spec-correct research baseline (`enabled:false`); do **not** tune assumptions to chase the gate (raises honest `n_trials`, deflates DSR). Binding constraints: short OOS track length + weak/unstable edge. See `tasks/2026-06-24-xs-momentum-phase-c-review.md`. |
| H-003 | F-S7-BASIS-MEANREV | 72 | A delta-neutral BTC/ETH perp-vs-spot basis mean-reversion book (enter on extreme basis z-score, exit on convergence) earns a positive net-of-cost Sharpe that beats the static funding-carry baseline, surviving WF and CPCV with DSR >= 0.95 and PSR >= 0.95. | `research/strategy_synthesis.md` Strategy 7; `docs/superpowers/specs/2026-06-25-s7-basis-meanrev-hypothesis.md` | shelved | E-006 (planned); E-011 (data-blocked); E-013 (invalid no-trade); E-016 | Pipeline batch 1 S7 was rerun with a non-degenerate finite half-life grid after the zero-return artifact. E-016 has nonzero grid activity but fails the statistical gate: WF OOS Sharpe -0.4359, CPCV OOS Sharpe -1.1124, DSR ~0, PSR ~0, `promotion_gate_passed:false`. Shelved pending Claude review; no promotion evidence and no refutation verdict from the earlier no-trade artifact. |
| H-004 | F-S5-RESIDUAL-MEANREV | 72 | A market-neutral basket that removes BTC/ETH common beta and trades residual mean reversion earns a positive net-of-cost Sharpe beating an equal-weight universe basket, surviving WF/CPCV with DSR >= 0.95 and PSR >= 0.95. | `research/strategy_synthesis.md` Strategy 5; `docs/superpowers/specs/2026-06-25-s5-residual-meanrev-hypothesis.md` | inconclusive | E-007 (planned); E-009; E-014 | E-014 reran S5 through the fold-refit harness after ETH perp data repair, but current point-in-time membership and venue-scoped candle coverage produce no grid activity. Treat as a data-universe artifact, not strategy refutation or support. |
| H-005 | F-S6-TS-MOMENTUM | 48 | A low-turnover time-series momentum sleeve on BTC/ETH perps (own-trend, vol-targeted, crash-filtered) earns a positive net-of-cost Sharpe beating BTC buy-and-hold, surviving WF/CPCV with DSR >= 0.95 and PSR >= 0.95. | `research/strategy_synthesis.md` Strategy 6; `docs/superpowers/specs/2026-06-25-s6-ts-momentum-hypothesis.md` | inconclusive | E-008 (planned); E-010 (data-blocked); E-012 (invalid harness); E-015 | E-012's apparent statistical pass used a non-refitting WF/CPCV harness and is not OOS edge evidence. E-015 reran S6 with fold-local parameter selection: WF OOS Sharpe 0.0088, CPCV OOS Sharpe 0.5422, DSR 0.1963, PSR 0.7387, `promotion_gate_passed:false`. No adapter/ct_val work until a refitting harness re-earns the statistical gate. |

2026-06-24 correction: H-002 is **refuted under current evidence**. E-003 is
superseded/invalid due to the daily-target lookahead leak and stale
`promotion_gate_passed:true`; E-004 failed PSR after the leak fix; E-005 fixed
DSR and portfolio-vol sizing but still failed promotion gates with DSR 0.7823
and PSR 0.8234.

2026-06-25 trial-accounting note: future CPCV for any family must use the
family-cumulative `n_trials` from this ledger and [[EXPERIMENT_REGISTRY]], not a
per-run grid count alone.

## How to add an entry

1. State the hypothesis so it can be **refuted** by evidence ("X improves Y by
   >= Z under condition C"), not as an aspiration.
2. Assign a stable `family_id` for retry accounting.
3. Record where it came from (design decision, review question, observed
   anomaly).
4. When you run a test, set status `testing` and link the
   [[EXPERIMENT_REGISTRY]] entry.
5. On resolution, record the outcome and what it implies for
   [[DOMAIN_RULES]] / [[INVARIANTS]] / [[DESIGN_SPACE]].

Related: [[EXPERIMENT_REGISTRY]] - [[DESIGN_SPACE]] - [[QUESTION_BANK]].
