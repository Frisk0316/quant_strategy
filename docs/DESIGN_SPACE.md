---
status: current
type: reference
owner: human
created: 2026-06-12
last_reviewed: 2026-06-12
expires: none
superseded_by: null
---

# Design Space

Every design-heavy task must begin by **expanding the design space** before
converging. The failure mode this prevents is committing to the first plausible
approach and discovering its flaws only after implementation.

## Protocol

For any non-trivial design decision, write down — briefly — at least the
following before choosing:

1. **Problem statement.** One sentence. What must be true after this change that
   is not true now?
2. **Constraints.** Hard limits (config authority, do-not-touch areas, gates,
   schema/API contracts) and soft limits (effort, blast radius).
3. **At least three options.** Including the "do nothing / smallest change"
   option. For each: mechanism, blast radius, what it assumes, how it could be
   wrong.
4. **Trade-off axis.** Name the axis the options actually differ on
   (correctness vs. speed, generality vs. simplicity, reversibility vs. power).
5. **Decision + why.** Which option, and the single most important reason.
6. **What would change the decision.** The evidence or condition that would flip
   the choice — this becomes a [[HYPOTHESIS_LEDGER]] entry if testable.

Keep it short. Three bullets per option is enough. The point is to make the
discarded options *visible*, not to write an essay.

## When this is required

- New strategy, signal, or sizing approach.
- Any change to accounting, fills, funding, or gates.
- Schema, API contract, or data-flow changes.
- Anything an ADR would document.

A pure bug fix that restores documented behavior does not need design-space
expansion — but naming the one alternative you rejected still helps review.

## Worked template

```markdown
### <decision title> — <date>

**Problem:** <one sentence>
**Constraints:** <hard / soft>

**Option A — <name>:** <mechanism>. Assumes <x>. Wrong if <y>. Blast radius: <z>.
**Option B — <name>:** ...
**Option C — smallest change:** ...

**Axis:** <the real trade-off>
**Decision:** Option <x> because <reason>.
**Would change if:** <evidence> → ledger entry [[HYPOTHESIS_LEDGER]] H-NNN.
```

Related: [[MENTAL_MODELS]] · [[CRITIQUE_PROTOCOL]] · [[HYPOTHESIS_LEDGER]] ·
`docs/ADR/README.md`.
