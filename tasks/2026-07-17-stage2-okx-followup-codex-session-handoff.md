---
status: current
type: handoff
owner: codex
created: 2026-07-17
last_reviewed: 2026-07-17
expires: none
superseded_by: null
---

# Session Handoff: Stage-2 and OKX authorized follow-up — 2026-07-17

## Implementation summary

Ratified and documented the Stage-2 reference floor/scope, repaired all active
legacy caller paths and funnel error isolation, added ADR-0014's additive
source-aware canonical layer, promoted the fixed OKX BTC/ETH window, verified
exact parity/idempotence, and split Tasks A/B/C/data/shared work for auditability.

## Diff scope

- Files added: power-screen module/tests/ADR/manifest/spec; history audit and
  verifier; Ledger view/history/tasks; venue-canonical migration, promotion
  script, ADR/manifest/tests; context/session handoffs.
- Files changed: Stage-2 registry/evaluator/orchestrator/callers/funnel; canonical
  store/policy/writer/readers/delete paths; frontend/config and governance/state
  docs.
- Files deleted: none.

## Business-rule change?

- Yes. Stage-2 manifest:
  `docs/change_manifests/2026-07-16-stage2-power-screen.md`; source-aware data
  manifest: `docs/change_manifests/2026-07-17-source-aware-canonical-candles.md`.
  DOC_IMPACT rows reviewed: A5, A6, A9; strict checker passed.

## Source-of-truth updates

- research/strategy_synthesis.md: N/A, read only.
- config/: `config/workstreams.yaml` status text only; no trading threshold or
  deployment configuration changed.
- ADR: ADR-0013 updated; ADR-0014 added and accepted.

## Experiments

- HYPOTHESIS_LEDGER entries: none.
- EXPERIMENT_REGISTRY entries: none.

## Tests / checks run

- `pytest tests/unit -q -p no:cacheprovider` — 896 passed, 1 skipped.
- Focused Stage-2 suite — 31 passed; focused source-aware suite — 45 passed.
- Targeted Ruff — PASS.
- Docs metadata, feature links, ledger consistency, strict impact — PASS.
- Config, `node --check frontend/view-ledger.js`, backtest smoke, diff check — PASS.
- Real promotion/verifier — 1,293,120 rows per symbol, raw mismatch 0,
  coverage/alignment 1.0, resolved OKX 0; rerun changed 0.

## Docs updated

- ADR README/0013/0014, both Change Manifests, DOMAIN_RULES, INVARIANTS,
  FAILURE_MODES, FEATURE_MAP, UI_MAP, DATA_FLOW, RUNBOOK, KNOWN_ISSUES,
  CURRENT_STATE, AI_HANDOFF, CHANGELOG_AI, CONTEXT_INDEX, workstream state.

## Known limitations / risks

- Source-aware higher-timeframe CAGGs are intentionally absent.
- Independent-bet breadth remains an ex-ante assertion; BTC/ETH independence is
  unconfirmed.
- Data readiness does not establish H-010 edge, statistical validity, or any
  deployment readiness.

## Rollback plan

- Stop source-aware consumers; delete only authorized OKX venue rows in the
  frozen window; revert data readers/writers/delete paths; drop the compatibility
  view and venue table. Revert Stage-2 caller/funnel commits separately. Never
  delete raw/resolved canonical data, CAGGs, ledgers, or existing results.

## Context Handoff

- See `tasks/2026-07-17-stage2-okx-followup-codex-context-handoff.md`.

## Questions for human review

- Confirm the resolved/source-aware split is preferred over any future in-place
  canonical identity migration.
- Confirm H-010 remains research-untouched despite the now-green data verifier.

## Next recommended task

- Claude correctness/source-fidelity review only. Any H-010 retry requires a new
  explicit research authorization and immutable experiment record.

## Human Learning Notes (required)

The missing OKX leg was a consumer identity problem, not missing raw data.
Separating resolved defaults from venue identity preserved every existing CAGG
and made rollback precise. Caller validation must occur before artifacts so
integration errors never masquerade as candidate failures.
