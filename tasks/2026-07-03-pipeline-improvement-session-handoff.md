---
status: current
type: handoff
owner: human
created: 2026-07-03
last_reviewed: 2026-07-03
expires: none
superseded_by: null
---

# Session Handoff: Pipeline Improvement P1-P8 - 2026-07-03

## Implementation summary
Implemented the three requested waves from `tasks/2026-07-03-pipeline-improvement-tasks.md`: funding backfill/reprobe tooling, literature abstract/session-scoring hardening, Binance Vision OI parsing, refuted-family twist gating, feedback ranking tags/accounting, keyless OKX liquidation forward accumulation, advisory orchestrator reprobe, and per-batch funnel metrics.

## Diff scope
- Files added: `config/pipeline_feedback_tags.yaml`, `docs/change_manifests/2026-07-03-pipeline-improvements.md`, `scripts/market_data/backfill_universe_funding.py`, `scripts/market_data/download_binance_vision_metrics.py`, `scripts/run_pipeline_funnel_report.py`, `src/okx_quant/data/external_clients/okx_liquidation.py`, `tests/unit/test_backfill_universe_funding.py`, `tests/unit/test_binance_vision_metrics.py`, `tests/unit/test_ingest_external_liquidation.py`, `tests/unit/test_pipeline_funnel_report.py`, this handoff pair.
- Files changed: `.gitignore`, `backtesting/pipeline_idea_generator.py`, `backtesting/pipeline_orchestrator.py`, `config/workstreams.yaml`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `docs/DATA_FLOW.md`, `docs/FEATURE_MAP.md`, `docs/INVARIANTS.md`, `research/crypto-alpha-lab/src/crypto_alpha_lab/pipeline/paper_ingestion.py`, `research/crypto-alpha-lab/tests/test_pipeline_adapters.py`, `scripts/literature_keyword_scorer.py`, `scripts/market_data/ingest_external.py`, `scripts/run_pipeline_idea_generator.py`, `scripts/run_pipeline_literature_ideas.py`, `scripts/run_pipeline_orchestrator.py`, `src/okx_quant/data/external_clients/__init__.py`, and related unit tests.
- Files deleted: none.

## Business-rule change?
- Yes, governance/trial-accounting only. Change Manifest: `docs/change_manifests/2026-07-03-pipeline-improvements.md`; DOC_IMPACT_MATRIX rows reviewed: A5, A9, and data-provenance ingestion implications.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A, unchanged.
- config/: added `config/pipeline_feedback_tags.yaml`; no risk/settings/strategy/deployment gate changed.
- ADR: N/A, no major rule/policy/gate/schema change.

## Experiments
- HYPOTHESIS_LEDGER entries: none.
- EXPERIMENT_REGISTRY entries: none.

## Tests / checks run
- `python -m pytest tests/unit/test_pipeline_stage2_data_probe.py tests/unit/test_backfill_universe_funding.py tests/unit/test_literature_keyword_scorer.py tests/unit/test_pipeline_literature_ideas.py tests/unit/test_pipeline_idea_generator.py tests/unit/test_pipeline_orchestrator.py tests/unit/test_pipeline_checkpoint1_check.py tests/unit/test_ingest_external_liquidation.py tests/unit/test_external_clients.py tests/unit/test_binance_vision_metrics.py tests/unit/test_pipeline_funnel_report.py -q -p no:cacheprovider` -> 76 passed.
- `python -m pytest research/crypto-alpha-lab/tests -q -p no:cacheprovider` -> 18 passed.
- `python -m ruff check <touched Python files>` -> all checks passed.
- `python scripts/market_data/ingest_external.py --dataset liq_okx_btc --dry-run` -> OK.
- `python scripts/market_data/download_binance_vision_metrics.py --symbol BTCUSDT --start 2024-01-01 --end 2024-01-02 --dry-run` -> real public endpoint OK, 288 rows, no missing day, no DB write.
- `python -c "... OKXLiquidationClient(...).fetch(inst_type='SWAP', inst_id='BTC-USDT-SWAP', ...) ..."` -> real public OKX endpoint OK after switching to `uly`, 1600 recent rows.
- `python scripts/docs/check_doc_metadata.py` -> 0 warnings.
- `python scripts/docs/check_feature_map_links.py` -> 178 concrete paths checked.
- `python scripts/docs/check_doc_impact.py --strict` -> exit 0 but reported "no changed files detected", likely because the checker only sees staged diff in this workflow.
- `git diff --check` -> exit 0, only LF/CRLF warnings.
- `make docs-impact` -> not run; `make` is unavailable in this Windows sandbox.

## Docs updated
- `docs/INVARIANTS.md`, `docs/FEATURE_MAP.md`, `docs/DATA_FLOW.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `config/workstreams.yaml`, and Change Manifest.

## Known limitations / risks
- Real funding/OI/liquidation backfill and reprobe artifacts require DB/network access and were not generated here.
- Existing dirty `results/idea_batch_20260702_literature_001/hypothesis_ledger_draft.md` predates this run and remains outside this task's ownership.
- `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `STATUS.md`, `scripts/smoke/backtest_smoke.py`, and some maintenance docs had pre-existing or parallel unrelated changes from the M1-M5 stream.

## Rollback plan
- Revert the files listed in Diff scope for P1-P8; do not revert unrelated maintenance docs or pre-existing dirty result artifacts.

## Context Handoff
- See `tasks/2026-07-03-pipeline-improvement-context-handoff.md`.

## Questions for human review
- Should OKX-only liquidation REST be accepted for P5, with Binance liquidation collection deferred until a daemon/websocket decision?
- Should `stage2_pass_on_reprobe` remain the terminal advisory status name?
- Should session-scored `twist_evidence` stay in `PaperScoring.notes` as `twist_evidence=...`, or become a structured field in a later schema revision?

## Next recommended task
- Run DB/network-backed P1/P5/P8 ingest and advisory Stage2 reprobe, then ask Claude to review P1-P8 against the task file's acceptance criteria.

## Human Learning Notes (required)
The useful mental model is "unlock the inlet, do not touch the gates." P1-P8 improves what reaches review and how it is measured, but every promotion/live claim still depends on the old gates plus human approval. Also, on this Windows environment, `python` may resolve to the Microsoft Store shim; use the explicit Python 3.12 executable for reliable verification.
