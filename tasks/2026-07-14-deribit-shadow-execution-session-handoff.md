---
status: current
type: handoff
owner: codex
created: 2026-07-14
last_reviewed: 2026-07-14
expires: none
superseded_by: null
---

# Session Handoff: ADR-0011 H-014 shadow execution — 2026-07-14

## Implementation summary

Implemented T1–T4 as a manual, isolated shadow-only package: imported research
signal/strike/accounting definitions, F26-safe exact-day DB reads, bounded
three-leg intents, public order-book hypothetical fills, append-only JSONL,
marks/settlement, and the exit-criteria report. A bounded data refresh enabled
the first valid real-DB cycle; both symbols were `not_rich`.

## Diff scope

- Files added: shadow package, `config/h014_shadow.yaml`, manual CLI, unit test,
  module brief, Change Manifest, human overview, and two handoffs.
- Files changed: ADR index, R8/I39/I40/F39/G-004 governance, impact matrix,
  feature/data/runbook maps, current state, known issues, changelog, overview
  index, and module-brief index.
- Files deleted: none.

## Business-rule change?

- Yes. Change Manifest at
  `docs/change_manifests/2026-07-14-deribit-options-shadow-execution.md`;
  DOC_IMPACT_MATRIX rows A2 and A12 checked.

## Source-of-truth updates

- research/strategy_synthesis.md: N/A; not modified.
- config/: added only `config/h014_shadow.yaml`; frozen values validate at load.
- ADR: ADR-0011 was already accepted; only the ADR index was synchronized.

## Experiments

- HYPOTHESIS_LEDGER entries: none by Codex.
- EXPERIMENT_REGISTRY entries: none by Codex.

## Tests / checks run

- Full unit suite: 861 passed, 1 skipped; existing numerical warnings only.
- Targeted shadow plus R8 golden: 17 passed.
- Ruff, config check, doc metadata, feature links, ledger, human overview, and
  strict doc impact: passed.
- Real DB five-day parity: within `|Δivp| < 0.5`, `|Δz| < 0.05`.
- Public Deribit book smoke: succeeded without credentials.
- Manual cycle/report: succeeded; BTC/ETH `not_rich`; all live gates false.

## Docs updated

- `docs/DOMAIN_RULES.md`, `docs/INVARIANTS.md`, `docs/FAILURE_MODES.md`,
  `docs/GOLDEN_CASES.md`, `docs/DOC_IMPACT_MATRIX.md`, `docs/ADR/README.md`.
- `docs/FEATURE_MAP.md`, `docs/DATA_FLOW.md`, `docs/RUNBOOK.md`, module brief.
- `docs/CURRENT_STATE.md`, `docs/KNOWN_ISSUES.md`, `docs/CHANGELOG_AI.md`,
  human overview/index, this handoff and its context companion.

## Known limitations / risks

- Eight weeks and the three bias metric families are not yet complete.
- The valid day was not RICH; quote reachability was tested independently.
- Data refresh and shadow cycles remain manual; JSONL assumes one process.
- Imported research helpers are intentional authorities and remain an upstream
  dependency; their accepted definitions must not drift silently.

## Rollback plan

- Remove the new package/config/CLI/test/docs and revert only this task's doc
  additions. No DB schema or existing tracked result migration exists. The
  public market-data upserts/parquet extensions are valid source refreshes and
  need no destructive rollback for a code rollback.

## Context Handoff

- See `tasks/2026-07-14-deribit-shadow-execution-context-handoff.md`.

## Questions for human review

- Does the reviewer accept exact-day fail-closed behavior, signal-day-qualified
  IDs, and the dual span/distinct-week interpretation of “at least 8 weeks”?
- Does Claude agree that incomplete top-of-book makes the whole three-leg
  shadow entry missed and that current R8 mark/settlement signs match research?

## Next recommended task

- Claude review, then continue daily manual cycles; do not schedule anything.

## Human Learning Notes (required)

The real smoke found two bugs that synthetic tests alone missed: research days
close at 08:00 UTC rather than midnight, and append-only recovery needs the
signal date in identity. Preserving the bad rows while excluding them from the
gate gave both auditability and correct forward behavior.
