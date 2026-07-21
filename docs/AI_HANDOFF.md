---
status: current
type: handoff
owner: human
created: 2026-05-11
last_reviewed: 2026-07-17
expires: none
superseded_by: null
---

# AI Handoff

Cross-session current state for Claude and Codex. Read `docs/CURRENT_STATE.md`
first; use `docs/CHANGELOG_AI.md` for history and `docs/KNOWN_ISSUES.md` for the
durable backlog.

## Current goal

Have Claude review the user-ratified ADR-0013 scope/reference floor, F45/F46
caller/funnel repair, and ADR-0014 source-aware OKX data promotion. Confirm the
data-only boundary and raw-parity evidence without treating it as an H-010
retry/verdict or deployment evidence. Preserve every strategy, research, and
deployment gate.

## Branch and working tree

- Current branch: `feature/h014-e052-shadow` at `b2eb27e`, with the uncommitted
  2026-07-16 delivery and 2026-07-17 strategy-history/funnel-v2/Ledger-detail
  delivery in the shared working tree. No commit was requested.
- Pushed 2026-07-14: `origin/codex/pipeline-batch1-stage3` through `d046978`,
  F-VOL research delivery `d66f08a`, and Taxonomy_003 research delivery
  `821f761`; the final shared-state commit is on the Taxonomy_003 branch.
- PR #9 merged to `main` at `b378e16`; its PR head was `00c7a51`. Commits
  `6129f94` through `037b15f` and the current repairs were not in PR #9 and
  require a separate follow-up PR. No force-push or history rewrite.

## Current implementation state

- Turtle: accepted research-only standalone runner; real-data golden parity,
  API/UI, and resumable large sweeps exist. Audit fix restores the documented
  fraction-unit sweep behavior.
- Deribit: D1-D5 and review fixes accepted; BTC/ETH DVOL/funding/option-flow
  history is present through 2026-07-10 23:00Z. Forward schedulers are not
  registered; option-surface remains snapshot-only.
- Manual/Progress: all manual chapters exist. The standalone server now wires
  `/api/manual`, chapter frontmatter is removed, and configured Progress markdown
  links are served through a contained allow-list route only on loopback binds.
  Engine and non-loopback views render those paths without a file endpoint.
- Runtime: the pre-existing listener on 127.0.0.1:8080 (PID 23696 during audit)
  timed out and was left untouched; temporary 8081 smoke was healthy and cleaned
  up. Demo engine login still needs a valid key. P1.4 repo support now pins the
  liquidation task's Python executable and documents least-privilege S4U task
  registration/run/removal; the host task still reports `Interactive` until the
  user runs the Administrator PowerShell registration and verifies result `0`.
- P0 hardening: artifact-ID containment and venue fail-closed behavior remain
  closed. The accepted finite-positive `ct_val <=1e7` rule now fails closed at
  DB/registry/caller-spec boundaries, and rejected fills leave ledger state
  unchanged. No PnL formula or existing result changed.
- Research pipeline: H-009 remains non-passing `testing`; H-012 is user-shelved
  with no retry and E-037 remains immutable non-promotion evidence. H-010 is
  data-blocked on OKX 1m. H-013/E-050 is shelved after statistical failure.
  Taxonomy_003 E-044..E-049 completed and all six candidates failed their
  statistical gates. H-014/E-051/E-052 is supported but promotion-blocked;
  ADR-0011's >=8-week manual shadow gate is next. Taxonomy_004 H-021/E-056 is
  refuted after its separately authorized first Stage-3 full-PnL validation:
  WF -0.2158, CPCV -0.0375, DSR 0.2357, PSR 0.4818, family-cumulative
  `n_trials=12`, K 0/2. Stop with no retry, retune, promotion, or deployment
  claim.
- Pipeline observability/triage: under ADR-0013, new registry-written Stage-2
  artifacts fail closed on a fourth `statistical_power` check using
  registry-cumulative trials. `docs/STRATEGY_HISTORY.md` consolidates H-000–H-021
  and E-000–E-056 without inventing unrecorded metrics. The disposable funnel is
  now schema v2 and the read-only 研究總表 / Ledger view exposes each family's
  source, hypothesis, and full iteration timeline; schema v1 degrades to a
  regeneration hint. The Markdown ledgers remain authoritative and generated
  JSON is not checked in. This does not alter Stage-3 or deployment gates.
- Stage-2 follow-up: the five-line evaluator scope and computed `1.7206`
  reference case were ratified. Active CLI/backfill/orchestrator callers reject
  missing candidate-specific power inputs before probes/artifacts/status
  changes. Funnel schema v3 isolates malformed files under
  `stage2_artifact_errors`; no research inputs are inferred.
- History/data boundary: the read-only scan completed over 68 canonical and 46
  external datasets. Under separately approved ADR-0014, the existing complete
  raw OKX BTC/ETH 1m window was promoted to an additive source-aware canonical
  layer. Each symbol has 1,293,120 rows, raw mismatches 0,
  coverage/alignment 1.0, resolved OKX rows 0, and an idempotent rerun changed 0
  rows. No network ingest, H-010 retry, ledger/verdict change, or result artifact
  was performed.
