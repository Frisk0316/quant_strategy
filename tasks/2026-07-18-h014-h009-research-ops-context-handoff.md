---
status: current
type: handoff
owner: codex
created: 2026-07-18
last_reviewed: 2026-07-18
expires: none
superseded_by: null
---

# Context Handoff: H-014/H-009 Research Ops — 2026-07-18

## Goal (one sentence)

Make H-014 and H-009 operable from the local frontend without deploying either
strategy or weakening any research, shadow, promotion, credential, or live gate.

## Current state

- Branch: `feature/h014-e052-shadow`.
- Last known good commit / state: HEAD `3b0a975`; the requested work remains
  uncommitted in a dirty multi-session tree.
- In-progress edits (files): see paired session handoff; other H-010/E-057 and
  source-aware-canonical edits pre-existed and must remain untouched.
- What works right now: Analysis > Research Ops shows H-014 journal/bias status,
  runs exactly one existing public-data shadow cycle on loopback, and submits a
  bounded H-009 lookback/quantile full-sample screen. Engine/non-loopback actions
  and requests missing the local-action header fail with HTTP 403.
- What does not work / unfinished: no deployment surface exists or is authorized;
  H-009 jobs are process-local after submission; no real H-009 sweep was run in
  this session; H-014 currently has 0.29/8 journal weeks, 1/8 distinct weeks,
  and incomplete bias metrics.

## Decisions made (and why)

- A separate Research Ops page owns these controls — the normal Backtest view has
  different semantics and would obscure their non-promotion boundary.
- H-014 reuses the accepted runner/report unchanged in strategy/accounting terms;
  its blocking public/DB work runs on a worker thread so the API event loop stays
  responsive.
- Manual, UI, and scheduled H-014 cycles share a standard-library non-blocking
  cross-process lock — the approved scheduler made a process-local UI lock unsafe.
- H-009 exposes only existing `lookback_days` and `quantile`, capped at 25 cells.
  Each request is written before computation and counted in a known trial lower
  bound; the Experiment Registry remains authoritative for outside activity.
- No real sweep/cycle was clicked during verification — doing so would create new
  runtime evidence, while this task was implementation and safety verification.

## Open questions / unverified assumptions

- Claude should review whether the E-031 registered baseline of four trials is
  still the correct lower-bound anchor before any decision-relevant H-009 use.
- A real DB-backed H-009 UI screen remains an operator action and must not be
  interpreted as a registered experiment or promotion retry.

## Rules in play (preserve verbatim)

- Invariants touched: I39 requires one cross-process H-014 journal-producing
  cycle at a time; I40 preserves exact-prior-day research parity and no
  private/order method.
- Domain rules touched: R7.1/R7.4 (in-sample output is not promotion evidence;
  honest total trials required for promotion DSR), R8.7 (append-only,
  credential-free shadow evidence and single-writer cycle lock).
- Do-not-touch: `research/`, existing `results/**`, frozen H-014 `ivp=85/z=0.5`,
  H-009 verdict/ledgers, `config/strategies.yaml`, `config/risk.yaml`, private
  endpoints, credentials, broker/orders, live/demo mode, and deployment gates.

## Context to load next (the reading list)

- Source of truth: `research/strategy_synthesis.md`,
  `docs/ADR/0011-deribit-options-shadow-execution.md`,
  `docs/DOMAIN_RULES.md` R7/R8, `config/h014_shadow.yaml`.
- Owning files / MODULE_BRIEFS: `src/okx_quant/api/routes_research.py`,
  `frontend/view-research.js`,
  `scripts/run_funding_xs_dispersion_checkpoint.py`,
  `src/okx_quant/execution/deribit_shadow/runner.py`, and
  `docs/MODULE_BRIEFS/deribit-shadow-execution.md`.
- Context Pack: `docs/CONTEXT_PACKS/deployment.md` and the research-pipeline pack
  selected by `docs/CONTEXT_INDEX.md`.

## Checks run

- Focused route/shadow/funding tests — 24 passed.
- Final targeted unit/integration matrix — 45 passed; only pytest-cache write
  permission warning.
- Targeted Ruff, full frontend syntax check, config check, docs checks, strict
  doc-impact, API smoke, backtest smoke, and `git diff --check` — passed.
- Playwright CLI with installed Edge — Research Ops rendered correctly, current
  H-014 lock state displayed, mutation buttons available only on loopback, and
  browser console had 0 errors/warnings.
- Real server POST without `X-Research-Action` — H-014 and H-009 both HTTP 403.

## Approvals

- Human approval obtained 2026-07-18 for a frontend-operable research/shadow
  surface. No approval was given for live deployment, orders, or gate changes.
- Business-rule safety hardening is recorded in
  `docs/change_manifests/2026-07-18-h014-research-ops-journal-safety.md`.

## Next action (single, concrete)

- Have Claude review the cross-process journal lock and H-009 lower-bound trial
  provenance, then the user can launch `python scripts/run_server.py --port 8082`
  and operate Analysis > Research Ops locally.

## Human Learning Notes

The eight-week shadow period is an evidence-collection window, not a deployment
delay timer. A frontend button creates a second operating process, so the
previously acceptable in-process dedupe was no longer enough once the Windows
scheduler existed. H-009 parameter browsing is also a research act: preserving
request sidecars and calling the count a lower bound prevents a convenient UI
from silently becoming a gate-chasing tool.
