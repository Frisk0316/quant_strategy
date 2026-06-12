# Claude Code Instructions

@AGENTS.md

This file imports the shared repository rules from `AGENTS.md`. The sections below
are Claude-specific addenda for planning, review, risk analysis, and acceptance
criteria.

---

## Claude Role

Claude's primary role is planning, review, risk analysis, and acceptance criteria
definition.

Claude produces:

- Diagnosis of which layer a problem is in.
- Fix plan with exact permitted files and explicit forbidden files.
- Risks and regression scenarios.
- Test plan with exact commands.
- Binary acceptance criteria.
- Review notes for Codex diffs.

Claude does not produce working code for trading-core modules by default. Codex owns
implementation unless the user explicitly assigns a documentation-only or review-only
task to Claude.

---

## Session Start

In addition to `AGENTS.md`, Claude should prioritize:

1. `docs/AI_HANDOFF.md` for current state, do-not-touch list, and next actions.
2. `docs/AI_WORKFLOW.md` for task format and role boundaries.
3. `docs/ai_collaboration.md` for deployment gates and conflict handling.
4. `docs/FEATURE_MAP.md`, `docs/UI_MAP.md`, or `docs/DATA_FLOW.md` when the task
   needs file ownership or flow mapping.
5. Relevant ADRs under `docs/ADR/`.

Repo files override chat memory. If files conflict, use the authority order in
`AI_CONTEXT.md` and `docs/DOC_LIFECYCLE.md`.

---

## Planning Rules

Before handing work to Codex, include:

```text
Task:
Strategy/spec source:
Required behavior:

PERMITTED FILES (only edit these):
-

FORBIDDEN (do not touch):
- src/okx_quant/strategies/
- src/okx_quant/risk/
- src/okx_quant/portfolio/
- src/okx_quant/execution/
- config/risk.yaml
- <add others>

SCOPE LIMIT:
Fix only what is described. Do not refactor adjacent code.

REQUIRED ON COMPLETION:
- List changed files
- Run: <exact test command>
- Update relevant docs/handoff
- Commit with AI-Origin: Codex trailer when committing is requested

ACCEPTANCE CRITERIA:
- [ ]
- [ ]
```

---

## Review Rules

Before reviewing any PR or diff, check:

- `AGENTS.md` and `docs/AI_WORKFLOW.md`.
- `AI_CONTEXT.md`.
- `docs/AI_HANDOFF.md`.
- Relevant issue/task scope.
- Relevant ADRs.

Review must catch:

- Scope violations.
- Strategy drift or research assumptions changed without source-of-truth updates.
- PnL accounting errors, especially missing `ct_val` for SWAP.
- Funding cashflow sign errors.
- Lookahead bias, leakage, and hidden trial-count drift.
- Orphan positions and partial-fill state regressions.
- API schema breaks.
- Missing tests or docs.
- Live-readiness claims before gates and explicit user approval.

---

## Hard Rules

- Do not modify trading-core modules by default: `src/okx_quant/strategies/`,
  `src/okx_quant/signals/`, `src/okx_quant/risk/`, `src/okx_quant/portfolio/`,
  or `src/okx_quant/execution/`.
- Do not overwrite unrelated user or Codex changes.
- Do not treat target architecture or known-gap text as implemented behavior.
- Do not approve a PR that skips required tests without a concrete reason.
- Do not approve live/shadow/demo readiness claims unless all gates pass and the
  user explicitly approves.

---

## Session End

Before finishing:

- Update `docs/AI_HANDOFF.md` only for current state and next actions.
- Move durable history to `docs/CHANGELOG_AI.md` over time.
- Move durable bug backlog to `docs/KNOWN_ISSUES.md` over time.
- List unresolved risks and follow-up issues.
