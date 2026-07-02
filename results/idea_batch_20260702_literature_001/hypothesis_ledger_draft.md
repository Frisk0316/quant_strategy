# Hypothesis Ledger Draft

| Candidate | Source | Family | Mechanism | Draft status | Family decision |
|---|---|---|---|---|---|
| alpha-doi-10-2139-ssrn-6609698 | A_literature | F-FUNDING-CARRY | Path Signatures for Regime Detection in Cryptocurrency Markets: A Rough-Path Framework Using Spot, Perpetual Basis, and Funding Rates may define a testable crypto alpha after costs. | pending_llm | SKIP (Claude Stage-1 review, 2026-07-02) |

## Claude Stage-1 review: alpha-doi-10-2139-ssrn-6609698 — SKIP, not promoted

Per `docs/superpowers/pipeline/stage1-hypothesis.md`, a Stage-1 hypothesis
needs a testable signal/entry/exit/sizing spec sourced from
`research/strategy_synthesis.md`, the paper itself, or explicit user
instruction — not invented from a title alone. This candidate does not clear
that bar:

- **Mechanism mismatch, not just a weak match.** The paper title is a
  regime-*detection* methodology (rough-path signatures over spot/basis/
  funding as input features), not a funding-carry *trading rule*. The
  mechanical keyword scorer assigned `family_id_or_NEW=F-FUNDING-CARRY` purely
  because "funding/perpetual/basis/carry" co-occur in the title
  (`priority_score=3.82`, barely above the 3.8 threshold) — this is exactly
  the coarse-categorization limitation the scorer's own `notes` field flags
  (`scoring_method=mechanical_keyword_placeholder`).
- **No abstract fetched (keyless metadata only), so no concrete rule exists
  to tighten.** The draft's placeholder fields (`signal_definition`:
  "paper-derived signal; requires human Stage 1 tightening",
  `entry_rule`: "enter only after Stage 1 defines a pre-registered
  threshold") are literally empty of a testable rule. Writing a real
  entry/exit/sizing spec from the title alone would mean inventing the
  strategy, which the Stage-1 template explicitly forbids.
- **Even under a charitable reading** (e.g., "use regime detection to gate
  *when* to run funding-carry"), `F-FUNDING-CARRY` is already refuted with
  concrete evidence (H-007/E-026: DSR 0.0041, realized vol 0.247% —
  structurally too calm, not a marginal miss), so promoting this would need
  to clear the family-minting "genuine twist" bar, which requires reading the
  actual paper (paywalled SSRN, not fetched) — out of scope for a
  title-only mechanical batch.

**Decision:** SKIP. No `docs/HYPOTHESIS_LEDGER.md` or
`docs/EXPERIMENT_REGISTRY.md` entry — nothing was specified or run, so there
is nothing to ledger. No Stage 2/3 work follows from this candidate.
