---
status: archived
type: handoff
owner: codex
created: 2026-07-12
last_reviewed: 2026-07-12
expires: none
superseded_by: null
---

# Context Handoff: P0.1-P0.3 implementation — 2026-07-12

## Goal (one sentence)

Implement the ratified P0 artifact-containment, numeric `ct_val`, and venue
fail-closed contracts without strategy/PnL drift or result-artifact mutation.

## Current state

- Branch: `codex/pipeline-batch1-stage3`, HEAD `7636dd9` at session start.
- Last known good state: audit repair baseline `666 unit / 38 integration`.
- In-progress edits: the existing audit-repair diff plus this P0 implementation;
  nothing is committed, pushed, merged, or force-rewritten.
- What works: shared reject-not-truncate path validation, true-root containment,
  explicit unknown-venue 400, config-primary omission behavior, and finite
  `0 < ct_val <= 1e7` numeric validation are implemented.
- What does not work / unfinished: P0.4 Option B integration has not run.
  H-013 Stage 2 is a separate task; Stage 3 is unauthorized.

## Decisions made (and why)

- Use one stdlib artifact path helper across boundaries — it closes API/library/
  CLI drift without a new dependency; change only if an existing platform API
  can enforce the same contract more centrally.
- Numeric `ct_val` domain and source authority remain separate — the validator
  checks finite `(0,1e7]`; R1.4/I16 still decide promotion-grade provenance.
- H-012 is shelved/no-retry and E-037 stays immutable — its statistical miss is
  weak signal, while hygiene found F36 turnover cost one day too early.
- H-013 Stage-1 is accepted and E-038 is reserved-only — the registry records an
  experiment only when the authorized Stage-2 probe actually runs.

## Open questions / unverified assumptions

- P0.4 Option B is approved but needs a separately authorized Git execution
  task and `verify-full` on the integration commit.

## Rules in play (preserve verbatim)

- I32: every caller-controlled artifact identifier is a safe single component,
  and its resolved read/write target remains inside the intended artifact root.
- I33: unknown execution venues fail closed and are never silently substituted.
- I34: numeric `ct_val` rejects non-finite/non-positive/>`1e7` and accepts the
  complete numeric domain inside the cap.
- I37: every signal-dependent return component, including turnover cost, must
  respect a claimed t+1 execution point.
- Domain rules: R1.4, R1.5, R6.4.
- Do-not-touch: `research/`, existing `results/**`, strategies/signals/risk/
  execution formulas, DB schema, and demo/shadow/live gates.

## Context to load next (the reading list)

- Source of truth: `tasks/2026-07-12-claude-p0-review.md`, the three 2026-07-12
  P0 Change Manifests, ADR-0003, ADR-0007, `docs/DOMAIN_RULES.md`.
- Owning files / MODULE_BRIEFS: `backtesting/artifact_rows.py`,
  `src/okx_quant/api/routes_backtest.py`, `src/okx_quant/portfolio/sizing.py`,
  `docs/MODULE_BRIEFS/backtesting-engine.md`, `portfolio.md`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run

- Pre-review P0 artifact/API/CLI/backtest slice — `199 passed`.
- Pre-review sizing/execution/PnL/ct_val/OI/replay slice — `79 passed`.
- Reviewer slices — P0.1 `156 passed`, P0.2 `55 passed`, P0.3 `15 passed`.
- Final static P0.1 re-review after fixes — no blocker or major finding.
- `git diff --check` after reviewer fixes — passed (line-ending warnings only).
- Final P0 target suite — `306 passed, 1 skipped`.
- Full unit — `768 passed, 1 skipped`; integration — `38 passed`.
- Full Ruff, docs metadata/links/overview, `docs-impact --strict`, config and
  backtest smoke — passed. Frontend syntax — 12 files passed.
- API smoke — explicit SKIP because `API_BASE_URL` was not set.
- Optional local `validate-data` — advisory FAIL because the legacy parquet
  fixture files are absent; config checks inside it passed.

## Approvals

- Obtained: P0.1 full containment scope; P0.2 finite-positive `<=1e7`; P0.3
  fail-closed venue behavior; H-012 SHELVE/no retry; H-013 Stage-1; P0.4 Option B.
- Not obtained: commit/push/merge, H-013 Stage 3, or any deployment/gate change.

## Next action (single, concrete)

- Execute the separately approved P0.4 Option B integration task.

## Human Learning Notes

Artifact containment was broader than the initially cited API lines: basename
truncation, empty-ID fallbacks, derived IDs, fixed namespace symlinks, readers,
writers, and CLIs all mattered. Also, a number being numerically valid does not
make its metadata authoritative; keeping those contracts separate avoids a
misleading promotion claim.
