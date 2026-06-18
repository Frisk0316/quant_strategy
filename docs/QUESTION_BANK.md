---
status: current
type: reference
owner: human
created: 2026-06-12
last_reviewed: 2026-06-12
expires: none
superseded_by: null
---

# Question Bank

Reusable questions to ask *before* writing code or a plan. Pull from the
relevant section at the start of a task. These generate the options in
[[DESIGN_SPACE]] and the checks in [[REVIEW_QUESTIONS]].

## Framing (every task)

- What must be true after this change that is not true now? (one sentence)
- Which layer is this actually in — strategy, signal, risk, portfolio,
  execution, backtesting, API, frontend, data, or docs?
- Where is the source of truth for the intended behavior — config, `research/`,
  an ADR, or a test? Have I read it, not remembered it?
- What is the smallest change that is correct?
- What is the blast radius, and what is the rollback?

## Money / risk (any business-rule change)

- Does this touch PnL, fees, funding, sizing, risk limits, or fill semantics?
  If yes → Change Manifest + [[DOC_IMPACT_MATRIX]].
- Is `ct_val` applied correctly? (R1.1)
- Are fee maker/taker and funding signs correct? (R2, R3.1)
- Could this introduce lookahead or leakage? (R5.3, R6.1)
- Does this change the trial count or selection process? (R6.3)
- Could this create orphan/phantom positions or partial-fill state bugs? (R5.2)

## Data / backtest

- DB or parquet source? Do they agree for this range? (R6.2)
- Is the data coverage sufficient for the claim? (I11)
- Is the result idealized-fill / in-sample? Then it is a bound, not evidence.
  (R7.1)
- Is there a reproducible artifact and a recorded trial count?

## API / frontend / schema

- Does this change a response schema or contract the frontend depends on?
- Are `docs/UI_MAP.md` and `docs/DATA_FLOW.md` still accurate?

## Promotion / deployment

- Have all gates in `docs/ai_collaboration.md` passed?
- Is there explicit, recorded human approval? If not, no readiness claim. (R7.2)

## Meta (when stuck or uncertain)

- What am I assuming that I have not verified? → [[HYPOTHESIS_LEDGER]].
- How would this silently produce a wrong-but-plausible result? →
  [[FAILURE_MODES]].
- What is the strongest version of the option I'm about to reject?

Related: [[DESIGN_SPACE]] · [[REVIEW_QUESTIONS]] · [[CRITIQUE_PROTOCOL]] ·
[[MENTAL_MODELS]].
