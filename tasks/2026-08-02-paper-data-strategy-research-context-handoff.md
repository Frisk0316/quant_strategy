---
status: current
type: handoff
owner: codex
created: 2026-08-02
last_reviewed: 2026-08-02
expires: none
superseded_by: null
---

# Context Handoff: free-data, papers, and limited-probe research — 2026-08-02

## Goal (one sentence)

Expand useful free research data, test paper-motivated strategies under the
project's frozen gates, and deliver an auditable classification and roadmap.

## Current state

- Branch: `feature/deribit-moneyness-hypotheses`.
- Last known good commit / state: `0e5eec5`; the working tree already contained unrelated concurrent-session edits and remains uncommitted.
- In-progress edits (files): none for this task; generated results and reports are complete.
- What works right now: Wikimedia/Coin Metrics adapters and registrations; duplicate-safe external ingestion; explicit pre-DB power breadth; immutable seven-candidate probe artifacts; governance reconciliation; Markdown and verified portable HTML report.
- What does not work / unfinished: no new candidate is eligible for Stage 3 or deployment; Coin Metrics commercial licensing is unresolved; daily USDT reference data cannot resolve severe depeg events; OKX exact-venue candles/funding remain incomplete for future cross-venue work.

## Decisions made (and why)

- Treat all seven new candidates as governance-effective Stage-2 stops — ADR-0013 requires independently justified breadth, and breadth=1 makes H-041/H-045/H-046 fail power.
- Preserve the mechanically generated Stage-3 artifacts and count one observed family trial for each — seen selection information cannot be erased, even though it is inadmissible gate evidence.
- Do not rerun the frozen probe — its result is already observed and the pre-run receipt is intentionally stale after result/audit updates.
- Call 13,347 the selected task-attributable unique-row subtotal, not the day's/project's total — parallel workstreams also wrote data.
- Keep H-040/H-043/H-044 exact specs stopped, H-042 data-inconclusive, and H-041/H-045/H-046 as data/mechanism directions only.
- Retain H-014 as research/shadow only and prior H-023 as the closest governance-valid Stage-2 power gap; neither is live-ready.

## Open questions / unverified assumptions

- Coin Metrics Community non-commercial terms must be reviewed before product/commercial use → H-041/H-042.
- H-041 needs a breadth=1 forward power design and more independent history/security-factor data before any retry → H-041.
- H-045 needs a longer revision-aware event history and attribution frozen before retry → H-045.
- H-042 needs exchange-specific minute-level event feasibility before another strategy test → H-042.

## Rules in play (preserve verbatim)

- I62: external macro/event values are unusable before stored `published_at`; derived targets affect PnL/funding/turnover/cost no earlier than t+1; bounded calendar carry and eligible-calendar coverage are explicit.
- I63: paginated adapters and the shared store emit/reconcile one durable `(dataset_id, observed_at)` key with deterministic last-row-wins accounting.
- I64: Stage-2 power breadth is an explicit finite positive candidate input validated before DB access and never inferred from active legs or position count.
- Domain rules touched: R3.1-R3.4, R5.3, R6.1-R6.4, R6.8-R6.9, R7.4.
- Do-not-touch: `research/`; immutable `results/paper_data_limited_probe_20260802/`; live/demo/shadow/promotion gates; H-038 terminal K without explicit authorization; unrelated dirty worktree files.

## Context to load next (the reading list)

- Source of truth: `AI_CONTEXT.md`, `docs/ai_collaboration.md`, `research/strategy_synthesis.md`, `docs/backtest_live_parity_plan.md`, `config/`.
- Owning files / MODULE_BRIEFS: `docs/FEATURE_MAP.md`, `backtesting/paper_signal_probe.py`, `scripts/run_paper_signal_limited_probe.py`, `src/okx_quant/data/external_clients/`, `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md`.
- Governance: `docs/ADR/0013-statistical-power-and-trial-accounting.md`, `docs/ADR/0016-autonomous-strategy-finding-loop.md`, `tasks/2026-08-02-paper-data-limited-probe-governance-audit.md`.
- Evidence: `reports/2026-08-02-paper-data-strategy-research.md`, portable `report.html`, and `results/paper_data_limited_probe_20260802/limited_probe_report.json`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run

- Targeted four-file pytest suite — 24 passed.
- Targeted Ruff — passed.
- Config validation — passed.
- Docs metadata, feature-map links, ledger consistency, and doc-impact — passed; two pre-existing metadata warnings.
- Backtest smoke — passed; idealized fixture explicitly not promotion evidence.
- Portable report verification — passed: 21 blocks, 2 charts, 5 tables, 3 metrics; 1440/390 viewports and source keyboard interaction.

## Approvals

- Human approval obtained for broad research, free-data download, DB ingestion, and backtesting through the 2026-08-02 goal request.
- No approval obtained for H-038 terminal K use, strategy promotion, demo/shadow activation changes, or live trading.

## Next action (single, concrete)

- Continue the already-approved H-014 shadow/parity evidence path without changing gates; separately design any H-041/H-045 retry from breadth=1 power requirements before collecting more data.

## Human Learning Notes

The most important surprise was governance, not performance: counting BTC and
ETH legs as two independent bets lowered the MDS enough to expose three
ineligible Stage-3 results. Active legs are not statistical breadth. Also,
`data_quality_events=0` means no events were recorded, and durable DB unique
keys—not API/job counts—must anchor ingestion totals. The portable report tool's
`100vw` top bar also needs a Windows classic-scrollbar override; the delivered
HTML contains that one-line compatibility fix and passes the original verifier.
