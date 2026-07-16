---
status: current
type: handoff
owner: codex
created: 2026-07-15
last_reviewed: 2026-07-15
expires: none
superseded_by: null
---

# Session Handoff: H-014 Claude-review conditions — 2026-07-15

## Implementation summary

Replaced the self-delegation signal test with a recorded real-DB-shape fixture
checked against five immutable E-039 days per symbol. Intent construction and
R8.3 validation `ValueError`s now journal `missed_entry` and `rejected`
respectively, preserve error text, continue the other currency, and report
rejections outside the missed-entry denominator.

## Diff scope

- Files added: `tests/fixtures/h014_shadow_db_signal.json`, this handoff, and
  `tasks/2026-07-15-h014-shadow-review-conditions-context-handoff.md`.
- Files changed: H-014 runner/test/config comment, module brief,
  `docs/DOMAIN_RULES.md`, `docs/INVARIANTS.md`, `docs/FAILURE_MODES.md`,
  `docs/FEATURE_MAP.md`, and the existing ADR-0011 Change Manifest.
- Files deleted: none.

## Business-rule change?

- Yes, implementation/clarification of existing R8.3/R8.7 audit semantics.
  Updated Change Manifest at
  `docs/change_manifests/2026-07-14-deribit-options-shadow-execution.md`; checked
  DOC_IMPACT_MATRIX rows A2 and A12. No policy change or new ADR.

## Source-of-truth updates

- research/strategy_synthesis.md: N/A; research and immutable results unchanged.
- config/: comment only in `config/h014_shadow.yaml`; frozen values unchanged.
- ADR: N/A; accepted ADR-0011 scope and policy are unchanged.

## Experiments

- HYPOTHESIS_LEDGER entries: none.
- EXPERIMENT_REGISTRY entries: none.

## Tests / checks run

- `python -m pytest tests/unit/test_h014_shadow.py tests/unit/test_h014_options_accounting.py -q`
  — 19 passed.
- `python -m ruff check` on touched Python — passed.
- One-line `published_at <= $2` mutation — fixture test failed; reverted.
- One-line 08:00 close-boundary mutation — fixture test failed; reverted.
- Metadata, feature-link, ledger-consistency, strict doc-impact checkers — passed.
- `scripts/validate_pipeline.py --check-config-only` — passed.

## Docs updated

- Module brief documents the 1,570-day measurement and 08:00 convention.
- R8.7, I39, F40, Feature Map, and the existing Change Manifest reflect the
  journaled failure/rejection behavior and fixture guard.

## Known limitations / risks

- The committed fixture samples five days per symbol rather than replaying all
  1,570 measured days; it contains both RICH and not-rich states and pins both
  SQL contracts.
- Shared-worktree P1.4 liquidation edits are concurrent and unrelated; they
  must not be attributed to this H-014 task.

## Rollback plan

- Revert only the files listed in this handoff and remove the new fixture/two
  handoffs. No DB, existing result artifact, scheduler, or deployment state was
  changed.

## Context Handoff

- See `tasks/2026-07-15-h014-shadow-review-conditions-context-handoff.md`.

## Questions for human review

- None before Claude re-review. Scheduler registration remains a separate
  explicit user decision after Claude passes this diff.

## Next recommended task

- Claude re-review of both conditions; do not register a scheduler.

## Human Learning Notes (required)

The previous parity test could only prove that a function equaled its own
delegate. The durable guard is the combination of immutable expected outputs,
recorded DB-return rows, and explicit SQL-contract assertions; all three are
needed to catch shape drift offline.
