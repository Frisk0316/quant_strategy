# Context Handoff: C3 Sentiment Stage 3 - 2026-06-29

## Goal (one sentence)
Complete C3 Fear & Greed Stage-3 checkpoint generation after the dataset became available.

## Current state
- Branch: `codex/pipeline-batch1-stage3`.
- Last known good commit / state: pre-existing branch with Stage-2 feasibility automation.
- In-progress edits (files): C3 research runner, batch2 runner, C3 tests, H-008/E-027 docs, `FEATURE_MAP.md`, handoff docs, workstream YAML.
- What works right now: `run_c3()` writes Stage-2 PASS plus real Stage-3 WF/CPCV fields to `results/pipeline_batch2_20260625/c3_sentiment/summary.json`.
- What does not work / unfinished: no portable validation adapter or promotion path; C3 is refuted under current WF/CPCV evidence.

## Decisions made (and why)
- C3 uses a vectorized research module instead of changing `FearGreedSentimentStrategy` because the task forbids live strategy edits.
- The Stage-3 grid stays the pre-registered 9 combinations because hidden trials would violate I23.
- `promotion_gate_passed` stays false because statistical gate failed and portable validation remains absent.

## Open questions / unverified assumptions
- Claude should review whether the vectorized daily missing-feature handling is strict enough for the research convention, though the current ingested dataset has full daily coverage in-window.

## Rules in play (preserve verbatim)
- Invariants touched: I4 funding sign, I8 no lookahead, I13/I23 trial counts, I25 CPCV path retention.
- Domain rules touched: R3.1, R6.1, R6.3, R7.1-R7.4.
- Do-not-touch: `src/okx_quant/strategies/**`, `src/okx_quant/signals/**`, `src/okx_quant/risk/**`, `src/okx_quant/portfolio/**`, `src/okx_quant/execution/**`, `config/strategies.yaml`, `config/risk.yaml`, `research/**`, C1/C2 artifacts.

## Context to load next (the reading list)
- Source of truth: `tasks/2026-06-29-c3-sentiment-stage3-task.md`, `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md`, `results/pipeline_batch2_20260625/c3_sentiment/summary.json`.
- Owning files / MODULE_BRIEFS: `docs/FEATURE_MAP.md` Pipeline Batch 2 Research Candidates.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run
- `python -m pytest tests/unit/test_c3_sentiment_backtest.py tests/unit/test_pipeline_batch2_checkpoint_runner.py -q -p no:cacheprovider` - passed, 10 tests.
- `python -c "from scripts.run_pipeline_batch2_checkpoint import run_c3; run_c3()"` - passed, wrote C3 checkpoint artifact.

## Approvals
- Human approval needed / obtained: task scope approved by current user request; no approval obtained for promotion, demo, shadow, live, adapter, or config enablement.

## Next action (single, concrete)
- Run final docs impact check and hand the diff to Claude for research/result review.

## Human Learning Notes
C3 moved from "no data, no test" to "tested and refuted." That is useful progress:
the pipeline can distinguish a blocked idea from an honestly failed one, and the
failed result prevents future tuning from pretending the original 9-trial family
budget is still unused.
