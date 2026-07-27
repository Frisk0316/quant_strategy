---
status: current
type: handoff
owner: codex
created: 2026-07-27
last_reviewed: 2026-07-27
expires: none
superseded_by: null
---

# Context Handoff: GenAI Strategy-Finding Pipeline — 2026-07-27

## Goal (one sentence)

Make one prompt-triggered strategy-finding round discover broadly and
deterministically evaluate at least ten paper-new plus existing-iteration
strategies without letting GenAI output become canonical evidence.

## Current state

- Branch: `feature/h014-e052-shadow`.
- Last known good commit / state: HEAD `5374ce5`; this session's changes are
  uncommitted documentation/governance changes.
- In-progress edits (files): ADR-0016, R6.8/R6.9, I53/I54, F56/F57,
  workflow/collaboration/feature/current-state docs, workstream progress, Change
  Manifest, and handoffs. The earlier sparse-round correction in
  `docs/STRATEGY_HISTORY.md` and `docs/README.md` remains in the same working
  tree.
- What works right now: existing paper APIs/fetcher, firewall, idea generator
  cap of 15, registered Stage-2/Stage-3 runners, sequential resumable
  orchestrator, and deterministic sidecar/report code. Documentation/config
  checks pass.
- What does not work / unfinished: no unified prompt entry point, 8/2/10
  executable manifest validator, paper identity dedupe, GenAI candidate-spec
  adapter, generic candidate-specific runner, manifest-hash resume, or
  per-round reconciled report. Current literature drafts usually remain
  `pending_llm`; new families without runners stop before execution.

## Decisions made (and why)

- A complete round seals 10–15 execution-ready strategies before results,
  including at least eight verified-paper-backed new mechanisms and two
  eligible ex-ante existing-strategy iterations. This reconciles the user's
  minimum with the existing cap of 15.
- Invalid/deduplicated/data-infeasible/unimplemented candidates stay visible
  but do not count; backfill or stop incomplete. This prevents quota gaming.
- GenAI handles discovery, interpretation, and schema-valid specs; deterministic
  repository code owns backtests, metrics, trial/K, gates, and reports. This
  keeps evidence reproducible.
- Reuse the existing drafted candidate contract and `signal_ref` registry.
  Keep execution sequential until profiling justifies concurrency. This is the
  smallest implementation that can satisfy the contract.

## Open questions / unverified assumptions

- The registered `signal_ref` contract is expected to cover enough mechanisms
  for a 10–15 strategy slate. If it proves too narrow, consider sandboxed,
  tested, reviewable generated implementations; never direct arbitrary code as
  canonical evidence.
- The eventual headless GenAI adapter/provider is intentionally undecided. The
  first version can use the active Codex/Claude session and JSON handoff.

## Rules in play (preserve verbatim)

- I53/R6.8: before results, a complete round contains 10–15 unique executable
  strategies, at least eight verified-paper-backed new mechanisms and two
  eligible existing iterations; rejected/unimplemented candidates are
  backfilled and every counted candidate gets a terminal deterministic Stage-2
  evaluation.
- I54/R6.9: GenAI cannot see same-round OOS/fold results before sealing, execute
  arbitrary generated code as evidence, decide gates, or author the canonical
  report; frozen provenance/spec hashes and deterministic code own evidence.
- Do-not-touch: `research/`, existing `results/**`, strategy/risk/portfolio/
  execution code, differential validation, deployment config/gates, and the
  unrelated untracked
  `results/ui_funding_carry_2a3cdd23_execution_comparison.json`.

## Context to load next (the reading list)

- Source of truth:
  `docs/ADR/0016-genai-discovery-deterministic-strategy-evaluation.md`,
  `docs/DOMAIN_RULES.md`, `docs/AI_WORKFLOW.md`,
  `docs/ai_collaboration.md`, `docs/STRATEGY_HISTORY.md`, and read-only
  `research/strategy_synthesis.md`.
- Owning files / MODULE_BRIEFS: `backtesting/pipeline_idea_generator.py`,
  `backtesting/pipeline_orchestrator.py`,
  `backtesting/pipeline_stage2_registry.py`,
  `backtesting/pipeline_stage3_registry.py`,
  `scripts/run_pipeline_literature_ideas.py`, and
  `scripts/run_pipeline_funnel_report.py`.
- Existing contract:
  `docs/superpowers/specs/2026-06-30-drafted-candidate-stage3-contract.md`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run

- `scripts/docs/check_doc_metadata.py` — PASS with one known warning for the
  pre-existing metadata-less
  `docs/superpowers/specs/2026-07-26-strategy-finding-round.md`.
- `scripts/docs/check_feature_map_links.py` — PASS, 252 concrete paths.
- `scripts/docs/check_ledger_consistency.py` — PASS, 24 hypotheses,
  64 experiments, 23 K-budget families.
- `scripts/validate_pipeline.py --check-config-only` — PASS.
- `scripts/docs/check_doc_impact.py --strict` — PASS, 18 changed files at that
  checkpoint and no violations.
- `git diff --check` — PASS; line-ending warnings only.

## Approvals

- Human approval obtained 2026-07-27 for the complete-round minimum, new-paper
  plus existing-iteration mix, GenAI discovery/spec generation, and
  deterministic backtest/report boundary.
- No promotion, deployment, gate relaxation, or live authorization was given.

## Next action (single, concrete)

- Implement and test a result-blind round-manifest validator at the orchestrator
  boundary, including 8/2/10 executable counts, unique identities, provenance,
  manifest hashing, and explicit `limited_probe` bypass labeling.

## Human Learning Notes

The bottleneck is not paper retrieval or the existing maximum of 15; it is the
conversion from generic `pending_llm` ideas into candidate-specific executable
contracts. Future reports must separate papers fetched, ideas generated,
execution-ready strategies, parameter/trial cells, and actually evaluated
strategies. "One prompt" should mean one user action, not one LLM completion.
