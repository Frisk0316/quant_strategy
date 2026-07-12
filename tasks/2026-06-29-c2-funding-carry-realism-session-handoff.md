---
status: archived
type: handoff
owner: codex
created: 2026-06-29
last_reviewed: 2026-06-29
expires: none
superseded_by: null
---

# Session Handoff: C2 Funding-Carry Realism Re-Cost - 2026-06-29

## Implementation summary
Added research-only realism costs and stress reporting to C2 funding carry, then ran the DB-backed realism retry into a new artifact directory. The retry fails the statistical gate and shelves H-007; no live strategy behavior, risk/portfolio/execution, config gate, DSR/CPCV/WF harness, or old artifact was changed.

## Diff scope
- Files added: `scripts/run_c2_realism.py`, `docs/change_manifests/2026-06-29-c2-funding-carry-realism-recost.md`, `tasks/2026-06-29-c2-funding-carry-realism-context-handoff.md`, `tasks/2026-06-29-c2-funding-carry-realism-session-handoff.md`, `results/pipeline_batch2_20260625/c2_funding_carry_realism/summary.json`.
- Files changed: `backtesting/c2_funding_carry_backtest.py`, `tests/unit/test_c2_funding_carry_backtest.py`, `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `config/workstreams.yaml`.
- Files deleted: none.

## Business-rule change?
- Yes, A5/A11 scope. Change Manifest at `docs/change_manifests/2026-06-29-c2-funding-carry-realism-recost.md`; `DOC_IMPACT_MATRIX` checked.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A, Claude-owned and not modified.
- config/: `config/workstreams.yaml` progress metadata only; no strategy/risk/gate config changed.
- ADR: N/A; no schema, gate policy, DB schema, or durable business-rule text changed.

## Experiments
- HYPOTHESIS_LEDGER entries: H-007 updated to `refuted / shelved`, family trials 48.
- EXPERIMENT_REGISTRY entries: E-026 added as the C2 realism-recost retry.

## Tests / checks run
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_c2_funding_carry_backtest.py -q` - 4 passed; pytest cache warning.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -B -c "import scripts.run_c2_realism as m; print(m.CANDIDATE_DIR)"` - passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\run_c2_realism.py` - completed DB-backed realism rerun.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_doc_impact.py` with temporary `GIT_CONFIG_*` safe-directory variables - passed; 26 changed files, no impact-matrix violations.

## Docs updated
- `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, Change Manifest, context/session handoffs, `config/workstreams.yaml`.

## Known limitations / risks
- C2 is refuted under the vectorized realism retry, but the modeled vol remains only 0.247% annualized, so this artifact is not proof of fully realistic two-leg execution.
- C3 remains data-blocked until `fear_greed_btc` is ingested; no proxy was fabricated.

## Rollback plan
- Revert the listed code/test/doc files and remove `results/pipeline_batch2_20260625/c2_funding_carry_realism/` if this retry should be discarded.

## Context Handoff
- See `tasks/2026-06-29-c2-funding-carry-realism-context-handoff.md`.

## Questions for human review
- Should C3 be unblocked with the cheap Alternative.me Fear & Greed ingest, or left parked as data-blocked?
- Does Claude want a separate replay-engine realism task for funding carry, or is H-007 shelved for now?

## Next recommended task
- Claude review of E-026/H-007; then either park batch 2 or run the optional C3 ingest task.

## Human Learning Notes (required)
The important signal is not just that costs hurt C2. The stress/re-cost retry converted a suspicious statistical pass into a statistical fail, while still showing the vectorized hedge is too calm; this is exactly why realism gates should run before adapter or promotion work.
