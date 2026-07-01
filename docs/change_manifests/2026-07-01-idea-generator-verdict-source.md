---
status: current
type: manifest
owner: codex
created: 2026-07-01
last_reviewed: 2026-07-01
expires: none
superseded_by: null
---

# Change Manifest: Idea Generator Verdict Source

## Summary
The B-taxonomy idea generator now reads occupied-family verdicts from
`docs/HYPOTHESIS_LEDGER.md` `Status` while keeping `docs/EXPERIMENT_REGISTRY.md`
as the source for trial and K-budget checks. It also skips inconclusive
no-twist families and overlay-only rows before drafting advisory sidecars.

## Business rule(s) affected
R6.3 and R7.4. This is a research-selection/trial-accounting guard; no money,
PnL, fee, funding, sizing, fill, or deployment behavior changed.

## Trigger area(s) (DOC_IMPACT_MATRIX)
A5 backtesting automation. A9 validation/gates was reviewed because the change
guards trial/K-budget selection behavior, but no deployment or DSR/PSR gate was
changed.

## Files changed
- `backtesting/pipeline_idea_generator.py` - separates hypothesis verdicts from
  experiment registry trial/K plumbing; adds inconclusive and overlay skips.
- `scripts/run_pipeline_idea_generator.py` - adds `--hypothesis-ledger` while
  preserving `--ledger` for `EXPERIMENT_REGISTRY`.
- `tests/unit/test_pipeline_idea_generator.py` - covers authoritative
  HYPOTHESIS status, inconclusive skip reason, overlay skip reason, CLI plumbing,
  and data-blocked continuity.
- `docs/INVARIANTS.md` - adds I28.
- `docs/FAILURE_MODES.md` - adds F23.
- `docs/FEATURE_MAP.md` - documents the idea-generator verdict source and
  overlay skip behavior.
- `results/idea_batch_20260701_taxonomy_002/` - new advisory sidecar batch only.

## Behavior delta
- Before: occupied-family skip logic could use taxonomy text or
  `EXPERIMENT_REGISTRY` outcome text as the verdict source, so inconclusive
  families and overlay-only rows could be drafted as fresh candidates.
- After: occupied-family verdicts come from `HYPOTHESIS_LEDGER.Status`;
  `refuted`/`shelved` without twist skip as `refuted_no_twist`,
  `inconclusive` without twist skips as `inconclusive_no_twist`, and overlay rows
  without base-family plumbing skip as `overlay_needs_base`.
- Money/risk impact: none. This affects advisory research sidecar selection
  before durable ledger append or backtesting.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A - no strategy assumption changed.
- config/: no gate or runtime config changed; `config/workstreams.yaml` is
  updated only to keep the Progress panel honest.
- ADR: N/A - this restores the documented research pipeline rule and does not
  alter promotion gates or result schema.

## Docs updated (from DOC_IMPACT_MATRIX row)
- [ ] `docs/DATA_FLOW.md` - confirmed unchanged; sidecar read/write path is
  unchanged.
- [x] `docs/FEATURE_MAP.md` - updated Strategy Research Pipeline Automation
  behavior notes.
- [x] `docs/INVARIANTS.md` - I28 added.
- [ ] `docs/GOLDEN_CASES.md` - confirmed unchanged; no golden trading case.
- [ ] ADR-0002/0005 - confirmed unchanged; no result schema or replay gate
  change.
- [ ] `docs/EXPERIMENT_REGISTRY.md` - confirmed unchanged; no experiment row or
  K-budget row changed.

## Invariants / golden cases
- Invariants checked: I28 added and covered by
  `tests/unit/test_pipeline_idea_generator.py`.
- Golden cases affected: N/A.

## Tests / checks run
- `pytest tests/unit/test_pipeline_idea_generator.py -q` - 13 passed; pytest
  cache write warned because `.pytest_cache` is not writable in this shell.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\run_pipeline_idea_generator.py --taxonomy docs\superpowers\specs\2026-06-30-mechanism-taxonomy.md --batch-id idea_batch_20260701_taxonomy_002` - passed; wrote the new advisory sidecar.
- `python scripts\run_pipeline_idea_generator.py --taxonomy docs\superpowers\specs\2026-06-30-mechanism-taxonomy.md --batch-id idea_batch_20260701_taxonomy_002` - failed before retry because the `python` shim could not start in this Windows session.
- `make docs-check` - not run; `make` is not installed in this Windows shell.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_doc_metadata.py` - passed, 0 warnings.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_feature_map_links.py` - passed, 166 concrete paths checked.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_doc_impact.py --strict` - script returned 0 but reported no changed files because its internal git subprocess lacks the `safe.directory` override in this sandbox.
- Direct `check_doc_impact.evaluate(...)` with the `git -c safe.directory=C:/quant_strategy` changed-file list - passed, no violations.

## Risks and rollback
- Risks: simple keyword twist detection can still only recognize `twist` or
  `轉折`; overlay rows remain skipped until a deterministic base-family contract
  exists.
- Rollback: revert this manifest, I28/F23 docs, the idea-generator code/CLI/test
  changes, and remove only `results/idea_batch_20260701_taxonomy_002/`.

## Approval
- Human approval required: no separate gate approval required; the user supplied
  the Claude-confirmed implementation task on 2026-07-01.
