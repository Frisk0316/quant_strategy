---
status: current
type: handoff
owner: codex
created: 2026-08-06
last_reviewed: 2026-08-06
expires: none
superseded_by: null
---

# Session Handoff: OKX 2020+ canonical promotion — 2026-08-06

## Implementation summary

Measured the live DB before writing, confirmed the historical extension already
existed from `b40f15b`, ran the existing promotion twice as no-ops, PASSed the
full-range verifier, and synchronized the permitted durable docs.

## Diff scope

- Files added: this session handoff and the paired context handoff.
- Files changed: ADR-0014, DATA_FLOW, RUNBOOK, CHANGELOG_AI, AI_HANDOFF,
  CURRENT_STATE, and `config/workstreams.yaml`.
- Files deleted: none.

## Business-rule change?

- No. This is an authorized window extension under unchanged ADR-0014 policy;
  no Change Manifest or new ADR is required.

## Source-of-truth updates

- research/strategy_synthesis.md: N/A; forbidden and no strategy change.
- config/: state mirror only (`config/workstreams.yaml`); no runtime setting.
- ADR: dated ADR-0014 amendment added; Claude/user review pending.

## Experiments

- HYPOTHESIS_LEDGER entries: none.
- EXPERIMENT_REGISTRY entries: none.

## Tests / checks run

- Exact pre-write DB coverage — `market_klines` and `raw_candles` agreed:
  BTC first/last/count `2020-01-01 00:00` / `2026-07-01 14:59` / 3,418,020;
  ETH `2020-01-01 00:00` / `2026-06-16 23:59` / 3,396,960.
- Exact pre-2024 gap SQL — each symbol 2,103,840/2,103,840 minutes, zero
  missing minutes, zero gap runs, largest gap zero minutes.
- Promotion command twice — COMPLETE, zero changed rows both times.
- `verify_okx_1m_backfill.py --start 2020-01-01 --end 2026-06-17` — PASS.
- Canonical Binance before/after SQL — unchanged per affected symbol.
- `pytest tests/unit/test_venue_canonical_promotion.py -q` — 10 passed in 2.86s.
- Docs metadata/links/ledger checks — PASS.
- Doc impact — PASS, no impact-matrix violations.
- Config validation — PASS.

## Docs updated

- ADR-0014, DATA_FLOW, RUNBOOK, CHANGELOG_AI, AI_HANDOFF, CURRENT_STATE, and
  workstream mirror. FEATURE_MAP is N/A because ownership/behavior did not
  change and it is outside the permitted file list.

## Known limitations / risks

- Only BTC/ETH price history is extended. The 30-symbol cross-section stays
  2024+; BTC/ETH price-only consumers can join at most the measured 2,359
  candle days before their own warmup/input constraints. Pre-2024 OKX funding
  remains absent, and H-010 remains shelved.
- Future power floors require measured consumer-specific joined observations.
- Independent fresh-context verification remains pending with Claude; this
  session completed deterministic DB, test, docs, config, and scope checks.

## Rollback plan

- Revert this task's doc/handoff diff. No data rollback is needed because both
  authorized promotion runs changed zero rows.

## Context Handoff

- See `tasks/2026-08-06-okx-2020-canonical-promotion-context-handoff.md`.

## Questions for human review

- Confirm the dated ADR-0014 amendment accurately records the already-complete
  July extension and the 2026-08-06 re-verification.

## Next recommended task

- Claude performs the requested delivery review; do not rerun H-010.

## Human Learning Notes (required)

The live DB and git history contradicted the stale task premise: the extension
already existed. Reporting zero-row no-op evidence is more accurate than
claiming a second promotion inserted historical data.
