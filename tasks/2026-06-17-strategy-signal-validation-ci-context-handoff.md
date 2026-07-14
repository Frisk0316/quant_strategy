---
status: archived
type: handoff
owner: codex
created: 2026-06-17
last_reviewed: 2026-06-17
expires: none
superseded_by: null
---

# Context Handoff: Strategy Signal Validation CI - 2026-06-17

## Goal (one sentence)
Promote the active-strategy fixture signal-validation batch into CI, then keep the next validation priority focused on real-data/source provenance before execution parity.

## Current state
- Branch: `feature/chart-ux-overhaul`.
- Last known good state: targeted differential-validation tests pass, docs checks pass, and `codex_ci_validation_20260617` produced PASS rows for all 9 active strategies.
- In-progress edits (files): `.github/workflows/ci.yml`, `Makefile`, `docs/RUNBOOK.md`, `docs/CURRENT_STATE.md`, `docs/CHANGELOG_AI.md`, `docs/KNOWN_ISSUES.md`, `docs/AI_HANDOFF.md`, plus this handoff pair.
- What works right now: CI has a `strategy-signal-validation` job that installs `.[dev,validation]` and runs `make strategy-signal-validation` with artifacts in runner temp storage.
- What does not work / unfinished: real-data/source-provenance validation is not implemented; full execution/PnL/funding parity remains out of scope.

## Decisions made (and why)
- Added a separate CI job instead of folding validation into unit tests, because validation dependencies are heavier than the base dev set.
- Added `VALIDATION_RESULTS_DIR`, because CI should not write generated validation artifacts into repo `results/`.
- Deferred execution parity, because signal fixtures and real-data provenance are cheaper gates and catch drift earlier.

## Open questions / unverified assumptions
- GitHub Actions dependency install time for `.[dev,validation]` is not yet observed remotely.
- Branch protection still needs a human decision on whether `strategy-signal-validation` is required.

## Rules in play (preserve verbatim)
- Invariants touched: I14, I15 as review constraints only; no business-rule behavior changed.
- Domain rules touched: R7 as a documentation boundary only; no promotion-gate rule changed.
- Do-not-touch: `src/okx_quant/strategies/`, `src/okx_quant/signals/`, `src/okx_quant/risk/`, `src/okx_quant/portfolio/`, `src/okx_quant/execution/`, `config/`, DB schema, deployment gates, existing result artifacts.

## Context to load next (the reading list)
- Source of truth: `AI_CONTEXT.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `docs/RUNBOOK.md`.
- Owning files / MODULE_BRIEFS: `docs/FEATURE_MAP.md` Validation / Promotion Gates; `.github/workflows/ci.yml`; `Makefile`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -c "<workflow yaml assertions>"` - passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/unit/test_all_strategy_signal_validation.py tests/unit/test_differential_validation.py -q` - 46 passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts/docs/check_doc_metadata.py` - passed with 11 pre-existing warnings.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts/docs/check_feature_map_links.py` - passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts/docs/check_doc_impact.py` - passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts/run_all_strategy_signal_validation.py --results-dir C:\Users\woody\AppData\Local\Temp\quant_strategy_ci_validation_20260617 --strategies all --batch-id codex_ci_validation_20260617` - all 9 rows PASS.
- `git -c safe.directory=C:/quant_strategy diff --check` - passed.
- `where.exe make` - failed locally; make is not installed in this Windows shell.

## Approvals
- Human approval obtained in chat: "好, 照你的優先級安排".

## Next action (single, concrete)
- Implement the smallest DB/canonical-candle real-data/source-provenance validation slice, keeping execution parity out of scope.

## Human Learning Notes
Fixture signal validation is now cheap enough to gate in CI, but it still proves only signal-point portability. The next useful confidence step is data/provenance, not a larger matching-engine project.
