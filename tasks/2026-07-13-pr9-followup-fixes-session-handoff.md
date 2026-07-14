---
status: current
type: handoff
owner: codex
created: 2026-07-13
last_reviewed: 2026-07-13
expires: none
superseded_by: null
---

# Session Handoff: PR #9 follow-up fixes — 2026-07-13

## Implementation summary

Closed the remaining PR #9 follow-up findings. Replay now validates every
present DB, registry, or caller-supplied `ct_val` before assigning authoritative
provenance, and incomplete explicit specs fail instead of falling through.
Position fills validate before ledger insertion, so rejected fills leave no
ghost position or accounting mutation. Governance checks now enforce evidence
ownership, explicit reservation, robust Markdown row discovery, exact template
exemptions, and populated lifecycle metadata. PR/current-state documents now
reflect that PR #9 already merged and these changes require a separate PR.

## Diff scope

- Files added: this Session Handoff and
  `tasks/2026-07-13-pr9-followup-fixes-context-handoff.md`.
- Files changed: replay/position code; five focused unit-test files; two docs
  checkers and their tests; R1.5/I34/I38/F32/F37/F38/data-flow/Manifest records;
  current-state, workstream, review, changelog, and archived handoff records.
- Files deleted: none.

## Business-rule change?

- Yes, enforcement-only: the accepted finite `0 < ct_val <= 1e7` rule and PnL
  formulas are unchanged, but all explicit boundaries now enforce it before
  mutation. Change Manifest:
  `docs/change_manifests/2026-07-12-ct-val-validation-contract.md`.
  DOC_IMPACT_MATRIX rows: A2, A5, A9.

## Source-of-truth updates

- `research/strategy_synthesis.md`: N/A; not modified.
- `config/`: trading configuration N/A; only `config/workstreams.yaml` state
  synchronized with `docs/AI_HANDOFF.md`.
- ADR: ADR-0003 and ADR-0007 reviewed; no policy/formula change, so no new ADR.

## Experiments

- HYPOTHESIS_LEDGER entries: none.
- EXPERIMENT_REGISTRY entries: none.

## Tests / checks run

- Targeted code/governance suite — `139 passed`.
- Full unit — `841 passed, 1 skipped`; skip is the existing Windows symlink
  privilege case.
- Integration — `38 passed`; crypto-alpha-lab — `18 passed`.
- Full Ruff — PASS.
- Config validation — PASS.
- Backtest smoke — PASS (`strategy_fill` fixture; not promotion evidence).
- Documentation metadata (0 warnings), feature links (212 paths), ledger
  consistency (14 hypotheses / 38 experiments / 13 K-budget families), and
  Human Review Overview (4 overviews) — PASS.
- Strict doc impact from base `00c7a51` — PASS across 131 changed files.

## Docs updated

- `docs/DOMAIN_RULES.md`, `docs/INVARIANTS.md`, `docs/FAILURE_MODES.md`,
  `docs/DATA_FLOW.md`, the `ct_val` Change Manifest, `docs/CHANGELOG_AI.md`,
  `docs/CURRENT_STATE.md`, `docs/AI_HANDOFF.md`, Human Review Overview/index,
  `config/workstreams.yaml`, and superseded task handoffs/backlog wording.

## Known limitations / risks

- The fixed `1e7` cap detects numeric corruption, not venue authority; R1.4
  provenance remains a separate gate.
- API smoke was not required by this code/config shape and no server was
  started. Full replay against TimescaleDB/data was not run; the deterministic
  backtest smoke passed.
- Repair commit `df53f73` is local only. The sandbox could not reach GitHub and
  escalation was rejected by the tool usage limit, so push/PR creation remain
  external follow-up steps.
- No strategy is promotion/demo/shadow/live ready as a result of this repair.

## Rollback plan

- Revert the follow-up commit(s). No schema, data, result artifact, strategy
  assumption, formula, or deployment-gate migration is involved.

## Context Handoff

- See `tasks/2026-07-13-pr9-followup-fixes-context-handoff.md`.

## Questions for human review

- Confirm fail-closed treatment for present-but-incomplete DB/registry specs.
- Confirm the governance parser's strict malformed-row behavior and exact four
  template exemptions.
- Confirm the follow-up PR contains the five post-merge commits plus this repair
  and no protected research/result/gate changes.

## Next recommended task

- Push `codex/pipeline-batch1-stage3`, then open and review the separate follow-up
  PR; after merge, return to the recorded OKX liquidation unattended-mode P1
  task.

## Human Learning Notes (required)

A successful source-provenance label is unsafe if the value was never validated,
and exception order matters: validation after inserting a ledger object leaves
observable ghost state even when the fill raises. Governance checks have the
same failure mode at a different layer — a parser that ignores unusual but
recognizable rows makes malformed evidence look valid. Test the rejection path
and the absence of side effects, not only the raised exception.
