---
status: current
type: handoff
owner: codex
created: 2026-06-30
last_reviewed: 2026-06-30
expires: none
superseded_by: null
---

# Session Handoff: Family-Minting K-Budget + First Idea Sidecar — 2026-06-30

## Implementation summary
Wired the family-minting checker to the real Family K-budget table, removed the
stale `inherited_K = inherited_n_trials` proxy, fixed direct execution of the
idea-generator CLI, and generated the first taxonomy-only advisory idea sidecar.
No durable hypothesis/experiment ledger row was appended and no backtest was run.

## Diff scope
- Files added:
  - `docs/change_manifests/2026-06-30-family-minting-k-budget.md`
  - `tasks/2026-06-30-family-minting-k-budget-sidecar-context-handoff.md`
  - `tasks/2026-06-30-family-minting-k-budget-sidecar-session-handoff.md`
- Files changed:
  - `backtesting/pipeline_checkpoint1.py`
  - `backtesting/pipeline_family_minting.py`
  - `scripts/run_pipeline_idea_generator.py`
  - `tests/unit/test_pipeline_family_minting.py`
  - `tests/unit/test_pipeline_idea_generator.py`
  - `docs/FEATURE_MAP.md`
  - `docs/KNOWN_ISSUES.md`
  - `docs/AI_HANDOFF.md`
  - `docs/CURRENT_STATE.md`
  - `config/workstreams.yaml`
- Files deleted: none.

## Business-rule change?
- Yes, advisory validation/governance wiring under R6.3/R7.4. Change Manifest:
  `docs/change_manifests/2026-06-30-family-minting-k-budget.md`.
  DOC_IMPACT_MATRIX checked: A5 backtesting workflow; A9 validation/gates
  reviewed via manifest.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A - no strategy assumption changed.
- config/: `config/workstreams.yaml` updated for Progress panel honesty only.
- ADR: N/A - no result schema, DB schema, promotion gate, or business rule changed.

## Experiments
- HYPOTHESIS_LEDGER entries: none.
- EXPERIMENT_REGISTRY entries: none.
- Generated advisory sidecar:
  `results/idea_batch_20260630_taxonomy_001/idea_batch.json` and
  `results/idea_batch_20260630_taxonomy_001/hypothesis_ledger_draft.md`.

## Tests / checks run
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_pipeline_family_minting.py -q` — red first: 3 failed for missing `k_used`; green after fix: 8 passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_pipeline_family_minting.py tests\unit\test_pipeline_checkpoint1_check.py -q` — 13 passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_pipeline_idea_generator.py::test_idea_generator_script_runs_from_repo_root -q` — red first for `ModuleNotFoundError: backtesting`; green after fix: 1 passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_pipeline_idea_generator.py -q` — 6 passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_pipeline_family_minting.py tests\unit\test_pipeline_checkpoint1_check.py tests\unit\test_pipeline_idea_generator.py -q` — 19 passed, pytest cache warning only.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m ruff check backtesting\pipeline_checkpoint1.py backtesting\pipeline_family_minting.py scripts\run_pipeline_idea_generator.py tests\unit\test_pipeline_family_minting.py tests\unit\test_pipeline_idea_generator.py` — passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_doc_metadata.py` — passed with 32 pre-existing warnings.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_feature_map_links.py` — passed, 166 paths.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_human_overview.py` — passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\validate_pipeline.py --check-config-only` — passed.
- `check_doc_impact.py --strict` with process-local `safe.directory=C:/quant_strategy` — passed.

## Docs updated
- `docs/FEATURE_MAP.md`
- `docs/KNOWN_ISSUES.md`
- `docs/AI_HANDOFF.md`
- `docs/CURRENT_STATE.md`
- `docs/change_manifests/2026-06-30-family-minting-k-budget.md`
- this session/context handoff pair.

## Known limitations / risks
- The K-budget table is human-maintained checkpoint①#9 state; if stale, the
  checker reports stale K state accurately.
- The sidecar candidates are `pending_llm`; no mechanism-specific Stage 1 draft
  has been accepted.
- `F-S6-TS-MOMENTUM` appeared as eligible because the current taxonomy/ledger
  logic treats it as inconclusive/statistical-fail, not refuted; Claude should
  decide whether it is worth a new twist.

## Rollback plan
- Revert the touched files above and remove
  `results/idea_batch_20260630_taxonomy_001/` if the sidecar should be discarded.
  Do not touch unrelated `results/ui_funding_carry_55708fee_execution_comparison.json`.

## Context Handoff
- See `tasks/2026-06-30-family-minting-k-budget-sidecar-context-handoff.md`.

## Questions for human review
- Should Claude review all 4 pending candidates, or should we discard
  `F-S6-TS-MOMENTUM` before drafting because batch 1 already failed the
  fold-refit statistical gate?

## Next recommended task
- Claude/human review
  `results/idea_batch_20260630_taxonomy_001/hypothesis_ledger_draft.md`; only
  after approval should a candidate be converted into a durable Stage 1 ledger
  row and sent to Stage 2.

## Human Learning Notes (required)
K is retry attempts, not parameter combinations. Keeping those fields separate
matters before the first autonomous sidecar because otherwise the pipeline can
look stricter than it is while still failing to enforce the K=2 stop condition.
The direct-script regression also caught an ordinary but important harness gap:
import-based tests do not prove the exact command a human will run.
