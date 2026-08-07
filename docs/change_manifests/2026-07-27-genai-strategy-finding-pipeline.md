---
status: current
type: manifest
owner: codex
created: 2026-07-27
last_reviewed: 2026-08-07
expires: none
superseded_by: null
---

# Change Manifest: GenAI Strategy-Finding Pipeline Contract

## Summary

Defines a completed prompt-triggered strategy-finding round as 10–15
execution-ready strategies, with at least eight verified-paper-backed new
mechanisms and two ex-ante existing-strategy iterations. It also separates
GenAI discovery/specification from deterministic backtesting, gates, and
canonical reporting.

## Business rule(s) affected

R6.8 and R6.9 added. R6.1 and R6.3 remain unchanged.

## Trigger area(s) (DOC_IMPACT_MATRIX)

A9 research execution controls and A10 core governance contracts.

## Files changed

- `docs/ADR/0016-genai-discovery-deterministic-strategy-evaluation.md` —
  accepted architecture and implementation boundary.
- `docs/ADR/README.md` — ADR index.
- `docs/DOMAIN_RULES.md` — complete-round and GenAI/deterministic rules.
- `docs/AI_WORKFLOW.md` — operational round definition.
- `docs/ai_collaboration.md` — GenAI/Codex/ordinary-program ownership boundary.
- `docs/INVARIANTS.md` — I53/I54 reviewable constraints.
- `docs/FAILURE_MODES.md` — sparse-round and nondeterministic-evidence failures.
- `docs/FEATURE_MAP.md` — current/target/known-gap pipeline state.
- `docs/KNOWN_ISSUES.md` — current automation blockers.
- `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`,
  `config/workstreams.yaml` — current state and next implementation slice.
- `docs/README.md`, `docs/STRATEGY_HISTORY.md` — prior sparse-round correction
  retained and aligned with the new rule.
- `tasks/2026-07-27-genai-strategy-pipeline-context-handoff.md`,
  `tasks/2026-07-27-genai-strategy-pipeline-session-handoff.md` — durable
  handoff.
- `tasks/2026-07-27-strategy-finding-scope-context-handoff.md`,
  `tasks/2026-07-27-strategy-finding-scope-session-handoff.md` — archived in
  favor of the stricter ADR-0016 handoffs.

## Behavior delta

- Before: a completed round could be described by pre-registration counts, and
  deduplication/data/runner gaps could reduce actual execution below ten.
- After: a complete round must seal 10–15 unique executable strategies before
  results, then deterministically evaluate all of them; invalid candidates must
  be backfilled or the run is incomplete/limited.
- Money/risk impact: none. No PnL, fee, funding, sizing, fill, validation
  threshold, or deployment rule changes.

## Source-of-truth updates

- `research/strategy_synthesis.md`: N/A — no strategy assumption changed and
  Codex does not modify `research/`.
- `config/`: only `config/workstreams.yaml` progress text; no strategy, risk,
  settings, or gate value changed.
- ADR: ADR-0016 added because the research execution and AI authority boundary
  is a durable architectural pattern.

## Docs updated (from DOC_IMPACT_MATRIX row)

- [x] `docs/DOMAIN_RULES.md` — R6.8/R6.9 added.
- [x] `docs/ai_collaboration.md` — model/program boundary added.
- [x] `docs/INVARIANTS.md` — I53/I54 updated/added.
- [x] ADR-0005 reviewed and unchanged — replay promotion gates are untouched.
- [x] `docs/EXPERIMENT_REGISTRY.md` reviewed and unchanged — no experiment or
  trial was run.
- [x] `docs/README.md` updated for the workflow scope.
- [x] `docs/DOC_LIFECYCLE.md` reviewed and unchanged.
- [x] `docs/DOC_IMPACT_MATRIX.md` reviewed and unchanged.

## Invariants / golden cases

- Invariants checked: I53 and I54; existing I8, I13, I23, I45, and I46 remain
  unchanged.
- Golden cases affected: none.

## Tests / checks run

- `scripts/docs/check_doc_metadata.py` — PASS with one known pre-existing
  metadata warning.
- `scripts/docs/check_feature_map_links.py` — PASS, 252 paths.
- `scripts/docs/check_ledger_consistency.py` — PASS, 24 hypotheses,
  64 experiments, 23 K-budget families.
- `scripts/validate_pipeline.py --check-config-only` — PASS.
- `scripts/docs/check_doc_impact.py --strict` — PASS, 20 changed files and no
  impact-matrix violations.
- `git diff --check` — PASS; line-ending warnings only.

