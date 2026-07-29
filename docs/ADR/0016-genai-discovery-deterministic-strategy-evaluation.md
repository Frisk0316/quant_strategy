---
status: accepted
type: adr
owner: codex
created: 2026-07-27
last_reviewed: 2026-07-27
expires: none
superseded_by: null
---

# ADR-0016: GenAI Discovery with Deterministic Strategy Evaluation

## Status

Accepted — 2026-07-27 through the user's explicit instruction that one
prompt-triggered strategy-finding round execute at least ten strategies,
combining new paper-backed directions with ex-ante iterations of existing
strategies.

This is a research-pipeline decision only. It does not relax Stage-3,
promotion, demo, shadow, live, cost, trial-count, or validation gates.

## Context

The repository already has literature retrieval, prompt-firewall screening,
taxonomy idea generation, a batch cap of 15, a resumable orchestrator,
registered Stage-2/Stage-3 runners, and deterministic reports. It does not yet
provide the requested end-to-end behavior:

- candidate generation has a maximum but no complete-round minimum or track
  quota;
- the literature and taxonomy entry points are separate;
- literature candidates normally stop at `pending_llm`;
- new or unregistered families stop at `awaiting_stage2_implementation`;
- the existing report cannot prove that one frozen round completed its entire
  candidate funnel.

The phrase "one prompt" means one user-triggered pipeline run. The pipeline may
make several bounded GenAI calls internally for query expansion, paper
interpretation, and candidate specification.

## Design-space expansion

**Problem:** one prompt-triggered round must produce broad, auditable discovery
and actually evaluate at least ten executable strategies.

**Constraints:** preserve the current 15-candidate execution cap, result-blind
pre-registration, honest family-cumulative trials/K, current data provenance
and promotion gates, and the ownership boundary on `research/`. Do not execute
unreviewed arbitrary model-generated code.

- **Option A — document the count and keep per-family manual runners:** smallest
  change, but most new candidates would still stop before execution.
- **Option B — let GenAI emit and directly run Python:** fastest mechanism
  coverage, but creates an unauditable code/data/leakage boundary and makes
  canonical evidence depend on nondeterministic code generation.
- **Option C — schema-valid candidate specs plus a registered deterministic
  runner:** reuses the existing drafted candidate contract and `signal_ref`
  registry pattern; GenAI expands discovery while ordinary code owns evidence.
- **Option D — add a workflow/agent framework:** could support scheduling and
  concurrency, but does not solve the executable-contract gap and adds
  operational surface before throughput is measured.

**Axis:** discovery breadth versus deterministic reproducibility and reviewable
execution.

**Decision:** Option C. It is the smallest design that can satisfy the requested
round size without letting model output become canonical backtest evidence.

**Would change if:** the registered contract proves unable to express a
material share of verified mechanisms. The next option would be sandboxed,
tested, human-reviewable generated implementations, never direct execution as
canonical evidence.

## Decision

### 1. Complete-round quota

A completed prompt-triggered round seals **10–15 unique, execution-ready
strategies** before any candidate result is visible:

- at least **8** are genuinely new mechanisms derived from verified research
  papers and not already represented in strategy history;
- at least **2** are material, ex-ante iterations of eligible existing
  strategies;
- remaining slots may come from either track.

Parameter cells, threshold changes without a mechanism rationale, renames, and
duplicate family formulations do not count as distinct strategies. A smaller
run is a `limited_probe` or `incomplete_round`, never a completed round.

Discovery should oversample beyond the final slate and report unique papers,
candidate specifications, deduplication, feasibility, and execution-ready
counts separately. Only execution-ready strategies count toward 10–15.

### 2. Result-blind round manifest

The pipeline freezes a `round_manifest.json` after GenAI discovery/specification
and before deterministic execution. Every counted candidate must have:

- a unique candidate and family identity;
- a track (`new_research` or `existing_iteration`);
- verified paper provenance for `new_research`, or an ex-ante iteration
  rationale and eligible source hypothesis for `existing_iteration`;
- declared data, timing, signal, cost, parameter-grid, trial/K, power, and
  validation contracts;
- a known `signal_ref`/runner and successful schema/data preflight;
- prompt/model/template and candidate-spec hashes.

Duplicates, unverifiable papers, unavailable data, missing runners, and invalid
contracts remain in the audit funnel but do not count. The pipeline must
backfill them before sealing; otherwise it stops as incomplete. Resume requires
the same manifest hash.

### 3. Deterministic execution and report

Ordinary repository code, not GenAI, must:

1. validate and seal the manifest;
2. execute a deterministic Stage-2 screening backtest or research-return
   evaluation for every sealed strategy and write a terminal artifact;
3. execute Stage 3 only for Stage-2 passes under unchanged gates;
4. calculate metrics, family-cumulative trial/K use, and pass/fail decisions;
5. generate the canonical per-candidate and aggregate funnel report.

One candidate error must remain visible and must not silently turn the rest of
the round into a completed run.

### 4. GenAI boundary

GenAI may:

- expand literature queries and rank verified papers;
- interpret paper mechanisms against available data;
- propose novel mechanisms and eligible existing-strategy iterations;
- emit schema-valid candidate specifications and reviewer notes.

GenAI must not:

- inspect current-round OOS/fold results before the manifest is sealed;
- execute arbitrary generated code as canonical evidence;
- compute or override canonical metrics, trial/K counts, or gates;
- retune a candidate from same-round results without a new registered
  experiment;
- author the canonical backtest report.

### 5. Minimal implementation pattern

Reuse `docs/superpowers/specs/2026-06-30-drafted-candidate-stage3-contract.md`
and its `signal_ref` registry boundary. The first version uses the current
Codex/Claude session as the GenAI adapter and JSON files as the handoff. A later
headless adapter may call a provider-neutral model command/API, but no new agent
framework or SDK is required for the first working version.

Keep execution sequential and resumable initially. Add bounded parallel
backtests only after measured runtime or DB contention justifies it.

## Implementation status and phases

This ADR defines target authority; the complete-round automation is **not yet
implemented**.

1. Add the round manifest, fail-fast 8/2/10 validation, manifest-hash resume,
   and a per-round reconciled report.
2. Join literature discovery and existing-strategy iteration planning; add
   DOI/arXiv/title deduplication and schema-valid GenAI output.
3. Generalize candidate-specific registered Stage-2 runners so every counted
   strategy has a deterministic screening backtest.
4. Add one prompt/command orchestration, atomic state writes, and per-candidate
   error isolation.
5. Consider bounded concurrency only after profiling the sequential path.

Until phases 1–4 are complete, current commands may produce advisory or limited
probes but must not claim a complete ADR-0016 round.

## Consequences

- A complete round can no longer be represented by a few ideas, `pending_llm`
  drafts, data-only checks, or unimplemented runners.
- Search breadth and executed-strategy breadth become separate, reconcilable
  funnel counts.
- Model creativity remains useful without making model output the evidence
  authority.
- The stricter definition may stop a round before backtesting when the system
  cannot assemble ten valid runners. That is an honest incomplete result, not a
  reason to fill the slate with duplicate or low-quality variants.
- Existing artifacts and the 2026-07-26 limited two-candidate probe remain
  unchanged.
