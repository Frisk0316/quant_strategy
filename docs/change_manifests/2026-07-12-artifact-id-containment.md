---
status: current
type: manifest
owner: codex
created: 2026-07-12
last_reviewed: 2026-07-12
expires: none
superseded_by: null
---

# Change Manifest: Artifact identifier containment

## Summary

Reject caller-controlled artifact identifiers that are not safe single path
components and assert every resolved child remains below its intended root.

## Design-space decision

- Do nothing leaves arbitrary reads/writes possible.
- Per-caller truncation stays inconsistent and can select the wrong artifact.
- Chosen: one stdlib allowlist/resolution helper reused by writers, validation,
  API and CLI entrypoints. It is the smallest option that closes every boundary.

## Business rule(s) affected

None; this is a trust-boundary repair for F30/I32. R7 validation/admissibility
semantics remain unchanged.

## Trigger area(s) (DOC_IMPACT_MATRIX)

A5 backtesting, A7 API, A9 differential/source-provenance validation.

## Files changed

- `backtesting/artifact_rows.py` — shared validate-and-resolve helper.
- `backtesting/artifacts.py`, `backtesting/parameter_sweep.py`,
  `backtesting/turtle_backtest.py` — writer/identifier backstops.
- `backtesting/differential_validation.py` — validation read/write backstops.
- `src/okx_quant/api/routes_backtest.py` — reject before queue/read/delete.
- `scripts/run_all_strategy_signal_validation.py`,
  `scripts/run_differential_validation.py`,
  `scripts/run_replay_backtest.py`,
  `scripts/run_source_provenance_validation.py`,
  `scripts/backfill_backtest_artifact_rows.py` — CLI boundaries.
- Targeted tests and owning maps — regression and navigation evidence.

## Behavior delta

- Before: separators, absolute/drive-relative paths, `.`/`..`, overlong IDs and
  truncation could escape a root or silently select another artifact.
- After: only 1–128 ASCII letters, digits, `.`, `_`, `-` are accepted, excluding
  dot components, trailing dots and Windows device aliases; resolved targets
  must remain under the true requested root even through fixed validation
  namespaces. Execution-comparison reads use only deterministic filenames
  derived from the validated run ID, never a payload-provided sibling path.
- Money/risk impact: none; no result values, gates or existing artifacts change.

## Source-of-truth updates

- research/strategy_synthesis.md: N/A — no strategy assumption changed.
- config/: N/A — no runtime setting changed.
- ADR: N/A — ADR-0002/0005 reviewed; schema and gate policy are unchanged.

## Docs updated (from DOC_IMPACT_MATRIX row)

- [x] `docs/DATA_FLOW.md` — identifier boundary documented.
- [x] `docs/FEATURE_MAP.md` / `docs/UI_MAP.md` — owning helper/tests documented.
- [x] `docs/INVARIANTS.md` / `docs/FAILURE_MODES.md` — I32/F30 closed by tests.
- [x] `docs/GOLDEN_CASES.md` — confirmed unchanged; no expected output changed.
- [x] `docs/DOMAIN_RULES.md`, `docs/ai_collaboration.md`, ADR-0002/0005 — reviewed,
  unchanged because validation conclusions and artifact schema do not change.

## Invariants / golden cases

- Invariants checked: I32; I14/I15 unchanged.
- Golden cases affected: none.

## Tests / checks run

- Final targeted artifact/API/CLI/differential/backtest suite — `306 passed,
  1 skipped` (Windows symlink privilege).
- Full unit `768 passed, 1 skipped`; integration `38 passed`; full Ruff,
  docs/config/backtest-smoke passed. Details:
  `tasks/2026-07-12-p0-implementation-session-handoff.md`.

## Risks and rollback

- Risks: a previously accepted non-portable custom ID now fails explicitly.
- Rollback: revert the helper, caller replacements, tests and this manifest; no
  DB or result-artifact migration is required.

## Approval

- Human approval required: yes — obtained in the user's 2026-07-12 request to
  implement `tasks/2026-07-12-claude-p0-review.md`.
