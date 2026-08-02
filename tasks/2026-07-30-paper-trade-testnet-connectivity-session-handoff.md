---
status: current
type: handoff
owner: codex
created: 2026-07-30
last_reviewed: 2026-07-30
expires: none
superseded_by: null
---

# Session Handoff: Paper-trade testnet connectivity — 2026-07-30

## Implementation summary

Implemented Deribit Phase 1's testnet hard lock and mocked full order lifecycle,
new fixed-host Binance Spot/USD-M signed clients plus a bounded independent-
venue smoke, and a small OKX demo smoke that reuses the existing broker and
credential names. No authenticated request, strategy wiring, scheduler,
runtime gate, or real-capital path was activated.

## Diff scope

- Files added: Binance testnet package (three files), Binance and OKX smoke
  scripts, Binance tests, the Change Manifest, and this handoff pair.
- Files changed: Deribit private client/adapter and two tests,
  `.env.example`, `docs/FEATURE_MAP.md`, `docs/AI_HANDOFF.md`,
  `docs/CURRENT_STATE.md`, and `config/workstreams.yaml`.
- Files deleted: none.

## Business-rule change?

- Yes. R8.9's accepted ADR-0018 exception is implemented as a test-only hard
  lock. Change Manifest:
  `docs/change_manifests/2026-07-30-h014-testnet-activation.md`; impact row A2.

## Source-of-truth updates

- `research/strategy_synthesis.md`: N/A — frozen and untouched.
- `config/`: no execution/risk setting changed; only workstream status was
  synchronized with `docs/AI_HANDOFF.md`.
- ADR: N/A — ADR-0018 was already accepted; no ADR content changed.

## Experiments

- HYPOTHESIS_LEDGER entries: none.
- EXPERIMENT_REGISTRY entries: none.

## Tests / checks run

- `python -m pytest -p no:cacheprovider` on the three targeted test files —
  49 passed.
- Targeted `ruff check` — passed; new Binance/OKX files pass
  `ruff format --check`.
- Config validation — passed.
- Documentation metadata/links/ledger checks — passed; two unrelated metadata
  warnings remain.
- Documentation impact advisory and strict — passed.
- Deribit, Binance, and OKX credential preflights — blocked before real
  authenticated traffic because valid paper keys are absent.
- H-014 panic `--dry-run` — passed without a network call or state write.

## Docs updated

- `docs/FEATURE_MAP.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`,
  `config/workstreams.yaml`, the Change Manifest, and this handoff pair.
- `docs/DOMAIN_RULES.md`, `docs/INVARIANTS.md`, and
  `docs/FAILURE_MODES.md` were reviewed and recorded unchanged in the manifest.

## Known limitations / risks

- No real venue output exists; credentials, permissions, account mode, and
  order responses remain unverified.
- A Binance POST followed by a failed cancellation can still leave order state
  unknown; the smoke makes a bounded cancel-by-client-ID attempt and surfaces
  the original placement error.
- Futures smoke needs an existing non-zero one-way test position and refuses
  flat/hedge accounts.
- New smoke commands are not yet in `docs/RUNBOOK.md` because the task's
  permitted-file lists excluded it.

## Rollback plan

- Revert only the implementation/tests/docs listed above. No DB, scheduler,
  config gate, result artifact, or venue state was changed.

## Context Handoff

- See `tasks/2026-07-30-paper-trade-testnet-connectivity-context-handoff.md`.

## Questions for human review

- Does Claude approve the Phase 1 code/evidence as far as it can be reviewed
  without credentials? Phase 2 must remain no-go until real plumbing evidence
  exists and Claude says go explicitly.
- Approve the current official Binance USD-M host
  `https://demo-fapi.binance.com` in place of the stale task hostname.
- Authorize a docs-only follow-up for RUNBOOK/ADR index/human-review overview
  if those surfaces are required before merge.

## Next recommended task

- Supply trade-scoped paper keys, run the three manual authenticated smokes,
  and stop again for Claude's Deribit Phase 1 review.

## Human Learning Notes (required)

Connectivity code presence is not connectivity evidence. The safe Futures
smoke must not create exposure just to satisfy a checklist, so flat/hedge is an
honest blocked result while Spot proceeds independently. Lost POST responses
also require a pre-generated client order ID; waiting for an exchange order ID
is too late for cleanup.
