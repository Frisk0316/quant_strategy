# Review Diff

Review stance:

- Lead with bugs, regressions, gate violations, missing tests, and scope creep.
- Use file and line references.
- Do not praise broad rewrites; focus on evidence.

Checklist:

- Does the diff stay inside permitted files?
- Does it change strategy assumptions without updating `research/strategy_synthesis.md`?
- Does it touch risk, portfolio, execution, DB schema, live/shadow/demo mode, deployment gates, or result artifacts without explicit approval?
- Does it preserve `ct_val` and funding cashflow semantics?
- Does it avoid lookahead, data leakage, survivorship bias, and hidden trial-count drift?
- Are tests and docs updated for the changed surface?
- Does it avoid claiming live readiness before all gates pass and the user approves?

Required output:

- Findings ordered by severity.
- Open questions or assumptions.
- Test gaps and residual risk.
