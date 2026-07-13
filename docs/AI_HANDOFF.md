---
status: current
type: handoff
owner: human
created: 2026-05-11
last_reviewed: 2026-07-13
expires: none
superseded_by: null
---

# AI Handoff

Cross-session current state for Claude and Codex. Read `docs/CURRENT_STATE.md`
first; use `docs/CHANGELOG_AI.md` for history and `docs/KNOWN_ISSUES.md` for the
durable backlog.

## Current goal

Deliver the verified post-merge repairs through a separate follow-up PR. Preserve
every strategy, research, and deployment gate. No retry, adapter, promotion,
demo, shadow, or live work is authorized by this handoff.

## Branch and working tree

- Branch: `codex/pipeline-batch1-stage3`. Verified repair commit `df53f73` is
  local; `origin/codex/pipeline-batch1-stage3` remains at `037b15f` because the
  sandbox could not reach GitHub and the escalation was rejected by the tool's
  usage limit.
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
  up. Demo engine login still needs a valid key.
- P0 hardening: artifact-ID containment and venue fail-closed behavior remain
  closed. The accepted finite-positive `ct_val <=1e7` rule now fails closed at
  DB/registry/caller-spec boundaries, and rejected fills leave ledger state
  unchanged. No PnL formula or existing result changed.
- Research pipeline: H-009 remains non-passing `testing`; H-012 is user-shelved
  with no retry and E-037 remains immutable non-promotion evidence. H-010 is
  data-blocked. H-013 Stage-1 is user-signed-off; E-038 is reserved-only and has
  not run.
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
- `make` is unavailable in this Windows environment. Use the absolute Python
  executable and Makefile-equivalent commands; report API smoke SKIP unless a
  healthy server is explicitly provided.

## Next steps

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
   PASS across 131 changed files. Local repair commit: `df53f73`. Next: push the
   branch when network/tool access is available, then open a separate follow-up
   PR for commits `6129f94` through `037b15f` plus this repair.
4. DONE 2026-07-12 (Claude, user-authorized): P1.1 — `make test-lab` wired into `verify`,
   A11 validator `check_ledger_consistency.py` in `docs-check` (+8 unit tests,
   fixed missing F-VRP-TIMING K-budget row), lifecycle frontmatter enforced for
   every new Markdown file under `tasks/` recursively, with only the frozen
   legacy filename allowlist and four exact templates exempt. Overview coverage
   remains a documented manual review step. P1.2 — README 897→101 lines with
   operational detail moved verbatim to
   RUNBOOK, two completed 2026-06-25 plans archived, CHANGELOG backfilled
   07-05/07-07/07-11.
   Remaining Codex P1 work: liquidation unattended mode.
5. E-038 Stage-2 is a separate task; Stage 3 remains unauthorized.
6. Daily `dvol_deribit_*` backfill DONE 2026-07-12: 1,936 gap-free rows per
   symbol, 2021-03-24→2026-07-11, values cross-checked against the hourly
   series; manual-update command recorded in `docs/RUNBOOK.md` (must pass
   `--start` AND `--end`). User creates the OKX Demo key later.

## Open decisions

- Human review/merge decision for the separate PR #9 follow-up remains pending.
  ADR-0001 local-task exception is approved; ADR-0006 accepted; E-038 stays
  reserved-only; H-012 shelved; P1.4 operations decided.
