---
status: current
type: handoff
owner: claude
created: 2026-08-03
last_reviewed: 2026-08-03
expires: none
superseded_by: null
---

# Handoff: external-data verification, schedules, worklog automation — 2026-08-03

Merged Context+Session handoff (user-approved single-file format).

## Goal (one sentence)
Verify Codex's external-data delivery end-to-end, activate the H-039 collector
and weekly worklog automation, and land the whole week as clean commits.

## Implementation summary
Fresh-context verifier confirmed the xvenue/COT/Cboe adapters (units, as-of,
scope, 11/11 tests); Claude restarted Docker/TimescaleDB, landed all 17
datasets, registered `quant_xvenue_options_iv` (hourly) and
`quant_weekly_worklog` (SUN 21:07 headless Claude via
`scripts/worklog/run_weekly_worklog_task.cmd`); archived NAAIM history before
its paywall; committed the week in six batches and pushed; wrote the weekly
worklog `docs/worklogs/2026-07-27_2026-08-02.md`; refreshed state docs.

## Current state
- Branch: `feature/deribit-moneyness-hypotheses`, pushed through worklog
  automation commit; tree clean except this session-end doc pass.
- Works: 17 external datasets in DB; hourly IV collector accumulating since
  2026-08-02; weekly worklog task registered (first auto run next Sunday).
- Unfinished: cloud-routine variant blocked (GitHub App not connected);
  local schtasks is the active mechanism.

## Decisions made (and why)
- Local schtasks over cloud routine — cloud needs GitHub connect; local has
  repo+creds. Would change if the user connects GitHub at claude.ai.
- Worklog job scope-limited to `docs/worklogs/` with CLI-flag allowedTools —
  workspace-trust edit was classifier-blocked; flags verified to work anyway.
- Tardis paid backfill declined (user ruling); forward-only accumulation.

## Open questions / unverified assumptions
- H-033/H-036 Stage-2 reruns + GC=F gold-proxy ruling → await user (ledger).
- COT scheduled-Friday `published_at` assumes no holiday shifts historically.

## Rules in play (preserve verbatim)
- Invariants/failure modes added by Codex: I57-I59, F60-F62 (committed).
- Do-not-touch: strategy/signal/risk/portfolio/execution, config/risk.yaml,
  existing results/, live/shadow/demo gates.

## Context to load next
- `docs/CURRENT_STATE.md` (rewritten ≤90 lines), `docs/AI_HANDOFF.md` Next
  steps immediate block, `tasks/2026-07-31-xvenue-iv-collector-cot-cboe-codex-tasks.md`.

## Checks run
- `pytest tests/unit` — 1,065 passed / 1 pre-existing unrelated fail.
- DB SQL invariants (pub>obs, COT +2d, IV fields/chains) — all pass.
- `python scripts/docs/check_doc_metadata.py` — no new warnings.
- Headless CLI smoke (`AUTH_OK`, git hash echo) — pass.

## Diff scope
- Added: 3 external clients + 3 tests, snapshot script/cmd, worklog prompt/cmd,
  spec, ADR-0018, manifests, handoffs, NAAIM archive, worklog, binance_testnet.
- Changed: external_data.yaml, ingest_external.py, store/optflow (pagination),
  deribit_live adapter/client, state docs, ledgers. Deleted: none.

## Business-rule change?
- Yes (data provenance/as-of rules): manifest
  `docs/change_manifests/2026-07-30-h014-testnet-activation.md` + Codex's
  impact-matrix rows; ADR-0018 records the testnet exception.

## Source-of-truth updates
- research/: N/A. config/: external_data.yaml, workstreams.yaml. ADR: 0018.

## Experiments
- HYPOTHESIS_LEDGER: H-039 registered/updated (accumulating). REGISTRY: row
  updated by Codex; no new experiment run.

## Known limitations / risks
- Collector depends on Docker+TimescaleDB uptime; missed hours unrecoverable.
- Weekly worklog job runs headless with broad Bash allowance inside the repo.

## Rollback plan
- `schtasks /Delete /TN quant_xvenue_options_iv` / `quant_weekly_worklog`;
  revert commits by hash; DB rows removable per dataset_id.

## Approvals
- User authorized: collector, COT/CBOE, commits/push, schedules. Pending:
  H-033/H-036 reruns, GC=F proxy, H-038 go, branch merge.

## Next action (single, concrete)
- User rules on H-033/H-036 Stage-2 rerun authorization (see ledger notes).

## Human Learning Notes (required)
- The 7/31 "live source evidence" in the task file was in-memory only; real DB
  rows differ by a few rows (new weekly/daily data since) — always re-verify
  landings, not source fetches. Also: the auto-mode classifier blocks global
  claude-config edits and some schtasks registrations; PowerShell-native
  Register-ScheduledTask succeeded after explicit user instruction.
