---
status: current
type: handoff
owner: human
created: 2026-07-11
last_reviewed: 2026-07-11
expires: none
superseded_by: null
---

# Context Handoff: Deribit Review Fixes and D4 Backfill - 2026-07-11

## Goal (one sentence)
Apply Claude review fixes R1-R5 for Deribit ingestion and complete the D4 option-flow full backfill through 2026-07-11.

## Current state
- Branch: codex/pipeline-batch1-stage3
- Last known good commit / state: working tree with unrelated pre-existing Turtle/OI/pipeline changes; no commit requested.
- In-progress edits (files): Deribit clients/scripts/tests, external-series API/frontend card, docs/runbook/state handoffs, and config/workstreams.yaml.
- What works right now: R1-R5 targeted tests pass; D4 option-flow full backfill completed through 2026-07-10 23:00 UTC for BTC and ETH with no >6h gaps.
- What does not work / unfinished: full `pytest tests/unit` has one unrelated Turtle UI unit failure in `tests/unit/test_backtest_visual_fallbacks.py::test_turtle_invest_pct_result_rows_use_fraction_unit`.

## Decisions made (and why)
- Hourly aggregate PIT convention is `observed_at = bucket_start` and `published_at = bucket_end` because downstream point-in-time consumers must not see aggregate values before the bucket closes.
- Checkpoints only advance `cursor_time` on successful chunks because failed chunks must resume from the last successful cursor.
- Option-flow backfill bounds must be UTC hour-aligned because the hourly aggregate writer and gap scanner are bucket-based.
- Empty option-flow chunks are allowed to advance because some Deribit history windows can legitimately contain no inverse option trades.
- USDC-linear option trades remain excluded in v1, but hours with only excluded rows emit an explicit exclusion marker row so data loss is visible.

## Open questions / unverified assumptions
- Premium-currency units: confirm with Claude whether inverse option premium aggregation should remain `premium * amount` in premium currency for v1 reporting.
- Endpoint deviations: no deviation from the reviewed endpoints was observed in this run; Claude should still review final implementation against research Section 1.
- History-host rate limits: no 429/10028 or persistent rate-limit blocks during full D4; largest observed days were BTC 63 pages/day on 2026-02-05 and ETH 37 pages/day on 2024-03-05.

## Rules in play (preserve verbatim)
- Invariants touched: PIT external aggregates must use `published_at` no earlier than the complete market event window.
- Domain rules touched: none in strategy/risk/PnL/fill semantics.
- Do-not-touch: strategies/signals/risk/portfolio/execution, `config/risk.yaml`, backtesting engine semantics, `results/**`, `research/`, existing migrations/schema, differential-validation implementation, and unrelated Turtle/OI dirty changes.

## Context to load next (the reading list)
- Source of truth: `tasks/2026-07-11-deribit-ingestion-review.md`, `tasks/2026-07-11-deribit-data-ingestion-tasks.md`, `research/deribit_data_strategy_research.md` Section 1-2.
- Owning files / MODULE_BRIEFS: `docs/FEATURE_MAP.md`, `docs/UI_MAP.md`, `docs/DATA_FLOW.md`, `docs/RUNBOOK.md`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run
- `pytest tests/unit -k "deribit" -q` -> 19 passed, 635 deselected, 1 warning.
- `pytest tests/unit` -> 653 passed, 1 unrelated Turtle UI failure, 1275 warnings.
- `node --check frontend\data.js` -> passed.
- `node --check frontend\view-config.js` -> passed.
- `python scripts/docs/check_doc_metadata.py` -> passed.
- `python scripts/docs/check_feature_map_links.py` -> passed.
- `python scripts/docs/check_doc_impact.py --strict` -> passed; no Change Manifest required.
- D4 backfill -> BTC 22126 rows, ETH 22125 rows, no >6h gaps, last bucket 2026-07-10T23:00:00+00:00.
- PIT scan -> dvol/optflow hourly datasets all have `bad_published_at = 0`.

## Approvals
- Human approval needed / obtained: user requested the review-fix order and D4 resume; no commit requested; Windows scheduled tasks were documented but not registered.

## Next action (single, concrete)
- Have Claude review the three flagged Deribit methodology topics, then the user can register the documented scheduled tasks if desired.

## Human Learning Notes
Deribit option-flow history can be slow but stable when chunked by day and throttled; preserving the last successful checkpoint cursor made the long run resumable without manual DB surgery. The main practical gotcha is that aggregate `published_at` semantics are easy to get subtly wrong: bucket-start labels look tidy but create a PIT leak unless consumers know the bucket is complete only at bucket end.
