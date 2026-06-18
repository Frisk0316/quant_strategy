---
status: current
type: handoff
owner: codex
created: 2026-06-17
last_reviewed: 2026-06-17
expires: none
superseded_by: null
---

# Context Handoff: Universal Price Chart - 2026-06-17

## Goal (one sentence)
Make the Backtest "Price + Trade Markers" card strategy-agnostic and render multi-symbol panels progressively.

## Current state
- Branch: `codex/fix-price-chart-universal`, created from `ff973e1`.
- Last known good commit / state: `ff973e1` has the coordination docs and price-chart task brief.
- In-progress edits (files): `frontend/view-backtest.js`, `docs/UI_MAP.md`, `docs/KNOWN_ISSUES.md`, `docs/AI_HANDOFF.md`, plus this handoff pair.
- What works right now: price chart panels render per selected symbol; loading/empty/error states are per panel; MA/EMA/MACD indicator gating remains technical-only.
- What does not work / unfinished: no browser-level interaction test exists for progressive chart loading.

## Decisions made (and why)
- Kept the fix frontend-only because the backend `price-series` route already falls back through `_fallback_price_series_from_result` for missing artifacts.
- Left indicator overlays behind `isTechnicalRun` because the task only generalized the base price chart.

## Open questions / unverified assumptions
- None for the scoped fix. Browser-level UI automation remains a known coverage gap.

## Rules in play (preserve verbatim)
- Do-not-touch: `backtesting/differential_validation.py`, ct_val provenance gate, trading-core strategy/signal/risk/portfolio/execution files, `config/risk.yaml`, existing `results/**` artifacts.
- No live-readiness claim; this is a UI review-surface fix only.

## Context to load next (the reading list)
- Source of truth: `tasks/2026-06-17-price-chart-universal-task.md`, `AI_CONTEXT.md`, `docs/AI_HANDOFF.md`.
- Owning files / MODULE_BRIEFS: `docs/FEATURE_MAP.md` Backtest Result Charts, `docs/UI_MAP.md`, `docs/DATA_FLOW.md`.
- Context Pack: no price-chart-specific pack exists; only `docs/CONTEXT_PACKS/harness-scaffolding.md` exists and was read for harness rules.

## Checks run
- Static RED check for global price-card loading gate - failed before edit, passed after edit.
- Direct frontend syntax sweep equivalent to `make frontend-check` - passed (`make` itself unavailable).
- `tests/unit/test_frontend_static_mime.py` + `tests/unit/test_backtest_visual_fallbacks.py` - 13 passed, 1 sandbox cache warning.
- Docs metadata/link scripts - passed with pre-existing metadata warnings.

## Approvals
- Human approval obtained in task prompt for branch creation and scoped implementation.

## Next action (single, concrete)
- Have Claude/human review the small `frontend/view-backtest.js` diff for UI behavior and scope.

## Human Learning Notes
The freeze was not caused by a missing backend route or technical-strategy gate. It was the UI's all-or-nothing card gate: one pending selected symbol hid panels that had already loaded.
