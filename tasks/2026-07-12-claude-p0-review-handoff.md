---
status: deprecated
type: handoff
owner: claude
created: 2026-07-12
last_reviewed: 2026-07-12
expires: none
superseded_by: tasks/2026-07-12-p0-implementation-context-handoff.md
---

# Context + Session Handoff: Claude review of P0.1–P0.3 and H-012/H-013 — 2026-07-12

Single-file merge of both handoff templates (user-approved 2026-07-03).

## Goal (one sentence)

Deliver the Claude review verdicts Codex requested for the audit P0 blockers
and the two pending research decisions, as durable files, without touching any
protected implementation.

## Current state

- Branch/HEAD: `codex/pipeline-batch1-stage3` at `7636dd9`; working tree also
  carries the earlier Codex audit-repair diff (untouched by this session).
- This session's files: `tasks/2026-07-12-claude-p0-review.md` (new, the review
  record), Claude-review notes appended to H-012/H-013 rows in
  `docs/HYPOTHESIS_LEDGER.md`, refreshed next actions in
  `docs/CURRENT_STATE.md` and `docs/AI_HANDOFF.md`, this handoff.
- Verdicts: P0.1 approve scope with binding amendments (validate-and-reject
  allowlist + resolved-root assert; no `Path().name` truncation); P0.2 propose
  finite-positive contract with ≤1e7 corruption cap and ADR-0003 amendment;
  P0.3 approve, mirror `_normalize_fetch_exchange` 400 pattern; H-012 SHELVE
  recommended; H-013 Stage-1 APPROVE recommended. All pending human ratification.

## Decisions made (and why)

- Recorded verdicts in the ledger without flipping status fields — status
  changes are the user's call (H-009 precedent: Claude review + user-ratified).
- Rejected truncation-based sanitizing for P0.1 because `Path("..").name == ""`
  collapses to root and POSIX keeps backslashes — reject, don't rewrite.
- Chose a constant 1e7 ct_val cap over venue-aware bounds: provenance rule R1.4
  already pins the source; dynamic bounds are speculative complexity.
- E-038 stays reserved-only; a planned zero-trial registry row is double truth.

## Open questions / unverified assumptions

- Human: ratify all four verdicts (P0.1 amendments, P0.2 cap value, P0.3
  omitted-exchange semantics — model default None→config primary recommended,
  H-012 shelve + H-013 sign-off).
- E-037 leak-lag spot check not yet run (pre-shelve hygiene, P1.3).
- Generated-ID formats assumed allowlist-compatible; P0.1 acceptance must prove.

## Rules in play (preserve verbatim)

- I15: no live/shadow/demo claim without all gates passed + human approval.
- I32/I33/I34 remain planned blockers; nothing here implements them.
- H-002 standing constraint: do not tune to chase the gate; retries need
  ex-ante rationale, consume K, and add grid size to family n_trials.
- No strategy, risk, portfolio, execution, config gate, research/, results/,
  differential-validation, or DB schema change was made by this session.

## Context to load next (reading list)

1. `tasks/2026-07-12-claude-p0-review.md` — the review Codex implements from.
2. `tasks/2026-07-12-project-diagnosis-followup-tasks.md` — scopes/acceptance.
3. `docs/CURRENT_STATE.md`, then `docs/AI_HANDOFF.md` next steps.
4. For P0.2 implementation: ADR-0003/0007, `docs/DOMAIN_RULES.md` R1.

## Checks run

- `scripts/docs/check_doc_metadata.py`: pass, 0 warnings.
- `scripts/docs/check_feature_map_links.py`: pass, 210 paths.
- No code changed, so no pytest/frontend/config checks were run (n/a).
- Key review claims spot-checked in-session at routes_backtest.py:3332,
  sizing.py:21-26, routes_data.py:498-502 (scout reports were not self-trusted).

## Approvals

- This session performed review + docs only, within the Claude role.
- P0.1/P0.2/P0.3 implementation, ledger status flips, and branch integration
  all still require explicit human approval.

## Next action (single, concrete)

- Human reads `tasks/2026-07-12-claude-p0-review.md` and ratifies or adjusts
  the four verdicts; then Codex starts P0.1 under the amended scope.

## Human Learning Notes

The review found the repo already contains the correct pattern for two of the
three P0s (read-side ID sanitization; `routes_data.py`'s 400-on-unknown-venue).
The bugs are consistency failures, not missing knowledge — when approving
fixes, prefer "reuse the existing in-repo pattern" over new mechanisms, and ask
which other entrypoints share the same rule.
