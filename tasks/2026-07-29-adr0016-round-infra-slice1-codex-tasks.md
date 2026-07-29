---
status: current
type: task
owner: claude
created: 2026-07-29
last_reviewed: 2026-07-29
expires: none
superseded_by: null
---

# ADR-0016 complete-round infrastructure — slice 1 (Codex)

Authority: ADR-0016 (accepted), R6.8/R6.9, I53/I54, and the standing
CURRENT_STATE next-action ("implement ADR-0016 in the smallest slices").
User directed 2026-07-29 to start this in parallel with the H-028/H-029 event
probe. Read first: `docs/ADR/0016-genai-discovery-deterministic-strategy-evaluation.md`,
`docs/change_manifests/2026-07-27-genai-strategy-finding-pipeline.md`,
`docs/superpowers/specs/2026-07-26-strategy-finding-round.md`.

Goal of slice 1 (exactly the smallest-safe-path list, nothing more):

## S1 — `round_manifest.json` + fail-fast 8/2/10 validation

A result-blind round manifest sealed BEFORE any evaluation: lists 10–15
unique execution-ready candidates with provenance (≥8 verified-paper-backed
new mechanisms, ≥2 eligible ex-ante existing-strategy iterations), each bound
to a registered deterministic runner. A validator refuses to seal (fail-fast,
named reasons) when the mix/minimum/executability contract is not met —
anything smaller is labeled `limited_probe` in the manifest itself.

## S2 — Hash-bound resume

The sealed manifest carries a content hash; resume/continuation of a round
must bind to that hash and refuse a mutated manifest (I53's "result-blind"
property survives interruptions).

## S3 — Joined candidate input

One entry point that joins literature-draft candidates and eligible
existing-strategy iterations, deduplicating by family/provenance, refusing
`pending_llm` drafts as counted candidates.

## S4 — Reconciled per-round report

One report generated FROM the sealed manifest + terminal Stage-2/Stage-3
artifacts, reconciling every counted candidate to a terminal state (no
mixing/overwriting of funnel stages); disagreements fail the report, not
silently resolve.

Constraints:
- Sequential execution only (no concurrency work in this slice).
- No Stage-2/Stage-3 evaluation logic changes; this slice is orchestration
  and validation only. GenAI boundary per I54 (no model-authored metrics).
- No new round is RUN under this slice — build + tests + a dry validation on
  a synthetic manifest fixture. Running the first real complete round is a
  separate user-authorized event.

PERMITTED: the pipeline orchestrator/generator modules and their tests (locate
via `docs/change_manifests/2026-07-27-genai-strategy-finding-pipeline.md`
"files" section; stay inside those + new files beside them), plus
`docs/AI_HANDOFF.md`, `config/workstreams.yaml`, `docs/CHANGELOG_AI.md`, and a
Change Manifest update.
FORBIDDEN: `src/okx_quant/{strategies,signals,risk,portfolio,execution}/`,
`config/risk.yaml`, ledgers' historical rows, existing `results/**`, any gate
doc semantic change.

ACCEPTANCE (binary):
- [ ] Validator test matrix: seals a valid 10-15/8/2 manifest; refuses (with
      named reason) undersized, mix-violating, non-executable, `pending_llm`,
      and duplicate-family slates; labels sub-threshold slates
      `limited_probe`.
- [ ] Resume test: mutated manifest → refused; identical manifest → resumes.
- [ ] Report test: a synthetic round with one missing terminal artifact fails
      reconciliation loudly.
- [ ] `python -m pytest` for the touched test modules green; ledger
      consistency + doc-impact advisory pass; diff only in permitted files.

REPORT: standard AGENTS.md block; note explicitly that no real round ran and
readiness is unchanged.
