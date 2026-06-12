---
status: current
type: governance
owner: human
created: 2026-05-11
last_reviewed: 2026-05-11
expires: none
superseded_by: null
---

# Archive

Archived documents are historical context only. They must not be used as implementation authority.

Move completed plans, resolved reviews, and obsolete coordination notes here when they are worth retaining but no longer represent current work.

Before archiving a document:

- Set `status: archived` in its lifecycle metadata when practical.
- Confirm any durable decision has been moved into an accepted ADR, current architecture doc, runbook, or `docs/AI_HANDOFF.md`.
- Remove completed historical detail from `docs/AI_HANDOFF.md`.

## Archived Documents

| Document | Historical context |
|---|---|
| `backtest_artifacts_claude_instructions.md` | Backtest artifact export task brief; superseded by ADR-0002 and current artifact implementation. |
| `Crypto_Quant_Plan_v1.md` | Original broad strategy and architecture research memo; superseded by the current strategy synthesis truth source. |
| `improved_ohlcv_timescaledb_plan.md` | PostgreSQL / TimescaleDB OHLCV pipeline planning note; retained as design history. |
| `pr1_pr2_review_and_next_pr_plan.md` | PR1 / PR2 governance review and follow-up PR plan; superseded by current handoff and governance docs. |
