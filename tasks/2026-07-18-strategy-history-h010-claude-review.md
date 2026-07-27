---
status: current
type: review
owner: claude
created: 2026-07-18
last_reviewed: 2026-07-18
expires: none
superseded_by: null
---

# Claude Review 2026-07-18: Strategy-History A/B/C + H-010 Stage-1/E-057

Protocol: `docs/REVIEW_QUESTIONS.md` + `docs/CRITIQUE_PROTOCOL.md` +
`docs/INVARIANTS.md`, executed via two independent review agents; verdicts
are Claude's. Scope: commits `497c7b7..3b0a975` (A/B/C portion) plus the
uncommitted 2026-07-18 H-010/E-057 working-tree delivery.

## Verdict 1 — Strategy-History doc + funnel v2/v3 + Ledger detail

**APPROVE-WITH-FINDINGS (no blockers).** Acceptance criteria met in
substance: all 22 hypothesis sections present; 9 spot-checked (incl. H-002,
H-009, H-014, H-021) digit-exact vs ledger/registry; the single annualized
value (H-002) verified against the live artifact; unrecorded metrics are
`n/a`; committed ledger diffs are EMPTY (read-only respected); funnel v1
fields preserved, per-family source/hypothesis/experiments added; Ledger
view degrades v1 JSON to a regeneration hint; no innerHTML (XSS clean);
no new backend route; `tests/unit/test_pipeline_funnel_report.py` 4 passed;
`node --check` passes on all three touched frontend files.

Fixes requested (minor, Codex, no re-review needed beyond diff check):

- A1. Add `frontend/research_funnel.json` to `.gitignore` (ground rule:
  generated JSON never committed; an untracked copy sits in the tree).
- A2. Extend the `frontend-check` Makefile target to cover
  `frontend/view-ledger.js` (criterion currently vacuous for the new file).
- A3. `run_pipeline_funnel_report.py:137-140`: artifacts missing
  `hypothesis_id`/`family_id` are silently skipped — record them in
  `stage2_artifact_errors` instead of dropping.

Accepted deviations: schema_version=3 (v2 fields + user-authorized
`stage2_artifact_errors`, frontend guards `>=2`); minimal `frontend/app.js`
nav wiring (plan premise "nav exists" was false); allow-list via
`config/workstreams.yaml` links with a guarding 404 test. Codex's two
questions: H-009 chronology — keep the honest disclosure, do NOT normalize;
H-014 branch wording — current branch-specific wording is correct.

## Verdict 2 — H-010 Stage-1/E-057 (uncommitted)

**APPROVE-WITH-FINDINGS: the recorded outcome stands; path repair required
before any reuse.** E-057 stage2_fail → H-010 `shelved` (Stage-2 shelf/data
gap, NOT a Stage-3 refutation) is honest and fail-closed: 0 trials, K 0/2,
registry math consistent; authorization scope respected (Stage-3 correctly
not built); no lookahead found (close-t signal, open-t+1 fill, no ffill,
gaps fail closed); funding sign correct; reads only ADR-0014
`canonical_candles_by_source` with dual-source HAVING clause; artifact
SHA-256s recomputed and match; scoped tests `18 passed`; Change Manifest
covers the R3.4/F47/I48 additions.

