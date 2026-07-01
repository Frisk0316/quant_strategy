---
status: current
type: manifest
owner: codex
created: 2026-07-01
last_reviewed: 2026-07-01
expires: none
superseded_by: null
---

# Change Manifest: Literature Idea Driver

## Summary
Added a research-only literature idea driver that orchestrates the existing
crypto-alpha-lab paper fetch, prompt firewall, static/callable scoring,
promotion, parent Stage 1 draft conversion, weekly screen output, and parent
`idea_batch.json` sidecar registration.

## Business rule(s) affected
R6.1, R6.3, and R7.4 reviewed. The driver enforces the literature prompt data
firewall, keeps literature drafts at `draft_status="pending_llm"` so they do
not mint families automatically, caps promoted drafts, and never appends durable
ledger rows. No money, PnL, fee, funding, sizing, fill, result-schema, or
deployment-gate behavior changed.

## Trigger area(s) (DOC_IMPACT_MATRIX)
A11 experiments/research runs. A5 backtesting automation and A9 validation/gates
were reviewed because the sidecar feeds the research pipeline and touches
trial/family-selection controls; no backtesting engine or validation gate
changed.

## Files changed
- `scripts/run_pipeline_literature_ideas.py` - new research-only literature
  driver and CLI.
- `tests/unit/test_pipeline_literature_ideas.py` - driver regression coverage.
- `docs/change_manifests/2026-07-01-literature-idea-driver.md` - this manifest.
- `docs/FEATURE_MAP.md` - maps the literature driver under research pipeline
  automation.
- `docs/AI_HANDOFF.md` - current session handoff.
- `docs/CURRENT_STATE.md` - current snapshot.
- `config/workstreams.yaml` - Progress panel state sync.

## Behavior delta
- Before: the lab A-half helpers existed, but there was no parent driver to run
  a bounded literature batch into parent advisory sidecars.
- After: a caller can run fixture/local-paper or keyless-source literature
  screening with static scores, write `weekly_screen/`, and register A-half
  `pending_llm` drafts into a new parent batch without family minting or durable
  ledger append.
- Money/risk impact: none. This is pre-backtest literature triage only and is
  not promotion or live-readiness evidence.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A - no strategy assumption changed.
- config/: no gate/runtime config changed; `config/workstreams.yaml` updated
  only to keep the Progress panel honest.
- ADR: N/A - no business rule, result schema, DB schema, or validation gate
  changed.

## Docs updated (from DOC_IMPACT_MATRIX row)
- [x] `docs/FEATURE_MAP.md` - updated Strategy Research Pipeline Automation
  script/test notes.
- [ ] `docs/DATA_FLOW.md` - confirmed unchanged; sidecar path remains
  `results/<batch_id>/` and no artifact schema changed.
- [ ] `docs/INVARIANTS.md` - confirmed unchanged; existing I27/I28 still govern
  family minting and idea selection boundaries.
- [ ] `docs/GOLDEN_CASES.md` - confirmed unchanged; no golden trading case.
- [ ] ADR-0002/0005 - confirmed unchanged; no result schema or replay gate
  change.
- [ ] `docs/HYPOTHESIS_LEDGER.md` / `docs/EXPERIMENT_REGISTRY.md` - confirmed
  unchanged; no durable ledger rows were appended.

## Invariants / golden cases
- Invariants checked: I27 and I28 remain in force; literature drafts stay
  `pending_llm` and do not call family minting.
- Golden cases affected: N/A.

## Tests / checks run
- `pytest tests/unit/test_pipeline_literature_ideas.py -q` - 7 passed; pytest
  cache write warned because `.pytest_cache` is not writable in this shell.
- `pytest research/crypto-alpha-lab/tests -q -p no:cacheprovider` - 16 passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\run_pipeline_literature_ideas.py --help` - passed.
- Temp fixture CLI smoke with `--papers`, `--scores`, `--ledger`,
  `--batch-id idea_batch_cli_smoke`, and temp `--output-root` - passed; wrote a
  temp-only `idea_batch.json` with one `A_literature` `pending_llm` candidate and
  `allow_live_trading=false`.
- `make docs-check` - not run; `make` is not installed in this Windows shell.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_doc_metadata.py` - passed, 0 warnings.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_feature_map_links.py` - passed, 168 concrete paths checked.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_doc_impact.py --strict` - script returned 0 but reported no changed files because its internal git subprocess lacks the `safe.directory` override in this sandbox.
- Direct `check_doc_impact.evaluate(...)` with the `git -c safe.directory=C:/quant_strategy` changed-file list - passed, no violations.

## Risks and rollback
- Risks: CLI scoring is deliberately static/file-backed unless a caller injects
  a scorer in Python; real LLM client wiring remains out of scope. The driver
  does not infer distinctness for literature ideas until Stage 1 supplies a
  signal.
- Rollback: remove the new driver, its unit test, this manifest, and the
  status-doc/workstream edits. Delete any newly generated literature batch
  sidecar created during verification.

## Approval
- Human approval required: no separate gate approval required for this
  research-only driver; user explicitly requested this Codex task on 2026-07-01.
