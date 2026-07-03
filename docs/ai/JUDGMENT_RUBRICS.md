---
status: current
type: reference
owner: ai
created: 2026-07-03
last_reviewed: 2026-07-03
expires: none
superseded_by: null
---

# Judgment Rubrics

High-level judgment converted into checklists a small model can execute.
Each rubric: binary criteria, one positive example (right call), one
negative example (wrong call). Examples are from this repo's actual error
classes. When a rubric and the user's explicit instruction conflict, the
user wins; note the conflict in the handoff.

## 1. When to escalate the model

Escalate (per the ladder in `docs/ai/MODEL_DISPATCH.md` §5) when ANY holds:

- [ ] The task changes or interprets money math: PnL, fees, funding
      cashflows, `ct_val`, sizing, liquidation.
- [ ] The current model exhausted its attempt budget on the same
      acceptance criterion (haiku: one failed attempt; sonnet: two — exact
      counts in `docs/ai/MODEL_DISPATCH.md` §5).
- [ ] The task requires choosing between designs with no spec to bound it.
- [ ] Correctness depends on an invariant spanning >2 files (e.g. position
      state machine across engine + strategy + report).

Stay cheap when ALL hold: the pattern is already solved somewhere you can
point at; acceptance criteria are binary; a test exists that fails if the
work is wrong.

- **Right call:** opus fixed a `ct_val` omission in one backtest file; the
  remaining six files with the identical pattern go to haiku as a batch,
  each verified by the existing unit test.
- **Wrong call:** sonnet is on attempt three of a funding-PnL mismatch and
  each attempt flips a different sign until the number looks right.
  Sign-flipping-until-it-matches is fitting to the answer, not fixing the
  bug — attempt two was the escalation point, with both failure trails.

## 2. When work is actually done

Done = ALL of:

- [ ] Every acceptance criterion has evidence: pasted command output tail
      or a `file:line` a reader can check.
- [ ] The verification-matrix command for this change type (`AGENTS.md`)
      ran; skipped checks are named with the reason ("no DB in env"), not
      omitted.
- [ ] `git diff --stat` shows ONLY permitted files.
- [ ] Docs-update-matrix rows (`AGENTS.md`) checked; touched or explicitly
      "n/a".
- [ ] A fresh-context verifier confirmed (required for any nontrivial
      change — defined in `docs/ai/MODEL_DISPATCH.md` §6).

- **Right call:** "T3 done: 14 tests pass (output below), diff touches only
  `backtesting/turtle_backtest.py` + its test, UI_MAP row n/a because no
  frontend change."
- **Wrong call:** "Implemented the fix; tests should pass now." — "should"
  means not run. This is reported as NOT done.

## 3. When to stop and ask the user

Ask FIRST (do not proceed) when ANY holds:

- [ ] The action is destructive or hard to reverse: deleting/overwriting
      backtest artifacts, force-push, rewriting history, dropping data.
- [ ] It changes gates, `config/risk.yaml`, live/shadow/demo posture, or
      anything in the do-not-touch list.
- [ ] Two truth sources disagree (e.g. `research/strategy_synthesis.md` vs
      implemented code) and the fix depends on which is right.
- [ ] The task as stated requires editing forbidden files.
- [ ] Completing it would silently expand scope beyond the permitted-files
      list.

Do NOT ask when: the action is reversible, in scope, and the answer is
derivable from repo files — derive it and proceed. Asking permission for
in-scope reversible work wastes a round-trip.

- **Right call:** spec says funding accrues on close, code accrues per
  funding event, both have tests pinning their behavior → stop, present
  both with `file:line`, ask which is truth.
- **Wrong call:** asking "shall I run the unit tests?" — running tests is
  reversible, in scope, and always allowed. Just run them.

## 4. Wrong-direction signals (change path, don't retry)

STOP the current approach when ANY holds:

- [ ] Two DIFFERENT fixes produced the same failure.
- [ ] Your fix works only if you also edit a forbidden or unrelated file.
- [ ] Each fix creates a new failure elsewhere (whack-a-mole).
- [ ] Your explanation of why the fix works keeps getting longer.
- [ ] You are editing the test/expected value to match output, without a
      spec source saying the expectation was wrong.

On STOP: write down (a) hypothesis so far, (b) evidence for/against,
(c) what was ruled out. Then re-read the failing case and form a hypothesis
at a DIFFERENT layer (data vs engine vs strategy vs report), using skill
`superpowers:systematic-debugging`. Retrying a variation of a stopped
approach counts against the 2-round retry budget.

- **Right call:** backtest equity off by ~0.02% only on SWAP symbols; two
  fee-side fixes failed → stop, check a different layer: funding cashflow
  timestamps. (Layer switch, not third fee tweak.)
- **Wrong call:** golden-case test fails by a small margin, so you widen
  the test tolerance. That deletes the alarm instead of the fire.

## 5. Quality floor — how to verify the minimum

- Claims need evidence. A statement about code behavior with no pasted
  output and no `file:line` is an opinion; label it as such ("unverified").
- Minimum command per change type = verification matrix in `AGENTS.md`.
  Below-matrix verification is only acceptable if the environment blocks
  it, and then it is reported as a limitation, not as a pass.
- File writes: verify by reading the file back (or verifier does), not by
  trusting the write succeeded.
- Placeholder/smoke output is not coverage: "0 tests collected", "skipped:
  no DB", or an empty result set is a FAIL-to-verify, never a pass.
- Numbers that must match (PnL totals, row counts, line counts): recompute
  from source once, independently, rather than reusing the number you
  wrote earlier.

- **Right call:** after editing `docs/ai/*.md`, run `make docs-check` and
  paste the tail, then have the verifier read the files back.
- **Wrong call:** treating `make backtest-smoke` printing a banner with
  zero cases executed as proof the backtest path works.
