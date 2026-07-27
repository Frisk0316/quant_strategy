---
status: archived
type: handoff
owner: codex
created: 2026-07-27
last_reviewed: 2026-07-27
expires: none
superseded_by: tasks/2026-07-27-genai-strategy-pipeline-context-handoff.md
---

# Context Handoff: strategy-finding round scope — 2026-07-27

## Goal (one sentence)

Make every completed strategy-finding round cover both genuinely new directions
and eligible existing-family iterations, while correcting the 2026-07-26 batch's
coverage label without altering its evidence.

## Current state

- Branch: `feature/h014-e052-shadow`.
- Last known good commit / state: `5374ce5`; this docs-only change is uncommitted.
- In-progress edits: `docs/AI_WORKFLOW.md`, `docs/README.md`,
  `docs/STRATEGY_HISTORY.md`, `docs/INVARIANTS.md`,
  `docs/FAILURE_MODES.md`, `docs/AI_HANDOFF.md`,
  `docs/CURRENT_STATE.md`, and `config/workstreams.yaml`.
- What works right now: the workflow defines the two required tracks, default
  candidate counts, stage routing, full-funnel reporting, and limited-probe
  label; current/history docs apply the correction.
- What does not work / unfinished: enforcement is review-based; no code validator
  was requested or added.

## Decisions made (and why)

- A full round defaults to 8–12 new mechanisms plus 2–4 ex-ante iterations of
  the strongest eligible existing families, because the user affirmed this
  breadth after the prior two-candidate batch was identified as insufficient.
- Every candidate surviving deduplication and data feasibility reaches Stage 2;
  Stage 3 remains pass-only, preserving current stop and trial-count rules.
- The 2026-07-26 batch is a limited two-candidate probe, because H-023 was its
  only new family and H-009/E-063 its only existing-family iteration.
- Existing pre-registration, ledgers, verdicts, and `results/**` remain
  immutable; this is a coverage-label and future-workflow correction only.

## Open questions / unverified assumptions

- None blocking. A machine-enforced slate-count validator would require a
  separate explicit task if review-only I53 proves insufficient.

## Rules in play (preserve verbatim)

- Invariant touched: I53 — a completed strategy-finding round contains both
  default candidate tracks, routes every surviving candidate through Stage 2,
  and reports the full rejection funnel; smaller work is a limited probe.
- Failure mode added: F56 — a sparse candidate batch presented as a completed
  strategy-finding round.
- Domain rules touched: none.
- Do-not-touch: `research/`, strategy/risk/portfolio/execution code, experiment
  ledgers, existing result artifacts, and demo/shadow/live gates.

## Context to load next (the reading list)

- Source of truth: current user instruction, `docs/AI_WORKFLOW.md`,
  `docs/STRATEGY_HISTORY.md`, `docs/INVARIANTS.md`.
- Owning files: the Strategy Research Pipeline Automation entry in
  `docs/FEATURE_MAP.md`; no module brief exists for this pipeline.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run

- `python scripts/docs/check_doc_metadata.py` — PASS with the pre-existing
  warning for the frozen 2026-07-26 strategy-finding spec.
- `python scripts/docs/check_feature_map_links.py` — PASS, 250 paths.
- `python scripts/docs/check_ledger_consistency.py` — PASS, 24 hypotheses,
  64 experiments, 23 K-budget families.
- `python scripts/docs/check_doc_impact.py --strict` — PASS.
- `python scripts/validate_pipeline.py --check-config-only` — PASS.

## Approvals

- Human approval obtained in the current conversation for the durable two-track
  strategy-finding rule and correction of the sparse prior round.

## Next action (single, concrete)

- Before any new backtest, pre-register the next full round's 8–12 new
  mechanisms and 2–4 eligible existing-family iterations with deduplication,
  Stage-2, and reporting contracts.

## Human Learning Notes

Calling one new strategy plus one revision a “round” hid how little of the
design space was searched. Future reports must separate candidate-slate size
from the smaller number that survives deduplication, data feasibility, and
Stage-2 stop rules.
