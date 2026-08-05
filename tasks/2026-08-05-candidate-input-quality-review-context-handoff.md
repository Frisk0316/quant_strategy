---
status: current
type: handoff
owner: codex
created: 2026-08-05
last_reviewed: 2026-08-05
expires: none
superseded_by: null
---

# Context Handoff: candidate input-quality review — 2026-08-05

## Goal (one sentence)

Define an evidence-backed pre-H-number candidate admission packet and validate
the historical claims in `tasks/2026-08-05-candidate-input-quality-review.md`.

## Current state

- Branch: `feature/deribit-moneyness-hypotheses`.
- Last known good commit / state: `663dd5d`; the task is documentation-only and
  no commit was created.
- In-progress edits: none for this task.
- What works right now: the corrected review reconciles all 44 Stage-2 files,
  30 artifact hypotheses, and 47 ledger rows; the manual admission packet is
  specified without changing runtime behavior.
- What does not work / unfinished: no validator enforces I68; the B3 2× ratio is
  a proposed manual-review heuristic, not an approved gate.
- Preserved unrelated working-tree changes: `docs/AI_HANDOFF.md`,
  `docs/CURRENT_STATE.md`, and `docs/ai/LESSONS.md` were already modified and
  were not edited by this task.

## Decisions made (and why)

- Normalize the four H-013/H-014 legacy artifacts before interpreting missing
  standard fields, because schema absence is not evidence absence.
- Keep admission before H-number assignment and use a manual JSON packet now,
  because patching Stage-2 happens after the failure and ADR-0016 is deferred.
- Do not add a free-form `breadth_provenance` string, because E-094/E-095 show
  that structured/hash-bound or self-contained evidence is the real contract.
- Keep 2× advisory, because eight repeated/post-run observations do not identify
  a universal hard threshold; 1.5× and 2× classify the same artifacts.

## Open questions / unverified assumptions

- Should B3 >=2 become a hard admission rule? Recommendation: no until a
  prospective sample exists; approval would require the A5/A9 Change Manifest
  and ADR path.
- I68 says DB-confirmed data, while the older Stage-2 template permits immutable
  files for research-tier screens. A future non-DB candidate needs an explicit
  ruling rather than an inferred exception.

## Rules in play (preserve verbatim)

- I68: execution-ready requires, before H-number assignment, DB-confirmed data
  count/range, ex-ante gross bps versus modelled cost bps, and breadth derived
  from realized positions; missing evidence does not count toward a sealed
  manifest and breadth fails closed to 1.
- I49/R6.6: every gating reference must contain dated returns with a declared
  intersection capable of meeting the minimum common-observation requirement;
  structural impossibility is a contract refusal.
- R6.3/I13: data-dependent candidate selection cannot hide trial count.
- R6.8/I53: only 10–15 execution-ready candidates, including at least eight new
  mechanisms and two eligible iterations, can form a completed round.
- Do not touch: `results/**`, `research/**`, strategy/signal/risk/portfolio/
  execution code, config, DB schema, or demo/shadow/live gates.

## Context to load next (the reading list)

- Source of truth: `docs/ADR/0013-stage2-statistical-power-triage.md`,
  `docs/ADR/0016-genai-discovery-deterministic-strategy-evaluation.md`,
  `docs/DOMAIN_RULES.md` R6, and `docs/INVARIANTS.md` I45/I49/I53/I64/I68.
- Owning files: `backtesting/pipeline_feasibility.py`,
  `backtesting/pipeline_round.py`, `backtesting/pipeline_stage2_registry.py`,
  and the Strategy Research Pipeline Automation section of
  `docs/FEATURE_MAP.md`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run

- Read-only audit assertions: PASS — 44 artifacts, 30 hypotheses, 23 standard
  data passes, 25 normalized data passes, 8 direct gross/cost pairs, 27 breadth
  values.
- `check_doc_metadata.py`: PASS with two pre-existing warnings.
- `check_feature_map_links.py`: PASS, 303 concrete paths.
- `check_ledger_consistency.py`: PASS, 47 hypotheses / 96 experiments / 39
  K-budget families.
- `check_doc_impact.py`: PASS, no impact-matrix violations.
- Standard `pwsh scripts/verify.ps1` could not start because PowerShell 7 is
  absent; Windows PowerShell then reached the harness but its default `python`
  app alias failed. The four Makefile-equivalent Python checks above ran with
  the repository's known Python 3.12 executable.

## Approvals

- User authorized completion of this review.
- No approval exists for a new hard B3 gate, Stage-2 schema change, Change
  Manifest, or ADR-0016 validator implementation.

## Next action (single, concrete)

- Fill the manual admission JSON from the review for the next proposed
  candidate before assigning its H-number.

## Human Learning Notes

Missing a common field is not the same as missing evidence when historical
artifacts have candidate-specific schemas. Also, a shared 8 bps unit cost can
be valid; the auditable requirement is the candidate's turnover-, holding-,
and funding-aware total cost in the same unit as expected gross edge.

