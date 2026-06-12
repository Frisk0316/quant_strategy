---
status: current
type: reference
owner: human
created: 2026-06-12
last_reviewed: 2026-06-12
expires: none
superseded_by: null
---

# Mental Models

Reusable reasoning lenses for this codebase. Use them to generate options in
[[DESIGN_SPACE]] and questions in [[QUESTION_BANK]]. They are heuristics, not
rules; the rules live in [[DOMAIN_RULES]] and [[INVARIANTS]].

## Trading / quant lenses

- **Edge after costs.** A signal is only an edge net of fees, funding, slippage,
  and latency. Always ask: does the edge survive R2 (fees) and R3 (funding)?
- **Idealized vs. realizable fill.** Idealized-fill and in-sample numbers are
  upper bounds, not evidence (R7.1). Treat them as "best case", never "expected".
- **Lookahead is the default bug.** Assume leakage until proven otherwise. Any
  feature using bar *t* data to act at bar *t* is suspect (R6.1, R5.3).
- **Selection bias compounds.** Every trial spent searching inflates the best
  result. Trial count is a first-class quantity (R6.3).
- **Sign conventions invert PnL.** Funding sign, long/short sign, and PnL sign
  are the highest-leverage one-character bugs (R3.1).
- **Contract multiplier is invisible until it's 100x.** `ct_val` errors are
  silent in unit tests that use ct_val=1 (R1.1).

## Systems / engineering lenses

- **Source of truth, not memory.** Config and `research/` are authoritative;
  chat history is not. When unsure, read the file.
- **Current / target / known-gap.** Never describe target behavior as
  implemented. If doc and code disagree, record the gap.
- **Blast radius before elegance.** The smallest change that is correct beats the
  most general change that is risky.
- **Reversibility.** Prefer changes that are cheap to undo. Hard-to-reverse
  changes (schema, gates, live mode) demand an ADR and human approval.
- **Make the invariant checkable.** A rule that no test enforces will eventually
  break silently. Push rules into [[INVARIANTS]] and tests.

## Reasoning hygiene lenses

- **Invert.** Instead of "how do I make this work", ask "how would this silently
  produce a wrong-but-plausible result?" → feeds [[FAILURE_MODES]].
- **Steelman the rejected option.** Before discarding an alternative, state its
  strongest form. If you can't, you don't understand the choice yet.
- **Name the assumption.** Every plan rests on assumptions; the dangerous ones
  are unnamed. Surface them as hypotheses ([[HYPOTHESIS_LEDGER]]).

Related: [[DESIGN_SPACE]] · [[CRITIQUE_PROTOCOL]] · [[DOMAIN_RULES]].
