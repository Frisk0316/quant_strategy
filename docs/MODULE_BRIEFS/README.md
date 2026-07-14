---
status: current
type: reference
owner: human
created: 2026-06-12
last_reviewed: 2026-07-14
expires: none
superseded_by: null
---

# Module Briefs

One short brief per module: the minimum a new session needs to safely work on it
without reading the whole codebase. Briefs are **navigation aids**, not
authority — code is authoritative for behavior, [[DOMAIN_RULES]] /
`research/strategy_synthesis.md` / `config/` for intent.

A brief should be skimmable in under a minute and point to the real source of
truth for anything that matters.

## Brief template

```markdown
---
status: current
type: reference
owner: human
created: <YYYY-MM-DD>
last_reviewed: <YYYY-MM-DD>
expires: none
superseded_by: null
---

# Module Brief: <module>

- **Path(s):** <owning code paths>
- **Responsibility:** <one or two sentences>
- **Owns business rules:** <DOMAIN_RULES ids, or none>
- **Key invariants:** <INVARIANTS ids>
- **Common failure modes:** <FAILURE_MODES ids>
- **Do not touch without approval:** <yes/no — why>
- **Source of truth for intent:** <config / research / ADR>
- **Tests:** <where the regression tests live>
- **Gotchas:** <the non-obvious thing that bites newcomers>
```

## Index

| Module | Brief | Path |
|---|---|---|
| Backtesting engine | [backtesting-engine.md](backtesting-engine.md) | `backtesting/` |
| H-014 Deribit shadow execution | [deribit-shadow-execution.md](deribit-shadow-execution.md) | `src/okx_quant/execution/deribit_shadow/` |
| Portfolio | [portfolio.md](portfolio.md) | `src/okx_quant/portfolio/` |

Add a brief when you first do non-trivial work in a module that lacks one. Keep
the index in sync.

Related: [[../FEATURE_MAP]] · [[../DOMAIN_RULES]] · [[../INVARIANTS]].
