---
status: current
type: handoff
owner: codex
created: 2026-07-26
last_reviewed: 2026-07-26
expires: none
superseded_by: null
---

# Session Handoff: strategy-finding round — 2026-07-26

## Implementation summary

Pre-registered and executed a two-direction research batch. H-023 added a
research-only BTC-residual idiosyncratic-volatility book and stopped at Stage-2
power. H-009 reused its frozen mechanism/grid with corrected 31-asset breadth,
passed Stage 2, completed fold-refit WF/CPCV, and failed checkpoint 1. The shared
funding loader now scopes rows to the declared venue before aggregation.

## Diff scope

- Files added:
  - `backtesting/xs_idiovol_backtest.py`
  - `scripts/run_strategy_finding_20260726.py`
  - `tests/unit/test_xs_idiovol_backtest.py`
  - `tests/unit/test_run_strategy_finding_20260726.py`
  - `docs/superpowers/specs/2026-07-26-strategy-finding-round.md`
  - `docs/change_manifests/2026-07-26-strategy-finding-round.md`
  - `tasks/2026-07-26-strategy-finding-preregistration-receipt.md`
  - this session handoff and its context handoff
  - new `results/strategy_finding_20260726/` artifacts
- Files changed:
  - `backtesting/funding_xs_dispersion_backtest.py`
  - `tests/unit/test_funding_xs_dispersion_backtest.py`
  - `docs/{AI_HANDOFF,CURRENT_STATE,EXPERIMENT_REGISTRY,FAILURE_MODES,GOLDEN_CASES,HYPOTHESIS_LEDGER,INVARIANTS,STRATEGY_HISTORY}.md`
  - `config/workstreams.yaml`
- Files deleted: none.
- Pre-existing unrelated dirty files were preserved.

## Business-rule change?

- Yes: mechanical A5 backtesting/provenance change. Change Manifest at
  `docs/change_manifests/2026-07-26-strategy-finding-round.md`; DOC impact row
  A5 checked strictly.

## Source-of-truth updates

- `research/strategy_synthesis.md`: N/A; Claude-owned, unchanged.
- `config/`: only Progress-panel `config/workstreams.yaml` state synced; no
  strategy/risk/deployment config changed.
- ADR: N/A; no policy, schema, accounting formula, or gate changed.

## Experiments

- HYPOTHESIS_LEDGER entries: H-009 updated; H-023 added and resolved.
- EXPERIMENT_REGISTRY entries: E-060/E-061 pre-registration; E-062 Stage-2
  power fail; E-063 Stage-3/checkpoint statistical fail.

## Tests / checks run

- `python -m pytest tests/unit -q -p no:cacheprovider` — 964 passed, 1 skipped.
- Focused strategy/runner tests — 11 passed.
- Independent adversarial focused suite — 26 passed.
- `python -m ruff check src tests backtesting scripts` — PASS.
- Direct Makefile equivalents for docs-check, strict docs-impact, config, and
  backtest-smoke — PASS (`make` is unavailable in this Windows environment).
- Checkpoint1 auto — FAIL as expected only on DSR/PSR threshold; six other
  checks PASS.
- `git diff --check` — no whitespace errors; line-ending warnings only.

## Docs updated

- Pre-registration spec and receipt.
- H/E ledgers and human-readable strategy history.
- G-007, I52, F55, Change Manifest.
- AI handoff, current state, and matching workstream status.
- Context and session handoffs with Human Learning Notes.

## Known limitations / risks

- Daily funding PnL uses the frozen existing AVG-to-daily research convention,
  not settlement-grade cashflow.
- The frozen spec lacked lifecycle frontmatter before hashing. Docs metadata
  emits one warning; adding metadata after execution was intentionally avoided
  because it would destroy the pre-run hash match.
- `decision.json` records the pre-registry checkpoint precheck; the final
  machine verdict is in `checkpoint1_auto.json` and consolidated in
  `checkpoint_review.json`.
- Both strategies failed; no deployment claim is valid.

## Rollback plan

- Remove only the new H-023/batch/test/handoff files and
  `results/strategy_finding_20260726/`.
- Revert the two funding SQL source predicates and their regression.
- Revert only H-009/H-023, E-060–E-063, G-007, I52, F55, strategy-history,
  current-state, and workstream additions. Preserve every unrelated dirty file
  and every pre-existing result artifact.

## Context Handoff

- See
  `tasks/2026-07-26-strategy-finding-context-handoff.md`.

## Questions for human review

- Claude: does the H-023 Stage-2 result justify a genuinely different future
  thesis, or should the family remain shelved indefinitely?
- Claude: should future research replace the daily AVG funding convention with
  settlement-grade cashflow under a separately pre-registered correctness
  change?

## Next recommended task

- No immediate implementation. Review E-062/E-063, then create a new
  pre-registration only if the mechanism or data rationale is materially new.

## Human Learning Notes (required)

Alias correctness changed the breadth target from 32 symbols to 31 economic
assets. H-009 demonstrates that better WF Sharpe alone is insufficient:
broader data raised WF while CPCV/DSR/PSR deteriorated. The pipeline correctly
stopped H-023 before consuming trials and correctly rejected H-009 after a full
retry, preventing another gate-chasing iteration.