## Risks and rollback

- Risks: quota-filling with duplicate mechanisms, hallucinated paper
  provenance, hidden same-round retuning, and documents being mistaken for
  implemented automation. ADR-0016 explicitly excludes those candidates and
  marks implementation incomplete.
- Rollback: revert the listed documentation/config changes and delete ADR-0016,
  this manifest, and the two handoffs. Existing strategy/result artifacts need
  no rollback.

## Approval

- Human approval required: yes — obtained explicitly in the user's 2026-07-27
  instructions. No deployment or gate-change approval was requested or used.

## 2026-07-29 implementation update — ADR-0016 slice 1

- Added `backtesting/pipeline_round.py` and its unit test as the deterministic
  boundary for joined candidate inputs, 10–15/8/2 executable validation,
  `pending_llm`/duplicate refusal, SHA-256-bound resume, and manifest-bound
  terminal reconciliation.
- This implements orchestration validation only. It does not add candidate
  runners, change Stage-2/Stage-3 logic, run a real round, or change R6.8/R6.9.
- Synthetic tests cover a valid 8/2/10 seal, every required refusal class,
  identical/mutated resume, joined-input filtering, and a missing terminal
  artifact. A complete real round remains blocked on enough registered
  deterministic runners.

## 2026-08-07 implementation update — ADR-0016 slice 2

- Extended manifest sealing with I68: every counted candidate now needs live
  DB-matched dataset counts and half-open ranges, finite positive gross/cost
  bps plus one-line gross provenance, and SHA-256-bound breadth provenance.
  Gross/cost is recorded without duplicating the admission form's ratio gate;
  unsupported breadth is recorded at 1 and the candidate is not counted.
- Added one sequential command path from joined inputs through validation,
  sealing, registered-runner execution, atomic per-candidate resume state, and
  manifest-bound reconciliation. The runner registry remains intentionally
  empty until phase 3 supplies reviewed `signal_ref` registrations.
- Trigger areas A5/A9 were reviewed. `docs/INVARIANTS.md` I68 now names the
  enforcing tests. `docs/FEATURE_MAP.md`, `docs/DATA_FLOW.md`, ADR-0005, and
  the experiment ledgers were reviewed and unchanged: no schema, evaluation
  gate, experiment, trial/K count, or data flow changed.
- Synthetic tests cover absent DSN, dataset count/range mismatch, missing gross
  inputs, breadth coercion/hash provenance, ordered execution, interruption
  resume, and mutated-manifest refusal. No real round or result artifact ran;
  promotion/demo/shadow/live readiness is unchanged.

## 2026-08-07 implementation update — ADR-0016 phase 3 round runners

- Added a thin adapter from an explicit reviewed runner-name/family map to the
  existing `STAGE2_PROBES` functions. It builds only manifest-sourced window,
  universe, and power context; maps the unchanged four-check result to a round
  terminal; and records probe exceptions as named Stage-2 errors. The reviewed
  Stage-2 map and candidate-specific authorized Stage-3 map both start empty.
- A runner now re-hashes and reads the sealed realized-position artifact and
  recomputes the recorded breadth formula/window before connecting or invoking
  a probe. A disagreement above `1e-9` refuses execution. Live dataset queries
  now return `MIN`/`MAX` timestamps as well as counts, and range validation
  enforces non-empty `min >= start` and `max < end` results.
- A new Stage-2 pass is atomically checkpointed and then raises
  `stage3_authorization_required:<candidate_id>`. Resume without an explicitly
  authorized candidate runner re-raises without repeating Stage 2; a synthetic
  authorized runner test proves checkpoint continuation and reconciliation.
- Trigger areas A5/A9 were reviewed. `docs/FEATURE_MAP.md`, `docs/DATA_FLOW.md`,
  `docs/GOLDEN_CASES.md`, `docs/INVARIANTS.md`, ADR-0005, and the experiment
  ledgers remain unchanged because no result schema, probe/gate semantics,
  experiment, trial/K count, or persistent data path changed.
- No real round, Stage 3, experiment, or result artifact ran. Readiness and all
  promotion/demo/shadow/live gates remain unchanged.
- Verification: 46 targeted tests passed; targeted Ruff, docs metadata/links,
  ledger consistency, config validation, and `git diff --check` passed.
  Doc-impact advisory exited 0 with its expected A5 warning: the task did not
  permit `FEATURE_MAP`/`DATA_FLOW`/`GOLDEN_CASES` edits, and those documents
  were reviewed unchanged because this slice adds no result/data-flow contract.
