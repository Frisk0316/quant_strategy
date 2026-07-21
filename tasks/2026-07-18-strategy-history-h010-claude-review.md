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

## UNCONFIRMED (inherited from agents)

- No browser eyeball of the expanded Ledger row (code-read + Codex's
  Playwright report only). 13/22 history sections not digit-checked.
- Full-suite "910 passed, 1 skipped" not independently re-run.
