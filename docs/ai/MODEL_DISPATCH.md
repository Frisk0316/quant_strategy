---
status: current
type: reference
owner: ai
created: 2026-07-03
last_reviewed: 2026-07-03
expires: none
superseded_by: null
---

# Model Dispatch Playbook

How to spend model budget in this repo. Written 2026-07-03 for sessions
running on any Claude model, including small ones. Rules are mechanical on
purpose — follow them literally.

## 0. Verified facts (do not fill these from memory)

Verified 2026-07-03 against the live harness and
<https://code.claude.com/docs/en/sub-agents.md> /
<https://code.claude.com/docs/en/model-config.md>:

- Agent tool `model` parameter accepts: `haiku`, `sonnet`, `opus`, `fable`.
- Subagent definitions in `.claude/agents/*.md` support frontmatter
  `model:` (`sonnet` | `opus` | `haiku` | `fable` | full model ID |
  `inherit`, default `inherit`) and `effort:` (`low` | `medium` | `high` |
  `xhigh` | `max`; available levels depend on the model). There is no
  per-call effort parameter on the Agent tool — effort is set in the agent
  definition file.
- Model IDs at time of writing: `claude-haiku-4-5-20251001`,
  `claude-sonnet-5`, `claude-opus-4-8`, `claude-fable-5`.
- `/model` aliases at time of writing: `default`, `best`, `fable`,
  `sonnet`, `opus`, `haiku`, `sonnet[1m]`, `opus[1m]`, `opusplan`.
- `fable` availability is exceptional, not assumed. Before referencing any
  model name, check the Agent tool description in YOUR current session; if
  a name is absent there, it does not exist for you. Never invent model
  names or parameters from training memory.
- UNCONFIRMED: whether requests safety-rerouted from Fable to Opus consume
  Fable-tier quota. Official docs describe the reroute mechanism only.
  Third-party articles claim rerouted requests bill as Opus and that Fable
  counts ~2x against weekly limits — unverified; if it matters, test on the
  usage dashboard.

## 1. The commander does not do the labor

The commander is the main conversation — the context that dispatches
subagents and talks to the user. It is the most expensive context in the
system. It holds
the plan, makes judgment calls, and integrates conclusions. It does NOT:

- read more than ~300 lines of file content for exploration,
- run more than 5 Grep/Glob rounds hunting for something,
- batch-edit more than 5 files with a known pattern,
- do web research,
- verify its own work.

Hitting any of those thresholds = dispatch a subagent instead. If a subagent
would need context you'd have to paste at length (>150 lines), pointing it
at file paths is fine — subagents can read.

## 2. Default assignment table

| Job | Agent type | Model | Why |
| --- | --- | --- | --- |
| Locate files/symbols, bulk read, repo scan | `scout` (or built-in `Explore`) | haiku | pattern matching, no judgment |
| Summarize/extract from known files | `scout` | haiku | mechanical |
| Batch-apply an already-solved pattern | `general-purpose` | haiku (sonnet if edits touch logic) | pattern established elsewhere |
| Implement from a written spec with acceptance criteria | `general-purpose` | sonnet | judgment bounded by the spec |
| Web research, doc verification | `general-purpose` (Claude Code questions: `claude-code-guide`) | sonnet | needs source evaluation |
| Verify a change (read-back, run tests) | `verifier` | sonnet | fresh context, cheap, mechanical checklist |
| Design, tricky debugging, PnL/funding/risk logic | main conversation, or `Plan` agent | opus (or best available) | this is where quality drops with cheap models |
| Review of trading-core-adjacent diffs | main conversation | best available | error classes are subtle (ct_val, funding signs, lookahead) |

`scout` and `verifier` are defined in `.claude/agents/` with model+effort
pinned. If they are missing, use `Explore`/`general-purpose` with an
explicit `model` parameter.

## 3. Every dispatch prompt contains three things

1. **Goal and why** — one sentence of intent, so the agent can resolve
   ambiguity in the right direction.
2. **Acceptance criteria** — binary checks the agent can self-test before
   reporting.
3. **Report format** — what to return (see §4).

Fill-in templates: `docs/ai/TASK_TEMPLATES.md`. A dispatch missing any of
the three is not sent.

## 4. Report contract (for subagents)

- Return conclusions and `file:line` references, not file dumps.
- Any artifact >30 lines (report, diff summary, extracted data) is written
  to a file (scratchpad for throwaway, `tasks/` or `docs/` for durable) and
  the report returns the path plus a ≤5-line summary.
- Explicitly list: what was checked, what was NOT checked, and anything
  UNCONFIRMED. Silence about coverage counts as a defect.
- The commander relays subagent conclusions to the user — the user never
  sees raw subagent output.

## 5. Escalation and downgrade ladder

- haiku fails a task once → resend to sonnet.
- sonnet fails the SAME subtask twice → send to opus (or best available)
  WITH the full failure trail: both attempts, error output, current
  hypothesis. Escalating without the trail wastes the better model.
- Once the better model solves one instance, extract the pattern and send
  remaining instances back down to haiku/sonnet as batch work.
- Max 2 retry rounds per approach on the same problem. After that: change
  the approach or ask the user — see `docs/ai/JUDGMENT_RUBRICS.md` §4.
- "Fails" means: acceptance criteria not met, or the verifier rejects the
  result. Not "the report sounded unsure".

## 6. Verification is never self-verification

- Every nontrivial change is checked by a FRESH-context agent (`verifier`),
  not by whoever wrote it. The writer's context is contaminated by its own
  intentions. Nontrivial = touches code, config, or any file outside the
  "edit freely" list in `docs/ai/MAINTENANCE.md`.
- Files: verifier reads the actual file back and checks it against the
  acceptance criteria (not against the writer's summary).
- Code: verifier runs the exact test command from the verification matrix
  in `AGENTS.md` and pastes the output tail. No pasted output = not
  verified.
- High-stakes judgment calls (anything touching PnL math, gates, data
  provenance): get a second opinion — dispatch the same question to a
  second agent with no access to the first answer, then compare. If they
  disagree, the commander decides and records why in the handoff.
