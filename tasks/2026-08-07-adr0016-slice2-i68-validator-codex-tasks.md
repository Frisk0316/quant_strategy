---
status: current
type: task
owner: claude
created: 2026-08-07
last_reviewed: 2026-08-07
expires: none
superseded_by: null
---

# ADR-0016 complete-round infrastructure — slice 2: I68 validator + real-path wiring (Codex)

Authority: ADR-0016 (accepted); I68 (REVIEW pending exactly this validator);
user ruling 2026-08-07 ("開工 ADR 0016") lifting the 2026-08-04 deferral for
INFRASTRUCTURE BUILD ONLY — running a real round remains a separate
user-authorized event. Read first:
`docs/ADR/0016-genai-discovery-deterministic-strategy-evaluation.md`,
`docs/INVARIANTS.md` row I68, `backtesting/pipeline_round.py`,
`tasks/2026-07-29-adr0016-round-infra-slice1-codex-tasks.md` (slice-1 scope),
`docs/ai/LESSONS.md` 2026-08-04 entry (why I68 exists).

Out of scope, later slices: DOI/arXiv/title literature identity (phase 2;
touches `research/` = Claude ownership) and the `signal_ref` runner registry
(phase 3). Their absence honestly blocks a real round; do not work around it.

## T1 — I68 execution-ready validator (extends `validate_round_manifest`)

Each COUNTED candidate's manifest entry must carry three verified numbers,
else it is not execution-ready and the slate falls below contract:

- (a) per named dataset: a DB-confirmed `row_count` and `[start, end)` date
  range. Sealing REQUIRES a live DSN: the validator re-queries each claim and
  refuses on mismatch or missing dataset (named reason, per dataset). No DSN
  → refuse to seal (data-first; structural-only sealing is the exact failure
  I68 was written against).
- (b) `expected_gross_capture_bps` and `modeled_cost_bps`, both finite
  positive, with a one-line provenance string for the gross estimate.
  Record `gross_over_cost`; do NOT add a ratio gate (B3's >=2.0 bar lives in
  the admission form, not here).
- (c) `breadth` derived from a referenced realized-position artifact
  (path + sha256). A declared breadth with no derivation reference fails
  closed to breadth=1, and the coercion is recorded in the manifest entry.

## T2 — One-command sequential wiring + real-path reconciled report

Wire slice-1's `seal_round_manifest` / `verify_resume` / `reconcile_round`
into `scripts/run_pipeline_orchestrator.py` as the single sequential
entry point: joined input → I68+8/2/10 validate → seal → execute registered
runners in manifest order → emit the reconciled report from that real path.
Candidates without a registered runner refuse at validation (named), not
mid-round. Interruption + rerun resumes hash-bound; a mutated manifest is
refused. Sequential only — no concurrency.

## T3 — Flip I68 enforcement from REVIEW to tests

Update ONLY the verification column of `docs/INVARIANTS.md` row I68 to the
named tests from T1. No wording change to the rule itself.

Constraints:
- No Stage-2/Stage-3 evaluation logic changes; orchestration and validation
  only. GenAI boundary per I54 (no model-authored metrics).
- No real round is RUN. Build + tests + dry validation on synthetic fixtures
  (DB checks in tests use a mocked/temporary query boundary, not the real DB).

PERMITTED: `backtesting/pipeline_round.py`, `backtesting/pipeline_orchestrator.py`,
`scripts/run_pipeline_orchestrator.py`, their tests, new files beside them;
`docs/INVARIANTS.md` (I68 verification column only);
`docs/change_manifests/2026-07-27-genai-strategy-finding-pipeline.md`;
`docs/AI_HANDOFF.md`, `config/workstreams.yaml`, `docs/CHANGELOG_AI.md`.
FORBIDDEN: `src/okx_quant/{strategies,signals,risk,portfolio,execution}/`,
`config/risk.yaml`, `research/`, ledger historical rows, existing
`results/**`, any gate-doc semantic change.

ACCEPTANCE (binary):
- [ ] Entry missing any of (a)/(b)/(c) → candidate not counted; validator
      names the candidate and the missing number; slate below 10/8/2 then
      refuses or labels `limited_probe` exactly as slice 1 does.
- [ ] Dataset claim mismatching the (mocked) DB row count/range → named
      refusal; absent DSN → seal refused.
- [ ] Declared breadth without derivation reference → coerced to 1 and
      recorded; derived breadth with reference + hash passes through.
- [ ] One command runs: validate → seal → execute (synthetic registered
      runner fixture) → reconciled report; kill + rerun resumes hash-bound;
      mutated manifest refused.
- [ ] I68 row cites the new tests; `python -m pytest` for touched modules
      green; ledger consistency + doc-impact advisory pass; diff only in
      permitted files.
- [ ] Report states explicitly: no real round ran, readiness unchanged,
      real rounds still blocked on phases 2–3 and candidate supply.

REPORT: standard AGENTS.md block.
