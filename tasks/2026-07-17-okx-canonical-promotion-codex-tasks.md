---
status: current
type: task
owner: codex
created: 2026-07-17
last_reviewed: 2026-07-17
expires: 2026-10-17
superseded_by: null
---

# Codex Task: OKX raw to source-aware canonical promotion

This restores the follow-up referenced, but not present, in
`tasks/2026-07-17-abc-delivery-claude-review.md`. The user explicitly authorized
the data-promotion task on 2026-07-17.

## Decision

The frozen H-010 window already has complete Binance and OKX BTC/ETH 1m rows in
`raw_candles`, but `canonical_candles` has one priority-resolved row per
`(inst_id, bar, ts)`. Re-running the existing OKX promotion would therefore
insert zero rows; changing that identity in place would mix existing continuous
aggregates and require a blocking migration of roughly 96 million rows.

Keep `canonical_candles` unchanged for default consumers and aggregates. Add an
additive venue-keyed canonical table plus a compatibility view for explicitly
source-scoped consumers. Promote only closed OKX BTC/ETH 1m rows in
`[2024-01-01, 2026-06-17)` and preserve future raw dual-writes.

## Permitted

- Additive market-data migration and canonical policy/store/writer changes
- H-010's source-aware Stage-2 read and the existing OKX coverage verifier
- A fixed-scope promotion command and focused data/delete tests
- ADR, Change Manifest, data/feature/runbook/current-state/known-issue docs and
  required handoffs

## Forbidden

- In-place `canonical_candles` identity or continuous-aggregate changes
- `research/`, hypothesis/experiment ledgers, Stage-1 spec, H-010 retry/verdict
- Existing result artifacts, strategy logic, demo/shadow/live gates
- Treating promotion coverage as a statistical or deployment approval

## Acceptance criteria

- Default canonical rows and aggregates remain byte/row-count compatible.
- Source-aware reads can return Binance and OKX at the same timestamp.
- Corrected/validated resolved rows take precedence over same-source raw rows.
- Promotion is fixed-scope, idempotent, and traceable to raw rows.
- Frozen-window BTC/ETH OKX coverage and cross-venue alignment are at least 95%.
- Pair deletion removes the additive venue rows.

