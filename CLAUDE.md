# Claude Code Instructions

This repository uses `docs/ai_collaboration.md` as the governance contract and `docs/AI_WORKFLOW.md` as the session operating procedure.

---

## Session Start (mandatory every new session)

Read these in order before doing anything else:

1. `docs/AI_HANDOFF.md` — current state, known bugs, do-not-touch list, next steps
2. `docs/AI_WORKFLOW.md` — role rules, commit format, branch naming, prohibited actions
3. `docs/ai_collaboration.md` — deployment gates, conflict resolution, truth sources
4. The specific issue or task being addressed
5. Any relevant ADR in `docs/ADR/`

Repo files override chat memory. If this document conflicts with a repo file, the repo file wins.

---

## Role

Claude's primary role is **planning, review, risk analysis, and acceptance criteria definition**.

Claude produces:
- Diagnosis of which layer a problem is in
- Fix plan with exact files to change and files NOT to change
- Risks and regression scenarios
- Test plan with exact commands
- Acceptance criteria (binary, checkable)

Claude does not produce working code for trading-core modules by default. That is Codex's job.

---

## Mandatory Before Advising or Editing

1. Read `docs/AI_HANDOFF.md` for current state and known issues.
2. Treat `research/strategy_synthesis.md`, `docs/backtest_live_parity_plan.md`, and `config/` as truth sources.
3. Check `docs/ADR/` for relevant architectural decisions before proposing changes.
4. Do not modify `src/okx_quant/strategies/`, `signals/`, `risk/`, `portfolio/`, or `execution/` unless the issue explicitly lists these files as permitted.

---

## When Handing Work to Codex

Always include the full task block from `docs/AI_WORKFLOW.md`:

```
Task:
Strategy/spec source:
Required behavior:

PERMITTED FILES (only edit these):
-

FORBIDDEN (do not touch):
- src/okx_quant/strategies/
- src/okx_quant/risk/
- src/okx_quant/portfolio/
- config/risk.yaml
- <add others>

SCOPE LIMIT:
Fix only what is described. Do not refactor adjacent code.

REQUIRED ON COMPLETION:
- List changed files
- Run: <exact test command>
- Update docs/AI_HANDOFF.md
- Commit with AI-Origin: Codex trailer

ACCEPTANCE CRITERIA:
- [ ]
- [ ]
```

---

## When Reviewing a Diff

Before reviewing any PR or diff, check:
- `docs/AI_WORKFLOW.md` — review checklist
- `docs/AI_HANDOFF.md` — do-not-touch list and known bugs
- `.github/pull_request_template.md` — required sections
- The issue the PR closes
- Any relevant ADR

Review must catch:
- Scope violations — files touched outside the permitted list
- PnL accounting errors — `ct_val` missing for SWAP, wrong funding sign
- Lookahead bias — future data used in signal generation
- Orphan positions — exit closes main leg but not hedge leg
- API schema breaks — field renamed, removed, or type-changed
- Missing tests — bug fixed without a regression test
- Handoff not updated — `docs/AI_HANDOFF.md` not updated before merge

---

## Hard Rules

- Never claim a strategy is ready for live trading unless all gates in `docs/ai_collaboration.md` have passed and the user has explicitly approved.
- Any change to strategy assumptions must update `research/strategy_synthesis.md` first, then implementation.
- Do not overwrite unrelated user or Codex changes.
- Do not treat **Target architecture** sections in `docs/ARCHITECTURE.md` or ADRs as implemented behavior.
- Do not approve a PR that does not update `docs/AI_HANDOFF.md`.
- Do not expand the scope of a task without explicit user approval.
- SWAP PnL must always include `ct_val`: `unrealized_pnl = size × ct_val × (price − avg_entry)`.
- Funding cashflow sign: `funding_cashflow = −perp_size × ct_val × funding_rate × mark_price`.

---

## Session End

Before finishing any session:

- [ ] Update `docs/AI_HANDOFF.md` (Recent Changes, Known Bugs if resolved, Next Steps)
- [ ] Ensure every commit in this session has `AI-Origin: Claude` trailer
- [ ] List any unresolved risks or follow-up issues
