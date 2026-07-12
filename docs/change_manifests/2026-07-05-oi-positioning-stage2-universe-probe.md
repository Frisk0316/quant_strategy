---
status: current
type: manifest
owner: codex
created: 2026-07-05
last_reviewed: 2026-07-05
expires: none
superseded_by: null
---

# Change Manifest: F-OI-POSITIONING Stage-2 Universe Probe

## Summary
Generalized the Binance Vision historical OI downloader and Stage-2 probe from the BTC/ETH seed datasets to PIT-universe OI datasets for H-012 / F-OI-POSITIONING. This records data availability only; it does not run a strategy or change any trading gate.

## Business rule(s) affected
None, mechanical data-probe plumbing only. Data provenance rules R6.1/R6.2 were checked and remain unchanged.

## Trigger area(s) (DOC_IMPACT_MATRIX)
A5 (`backtesting/`) because `backtesting/pipeline_stage2_registry.py` changed. A11 experiments/research run docs were also updated.

## Files changed
- `backtesting/pipeline_stage2_registry.py` — add PIT-aware OI universe coverage check and orchestration path while preserving fixed BTC/ETH `probe_oi()`.
- `scripts/market_data/download_binance_vision_metrics.py` — derive `oi_binance_hist_<base>` dataset ids and first PIT-eligible start dates.
- `scripts/run_pipeline_stage2_data_probe.py` — re-export the new OI universe probe helper.
- `tests/unit/test_binance_vision_metrics.py`, `tests/unit/test_pipeline_stage2_data_probe.py`, `tests/unit/test_pipeline_stage2_registry.py` — cover dataset id derivation, PIT start dates, OI-good gate, and registry wiring.
- `docs/EXPERIMENT_REGISTRY.md`, `docs/HYPOTHESIS_LEDGER.md` — record E-036 and H-012 state.
- `docs/FEATURE_MAP.md`, `docs/DATA_FLOW.md` — keep feature/data-path docs current.
- `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `config/workstreams.yaml` — keep current state and Progress panel honest.

## Behavior delta
- Before: F-OI-POSITIONING Stage-2 OI coverage only evaluated fixed BTC/ETH datasets over one fixed window.
- After: `run_pipeline_stage2_data_probe.py --candidate oi` evaluates all PIT-eligible universe symbols using `oi_binance_hist_<base>` datasets and per-symbol eligible days, requiring at least 10 OI-good symbols.
- Money/risk impact: none. No PnL, fees, funding cashflow, sizing, fills, risk, config gates, strategy code, demo/shadow/live behavior, or existing artifacts changed.

## Source-of-truth updates
- `research/strategy_synthesis.md`: N/A — research ownership untouched.
- `config/`: `config/workstreams.yaml` status text only; no strategy/risk/settings behavior changed.
- ADR: N/A — no rule or schema decision changed.

## Docs updated (from DOC_IMPACT_MATRIX row)
- [x] `docs/DATA_FLOW.md` — updated historical OI ingestion/provenance path.
- [x] `docs/FEATURE_MAP.md` — updated Strategy Research Pipeline Automation / F-OI Stage-2 description.
- [x] `docs/GOLDEN_CASES.md` — confirmed unchanged; no golden-case behavior changed.
- [x] `docs/INVARIANTS.md` — confirmed unchanged; I20/I29 remain applicable and tests cover the probe path.
- [x] ADR-0002/ADR-0005 — confirmed unchanged; no result schema or validation-gate rule changed.
- [x] `docs/KNOWN_ISSUES.md` — confirmed unchanged; the SHIB native OI gap is recorded in E-036/H-012 instead of durable backlog because 31/10 data gate passes.
- [x] `docs/EXPERIMENT_REGISTRY.md` — E-036 added.
- [x] `docs/HYPOTHESIS_LEDGER.md` — H-012 updated.

## Invariants / golden cases
- Invariants checked: I20, I29; R6.1/R6.2 provenance/leakage reviewed.
- Golden cases affected: N/A.

## Tests / checks run
- `python -m pytest -p no:cacheprovider tests/unit/test_binance_vision_metrics.py tests/unit/test_pipeline_stage2_data_probe.py tests/unit/test_pipeline_stage2_registry.py -q` — 15 passed.
- `python -m pytest -p no:cacheprovider tests/unit -k "stage2 or vision or pipeline" -q` — 108 passed, 504 deselected.
- `python scripts/run_pipeline_stage2_data_probe.py --candidate oi --output-root results/stage2_probe_20260705_oi_universe --universe-path data/universe/universe_membership.parquet` — data_availability PASS, 31/10 good symbols.
- `python scripts/docs/check_doc_metadata.py` — passed, 0 warnings.
- `python scripts/docs/check_feature_map_links.py` — passed, 194 paths.
- `python scripts/validate_pipeline.py --check-config-only` — passed.

## Risks and rollback
- Risks: native-symbol ambiguity (`SHIBUSDT` vs `1000SHIBUSDT`) could be misread by later strategy code if not preserved as a data gap.
- Rollback: revert this manifest plus the listed code/test/docs files and remove only the new E-036 result artifact if explicitly requested. Do not mutate existing artifacts.

## Approval
- Human approval required: no for code/docs/probe plumbing; escalated network approvals were obtained through the tool for Binance Vision backfills. Live/demo/shadow approval not requested or applicable.
