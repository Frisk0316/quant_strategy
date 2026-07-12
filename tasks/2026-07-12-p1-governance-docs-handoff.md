---
status: current
type: handoff
owner: human
created: 2026-07-12
last_reviewed: 2026-07-12
expires: none
superseded_by: null
---

# Session Handoff: P1.1 governance + P1.2 docs cleanup — 2026-07-12

## Goal (one sentence)

Execute user-authorized P1.1 governance enforcement and P1.2 documentation
cleanup on branch `claude/p1-governance-docs` for Codex review.

## Implementation summary

P1.1: added `make test-lab` (separate crypto-alpha-lab pytest invocation) and
wired it into `verify`; added `scripts/docs/check_ledger_consistency.py` (A11:
H↔E ID links, family agreement, K-budget bounds) into `docs-check` plus
`tests/unit/test_ledger_consistency.py`; enforced lifecycle frontmatter for
dated `tasks/` files ≥2026-07-01 in `check_doc_metadata.py` (28 July files
migrated, 4 templates updated, pre-July legacy exempt); documented overview
coverage as a manual review step. P1.2: README slimmed 897→101 lines with all
operational commands and gate wording moved verbatim into `docs/RUNBOOK.md`
(subagent-executed, gates unweakened); archived the two completed 2026-06-25
plan docs; backfilled CHANGELOG 07-05/07-07/07-11 entries.

## Current state / diff scope

- Branch: `claude/p1-governance-docs` off `f1aac94`; PR to
  `codex/pipeline-batch1-stage3` pending.
- Added: `scripts/docs/check_ledger_consistency.py`,
  `tests/unit/test_ledger_consistency.py`, this handoff.
- Changed: `Makefile`, `scripts/docs/check_doc_metadata.py`, `README.md`,
  `docs/RUNBOOK.md`, `docs/DOC_IMPACT_MATRIX.md`, `docs/EXPERIMENT_REGISTRY.md`
  (new F-VRP-TIMING K row only), `docs/CHANGELOG_AI.md`,
  `docs/CURRENT_STATE.md`, `docs/AI_HANDOFF.md`, `config/workstreams.yaml`,
  `docs/human_overviews/README.md`, 2 archived plan docs, 4 task templates,
  29 tasks/ frontmatter migrations. Deleted: none.

## Business-rule change?

No. Governance tooling and docs only; no PnL/fee/funding/sizing/fill/gate
behavior changed. `docs-impact --strict` passes.

## Source-of-truth updates

- research/strategy_synthesis.md: N/A. ADR: N/A (0001/0006 already fixed).
- config/: `config/workstreams.yaml` progress state only.

## Experiments

- None. EXPERIMENT_REGISTRY change is bookkeeping (F-VRP-TIMING 0/2 K row);
  E-038 remains reserved-only.

## Decisions made (and why)

- Lifecycle cutoff = filename date ≥ 2026-07-01 — deterministic, matches the
  recorded human decision; pre-July files are never scanned.
- Overview coverage stays manual (documented step) — format checker cannot
  judge coverage honestly; ponytail: document, don't fake automation.
- One `superseded` status in an existing July handoff normalized to
  `deprecated` (checker vocabulary).

## Rules in play (preserve verbatim)

- Do-not-touch: `research/` code (only ran its tests), existing `results/**`,
  strategies/signals/risk/portfolio/execution, `config/risk.yaml`, gates.
- Gate wording moved verbatim; README states research-only/not-live-ready.

## Tests / checks run

- Unit `776 passed, 1 skipped`; integration `38 passed`; lab `18 passed`
  (separate invocation; combined invocation fails collection — that is the
  import-mixing the separate target exists to avoid). Ruff pass; docs
  metadata/links/ledger/impact-strict/human-overview pass; frontend 12-file
  `node --check` pass; config check pass; backtest smoke pass.

## Known limitations / risks / rollback

- Ledger validator checks table consistency only, NOT artifact existence
  (stated in its output and DOC_IMPACT_MATRIX A11).
- `make` unavailable on Windows: targets verified via equivalent commands.
- Rollback: revert the branch; no data or artifacts touched.

## Approvals / questions for Codex review

- User authorized P0.4+subsequent tasks 2026-07-12; Codex reviews this PR.
- Review focus: RUNBOOK verbatim-move fidelity (gates/commands), lifecycle
  cutoff rule, ledger-validator parsing assumptions (8-col ledger, 9-col
  registry, `| F-` K rows, "reserved" exemption).

## Next action (single, concrete)

Codex reviews/merges PR #9, then this branch's PR; then implements OKX
liquidation unattended mode (approved P1.4 item).

## Human Learning Notes (required)

The A11 validator paid for itself on first run: F-VRP-TIMING was missing from
the K-budget table (H-013 existed in the ledger with no K row). Manual ledger
discipline drifts within days of a new hypothesis; the machine check catches
this class permanently. Also: combining lab + parent pytest in one invocation
fails collection — the separate `test-lab` target is load-bearing, not style.