- Shelved/refuted: XS Momentum and Batch 2 C1/C2/C3. No gate may be chased by
  unregistered retries.

## Audit closures and remaining blockers

1. **Closed - artifact containment (F30/I32):** one reject-not-truncate
   helper and resolved-root containment cover read/write API, library, sweep,
   artifact-writer and caller-facing CLI boundaries.
2. **Closed - `ct_val` enforcement (F32/F37/I34):** DB, registry, caller-spec,
   fill, and existing-position fallback values share the finite-positive
   `<=1e7` validator before provenance or ledger mutation.
3. **Closed - venue fail closed (F31/I33):** omitted/blank uses config
   primary; any explicit unknown venue returns 400 before the job queue.
4. **Closed - integration (P0.4):** Option B executed 2026-07-12; PR #9 merged
   to `main` at `b378e16` with PR head `00c7a51`. verify-full equivalent on
   `a950025`: unit 768/1
   skip, integration 38, Ruff/docs/frontend/config/backtest-smoke pass;
   api-smoke SKIP (no server); validate-data FAIL is the pre-existing thin
   parquet mirror, not merge-caused.
5. **Closed - follow-up governance checks (F38/I38):** H↔E ownership, explicit
   reservation, malformed/compact rows, exact template exemptions, and populated
   lifecycle metadata now fail closed under adversarial tests.
6. **Open - F36:** the shelved OI runner posts turnover cost on signal day even
   though positions/funding start t+1. Do not reuse E-037 as promotion evidence.

Full evidence and binary acceptance criteria are in the follow-up task file;
durable gaps are in `docs/KNOWN_ISSUES.md`.

## Do not touch without explicit approval

- `research/` and existing `results/**` artifacts.
- `src/okx_quant/strategies/`, `signals/`, `risk/`, `portfolio/`, `execution/`.
- `config/risk.yaml`, strategy assumptions, or demo/shadow/live gates.
- Differential-validation implementation beyond the completed P0.1 containment
  boundary.

## Verification baseline

- Audit baseline before repair: full unit `661 passed, 1 failed` (Turtle static
  contract); integration `37 passed, 1 failed` (stale ADR-0007 test). After the
  repair: full unit `666 passed`; integration `38 passed`.
- Final P0 checks: targeted `306 passed, 1 skipped`; full unit `768 passed,
  1 skipped`; integration `38 passed`; full Ruff, docs metadata/links/overview,
  `docs-impact --strict`, config and backtest smoke pass. The skip is the Windows
  no-symlink-privilege containment case.
- Audit-scope Ruff, frontend syntax, docs metadata/links/overview/impact, config,
  backtest smoke, live API smoke, and Playwright Manual/Progress checks pass.
- 2026-07-16 delivery checks: 99 targeted cross-module tests pass; targeted Ruff,
  all frontend syntax (including `view-ledger.js`), docs metadata/links/ledger/
  strict impact, config, backtest smoke, funnel CLI, and loopback HTTP contract
  pass. The real H-010 verifier correctly exits 1 at 0% coverage. Playwright is
  an environment SKIP because no local package exists and third-party npm
  download/execution was rejected; no browser-render claim is made.
- 2026-07-17 delivery checks: funnel and route tests pass (`3 + 10`), targeted
  Ruff and every frontend syntax check pass, and docs metadata/links/ledger plus
  config validation pass. A real disposable projection produced schema 2 with
  22 families and the expected F-FUNDING-CARRY timeline. Playwright against
  Edge verified both schema-v2 expansion and schema-v1 graceful fallback; the
  only console error was the unrelated missing favicon. Temporary JSON,
  screenshots, logs, server, and browser processes were removed.
- 2026-07-17 authorized follow-up: focused Stage-2 caller/funnel tests passed
  (31), source-aware data tests passed (45), real fixed-scope promotion inserted
  1,293,120 rows per symbol, verifier PASSed exact raw parity and 1.0
  coverage/alignment, and the second promotion changed zero rows. No H-010
  experiment command ran.
- `make` is unavailable in this Windows environment. Use the absolute Python
  executable and Makefile-equivalent commands; report API smoke SKIP unless a
  healthy server is explicitly provided.

## Next steps

First review the 2026-07-17 Stage-2 caller-fix and OKX promotion context/session
handoffs. Claude should confirm the candidate-specific input boundary,
schema-v3 error isolation, ADR-0014 resolved/source-aware split, and that data
availability did not change H-010 research evidence.

Claude review (`tasks/2026-07-12-claude-p0-review.md`) is user-ratified and
implemented for P0.1-P0.3, H-012, and H-013.

All 2026-07-12 audit decisions are now recorded — see "Human decisions
recorded 2026-07-12" in `tasks/2026-07-12-project-diagnosis-followup-tasks.md`.

