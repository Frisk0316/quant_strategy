---
name: AI Task
about: Structured task handed to Codex for implementation (requires Claude plan first)
labels: ai-task, codex
---

## Task Summary

<!-- One sentence: what should be implemented or fixed. -->

## Claude Plan Reference

<!-- Link to the Claude plan comment, or paste the diagnosis/proposed fix inline. -->

**Diagnosis:**

**Proposed Fix:**

## Strategy / Spec Source

<!-- Which document defines the expected behavior? -->

- [ ] `research/strategy_synthesis.md`
- [ ] `docs/backtest_live_parity_plan.md`
- [ ] `config/strategies.yaml`
- [ ] Other: <!-- specify -->

---

## PERMITTED FILES — Codex may only edit these

<!--
List every file Codex is allowed to touch.
If a file is not listed here, it must not be changed.
-->

-
-

## FORBIDDEN — Do not touch under any circumstances

- `src/okx_quant/strategies/` _(unless this task explicitly targets a strategy bug)_
- `src/okx_quant/risk/`
- `src/okx_quant/portfolio/` _(unless permitted above)_
- `config/risk.yaml`
- `docs/ai_collaboration.md`
- <!-- add others -->

## SCOPE LIMIT

Do not refactor adjacent code, rename variables, reorganize imports, or improve
error messages unless they are the direct cause of the bug or stated in this task.
One issue → one PR. Stop when acceptance criteria are met.

---

## Required Behavior

<!-- Describe the exact expected behavior after the fix, in concrete terms. Include edge cases. -->

## Required Tests

<!-- Tests Codex must write or update. Be specific. -->

- File: `tests/unit/<filename>.py`
- Scenario: <!-- describe what is being tested -->
- Expected assertion: <!-- e.g., assert pnl == 2.5 -->

## Acceptance Criteria

All must be ✅ before the PR is opened:

- [ ] <!-- Criterion 1 -->
- [ ] <!-- Criterion 2 -->
- [ ] Regression test added (file and test name listed above)
- [ ] `pytest tests/unit/ -v` passes
- [ ] `ruff check src/ tests/` — no new errors
- [ ] Commit includes `AI-Origin: Codex` trailer
- [ ] `docs/AI_HANDOFF.md` updated (Recent Changes section)

## Validation Commands

```bash
# Run after implementation:
pytest tests/unit/ -v
ruff check src/ tests/

# If replay / execution path is affected:
python scripts/run_replay_backtest.py --strategy <name> --start 2024-01-01 --end 2024-01-03 --bar 1H
```

## Risk Concerns

<!-- Claude's assessment: what could break if this is implemented incorrectly? -->

## Do Not Do

<!-- Explicit prohibitions beyond the scope limit above. -->

- Do not change the backtest result schema
- Do not alter strategy parameters or entry/exit logic
- <!-- add as needed -->

## Claude Review Checklist

For Claude to verify before marking the PR ready to merge:

- [ ] Scope: did Codex touch only permitted files?
- [ ] PnL: is `ct_val` applied correctly for SWAP instruments?
- [ ] Position state: are orphan positions possible after this change?
- [ ] API schema: did any response field get renamed, removed, or type-changed?
- [ ] Tests: does the test actually cover the bug or feature, not just pass trivially?
- [ ] Handoff: is `docs/AI_HANDOFF.md` updated?
- [ ] Commit: does it have `AI-Origin:` trailer and issue reference?

## Handoff from Claude to Codex

```
Task:
Strategy/spec source:
Required behavior:
Files likely affected:
Validation required:
Risk concerns:
Acceptance criteria:
```
