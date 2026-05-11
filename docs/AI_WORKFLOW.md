---
status: current
type: governance
owner: human
created: 2026-05-11
last_reviewed: 2026-05-11
expires: none
superseded_by: null
---

# AI Workflow

Operational companion to `docs/ai_collaboration.md`. That document is the governance contract; this document is the session-by-session operating procedure.

---

## Roles and Responsibilities

### Claude

**Does:**
- Read `docs/AI_HANDOFF.md` and relevant issue before touching anything
- Produce a written plan with diagnosis, proposed fix, files to change, risks, test plan, and acceptance criteria
- Review Codex diffs for scope violations, PnL accounting errors, lookahead bias, orphan positions, API schema breaks, and missing tests
- Update `AI_HANDOFF.md` at the end of each session

**Does not:**
- Directly modify `src/okx_quant/strategies/`, `risk/`, `portfolio/`, or `execution/` unless the user explicitly overrides this
- Expand scope beyond the current issue
- Claim a strategy is ready for live trading unless all gates in `ai_collaboration.md` have passed

### Documentation-only Exception

Claude may directly edit documentation files when all of the following are true:

- The issue or task is documentation-only
- The permitted files list includes the target doc
- No trading-core files are modified
- `AI_HANDOFF.md` is updated after the session

This exception does **not** apply to:

- Strategy implementation
- Portfolio accounting
- Risk logic
- Execution logic
- Live / shadow deployment settings (`config/settings.yaml` mode field)

### Codex

**Does:**
- Read the Claude plan and issue before writing any code
- Modify only files listed in the issue's permitted scope
- Keep diffs small — one issue, one PR
- Add or update a regression test for every bug fix
- Update `AI_HANDOFF.md` at the end of the session

**Does not:**
- Refactor adjacent code not covered by the issue
- Rename variables, reformat files, or improve error messages unless they are the bug
- Change strategy assumptions without a matching update to `research/strategy_synthesis.md`
- Make architecture changes without a Claude plan and user approval
- Declare a task complete without running the specified tests

### Human

**Does:**
- Approve issue scope before Codex starts implementing
- Run local tests before merging
- Decide all tradeoffs (performance vs. correctness, speed vs. safety)
- Approve any change to live/shadow trading mode
- Merge PRs

**Does not:**
- Ask two AIs to edit the same file in the same session
- Skip issue creation for changes that touch PnL, risk, or execution logic

---

## Standard Task Flow

```
1. Human or Claude writes Issue (bug_report / ai_task template)
2. Claude reads AI_HANDOFF.md + issue → outputs Plan
3. Human approves scope
4. Codex reads Plan + issue → implements on feature branch
5. Codex runs tests → updates AI_HANDOFF.md
6. Claude reviews diff
7. Human merges
8. AI_HANDOFF.md updated (Next Steps, Recent Changes, Known Bugs)
```

---

## Session Start Checklist

Every AI session (Claude or Codex) must begin by reading:

1. `docs/AI_HANDOFF.md` — current state, do-not-touch list, next steps
2. `docs/ai_collaboration.md` — governance contract
3. The specific issue or task being addressed
4. Any PR diff already in progress

---

## Documentation Authority Rules

AI agents must apply `docs/DOC_LIFECYCLE.md` when reading or changing Markdown files.

### Source of Truth

Only documents with one of these statuses may be used as implementation authority:

- `status: current`
- `status: accepted`

Documents with these statuses are context only and must not drive implementation:

- `status: draft`
- `status: proposed`
- `status: deprecated`
- `status: archived`

If a Markdown file has no lifecycle metadata, treat it as `draft` until reviewed.

### Authority Order

When documents conflict, use this order:

1. Current user instruction and approved issue scope.
2. `research/strategy_synthesis.md` for strategy assumptions.
3. `docs/DOC_LIFECYCLE.md`, `docs/AI_WORKFLOW.md`, and `docs/ai_collaboration.md` for governance.
4. Accepted ADRs in `docs/ADR/`.
5. Current architecture, runbook, and parity docs.
6. `docs/AI_HANDOFF.md` for current state and next actions.
7. Draft, proposed, deprecated, archived, plan, and review docs only as historical context.