1. DONE 2026-07-12: Claude reviewed the P0 diff and APPROVED all three P0s
   (implementation-review section of `tasks/2026-07-12-claude-p0-review.md`)
   and reran the blocked verification: full unit `768 passed, 1 skipped`
   (Windows symlink privilege), integration `38 passed`, Ruff pass,
   `docs-impact --strict` pass. Two minor findings, none blocking.
2. DONE: P0.4 Option B was executed at integration commit `a950025`; PR #9
   merged to `main` at `b378e16` from PR head `00c7a51`.
3. DONE 2026-07-13: repaired the remaining review findings. Final verification:
   unit `841 passed, 1 skipped`, integration `38 passed`, lab `18 passed`, full
   Ruff/docs/config/backtest smoke PASS, and strict doc impact from `00c7a51`
   PASS across 131 changed files. Repair commit `df53f73` and handoff commit
   `d046978` were pushed 2026-07-14. Next: open a separate follow-up PR for
   commits `6129f94` through `d046978`.
4. DONE 2026-07-12 (Claude, user-authorized): P1.1 — `make test-lab` wired into `verify`,
   A11 validator `check_ledger_consistency.py` in `docs-check` (+8 unit tests,
   fixed missing F-VRP-TIMING K-budget row), lifecycle frontmatter enforced for
   every new Markdown file under `tasks/` recursively, with only the frozen
   legacy filename allowlist and four exact templates exempt. Overview coverage
   remains a documented manual review step. P1.2 — README 897→101 lines with
   operational detail moved verbatim to
   RUNBOOK, two completed 2026-06-25 plans archived, CHANGELOG backfilled
   07-05/07-07/07-11.
   P1.4 repo implementation is complete; host S4U activation remains an
   Administrator PowerShell operation.
5. E-038 Stage-2 is a separate task; Stage 3 remains unauthorized.
6. P1.4 repo support DONE 2026-07-15: the OKX liquidation wrapper uses the
   verified Python 3.12 executable, and RUNBOOK documents S4U/Limited create,
   verify, run, rollback, and removal. Host activation is not yet done because
   non-elevated Task Scheduler updates returned Access Denied; the current task
   remains Interactive.
7. Daily `dvol_deribit_*` backfill DONE 2026-07-12: 1,936 gap-free rows per
   symbol, 2021-03-24→2026-07-11, values cross-checked against the hourly
   series; manual-update command recorded in `docs/RUNBOOK.md` (must pass
   `--start` AND `--end`). User creates the OKX Demo key later.
8. Taxonomy_003 CLOSED 2026-07-14 (user-authorized Stage-3 sweep, Claude
   solo, E-044..E-049, verifier clean): all six MINT, all six FAIL the
   DSR/PSR ≥ 0.95 gate — H-015 refuted, H-016 shelved (best 0.70/0.80),
   H-017 inconclusive, H-018 refuted, H-019 shelved, H-020 refuted. See
   `tasks/2026-07-14-taxonomy003-stage3-handoff.md`; no retries without
   ex-ante rationale + K.
9. H-014/E-039 done 2026-07-13 (`tasks/2026-07-13-vol-regime-opt-handoff.md`).
   Stage-2 handed to Codex: `tasks/2026-07-13-f-vol-regime-opt-stage2-codex-tasks.md`
   (T1 Tardis calibration/E-040, T2 vendor report; T3 NOT authorized). Claude
   is the reviewer for this workstream from 2026-07-13 on (user ruling).
   E-040 ran and FAILED CLOSED (2 GiB guard at 2024-03-01); Claude review
   ACCEPTED it (`tasks/2026-07-13-e040-stage2-claude-review.md`) — Stage 2 not
   passed at that point. UPDATE 2026-07-14: after the user-authorized
   hourly-DVOL backfill (2021→2024, 46,440 rows/symbol), E-043 completed all
   12 pairs — **Stage 2 PASS**, real/synthetic RICH-leg ratios 0.88–1.03 ≥
   the ex-ante 0.8 bar. Next gate is the user's: chain-history purchase and
   Stage-3/engine authorization (coin-accounting manifest + ADR first).

10. DONE 2026-07-17: Codex completed
    `tasks/2026-07-16-strategy-history-doc-frontend-codex-tasks.md` — Task A
    `docs/STRATEGY_HISTORY.md` records H-000–H-021 and E-000–E-056; Task B upgrades
    the disposable funnel to schema v2 with per-family source, hypothesis text,
    and dated experiments; Task C adds expandable Ledger iteration detail and
    schema-v1 fallback. Ledgers stayed read-only; no new route, checked-in JSON,
    strategy/gate change, or fabricated metric was introduced.

## Open decisions

- Human review/merge decision for the separate PR #9 follow-up remains pending.
  ADR-0001 local-task exception is approved; ADR-0006 accepted; E-038 stays
  reserved-only; H-012 shelved; P1.4 operations decided.
- H-014 pre-2024 hourly-DVOL backfill and E-043 are complete. Any chain-history
  purchase or Stage-3 engine/accounting work still needs explicit human approval.
