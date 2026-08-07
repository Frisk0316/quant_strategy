---
status: current
type: review
owner: claude
created: 2026-08-07
last_reviewed: 2026-08-07
expires: none
superseded_by: null
---

# Claude review — ADR-0016 phase 3 (round runners)

Scope: uncommitted working-tree diff vs `e5b0f6a` — new
`backtesting/pipeline_round_runners.py` (226 lines) + tests (129),
`pipeline_orchestrator.py` (+72/−), `pipeline_round.py` (+33/−), test
updates, change-manifest/CHANGELOG/handoff/workstreams updates.
Task: `tasks/2026-08-07-adr0016-phase3-round-runners-codex-tasks.md`.

## Verdict: APPROVE-WITH-FINDINGS (no blockers)

Fresh-context verifier: 29/29 targeted tests pass, Ruff clean, doc
metadata + ledger consistency pass, forbidden paths untouched, Stage-2
probe modules (`pipeline_stage2_registry/feasibility/power_screen`) have
ZERO diff, both registries start empty with wildcard refusal
(`pipeline_round_runners.py:23,25,259`), and the stage2 state write
precedes the authorization halt (`pipeline_orchestrator.py:560` before
`:562`). Acceptance criteria all verified:

- T1 adapter maps pass/fail/error; unregistered family refused at
  construction; probe context is built only from manifest fields (test
  asserts a context-injected result-derived value never reaches the probe).
- T2 halt: stage2 pass → atomic checkpoint → `stage3_authorization_required`;
  re-run without authorization re-raises WITHOUT re-running stage2 (state
  proof); resume with an authorized per-candidate stage3 runner completes
  reconciliation. Runners can no longer return stage3 at all — tightened
  beyond the task's letter, correctly.
- T3 breadth recompute: window-filtered nonzero-position counts from the
  SHA-verified artifact must reproduce declared breadth to 1e-9 before the
  probe runs; mismatch refuses pre-probe (test asserts probe not called).
- T4: live queries now return in-window MIN/MAX; the mismatch test goes
  through `query_dataset_claim` with a mocked connection.
- T5: `REVIEWED_ROUND_RUNNERS`/`AUTHORIZED_STAGE3_ROUND_RUNNERS` empty,
  `ROUND_RUNNERS = build_round_runners(REVIEWED_ROUND_RUNNERS)` only.

## Findings

1. MINOR (recurring, now accepted as documented behavior) — live-path
   `dataset_range_mismatch` remains structurally unfireable: SQL bounds
   MIN/MAX inside the claimed window, so `min < start` / `max >= end`
   cannot occur through a real connection; live range confirmation is
   count-equality + non-emptiness. The mocked-conn test exercises the
   function's mapping code, satisfying the acceptance letter. Stop
   re-flagging this; if span completeness ever matters, add an explicit
   expected-span field to the claim schema in a future slice.
2. MINOR — the round halts at the FIRST Stage-2 pass; later candidates'
   Stage-2 does not run until that candidate's Stage-3 authorization
   arrives. Safe, honest, resume-correct; wastes wall-clock only in the
   historically rare multi-pass round (1 pass in 47 hypotheses). No change
   requested.
3. NIT — `BREADTH_FORMULAS` is an exact-string allow-list (two entries).
   Correct fail-closed design; consumers must use the canonical E-095
   string verbatim. The S-001 packet's formula paraphrase differs — the
   H-047 spec (written alongside this review) uses the canonical string.

## Checklist disposition

Scope: permitted files only (+2 standard handoff files). Money/risk: no
PnL/fee/funding/sizing/fill code — N/A. Data/evidence: no experiment,
trial, K, or `results/**` change. Contracts: round-runner contract change
(no stage3 from runners) is internal to the build-only round path; no API/
backtest schema change. Tests: all new behavior covered, including
resume-idempotence. Docs: change manifest + CHANGELOG updated; doc-impact
A5 WARN is advisory and FEATURE_MAP already owns the touched files.
Readiness: report correctly claims none.