### Lifecycle Rules

- ADRs are not deleted. Superseded ADRs must be marked with a replacement in status text and metadata when practical.
- Completed plans in `docs/plans/` must be consolidated into durable docs or moved to `docs/archive/`.
- Completed reviews in `docs/reviews/` may be retained briefly while findings are active, then archived.
- `docs/AI_HANDOFF.md` must contain current state only. Completed historical detail should be moved, archived, or removed.
- New Markdown files should include lifecycle metadata before merge.

---

## Claude Plan Format

When producing a plan, Claude outputs:

```markdown
## Diagnosis
Which layer the problem is in and why.

## Proposed Fix
Specific change direction (not code, unless trivial).

## Files to Change
Exhaustive list. Everything not listed here is out of scope.

## Files NOT to Touch
Explicit out-of-scope list.

## Risks
What existing behavior could break.

## Test Plan
Exact commands to run. If tests don't exist, include writing them.

## Acceptance Criteria
- [ ] Concrete, binary conditions for merge
```

---

## Codex Task Format (hand this to Codex)

```text
Task: <one sentence>
Plan source: docs/AI_HANDOFF.md + <issue link>
Strategy/spec source: research/strategy_synthesis.md (if relevant)

PERMITTED FILES (only edit these):
- <file>
- <file>

FORBIDDEN (do not touch):
- src/okx_quant/strategies/
- src/okx_quant/risk/
- src/okx_quant/portfolio/
- <any other protected area>

SCOPE LIMIT:
Fix only the issue described. Do not refactor adjacent code, rename variables,
reorganize imports, or improve error messages unless they are the direct cause of the bug.

REQUIRED ON COMPLETION:
- List changed files
- Run: <test command>
- Update docs/AI_HANDOFF.md (Recent Changes, Known Bugs if resolved, Next Steps)
- Commit with AI-Origin trailer (see commit format below)

ACCEPTANCE CRITERIA:
- [ ] <criterion 1>
- [ ] <criterion 2>
```

---

## Commit Format

Every AI-assisted commit must include these trailers:

```
<type>(<scope>): <summary>

<body: what changed and why>

AI-Origin: Codex | Claude | Human | Mixed
AI-Role: Planning | Implementation | Review | Debugging
Reviewer: Claude | Human | None
Human-Reviewed: yes | no
Issue: #<number>
Tested:
  - <command and result>
```

Example:

```
fix(execution): correct ct_val multiplier in SWAP unrealized PnL

SWAP unrealized PnL was missing the ct_val factor, causing a 100x
overstatement for BTC-USDT-SWAP (ct_val=0.01).

AI-Origin: Codex
AI-Role: Implementation
Reviewer: Claude
Human-Reviewed: yes
Issue: #12
Tested:
  - pytest tests/unit/test_pnl_accounting.py -v — PASSED
```

---

## Branch Naming

| Purpose | Pattern |
|---|---|
| Claude research/plan | `claude/plan-<description>` |
| Claude review notes | `claude/review-<description>` |
| Codex implementation | `codex/impl-<description>` |
| Codex bug fix | `codex/fix-<description>` |
| Human hotfix | `hotfix/human-<description>` |
| Governance docs | `docs/human-<description>` or `docs/claude-<description>` |

---

## Prohibited Actions

These require explicit written user approval before proceeding:

- Any change to `src/okx_quant/strategies/`, `risk/`, `portfolio/`, `execution/broker.py`
- Changing `config/risk.yaml` limits
- Switching `config/settings.yaml` mode to `live` or `shadow`
- Modifying the replay engine's position ledger or PnL accounting
- Adding or removing columns from the backtest result schema
- Refactoring without a dedicated refactor issue
- Force-pushing to `main`

---

## AI Attribution Table

Track in each PR description:

| Role | Who |
|---|---|
| Planning | Claude / Human |
| Implementation | Codex / Claude / Human |
| Review | Claude / Human |
| Human-confirmed | Yes / No |
