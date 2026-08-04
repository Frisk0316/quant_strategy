---
status: current
type: task
owner: claude
created: 2026-08-04
last_reviewed: 2026-08-04
expires: none
superseded_by: null
---

# Handoff: public status page + 2026-08-04 decision batch — 2026-08-04

Merged Context + Session handoff (CLAUDE.md session-end step 3).
**Goal:** plan a public GitHub Pages progress page, then execute the user's
five decisions.

## Implementation summary / diff scope / business-rule change / experiments

Planned and reviewed the public research-status page (Codex implemented it in
parallel), corrected two stale CURRENT_STATE claims, authorized H-038 and a
three-item WS-C subset as Codex task files, diagnosed the candidate funnel from
38 Stage-2 artifacts, and recorded that diagnosis as invariant I68. Delivery is
commits `0286bb7`, `dc1383d`, `e3e4393`, `3e7d26f`, all pushed. Claude touched
no `results/**`, strategy, signal, risk, portfolio, or execution file.
**No business-rule change** — nothing in PnL, fees, funding, sizing, fills, or
gates moved, so no Change Manifest; I68 only defines an already-undefined term
(R6.8/I53 "execution-ready") and its enforcement is REVIEW.
**Experiments:** none ran; no trial or K consumed.

## Decisions made (and why)

1. Orphan `public-status` branch of three files as the publish boundary, not
   `/docs` or Actions — content not on the branch cannot be served.
2. Scope is progress + shadow observability only (user choice); no live or paper
   performance exists and a leak-canary test blocks signal values.
3. Did not push `main`: `origin/main` already held PRs #9/#14/#16/#18, local
   `main` was three weeks stale, and AI_WORKFLOW assigns merges to the human.
4. WS-C limited to C3/C5/C10 — the order-correctness defects reachable from the
   already-exercised Demo path. The rest need a running engine to bite.
5. The funnel diagnosis became I68, not a LESSONS entry alone, because only
   DOMAIN_RULES/INVARIANTS bind.

## Rules in play (preserve verbatim)

- Breadth is derived from realized positions, never declared, and fails closed
  to 1 (I68; E-092/E-093 precedent).
- H-038 consumes F-S5 K 2/2 and is terminal regardless of outcome.
- WS-C authorization is per item; C1/C2/C4/C6/C7/C8/C9/C11 and F2 are NOT
  authorized. No live/shadow/demo readiness claim follows from any of this.

## Checks run

`pytest tests/unit/test_publish_public_status.py -q` 6 passed; real generation
emits no `dvol`/`ivp`/`vrp`/`rv`/`z`/`px`/`signal`/`legs`/`intent` key;
`index.html` has no external `http(s)` reference; `ruff`, `check_doc_metadata`
(2 pre-existing warnings), `check_feature_map_links` (293) and
`check_ledger_consistency` pass. NOT run: full unit suite, `verify-full`, DB or
browser checks.

## Open questions / unverified assumptions

- I68 enforcement is REVIEW; nothing mechanically blocks a candidate registered
  without the three numbers until ADR-0016 resumes.
- The sweep reads `stage2_feasibility.json` only, so candidates rejected before
  an artifact existed are not among the 38. Advisory `check_doc_impact` shows
  2 A2/A5 violations against Codex's in-flight edits, not Claude's files.

## Rollback plan / context to load next / approvals

**Rollback:** delete the `public-status` branch, disable Pages, unregister the
daily task. Task files and I68 are docs-only reverts; no data or gate mutated.

Load CURRENT_STATE, the two 2026-08-04 Codex task files, the optimization plan's
§WS-C, and the LESSONS 2026-08-04 entry. User approved 2026-08-04: page scope +
daily cadence; merge; H-033/H-036 no action; H-038 run; WS-C C3+C5+C10 only;
ADR-0016 deferred with an input-quality review requested.

**Next action / questions for human review:** merge PR #19 and activate the page
per RUNBOOK; Codex is mid-flight on both task files, so review its diffs before
it commits. Open: give I68 a real validator now, or wait for ADR-0016? Waiting
is recommended; one built now targets a spec format that will change.

## Human Learning Notes

- Two findings came from cheap mechanical sweeps, not reading: tabulating 38
  artifacts showed `data_availability` is the most common first failure, and
  comparing `main` to `origin/main` showed the local ref was three weeks stale.
- CURRENT_STATE was wrong twice in one session — the H-033/H-036 action was
  superseded two days earlier and the 2026-08-02 slate was absent. A snapshot
  needs the same verification as any other claim.
- Reflowing is not shortening: several edits aimed at the ≤90-line caps changed
  wording without removing lines. Merging section headers finally worked.
