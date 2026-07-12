---
status: current
type: handoff
owner: human
created: 2026-07-03
last_reviewed: 2026-07-03
expires: none
superseded_by: null
---

# Context Handoff: Pipeline Improvement P1-P8 - 2026-07-03

## Goal (one sentence)
Complete `tasks/2026-07-03-pipeline-improvement-tasks.md` P1-P8 without changing strategy assumptions, deployment gates, durable ledgers, or existing result artifacts.

## Current state
- Branch: `codex/pipeline-batch1-stage3`.
- Last known good commit / state: pre-existing maintenance commits `df96682` and `79c1ddc`; working tree has unrelated maintenance docs changes plus this P1-P8 implementation.
- In-progress edits (files): pipeline automation, literature ingestion/scoring, external observations ingestion, new market-data utilities, tests, docs sync, and handoff files.
- What works right now: unit/mock coverage for P1-P8 is green for the commands recorded in the session handoff; `ingest_external.py --dataset liq_okx_btc --dry-run` works; feedback tags are fail-safe for missing files and fail-closed for bad schema; orchestrator `--reprobe` is advisory-only.
- What does not work / unfinished: real DB/network funding backfill, Binance Vision ingest, OKX liquidation ingest, and Stage2 reprobe artifacts were not produced in this environment.

## Decisions made (and why)
- Use `config/pipeline_feedback_tags.yaml` as a Claude/human-owned input because task P4 requires machine consumption but not automatic modification.
- Keep feedback tags as rank penalties only because P4 forbids eligibility/cap/gate bypass.
- Use built-in `liq_okx_btc` / `liq_okx_eth` dataset entries in `ingest_external.py` because P5 permitted dispatch changes but did not explicitly permit editing `config/external_data.yaml`.
- Use Binance Vision metrics as a standalone ingestion script because P8 replaces the paid historical OI idea with public dump parsing and schema validation.

## Open questions / unverified assumptions
- Whether OKX `public/liquidation-orders` reliably accepts `instId` for BTC/ETH in live network calls.
- Whether Binance Vision metrics schema remains exactly the expected 8 columns for current BTCUSDT daily zips.
- Whether a DB-backed P1 funding backfill changes Stage2 data feasibility; no DB run happened here.

## Rules in play (preserve verbatim)
- Invariants touched: I26 checkpoint summaries must reconcile family/CPCV `n_trials` to registry; I28 B-taxonomy uses `docs/HYPOTHESIS_LEDGER.md` status for occupied-family verdicts; I29 orchestrator state is append-only and does not write durable ledgers; I30 feedback tags only affect ranking and must preserve family trial accounting.
- Domain rules touched: R6.3, R7.4 governance/trial-accounting only.
- Do-not-touch: `src/okx_quant/strategies/`, `src/okx_quant/signals/`, `src/okx_quant/risk/`, `src/okx_quant/portfolio/`, `src/okx_quant/execution/`, `config/risk.yaml`, deployment/demo/shadow/live gates, `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md`, `research/strategy_synthesis.md`, and existing `results/**` artifacts.

## Context to load next (the reading list)
- Source of truth: `tasks/2026-07-03-pipeline-improvement-tasks.md`, `research/strategy_synthesis.md`, `docs/backtest_live_parity_plan.md`, `config/`, `docs/INVARIANTS.md`.
- Owning files / MODULE_BRIEFS: `docs/FEATURE_MAP.md`, `docs/DATA_FLOW.md`, `docs/CONTEXT_PACKS/harness-scaffolding.md`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run
- See session handoff for the full command list and results.

## Approvals
- Human approval needed / obtained: no deployment/live/promotion approval requested or obtained; changes are advisory tooling only.

## Next action (single, concrete)
- Run a DB/network-backed P1 funding backfill and P8/P5 external-observation ingest in an environment with TimescaleDB and internet access, then run advisory Stage2 reprobe and hand artifacts to Claude for acceptance review.

## Human Learning Notes
The hard boundary held: inlet quality can improve without weakening statistical or deployment gates. The practical blocker is no longer code shape for P1-P8, but environment-backed evidence: DB/network runs are now the difference between "implemented and mock-verified" and "accepted with artifacts."
