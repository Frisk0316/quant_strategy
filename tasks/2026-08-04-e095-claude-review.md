---
status: current
type: task
owner: claude
created: 2026-08-04
last_reviewed: 2026-08-04
expires: none
superseded_by: null
---

# Claude review — H-038/E-095 rerun (2026-08-04)

Reviewed the uncommitted working-tree delivery against
`tasks/2026-08-04-h038-e095-rerun-codex-tasks.md`. Protocol:
`docs/CRITIQUE_PROTOCOL.md`.

**Verdict: APPROVE. Codex may commit. No blockers, no majors.**

## Acceptance criteria — all verified

- Probe diff contains exactly the authorized delta: named
  `MIN_MEMBER_DAY_COVERAGE = 0.95`, artifact provenance dict (taker-flow
  precedent / I11 / user ruling), new `h038_stage2_e095` batch id. No other
  probe logic changed; `src/okx_quant/**` diff is empty.
- Artifact `results/h038_stage2_e095/stage2_feasibility.json` SHA-256
  `40c8158...` matches `sha256.json` and both ledger rows. Data check PASSes
  at 17,271/17,272 (0.999942) with the provenance field present.
- E-094 directory byte-identical: both recorded SHA-256 values re-verified.
- Breadth 5.743875 measured from the actual position sequence over 898 daily
  observations (formula + inputs in the artifact) — the ADR-0013 requirement
  E-091..E-093 established. Frozen E-014 params SHA-bound and unchanged;
  n_trials=72 registry-cumulative; no grid, no Stage 3.
- Ordered fail-closed is faithful: distinctness FAIL
  ("UNCONFIRMED: E-014 retains no dated return series"), cost/power
  NOT_EVALUATED with stop_point recorded.
- Ledgers record E-095 and K 2/2 terminal exactly as pre-registered. F76
  added; DATA_FLOW/FEATURE_MAP rows updated (outside the task's permitted
  list but required by AGENTS.md's docs-update matrix — accepted).
- Checks: probe tests 8 passed; full unit 1144 passed / 1 skipped; Ruff,
  ledger consistency (47/96/39), strict doc impact all pass.

## NOTE (non-blocking) — the family closed without a statistical measurement

F-S5's three stops are now: E-014 (data universe), E-094 (unprovenanced gate,
ruled contract error), E-095 (reference artifact lacks the series the
distinctness contract requires). The mechanism's returns were finally
produced this time but never statistically evaluated. The distinctness
impasse was knowable ex ante — E-014's `summary.json` visibly has no dated
return series, and the E-025 dated regeneration (`094742e`) was the known
remedy — so this is a defect in the task contract I wrote, not in Codex's
execution.

**Recommendation: let the terminal record stand.** The E-095 authorization
pre-committed "K 2/2 terminal regardless of outcome, no E-096" precisely so
this family would stop consuming attention; overturning a second consecutive
pre-registration would make every future "terminal" clause negotiable, which
is worth more than one family's unmeasured mechanism. The retained artifact
(returns, breadth, n_obs) keeps a future user-authorized audit possible
without any new run. Lesson recorded in `docs/ai/LESSONS.md`: verify the
reference artifact contains the series a pre-registered check needs before
sealing the contract.
