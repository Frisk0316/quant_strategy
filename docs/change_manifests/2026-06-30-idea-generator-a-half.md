---
status: current
type: manifest
owner: codex
created: 2026-06-30
last_reviewed: 2026-06-30
expires: none
superseded_by: null
---

# Change Manifest: Idea Generator A-Half Literature Adapter

## Summary
Added the research-lab A-half automation for paper metadata ingestion, validated
paper scoring, candidate promotion, weekly screen output, and conversion from a
lab `AlphaCandidate` into a parent Stage 1 draft.

## Business rule(s) affected
R6.1, R6.3, and R7.1 reviewed. The implementation adds a prompt data firewall,
keeps `allow_live_trading=false`, and routes candidates through parent sidecars;
it does not change strategy assumptions, trial-count rules, PnL, execution, or
promotion gates.

## Trigger area(s) (DOC_IMPACT_MATRIX)
A5 backtesting for the parent merge hook; research-lab helper code is
research-only and does not alter trading-core behavior.

## Files changed
- `research/crypto-alpha-lab/src/crypto_alpha_lab/pipeline/paper_ingestion.py` - paper fetch/score/promote helpers.
- `research/crypto-alpha-lab/src/crypto_alpha_lab/pipeline/__init__.py` - exports pipeline helpers.
- `research/crypto-alpha-lab/src/crypto_alpha_lab/adapters/parent_stage1.py` - `AlphaCandidate` to parent draft adapter.
- `research/crypto-alpha-lab/src/crypto_alpha_lab/adapters/__init__.py` - exports adapter.
- `research/crypto-alpha-lab/tests/test_pipeline_adapters.py` - focused lab coverage.
- `backtesting/pipeline_idea_generator.py` - accepts A-half drafts in the same sidecar batch.
- `docs/change_manifests/2026-06-30-idea-generator-a-half.md` - this manifest.

## Behavior delta
- Before: crypto-alpha-lab had schemas and fixtures but no working paper to parent-draft automation.
- After: public arXiv metadata can be parsed, validated scores can be promoted
  to research-only candidates, dated weekly screen files can be written, and
  parent Stage 1 drafts can be included in `idea_batch.json`.
- Money/risk impact: none. This is literature triage only and cannot trade or
  claim live readiness.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A - no strategy assumption changed.
- config/: N/A - no runtime or gate config changed.
- ADR: N/A - no business rule, result schema, or promotion gate changed.

## Docs updated (from DOC_IMPACT_MATRIX row)
- [x] `docs/superpowers/pipeline/stage1-hypothesis.md` - documents the literature data firewall.
- [x] `docs/FEATURE_MAP.md` - reviewed; no edit because this is research-lab plumbing, not a UI/user feature.
- [x] `docs/DATA_FLOW.md` - reviewed; no edit because lab screen files and parent sidecars are pre-backtest advisory artifacts.
- [x] `docs/GOLDEN_CASES.md` - reviewed; no edit because no golden trading case changed.
- [x] `docs/INVARIANTS.md` - reviewed; existing I13/I27 apply once drafts are reviewed into the parent ledger.
- [x] ADR-0002/ADR-0005 - reviewed; no edit because no backtest result schema or validation gate changed.

## Invariants / golden cases
- Invariants checked: I13/I14/I15/I27 remain in force.
- Golden cases affected: N/A.

## Tests / checks run
- `& 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' -m pytest tests\test_pipeline_adapters.py -q -p no:cacheprovider` - 4 passed.
- `(lab) & 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' -m pytest -q -p no:cacheprovider` - 12 passed.
- `& 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' -m ruff check <new idea-generator/lab files>` - passed.
- `& 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' scripts\docs\check_doc_metadata.py` - passed with 32 pre-existing metadata warnings.
- `& 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' scripts\docs\check_feature_map_links.py` - passed: 154 concrete paths checked.
- `check_doc_impact.py --strict` via the same Python interpreter plus process-local `safe.directory` git config - passed: 43 changed files, no impact-matrix violations.
- `make docs-check` - not available in this Windows shell (`make` command not found); direct Python scripts were run instead.

## Risks and rollback
- Risks: keyless metadata only, from arXiv + Semantic Scholar + Crossref (the
  latter two cover SSRN / NBER / RePEc / journal DOIs); paid full-text and
  direct-scrape corpus ingestion remain out of scope. Scoring unscored papers
  still requires a caller-provided scorer.
- Rollback: remove the lab pipeline helper, adapter, lab test, parent merge-hook
  support for A-half drafts, and this manifest.

## Approval
- Human approval required: no for research-lab sidecar automation; yes before
  any literature-derived draft enters the durable hypothesis ledger or a trading workflow.
