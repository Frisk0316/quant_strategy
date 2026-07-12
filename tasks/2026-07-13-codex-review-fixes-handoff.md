---
status: current
type: handoff
owner: human
created: 2026-07-13
last_reviewed: 2026-07-13
expires: none
superseded_by: null
---

# Session Handoff: Codex PR #9/#10 review fixes — 2026-07-13

## Goal (one sentence)

Fix every blocker/major from Codex's Request-changes reviews of PR #9 and the
already-merged PR #10 batch, all on `codex/pipeline-batch1-stage3`.

## Implementation summary

PR #9 blocker (P0.2/R1.5/I34): `PositionLedger._fill_ct_val` now routes every
explicitly provided multiplier through shared `validate_ct_val()` (inf/>1e7
raise; NaN no longer silently 1.0; fallback only when no value provided);
replay caller `instrument_specs` validated before the authoritative
`config_override` label. PR #10: RUNBOOK gate text defers to
`docs/ai_collaboration.md` (PSR restored, bar-proxy removed, `ctVal > 1` note
corrected to `<=1e7`); all completed June+July tasks/ docs demoted to
`archived` (only the active backlog + two latest handoffs stay `current`);
A11 validator hardened (reverse H-row listing required, per-ID reserved
scoping, empty-table failure, `K_used >= 0`, `K_limit == 2`); task metadata
checker scans tasks/ recursively with a frozen 65-name legacy allowlist
(undated/backdated/nested enforced); doc sync (new Human Review Overview +
review_index row, branch-ref staleness, 8080-abandoned wording, CHANGELOG
commit dates corrected).

## Diff scope

- Commits `6129f94` (money-path fix), `48fb9d3` (R1.5/I34 docs), `2c3ba18`
  (governance/docs fixes) on `codex/pipeline-batch1-stage3`, pushed.
- Added: `tests/unit/test_doc_metadata_tasks.py`,
  `docs/human_overviews/2026-07-13-p0-p1-governance-overview.md`, this file.
- Changed: positions.py, replay.py, both docs checkers, RUNBOOK,
  DOMAIN_RULES, INVARIANTS, ct_val manifest, CHANGELOG, state docs,
  review_index, workstreams.yaml, ~110 tasks/ frontmatter statuses.

## Business-rule change?

Enforcement closure only (R1.5/I34 unchanged in content): recorded as an
addendum in `docs/change_manifests/2026-07-12-ct-val-validation-contract.md`.
No PnL/fee/funding/sizing formula changed. `docs-impact --strict` passes.

## Experiments / source-of-truth

None; registry/ledger untouched except no-op formatting. config/: workstreams
progress text only. ADR: none.

## Tests / checks run

Full unit `801 passed, 1 skipped` (Windows symlink privilege); integration
`38 passed`; lab `18 passed`; Ruff; docs metadata/links/ledger/human-overview
and `docs-impact --strict`; backtest smoke earlier in session. api-smoke and
validate-data remain SKIP/environment-FAIL as before.

## Known limitations / risks / rollback

- K_limit hard-pinned to 2 in the validator; changing retry policy now
  requires editing registry text + validator together (intended friction).
- Frozen legacy allowlist means renaming a legacy file re-triggers
  enforcement (acceptable; rename = new file).
- Rollback: revert the three commits; no data/artifacts touched.

## Approvals / next action

PR #9 re-review by Codex is the single next action; merge needs the user's
explicit approval per P0.4.

## Human Learning Notes (required)

Two lessons: (1) "moved verbatim" is not automatically safe — the README text
was itself stale, so verbatim relocation propagated wrong gate rules into the
authoritative RUNBOOK; migration must reconcile against the source of truth,
not the source document. (2) My own guard test caught my first reserved-scope
fix as still leaky (comma-separated IDs inside one segment) — adversarial
tests on validators pay for themselves immediately.
