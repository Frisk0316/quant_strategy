---
status: current
type: handoff
owner: codex
created: 2026-06-29
last_reviewed: 2026-06-29
expires: none
superseded_by: null
---

# Context Handoff: Pipeline Batch 2 Checkpoint 1 - 2026-06-29

## Goal (one sentence)
Run Strategy Research Pipeline batch 2 [C3, C2, C1] through Stage 2 -> Stage 3 and stop at Claude evidence checkpoint 1.

## Current state
- Branch: current workspace branch, dirty before session with manual-related files.
- Last known good commit / state: not changed by this handoff.
- In-progress edits (files): C1/C2 research modules, batch-2 runner, contracts, tests, DB-backed result summaries, ledgers, current-state docs.
- What works right now: DB probe succeeded; C1/C2 unit leak and trial-count tests pass; C1/C2 adapter-required contracts are declared; batch-2 summaries and shortlist exist.
- What does not work / unfinished: Claude evidence review has not happened; no portable validation adapters exist for C1/C2, so no candidate is promotion-ready. C2/C1 Pass A parquet pre-screen was skipped because required BTC perp candle/funding parquet inputs are missing or incomplete.

## Decisions made (and why)
- C3 Stage-2 FAIL: `fear_greed_btc` event_count is 0 in `external_observations` over 2024-01-01 through 2026-06-17, so no sentiment proxy was fabricated.
- C2 Stage-2 PASS and Stage-3 completed, but it remains checkpoint-only because portable validation is adapter-required/absent.
- C1 Stage-2 PASS and Stage-3 completed; C1 is logged as first validation of the existing `pairs_trading` OU mechanism, not a fresh-family dodge.
- Stage-3 Pass A is marked skipped for C2/C1; Pass B DB venue-scoped fold-refit is the evidence produced for this checkpoint.
- All candidates remain unpromoted with `promotion_gate_passed:false`.

## Open questions / unverified assumptions
- Whether Claude accepts C2's statistical-pass evidence despite the portable validation block.
- Whether future work should build portable validation adapters for C2 before any further tuning.
- Whether `fear_greed_btc` will be provisioned later or C3 should remain data-blocked.

## Rules in play (preserve verbatim)
- Invariants touched: I4 funding sign; I8 no lookahead; I13/I23 honest trial count; I25 retained CPCV returns for future artifacts.
- Domain rules touched: R3.1, R6.1, R6.3, R7.1, R7.4.
- Do-not-touch: `research/`, `config/risk.yaml`, demo/shadow/live gates, live `funding_carry.py`, `src/okx_quant/analytics/dsr.py`, existing result payloads.

## Context to load next (the reading list)
- Source of truth: `AI_CONTEXT.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, batch-2 specs under `docs/superpowers/specs/`.
- Owning files / MODULE_BRIEFS: `docs/FEATURE_MAP.md` Pipeline Batch 2 Research Candidates.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\run_pipeline_batch2_checkpoint.py` -> completed; wrote C3/C2/C1 summaries and shortlist.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_c1_pairs_ou_backtest.py tests\unit\test_c2_funding_carry_backtest.py tests\unit\test_pipeline_batch2_contracts.py tests\unit\test_pipeline_batch2_checkpoint_runner.py -q` -> 7 passed; pytest cache warning.

## Approvals
- Human approval needed / obtained: DB probe/backtest run proceeded after DB was made available. No approval was requested or obtained for promotion, demo, shadow, live, or config-gate changes.

## Next action (single, concrete)
- Ask Claude to review checkpoint 1 evidence in `results/pipeline_batch2_20260625/` and the runtime rows E-023/E-024/E-025.

## Human Learning Notes
The DB being available changed the state from "blocked before evidence" to "checkpoint evidence ready." C2's high statistics are still not promotion evidence because the independent portable-validation gate is false.