Required fixes BEFORE any F-XVENUE-LEADLAG reprobe or Stage-2 path reuse
(blocking for reuse, not for E-057's recorded outcome):

- B1 (major). Distinctness gate structurally unpassable: 91-day candidate
  window vs `MIN_COMMON_DAYS=365` and references starting 2022+ → PASS is
  unreachable by construction; contract defect (task file :127-128). Amend
  the contract ex-ante for any future round AND reword registry/ledger
  notes so a structural impossibility is not presented as a data-conditional
  measurement (R6.3/R7.4).
- B2 (major). Orchestrator path `_run_xvenue_probe`
  (`pipeline_stage2_registry.py:1141-1146`) applies H-010 funding/cost/
  distinctness checks only when `calibration_evidence` is present, and the
  orchestrator never sets it — a reprobe would silently bypass the frozen-
  evidence rule and I48 census. Make this path fail closed like
  `run_data_probe:1196-1203`, with a guarding test.
- B3 (minor). Mark the Stage-1 spec's `0.8682` power floor superseded by the
  implemented `0.8838` (disclosed, strictly tightening).
- B4 (minor). Declare the funding-settlement boundary convention (entry
  inclusive / exit exclusive, `bisect_left`) in the probe docstring or
  DOMAIN_RULES note; zero numeric effect on E-057.
- B5 (process). Commit the tree as separate commits per delivery (H-010/
  E-057 vs sibling OKX 2020-2023 promotion task); stray
  `results/ui_funding_carry_2a3cdd23_execution_comparison.json` is not part
  of either handoff — user to confirm keep/delete.

## Ledger-integrity note

The uncommitted H-010 ledger row is a rewrite-in-place (placeholder text →
full falsifiable statement; E-035 narrative moved). Accepted: one-row-per-
hypothesis is the ledger design, experiment list and 0-trial accounting
preserved, no history falsification. E-057 was registered with ex-ante
fields, but ex-ante ORDERING is unprovable from git because everything is
uncommitted — a process reason to commit registration before running
future experiments.

## Follow-up verification 2026-07-21 (five-commit delivery 5982a7f..552188a)

Two fresh-context verifiers; full unit suite 921 passed / 1 skipped; ledger
consistency, doc impact/metadata/links all PASS. Answers to the four review
questions:

1. **B1 — PARTIAL.** Registry/ledger rewording and R6.6/I49 are correct and
   honest; but the distinctness CODE is byte-identical (MIN_COMMON_DAYS=365,
   91-day anchor, no pre-execution feasibility refusal). The ex-ante rule is
   documentation-only. H-010 Stage-2 path reuse therefore REMAINS PROHIBITED
   until a code-level guard (declare reference ranges, refuse impossible
   intersections before probe) ships with a test. Tracked as open item B1-code.
2. **B2 — YES, closed.** Both `run_data_probe` and the
   `STAGE2_PROBES["F-XVENUE-LEADLAG"]` registry path raise explicit
   ValueError without frozen calibration_evidence, before probe_xvenue runs;
   guarding test exercises the previously-bypassable path; no third caller
   exists; results/** untouched by the fix commit.
3. **E-057 honesty — YES.** stage2_fail / shelved / promotion-blocked and all
   recorded numbers (1.3636 vs 8.0 bps, 7,376 episodes, no OKX funding
   substitution) preserved verbatim; K=0/2 unchanged; artifact SHA-256
   recomputed byte-identical; git history shows only 5982a7f touching them.
4. **Commit boundaries — YES with one flag.** 4/5 commits clean;
   315b041 (Research Ops) also touches
   `src/okx_quant/execution/deribit_shadow/runner.py` — inspected: a pure
   cross-process file lock around run_cycle (msvcrt/fcntl), no PnL/sign/
   accounting change. This is a do-not-touch-path edit requiring explicit
   user ratification (or relocation to its own authorized commit record).
   Stray results JSON remains untracked and in no commit. OKX 2020-2023
   promotion DB-verified: 3,396,960 rows/leg continuous 2020-01-01→
   2026-06-16, resolved per-source counts unchanged.

**Verdict: APPROVE-WITH-FIXES.** Open items: B1-code guard (blocks any
F-XVENUE-LEADLAG reprobe); user ratification of the runner.py lock touch;
A/B/C fixes and B2-B4 are closed.

**User rulings 2026-07-21:** (1) the `315b041` runner.py cross-process lock
touch is RATIFIED (non-substantive concurrency safety; execution/ path edit
approved retroactively for that commit only). (2) The B1-code guard is
AUTHORIZED now: `tasks/2026-07-21-b1-distinctness-guard-codex-tasks.md`.
The reprobe prohibition stands until that guard ships and passes review.

**B1-guard delivery review 2026-07-21 (fresh verifier): APPROVE-WITH-FIXES.**
Functional criteria 1-7 all PASS (E-057 config reproduces pre-execution
refusal; feasible config proceeds; missing declaration fails closed; both
entry paths guarded before artifact writes; E-057 hashes byte-identical;
MIN_COMMON_DAYS=365 unchanged; full suite 927 passed / 1 skipped). Two
Claude rulings on Codex's questions:

- **Whitelist vs docs-impact --strict: NOT accepted.** Hard governance
  checks are never overridden by a task's PERMITTED FILES list; the manifest
  omission was a defect in the task spec, not license to skip A5. Whitelist
  officially expanded (FX2): add Change Manifest
  `docs/change_manifests/2026-07-21-b1-distinctness-guard.md` and a
  GOLDEN_CASES entry ("E-057 config must be refused before probe"), then
  `check_doc_impact.py --strict` must PASS.
- **Joint/overall intersection gating: NOT confirmed — demote (FX1).** The
  measurement (`build_distinctness_check`) evaluates each gating reference
  independently; joint-intersection gating exceeds the measurement and can
  mislabel per-pair-feasible configs as structural defects (verifier
  counterexample on record). Gate on per-reference achievable days only;
  keep `overall_common_days` as an advisory reported field. Add the
  per-pair-feasible/joint-zero test case.

Reprobe prohibition lifts after FX1+FX2 land and pass the final diff check;
lifting the prohibition is still not reprobe authorization (separate user
approval + ex-ante rationale + K accounting required).

**FINAL 2026-07-21 — commit `f38b6c0`: APPROVE, B1 CLOSED.** Claude
directly verified: refusal predicate gates on per-reference
achievable_common_days only (xvenue_leadlag_probe.py:223-226);
overall_common_days is advisory (computed, reported, non-gating); the
per-reference-feasible/joint-zero counterexample test passes (24/24);
Change Manifest `2026-07-21-b1-distinctness-guard.md` and GOLDEN_CASES
G-006 added; `check_doc_impact.py --strict` PASS; E-057
stage2_feasibility.json SHA-256 recomputed byte-identical
(5E167003...1000F). The H-010 Stage-2 reprobe PROHIBITION IS LIFTED.
Reprobe itself remains unauthorized until the user approves a new round
with ex-ante rationale and K accounting.

## UNCONFIRMED (inherited from agents)

- No browser eyeball of the expanded Ledger row (code-read + Codex's
  Playwright report only). 13/22 history sections not digit-checked.
- Full-suite "910 passed, 1 skipped" not independently re-run.
