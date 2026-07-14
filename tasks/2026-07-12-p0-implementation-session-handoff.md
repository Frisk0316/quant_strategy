---
status: archived
type: handoff
owner: codex
created: 2026-07-12
last_reviewed: 2026-07-12
expires: none
superseded_by: null
---

# Session Handoff: P0.1-P0.3 implementation — 2026-07-12

## Implementation summary

Implemented the user-ratified Claude P0 review. Artifact IDs now use shared
ASCII component validation and true-root containment across API, library,
artifact writers/readers, validation/sweep paths, and caller-facing CLIs;
unknown explicit venues fail before queueing while omitted/blank values use the
configured primary; numeric `ct_val` now requires finite `0 < value <= 1e7`.
H-012/H-013 decisions were synchronized without running research or editing
existing results.

## Diff scope

- Files added: three P0 Change Manifests; this session handoff and its Context
  Handoff.
- Files changed: artifact helpers/writers/sweeps/differential validation;
  backtest API and relevant CLIs; shared sizing validator; targeted unit tests;
  ADR/rules/invariants/failure modes/maps/state/progress/ledger/spec/overview.
- Files deleted: none.
- The working tree also contains the earlier project-audit repair diff; it was
  preserved and not treated as newly authored P0 code.

## Business-rule change?

- Yes. Numeric `ct_val` R1.5 and externally visible venue fail-closed behavior
  changed; artifact containment is a trust-boundary repair. Manifests:
  `docs/change_manifests/2026-07-12-{artifact-id-containment,ct-val-validation-contract,venue-fail-closed}.md`.
  DOC_IMPACT rows reviewed: A2, A5, A7, A9.

## Source-of-truth updates

- research/strategy_synthesis.md: N/A; forbidden and unchanged.
- config/: behavior values unchanged; `config/workstreams.yaml` status updated.
- ADR: ADR-0003 received the approved dated numeric-domain amendment; ADR-0007
  was reviewed unchanged.

## Experiments

- HYPOTHESIS_LEDGER entries: H-012 shelved/no retry; H-013 Stage-1 signed off.
- EXPERIMENT_REGISTRY entries: H-012 family note updated; no E-038 row created.
- Existing experiment/result artifacts: unchanged.

## Tests / checks run

- Pre-review artifact/API/CLI/differential/backtest slice — `199 passed`.
- Pre-review sizing/execution/PnL/ct_val/OI/replay slice — `79 passed`.
- Independent read-only reviewer slices — P0.1 `156 passed`, P0.2 `55 passed`,
  P0.3 `15 passed`; no behavior blocker found, and their findings were applied.
- Final static P0.1 re-review after all fixes — no blocker or major finding.
- `git diff --check` after reviewer fixes — passed (CRLF warnings only).
- Final P0 target suite — `306 passed, 1 skipped`.
- Full unit — `768 passed, 1 skipped`; integration — `38 passed`.
- Full Ruff, docs metadata/links/overview, `docs-impact --strict`, config and
  backtest smoke — passed. Frontend syntax — 12 files passed.
- API smoke — explicit SKIP because `API_BASE_URL` was not set.
- Optional local `validate-data` — advisory FAIL because
  `data/ticks/BTC_USDT_SWAP/{candles_1H,funding}.parquet` is absent; its config
  checks passed. This is not a P0 behavior failure.

## Docs updated

- ADR-0003, DOMAIN_RULES, INVARIANTS, FAILURE_MODES, KNOWN_ISSUES, FEATURE_MAP,
  DATA_FLOW, UI_MAP, CURRENT_STATE, AI_HANDOFF, CHANGELOG_AI, workstreams, task
  plan, hypothesis/experiment records, accepted H-013 spec, Human Review
  Overview/index, and three Change Manifests.

## Known limitations / risks

- The symlink-escape regression skips on Windows without symlink privilege; it
  remains executable on Linux or a privileged Windows environment.
- Local artifact-directory manipulation between resolve and I/O remains a
  general TOCTOU risk; caller-controlled components and fixed namespace symlink
  escapes are fail-closed, but the results root itself must remain trusted.
- H-012's F36 cost-lag bug is documented, not fixed; the strategy is shelved and
  its old artifact is not promotion evidence.

## Rollback plan

- Revert only the P0 helper/caller/test/doc/Manifest files. No DB migration or
  result-artifact rollback is needed. Preserve the unrelated audit-repair diff.

## Context Handoff

- See `tasks/2026-07-12-p0-implementation-context-handoff.md`.

## Questions for human review

- None for P0. Git execution remains separately scoped; P0.4 Option B is
  approved but this session did not merge/commit/push.

## Next recommended task

- Separately execute P0.4 Option B with `verify-full` on the integration commit.

## Human Learning Notes (required)

The initial three P0 findings shared one theme: plausible fallback behavior is
dangerous at trust boundaries. Rejecting bad IDs/venues and separating numeric
validity from provenance produced a smaller and more auditable design than
adding per-caller sanitizers or venue-specific multiplier machinery.
