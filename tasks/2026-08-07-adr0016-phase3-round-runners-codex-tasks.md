---
status: current
type: task
owner: claude
created: 2026-08-07
last_reviewed: 2026-08-07
expires: none
superseded_by: null
---

# ADR-0016 phase 3 — round runners from the Stage-2 registry (Codex)

Authority: ADR-0016 (accepted, phases list); user 2026-08-07 "雙軌並進"
(build phase 3 while Claude sources candidates). Read first:
`tasks/2026-08-07-adr0016-slice2-claude-review.md` (findings 1–2 are
requirements here), `backtesting/pipeline_orchestrator.py` `run_round`,
`backtesting/pipeline_stage2_registry.py` (STAGE2_PROBES contract),
`docs/superpowers/specs/2026-06-30-drafted-candidate-stage3-contract.md` §4.

Goal: a counted round candidate becomes executable by binding its manifest
`runner` name to the EXISTING family-keyed Stage-2 probe machinery — no new
evaluation logic, no Stage-3 execution.

## T1 — Stage-2 probe adapter as a round runner

A factory (e.g. `stage2_round_runner(family_id)`) returning a runner with the
`run_round` contract: it connects with the context DSN, builds the probe's
`Stage2Context` from the candidate's manifest entry (window, universe,
power inputs — all from the sealed manifest, nothing result-derived),
invokes the registered `STAGE2_PROBES[family_id]` probe unchanged, and maps
`FeasibilityResult` to `{"stage2": {"status": ..., "checks": [...]}}`:
all four checks pass → `pass`; any check fails → `fail`; probe exception →
`error` with the exception name. The factory refuses at construction if
`family_id` is not in `STAGE2_PROBES`.

## T2 — Stage-2 pass halts for Stage-3 authorization (fail loud, resume safe)

Stage 3 is user-authorization-gated and this slice must not run it. When an
adapted runner's Stage-2 result is `pass`, the round must (a) persist the
Stage-2 terminal into `round_state.json` under the manifest hash, then
(b) raise a named error (`stage3_authorization_required:<candidate_id>`)
instead of fabricating a stage3 result. A later resume with an explicitly
registered, user-authorized stage3 runner for that candidate continues from
the checkpoint. Never auto-derive a stage3 status.

## T3 — Runner preflight recomputes breadth (review finding 2)

Before invoking the probe, the runner re-derives breadth from the
candidate's `breadth_provenance` artifact (read the referenced
realized-position series; recompute with the formula/window recorded in the
manifest entry) and raises a named error if the recomputed value disagrees
with the sealed `breadth` beyond 1e-9. A manifest entry whose artifact
cannot reproduce its breadth must never execute.

## T4 — Live dataset query confirms the range (review finding 1)

`query_dataset_claim` additionally returns the in-window `min`/`max`
timestamp per locator query, and validation compares them against the
claim's `[start, end)` (min >= start, max < end, and non-empty), making
`dataset_range_mismatch` reachable through the real DB path. Update the
mismatch test to exercise it through `query_dataset_claim` with a mocked
connection rather than only an injected query.

## T5 — Reviewed registration surface

`ROUND_RUNNERS` is populated only from an explicit reviewed list (module
constant mapping runner name → family_id through the T1 factory), starting
EMPTY of entries. Add the mechanism + tests; do not pre-register families —
registrations land per-candidate when admission packets pass (Claude review
per entry). Auto-discovery/wildcards are forbidden.

Constraints:
- No change to any probe's evaluation logic, thresholds, or
  `FeasibilityResult` semantics; adapter maps, never edits.
- No real round, no Stage-3 execution, no experiment/trial/K consumption.
- Tests use synthetic probes/fixtures, not the real DB.

PERMITTED: `backtesting/pipeline_round.py`, `backtesting/pipeline_orchestrator.py`,
new `backtesting/pipeline_round_runners.py` (+ its test), existing round/
orchestrator tests, `scripts/run_pipeline_orchestrator.py`,
`docs/change_manifests/2026-07-27-genai-strategy-finding-pipeline.md`,
`docs/AI_HANDOFF.md`, `config/workstreams.yaml`, `docs/CHANGELOG_AI.md`.
FORBIDDEN: `src/okx_quant/{strategies,signals,risk,portfolio,execution}/`,
`config/risk.yaml`, `research/`, `results/**`, any probe evaluation change,
any gate-doc semantic change, `docs/INVARIANTS.md` rule text.

ACCEPTANCE (binary):
- [ ] Adapter maps a synthetic FeasibilityResult to pass/fail/error
      correctly; construction with an unregistered family refuses.
- [ ] Stage-2 pass → state file holds the stage2 terminal AND the round
      raises `stage3_authorization_required`; resume with an authorized
      stage3 runner completes reconciliation; resume without it re-raises.
- [ ] Breadth recompute mismatch → named refusal before the probe runs;
      matching artifact executes.
- [ ] Real-path range mismatch test passes through `query_dataset_claim`
      (mocked conn), not only an injected query.
- [ ] `ROUND_RUNNERS` starts with zero live registrations; the reviewed-list
      mechanism has tests; wildcard/auto-discovery absent.
- [ ] Targeted pytest green; Ruff clean; ledger consistency + doc-impact
      advisory pass; diff only in permitted files.
- [ ] Report states: no real round, no Stage 3, readiness unchanged.

REPORT: standard AGENTS.md block.
