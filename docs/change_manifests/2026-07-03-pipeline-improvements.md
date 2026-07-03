---
status: current
type: manifest
owner: codex
created: 2026-07-03
last_reviewed: 2026-07-03
expires: none
superseded_by: null
---

# Change Manifest: Pipeline Improvement P1-P8

## Summary
Implemented advisory research-pipeline inlet improvements from `tasks/2026-07-03-pipeline-improvement-tasks.md`: funding backfill tooling, literature abstract/session-scoring gates, refuted-family twist gating, feedback ranking tags, keyless liquidation forward accumulation, Stage2 reprobe advisories, funnel metrics, and Binance Vision historical OI ingestion.

## Business rule(s) affected
R6.3 and R7.4 governance/trial-accounting controls only. No PnL, fee, funding-cashflow sign, sizing, fill, DSR/PSR threshold, promotion, demo, shadow, or live rule changed.

## Trigger area(s) (DOC_IMPACT_MATRIX)
A5 backtesting / research pipeline automation; A9 validation/governance state; data-provenance ingestion paths adjacent to A4/A6 behavior but without config gate or schema changes.

## Files changed
- `backtesting/pipeline_idea_generator.py`, `backtesting/pipeline_orchestrator.py` - feedback tags, advisory reprobe, and funnel metrics.
- `scripts/run_pipeline_idea_generator.py`, `scripts/run_pipeline_literature_ideas.py`, `scripts/run_pipeline_orchestrator.py`, `scripts/run_pipeline_funnel_report.py` - CLI entrypoints and sidecar metrics.
- `scripts/literature_keyword_scorer.py`, `research/crypto-alpha-lab/src/crypto_alpha_lab/pipeline/paper_ingestion.py` - abstract/cache/search-log/review-bundle literature inlet.
- `scripts/market_data/backfill_universe_funding.py`, `scripts/market_data/download_binance_vision_metrics.py`, `scripts/market_data/ingest_external.py`, `src/okx_quant/data/external_clients/okx_liquidation.py` - funding/OI/liquidation ingestion tools.
- `config/pipeline_feedback_tags.yaml` - Claude/human-owned feedback tag input consumed by generator.
- Tests under `tests/unit/` plus `research/crypto-alpha-lab/tests/test_pipeline_adapters.py`.

## Behavior delta
- Before: literature selection could be title/placeholder driven, refuted-family literature needed no explicit twist, cross-round feedback was not implemented, Stage2 reprobes required manual reruns, no per-batch funnel sidecar existed, and OI/liquidation unlocks were recent-window or absent.
- After: selection requires abstract/session scoring, refuted/shelved families require LLM `twist_evidence`, feedback tags only demote ranking and mark `feedback_spawned`, reprobes are advisory-only, batches emit `funnel_metrics.json`, public Binance Vision OI history can be parsed, OKX liquidation data can be forward-accumulated, and funding can be backfilled across the PIT universe before Stage2 reprobe.
- Money/risk impact: none. No strategy, risk, portfolio, execution, or deployment gate behavior changed.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A; no strategy assumption change.
- config/: added `config/pipeline_feedback_tags.yaml` only; no risk/settings/strategy/deployment gate change.
- ADR: N/A; no major rule/policy change or schema/gate change.

## Docs updated (from DOC_IMPACT_MATRIX row)
- [x] `docs/INVARIANTS.md` - added I30 for feedback ranking/accounting.
- [x] `docs/FEATURE_MAP.md` - pipeline and ingestion ownership updated.
- [x] `docs/DATA_FLOW.md` - external observation/funding/research-pipeline flows updated.
- [x] `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `config/workstreams.yaml` - pipeline P1-P8 state noted without removing parallel maintenance state.
- [x] `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md` - reviewed/read-only; no experiment or durable hypothesis row was appended.

## Invariants / golden cases
- Invariants checked: I26, I28, I29, I30.
- Golden cases affected: N/A.

## Tests / checks run
- `python -m pytest tests/unit/test_pipeline_stage2_data_probe.py tests/unit/test_backfill_universe_funding.py tests/unit/test_literature_keyword_scorer.py tests/unit/test_pipeline_literature_ideas.py tests/unit/test_pipeline_idea_generator.py tests/unit/test_pipeline_orchestrator.py tests/unit/test_pipeline_checkpoint1_check.py tests/unit/test_ingest_external_liquidation.py tests/unit/test_external_clients.py tests/unit/test_binance_vision_metrics.py tests/unit/test_pipeline_funnel_report.py -q -p no:cacheprovider` - 76 passed.
- `python -m pytest research/crypto-alpha-lab/tests -q -p no:cacheprovider` - 18 passed.
- `python -m ruff check <touched Python files>` - all checks passed.
- Public endpoint smokes: Binance Vision BTCUSDT 2024-01-01 dry-run parsed 288 rows; OKX liquidation BTC-USDT-SWAP fetch returned 1600 recent rows.
- Docs checks: metadata 0 warnings; feature-map links 178 paths checked; `check_doc_impact.py --strict` exited 0 but reported no changed files detected; `make docs-impact` unavailable in this Windows sandbox.

## Risks and rollback
- Risks: live HTTP endpoint schemas may drift; OKX liquidation REST may expose only a short recent window; true DB-backed funding/OI/liquidation artifacts still require reachable DB and network.
- Rollback: revert the files listed above plus this manifest and I30.

## Approval
- Human approval required: yes for live/demo/shadow/promotion use; not requested or obtained. These changes are advisory research-pipeline tooling only.
