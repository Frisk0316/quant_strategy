---
status: current
type: governance
owner: human
created: 2026-06-12
last_reviewed: 2026-06-12
expires: none
superseded_by: null
---

# Review Questions

Checklist for reviewing a plan or diff. This operationalizes the review duties in
`CLAUDE.md` and `docs/ai_collaboration.md`. Work top to bottom; stop and block on
any failed money/risk item.

## Scope and process

- [ ] Did the change stay within the permitted files? Any scope creep?
- [ ] Was locate-before-edit done — does it touch the actual owning files?
- [ ] For a business-rule change: is there a Change Manifest, and was
      [[DOC_IMPACT_MATRIX]] honored?
- [ ] For a rule/policy change: is there an ADR?

## Money and risk (block on any failure)

- [ ] PnL: `ct_val` applied for SWAP? (R1.1 / I1)
- [ ] Realized/unrealized reconcile on close? (R1.3 / I2)
- [ ] Fees: maker vs. taker correct? (R2.1 / I3)
- [ ] Funding: sign and settlement window correct? (R3 / I4, I5)
- [ ] Sizing/risk: caps and reduce-only semantics intact? (R4 / I6, I7)
- [ ] Fills: no lookahead, no orphan/phantom positions, partial fills consistent?
      (R5 / I8, I9, I10)

## Data and evidence

- [ ] Correct data source; DB/parquet agreement? (R6.2 / I12)
- [ ] Coverage sufficient; not idealized-fill/in-sample passed off as evidence?
      (R6, R7.1 / I11, I14)
- [ ] Trial count recorded; no hidden trials? (R6.3 / I13)
- [ ] Reproducible artifact present; experiment logged in
      [[EXPERIMENT_REGISTRY]] and [[HYPOTHESIS_LEDGER]]?

## Schema and contracts

- [ ] No unreviewed change to backtest result schema or API response shape?
- [ ] `docs/UI_MAP.md` / `docs/DATA_FLOW.md` updated if contracts moved?

## Tests and docs

- [ ] New/changed behavior has a regression test? Invariants still guarded?
- [ ] Required docs updated (docs matrix in `AGENTS.md`)?
- [ ] No stale doc presented as current; no target-as-implemented claims?

## Readiness (harshest scrutiny)

- [ ] No live/shadow/demo readiness claim unless every gate passed AND human
      approval is recorded. (R7.2 / I15)

## Output

For each finding give severity, claim, evidence (file:line / rule id), and a
suggested resolution, per [[CRITIQUE_PROTOCOL]].

Related: [[CRITIQUE_PROTOCOL]] · [[QUESTION_BANK]] · [[INVARIANTS]] ·
[[FAILURE_MODES]].
