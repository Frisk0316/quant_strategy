---
status: current
type: handoff
owner: human
created: 2026-05-11
last_reviewed: 2026-07-12
expires: none
superseded_by: null
---

# AI Handoff

Cross-session current state for Claude and Codex. Read `docs/CURRENT_STATE.md`
first; use `docs/CHANGELOG_AI.md` for history and `docs/KNOWN_ISSUES.md` for the
durable backlog.

## Current goal

Review/integrate the implemented 2026-07-12 P0 hardening safely, then continue
the ordered P1 governance/docs backlog. Preserve every strategy, research, and
deployment gate. No retry, adapter, promotion, demo, shadow, or live work is
authorized by this handoff.

## Branch and working tree

- Branch/HEAD: `codex/pipeline-batch1-stage3`, tracking origin; tree clean.
  Tip contains: P0 work (`c84f5a1`), zero-delta integration merge (`a950025`),
  the merged P1 governance batch (PR #10, `00c7a51`), and the 2026-07-13 Codex
  review fixes.
- P0.4 Option B EXECUTED 2026-07-12 (Claude, user-authorized): `origin/main`
  merged (zero content delta, no conflicts); PR #9 open — documented
  integration-exception merge to main, awaiting Codex review. No force-push.

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
- P0 hardening: shared artifact-ID rejection/containment covers API, artifact
  writers, differential-validation paths, sweeps, and caller-facing CLIs;
  omitted/blank venues use configured primary while explicit unknown values
  fail before queueing; shared `ct_val` validation is finite-positive through
  `1e7`. No PnL formula or existing result changed.
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
2. **Closed - `ct_val` contract (F32/I34):** the approved finite-positive
   `<=1e7` contract, ADR-0003 amendment, Change Manifest and regressions agree;
   position/PnL formulas are unchanged.
3. **Closed - venue fail closed (F31/I33):** omitted/blank uses config
   primary; any explicit unknown venue returns 400 before the job queue.
4. **Closed - integration (P0.4):** Option B executed 2026-07-12; PR #9 carries
   the documented exception. verify-full equivalent on `a950025`: unit 768/1
   skip, integration 38, Ruff/docs/frontend/config/backtest-smoke pass;
   api-smoke SKIP (no server); validate-data FAIL is the pre-existing thin
   parquet mirror, not merge-caused. Codex review/merge of PR #9 pending.
5. **Open - F36:** the shelved OI runner posts turnover cost on signal day even
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
2. DONE 2026-07-12: P0.4 Option B executed by Claude (user-authorized) —
   integration commit `a950025`, PR #9 open for Codex review. Codex
   review fixes (ct_val enforcement closure and governance-tooling hardening)
   are committed on the same branch 2026-07-13.
3. DONE 2026-07-12 (Claude, user-authorized; Codex review pending on branch
   `claude/p1-governance-docs`): P1.1 — `make test-lab` wired into `verify`,
   A11 validator `check_ledger_consistency.py` in `docs-check` (+8 unit tests,
   fixed missing F-VRP-TIMING K-budget row), tasks/ lifecycle frontmatter
   enforced for dated files ≥2026-07-01 (28 files migrated, 4 templates
   updated, legacy exempt), overview coverage documented as a manual review
   step. P1.2 — README 897→101 lines with operational detail moved verbatim to
   RUNBOOK, two completed 2026-06-25 plans archived, CHANGELOG backfilled
   07-05/07-07/07-11.
   Remaining Codex P1 work: liquidation unattended mode; review both PRs.
4. E-038 Stage-2 is a separate task; Stage 3 remains unauthorized.
5. Daily `dvol_deribit_*` backfill DONE 2026-07-12: 1,936 gap-free rows per
   symbol, 2021-03-24→2026-07-11, values cross-checked against the hourly
   series; manual-update command recorded in `docs/RUNBOOK.md` (must pass
   `--start` AND `--end`). User creates the OKX Demo key later.

## Open decisions

- None. ADR-0001 local-task exception approved; ADR-0006 confirmed accepted;
  E-038 stays reserved-only; H-012 shelved; P0.4 = Option B; P1.4 operations
  decided (schedulers accepted-stale with manual updates, liquidation goes
  unattended, port 8080 abandoned, Demo key later).
