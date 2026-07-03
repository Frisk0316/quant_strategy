---
status: current
type: reference
owner: ai
created: 2026-07-03
last_reviewed: 2026-07-03
expires: none
superseded_by: null
---

# Task Dispatch Templates

Fill-in prompts for dispatching subagents (and for handing work to Codex).
Every dispatch needs the triad from `docs/ai/MODEL_DISPATCH.md` §3: goal+why,
acceptance criteria, report format. Copy the template, fill every `<...>`,
delete nothing. If you cannot fill a slot, you are not ready to dispatch.

Model/effort defaults come from the table in `docs/ai/MODEL_DISPATCH.md` §2.

## 0. Session openers (what the USER pastes to start a session)

Claude Code (CLAUDE.md auto-loads; keep the opener minimal — do not paste
background the repo already records, point at files instead):

```text
任務：<one sentence>
Task type（CLAUDE.md 路由表的哪一行）: <row, e.g. Review a diff/PR>
PERMITTED FILES: <list, or "read-only / 先給計畫不動手">
特殊驗收條件（路由表與 JUDGMENT_RUBRICS §2 之外的）: <criteria, or none>
```

Codex (loads AGENTS.md, not CLAUDE.md — hand it a filled §2 Implementation
template):

```text
Read AGENTS.md first, then execute:
<filled Implementation template from §2 below>
Also read docs/ai/JUDGMENT_RUBRICS.md §2 (definition of done) and §5
(quality floor) before reporting completion.
```

## 1. Search / locate (agent: scout, model: haiku)

```text
GOAL: Find <what> so that <why the commander needs it>.
SEARCH IN: <paths/globs>. Do not search outside these.
QUESTIONS (answer each, "NOT FOUND" is a valid answer):
1. <question>
2. <question>
ACCEPTANCE: every question answered with file:line or NOT FOUND.
REPORT: ≤40 lines; conclusions + file:line only; no file dumps;
end with what you did NOT search.
```

## 2. Implementation (agent: general-purpose, model: sonnet; or handoff to Codex)

```text
Task: <one sentence>
Strategy/spec source: <file, e.g. research/strategy_synthesis.md §X>
Required behavior: <exact behavior, with an example input→output>

PERMITTED FILES (only edit these):
- <file>

FORBIDDEN (do not touch):
- src/okx_quant/strategies/
- src/okx_quant/signals/
- src/okx_quant/risk/
- src/okx_quant/portfolio/
- src/okx_quant/execution/
- config/risk.yaml
- <add task-specific>

SCOPE LIMIT: fix only what is described; no adjacent refactoring.
(A FORBIDDEN bullet may be removed ONLY if the user explicitly authorized
editing that path this session — quote the authorization inline.)

REQUIRED ON COMPLETION:
- List changed files (git diff --stat).
- Run: <exact test command> and paste the output tail.
- Update docs per the AGENTS.md docs-update matrix (or state "n/a: <why>").
- Commit with AI-Origin trailer only if committing was requested.

ACCEPTANCE CRITERIA (binary):
- [ ] <criterion>
- [ ] <criterion>
- [ ] Diff contains only permitted files.

REPORT: changed files, test output tail, assumptions made, anything
UNCONFIRMED or skipped.
```

## 3. Refactor (agent: general-purpose, model: sonnet)

```text
GOAL: Refactor <what> to <goal> WITHOUT behavior change.
BASELINE FIRST: run <test command>; paste the passing tail before touching
anything. If baseline is red, STOP and report — do not refactor on red.
PERMITTED FILES: <list>
FORBIDDEN: <list — always include trading-core paths>
CONSTRAINTS: no public API/signature changes unless listed here: <list>.
No new dependencies.
ACCEPTANCE:
- [ ] Same test command passes after, output pasted.
- [ ] git diff shows only permitted files.
- [ ] No TODO/FIXME introduced.
REPORT: before/after test tails, diff stat, any behavior ambiguity found
(report it, do not resolve it silently).
```

## 4. Research (agent: general-purpose, model: sonnet; claude-code-guide for Claude Code topics)

```text
GOAL: Answer <question> to inform <decision>.
SOURCES: prefer <official docs / repo files>; for web sources record URL
and retrieval date. Distinguish official vs third-party.
ACCEPTANCE: each sub-question answered as CONFIRMED (with source) or
UNCONFIRMED. Guessing marked as guessing. An UNCONFIRMED answer is
acceptable; a fabricated one is not.
REPORT: numbered findings, each: claim → CONFIRMED/UNCONFIRMED → source.
If >40 lines, write to <path> and return the path + 5-line summary.
```

## 5. Review (main conversation on best available model; verifier for mechanical checks)

```text
GOAL: Review <diff/PR> against <task/spec source>.
READ FIRST: docs/REVIEW_QUESTIONS.md, docs/CRITIQUE_PROTOCOL.md,
docs/INVARIANTS.md; the task's permitted-files list.

MUST CATCH (this repo's expensive error classes):
- Scope violations (files outside the permitted list).
- Strategy drift / research assumptions changed without updating the
  source of truth.
- PnL accounting errors, especially missing ct_val on SWAP.
- Funding cashflow sign errors.
- Lookahead bias, leakage, hidden trial-count drift.
- Orphan positions and partial-fill state regressions.
- API schema breaks.
- Missing tests, docs, Change Manifest, or DOC_IMPACT_MATRIX rows on a
  business-rule change; missing ADR on a major rule change.
- Invariant regressions (docs/INVARIANTS.md); new failure modes not added
  to docs/FAILURE_MODES.md.
- Live/shadow/demo readiness claims without gates + user approval.

ACCEPTANCE: every MUST CATCH item explicitly marked found/clear/n-a.
VERDICT: approve / request-changes, with file:line per finding.
REPORT: findings ranked by severity; each finding = one sentence defect +
concrete failure scenario. No style nitpicks unless they hide a bug.
```
