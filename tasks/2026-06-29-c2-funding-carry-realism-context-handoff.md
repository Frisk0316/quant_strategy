---
status: current
type: handoff
owner: codex
created: 2026-06-29
last_reviewed: 2026-06-29
expires: none
superseded_by: null
---

# Context Handoff: C2 Funding-Carry Realism Re-Cost - 2026-06-29

## Goal (one sentence)
Re-cost C2 funding carry under realistic costs and the pre-registered funding-reversal / basis-blowout stress set without touching live strategy behavior.

## Current state
- Branch: current workspace branch; dirty before this session with batch-2 and manual-related files.
- Last known good commit / state: not changed by this handoff.
- In-progress edits (files): C2 research runner/tests, new C2 realism runner, new C2 realism summary, H-007/E-026 ledgers, handoff/current-state docs, workstreams registry.
- What works right now: `tests/unit/test_c2_funding_carry_backtest.py` passes; C2 realism DB rerun completed and wrote `results/pipeline_batch2_20260625/c2_funding_carry_realism/summary.json`.
- What does not work / unfinished: C2 remains a vectorized research approximation; realized annualized vol is still only 0.247%, so the artifact is a refutation/shelving result, not proof of fully realistic execution.

## Decisions made (and why)
- Used a small dedicated `scripts/run_c2_realism.py` instead of modifying the batch-2 checkpoint runner because the old artifact must stay untouched and this is a one-off gate retry.
- Counted E-026 as a retry of `F-FUNDING-CARRY`: prior family trials 24 + current grid 24 = `n_trials=48`.
- Used the user/Claude pre-registered stress rule: daily stress if trailing 7-day funding APR < 0 or abs(basis z) > 3, evaluated as one group.
- Marked H-007 `refuted / shelved` because DSR 0.0041 and PSR 0.4457 both fail the 0.95 gate.

## Open questions / unverified assumptions
- Whether Claude wants a later replay-engine realism task for funding carry despite this vectorized-family refutation.
- Whether C3 should be ingested/tested or left parked as data-blocked.

## Rules in play (preserve verbatim)
- Invariants touched: I4 funding sign; I8/I24 no lookahead/fold-refit evidence; I13/I23 honest trial count; I25 retained CPCV returns.
- Domain rules touched: R3.1, R6.1, R6.3, R7.1, R7.4.
- Do-not-touch: `research/`, live `src/okx_quant/strategies/funding_carry.py`, all `src/okx_quant/strategies/`, `signals/`, `risk/`, `portfolio/`, `execution/`, `src/okx_quant/analytics/dsr.py`, `backtesting/cpcv.py`, `backtesting/walk_forward.py`, `backtesting/pipeline_refit.py`, `config/risk.yaml`, `config/strategies.yaml` enable flags, demo/shadow/live gates, and existing result artifacts.

## Context to load next (the reading list)
- Source of truth: `AI_CONTEXT.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `research/strategy_synthesis.md` Strategy 3, `docs/backtest_live_parity_plan.md`, `tasks/2026-06-29-c2-funding-carry-realism-task.md`.
- Owning files / MODULE_BRIEFS: `docs/FEATURE_MAP.md` Pipeline Batch 2 Research Candidates.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_c2_funding_carry_backtest.py -q` - 4 passed; pytest cache warning.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -B -c "import scripts.run_c2_realism as m; print(m.CANDIDATE_DIR)"` - passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\run_c2_realism.py` - completed DB-backed realism rerun.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_doc_impact.py` with temporary `GIT_CONFIG_*` safe-directory variables - passed; 26 changed files, no impact-matrix violations.

## Approvals
- Human approval needed / obtained: current user approved the C2 task and supplied the stress-window rule. No approval was requested or obtained for adapter, promotion, demo, shadow, live, config-gate, or live strategy changes.

## Next action (single, concrete)
- Ask Claude to review E-026/H-007 and confirm C2/funding-carry family should stay shelved; only run C3 if the user wants the cheap Alternative.me ingest.

## Human Learning Notes
C2 did not merely lose its shiny Sharpe after costs; it failed the statistical gate outright. The remaining low modeled vol is also useful evidence: even a harsher vectorized hedge can stay unrealistically calm, so replay-engine realism is a separate future decision, not something to infer from this artifact.
