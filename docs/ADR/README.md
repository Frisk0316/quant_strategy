---
status: current
type: governance
owner: human
created: 2026-06-12
last_reviewed: 2026-07-17
expires: none
superseded_by: null
---

# Architecture Decision Records

ADRs capture **why** a significant or hard-to-reverse decision was made. Only
ADRs with `Status: Accepted` are implementation authority. Proposed ADRs
describe target design only and must not be implemented from without an explicit
task that lists permitted files.

## When an ADR is required

Add an ADR when a change:

- Alters a business rule in `docs/DOMAIN_RULES.md` (accounting, fees, funding,
  sizing, risk semantics, fill model, promotion gates).
- Changes the backtest result schema or a validation gate.
- Changes DB schema or a data-provenance contract.
- Changes the authority order or AI collaboration model.
- Introduces an architectural pattern future work must follow.

A pure bug fix that restores documented behavior does **not** need an ADR; a
Change Manifest is enough. When in doubt, add the ADR — they are cheap and
durable.

## Format

Use the existing ADRs as the pattern. Minimum sections:

```markdown
# ADR-XXXX: <title>

## Status
<Proposed | Accepted | Superseded by ADR-YYYY> - <YYYY-MM-DD>

## Context
<forces, constraints, and the problem>

## Decision
<the decision, stated as a rule>

## Consequences
<trade-offs, follow-ups, tests that must keep passing>
```

Number ADRs sequentially with a zero-padded four-digit id. Do not reuse or
delete numbers. To replace an ADR, add a new one and mark the old one
`Superseded by ADR-YYYY` in both the status line and lifecycle metadata.

## Index

| ADR | Title | Status |
|---|---|---|
| [0001](0001-ai-assisted-development.md) | AI-assisted development | Accepted |
| [0002](0002-backtest-result-schema.md) | Backtest result schema | Accepted |
| [0003](0003-position-pnl-accounting.md) | Position PnL accounting | Accepted |
| [0004](0004-frontend-module-loading.md) | Frontend module loading | Accepted |
| [0005](0005-replay-validation-gates.md) | Replay validation gates | Accepted |
| [0006](0006-reduce-only-risk-semantics.md) | Reduce-only risk semantics | Accepted |
| [0007](0007-multi-venue-instrument-specs.md) | Multi-venue instrument specifications | Accepted |
| [0008](0008-fast-backtest-artifact-rows.md) | Fast backtest artifact rows | Accepted |
| [0009](0009-xs-momentum-research-strategy.md) | XS momentum research strategy | Accepted |
| [0010](0010-inverse-options-research-accounting.md) | Coin-margined inverse-options research accounting | Accepted |
| [0011](0011-deribit-options-shadow-execution.md) | Deribit options shadow execution (v1) | Accepted |
| [0012](0012-inverse-perpetual-research-accounting.md) | Coin-margined inverse-perpetual research accounting | Accepted |
| [0013](0013-stage2-statistical-power-triage.md) | Stage-2 statistical-power triage | Accepted |
| [0014](0014-source-aware-canonical-candles.md) | Additive source-aware canonical candles | Accepted |

Keep this index in sync when adding an ADR. Related: [[DOMAIN_RULES]] ·
[[DOC_IMPACT_MATRIX]] · `docs/DOC_LIFECYCLE.md`.
