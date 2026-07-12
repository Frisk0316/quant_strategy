---
status: current
type: handoff
owner: codex
created: 2026-07-05
last_reviewed: 2026-07-05
expires: none
superseded_by: null
---

# Context Handoff: F-OI-POSITIONING Stage-2 Universe OI Probe - 2026-07-05

## Goal (one sentence)
Complete the user-directed Binance Vision OI backfill and PIT-aware Stage-2 data probe prerequisite for H-012 / F-OI-POSITIONING.

## Current state
- Branch: `codex/pipeline-batch1-stage3`.
- Last known good state: focused tests and pipeline/docs checks passed on 2026-07-05.
- In-progress edits: OI downloader/probe implementation, tests, registry/ledger/current-state docs, workstream status, this handoff.
- What works right now: Binance Vision OI datasets are backfilled for the PIT universe where native zips exist; E-036 artifact reports data availability PASS with 31 OI-good symbols.
- What does not work / unfinished: `SHIB-USDT-SWAP` has no native `SHIBUSDT` Binance Vision metrics zips; Stage-3 distinctness, WF/CPCV, checkpoint, and promotion gates have not run.

## Decisions made (and why)
- Generalized OI dataset ids as `oi_binance_hist_<base>` instead of maintaining a large static mapping, because the convention is deterministic and already used by the spec.
- Kept the original BTC/ETH fixed-window `probe_oi()` path, because E-034 should remain reproducible and untouched.
- Added `probe_oi_universe()` for orchestration/data-probe runs, because Task A needs PIT eligible-day coverage and the `>=10` good-symbol gate.

## Open questions / unverified assumptions
- Whether `SHIB-USDT-SWAP` should be represented by `1000SHIBUSDT` for this hypothesis is a research/spec question. Current implementation treats them as separate native Binance markets and records `SHIBUSDT` as a data gap.

## Rules in play (preserve verbatim)
- Invariants touched: I20 point-in-time universe membership; I29 pipeline orchestration state/probe behavior.
- Domain rules touched: R6.1/R6.2 data provenance and leakage; R6.3 trial count remains 0 for data probes.
- Do-not-touch: `research/`, `src/okx_quant/strategies/`, `signals/`, `risk/`, `portfolio/`, `execution/`, existing results artifacts, live/demo/shadow gates.

## Context to load next (the reading list)
- Source of truth: `docs/superpowers/specs/2026-07-04-f-oi-positioning-hypothesis.md`, `tasks/2026-07-04-f-oi-positioning-stage3-codex-plan.md`, `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md`.
- Owning files / MODULE_BRIEFS: `scripts/market_data/download_binance_vision_metrics.py`, `backtesting/pipeline_stage2_registry.py`, `scripts/run_pipeline_stage2_data_probe.py`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run
- `python -m pytest -p no:cacheprovider tests/unit/test_binance_vision_metrics.py tests/unit/test_pipeline_stage2_data_probe.py tests/unit/test_pipeline_stage2_registry.py -q` - 15 passed.
- `python -m pytest -p no:cacheprovider tests/unit -k "stage2 or vision or pipeline" -q` - 108 passed, 504 deselected.
- `python scripts/run_pipeline_stage2_data_probe.py --candidate oi --output-root results/stage2_probe_20260705_oi_universe --universe-path data/universe/universe_membership.parquet` - data_availability PASS, 31/10 good symbols.
- `python scripts/docs/check_doc_metadata.py` - passed, 0 warnings.
- `python scripts/docs/check_feature_map_links.py` - passed, 194 paths.
- `python scripts/validate_pipeline.py --check-config-only` - passed.
- `python scripts/docs/check_doc_impact.py --strict` - returned "no changed files detected"; treat as limited in this sandbox.

## Approvals
- Human approval obtained through tool approvals for escalated Binance Vision network backfills. No live/demo/shadow approval requested or needed.

## Next action (single, concrete)
- Start Task B by running the family-minting preflight for the constructed OI-fade signal vs the F-FUNDING-XS-DISPERSION reference; stop if ASSIGN/SKIP_RECOMMENDED.

## Human Learning Notes
Binance Vision has `1000SHIBUSDT` metrics but no `SHIBUSDT` metrics for the PIT span, so "base symbol" naming can hide native-market differences. Keep native dataset identity explicit in specs and reports.
