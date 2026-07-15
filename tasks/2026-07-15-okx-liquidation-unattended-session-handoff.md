---
status: current
type: handoff
owner: codex
created: 2026-07-15
last_reviewed: 2026-07-15
expires: none
superseded_by: null
---

# Session Handoff: OKX Liquidation Unattended Mode — 2026-07-15

## Implementation summary

Implemented the repo half of approved P1.4: the existing two-hour liquidation
wrapper now pins the verified Python executable, and the RUNBOOK provides a
least-privilege `woody / S4U / Limited` lifecycle with create, verify, run,
status, rollback, and removal commands. Host activation remains pending because
this session could not obtain Administrator Task Scheduler rights.

## Diff scope

- Files added: this session handoff and
  `tasks/2026-07-15-okx-liquidation-unattended-context-handoff.md`.
- Files changed: `scripts/market_data/run_liq_ingest_task.cmd`,
  `docs/RUNBOOK.md`, `docs/FEATURE_MAP.md`, `docs/KNOWN_ISSUES.md`,
  `docs/CURRENT_STATE.md`, `docs/AI_HANDOFF.md`, `docs/CHANGELOG_AI.md`,
  `config/workstreams.yaml`, and
  `tasks/2026-07-12-project-diagnosis-followup-tasks.md`.
- Files deleted: none.
- Unrelated file preserved: untracked
  `tests/fixtures/h014_shadow_db_signal.json`.

## Business-rule change?

- No. Ingestion data shape, contract values, checkpoints, schema, strategy,
  risk, execution, and gates are unchanged; no Change Manifest or ADR required.

## Source-of-truth updates

- research/strategy_synthesis.md: N/A; not touched.
- config/: only `config/workstreams.yaml` progress text updated; runtime config
  and gates unchanged.
- ADR: N/A.

## Experiments

- HYPOTHESIS_LEDGER entries: none.
- EXPERIMENT_REGISTRY entries: none.

## Tests / checks run

- `python -m pytest tests/unit/test_ingest_external_liquidation.py -q -p no:cacheprovider`
  — `5 passed`.
- `python scripts/market_data/ingest_external.py --dataset liq_okx_btc --dataset liq_okx_eth --dry-run`
  — passed for both datasets.
- Manual scheduled-task run — result `0`; task still `Interactive / Limited`.
- `python -m pytest tests/unit/ -v --tb=short -p no:cacheprovider` —
  `861 passed, 1 skipped, 1273 warnings` in 65.44s.
- Makefile-equivalent `docs-check`, `check-config`, and `docs-impact` — passed.

## Docs updated

- RUNBOOK: mandatory create/verify/run/status/rollback/remove commands.
- FEATURE_MAP: liquidation wrapper ownership and targeted test.
- CURRENT_STATE, AI_HANDOFF, KNOWN_ISSUES, CHANGELOG_AI, source task, and
  workstream progress: repo support complete, host activation pending.
- DATA_FLOW reviewed; no update because action, data path, schema, and
  checkpoint semantics did not change.

## Known limitations / risks

- Logged-out collection is not active until the user runs the Administrator
  RUNBOOK command and verifies `LogonType=S4U` plus result `0`.
- The wrapper pins a workstation-specific Python path; update it if Python moves.
- S4U does not provide delegated Windows network credentials. The current task
  uses public HTTPS and localhost TimescaleDB.

## Rollback plan

- Use the RUNBOOK `/IT` command to restore Interactive/Limited behavior, or
  delete the task with `schtasks /Delete`; revert the wrapper line and docs.

## Context Handoff

- See `tasks/2026-07-15-okx-liquidation-unattended-context-handoff.md`.

## Questions for human review

- Can the user run the documented command from Administrator PowerShell and
  provide/verify `S4U / Limited` plus manual-run result `0`?
- Claude: confirm least-privilege S4U is acceptable and no H-014/shadow or gate
  boundary was crossed.

## Next recommended task

- Activate and verify the S4U task; then Claude reviews this diff and the host
  evidence before P1.4 is marked complete.

## Human Learning Notes (required)

The existing action and two-hour trigger were healthy; only the principal was
wrong for retention across logout. Running a user-writable repo script as SYSTEM
would solve the symptom by creating a larger privilege problem, so S4U/Limited
is the correct narrow fix.
