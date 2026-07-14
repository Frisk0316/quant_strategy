---
status: current
type: handoff
owner: codex
created: 2026-07-13
last_reviewed: 2026-07-13
expires: none
superseded_by: null
---

# Context Handoff: PR #9 follow-up fixes — 2026-07-13

## Goal (one sentence)

Close the remaining correctness and governance gaps found after PR #9 merged,
then deliver the five post-merge commits and this repair as a separate
human-reviewed follow-up PR.

## Current state

- Branch: `codex/pipeline-batch1-stage3`; local repair commit `df53f73`, while
  origin remains at `037b15f`.
- Last known good state: `df53f73` plus the final environment-blocked-push
  handoff synchronization.
- Verified repair scope: replay `ct_val` resolution, position fill atomicity,
  documentation checkers/tests, current-state records, and handoffs.
- What works: explicit DB/registry/caller multipliers fail closed through the
  shared validator; rejected fills do not mutate the ledger; governance rows
  and lifecycle metadata fail closed under adversarial tests.
- Unfinished: push and creation of the separate GitHub PR.

## Decisions made (and why)

- Reuse `validate_ct_val()` at every explicit boundary — one numeric contract
  avoids source-specific interpretations and new abstractions.
- Validate a fill before inserting a `Position` — rejection must be atomic.
- Treat a present but incomplete DB/registry/caller spec as invalid, while a
  genuinely absent source retains the documented fallback behavior.
- Keep the repair on the existing branch and open a new PR — PR #9 is already
  merged, so rewriting or pretending to amend it would obscure review history.

## Open questions / unverified assumptions

- Human/Claude review must confirm the separate follow-up diff before merge.
- Push was attempted once and failed because the sandbox could not reach GitHub;
  escalation was rejected by the tool usage limit. Do not work around it.
- GitHub CLI authentication is unavailable locally; PR creation requires the
  user or a later authenticated environment after the branch is pushed.

## Rules in play (preserve verbatim)

- I34: Numeric `ct_val` validation rejects non-finite/non-positive values and
  values above `1e7` at every explicit input point (fill metadata, replay caller
  specs, DB/config paths); a missing fill value may reuse validated position
  state, while an invalid or incomplete explicit instrument spec must raise
  before entering positions, PnL, or an authoritative provenance label.
- I38: Governance checks fail closed: H↔E links agree in both directions, only
  an explicit per-ID `reserved` annotation exempts a missing experiment, valid
  Markdown table spacing cannot hide rows, and every non-exempt task document
  has non-empty lifecycle metadata.
- Domain rule: R1.5.
- Do-not-touch: `research/`, existing `results/`, strategy/signals/risk/
  execution behavior, DB schema, differential-validation implementation,
  config risk or demo/shadow/live gates.

## Context to load next (the reading list)

- Source of truth: `config/`, ADR-0003, ADR-0007, `docs/DOMAIN_RULES.md`, and
  `docs/change_manifests/2026-07-12-ct-val-validation-contract.md`.
- Owning files/module briefs: `docs/MODULE_BRIEFS/portfolio.md` and
  `docs/MODULE_BRIEFS/backtesting-engine.md`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run

- Targeted repair suite — `139 passed`.
- Full unit — `841 passed, 1 skipped`.
- Integration — `38 passed`; lab — `18 passed`.
- Full Ruff, config validation, and backtest smoke — PASS.
- Docs metadata/links/ledger/overview and strict impact from `00c7a51` — PASS.

## Approvals

- Human approval obtained for implementation: the user explicitly asked Codex
  to repair PR #9 on 2026-07-13.
- Human approval still required to merge the separate follow-up PR.

## Next action (single, concrete)

- Run `git push origin codex/pipeline-batch1-stage3` when GitHub access is
  available, then open its separate PR to `main`; human performs the merge.

## Human Learning Notes

PR state must be checked against the remote before documenting next actions:
five commits described as PR review fixes were created after PR #9's recorded
head and therefore could never have been included in that merge. Source labels
are not proof of value integrity; validate the value before writing either
state or provenance. Finally, fail-closed documentation checkers need
adversarial syntax tests because ordinary well-formed fixtures do not reveal
parser blind spots.
