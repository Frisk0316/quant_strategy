---
status: current
type: handoff
owner: codex
created: 2026-07-30
last_reviewed: 2026-07-30
expires: none
superseded_by: null
---

# Context Handoff: Optflow retention and FRED ingest — 2026-07-30

## Goal (one sentence)

Retain the full Deribit inverse-option trade tape and ingest the approved FRED
macro series plus an honestly labeled research-only gold proxy.

## Current state

- Branch: `feature/deribit-moneyness-hypotheses`.
- Last known good commit / state: no task commit was created; the scoped working
  tree is ready for review, while two pre-existing untracked 2026-07-29 handoffs
  remain untouched.
- In-progress edits: `.env.example`, `config/external_data.yaml`,
  `config/workstreams.yaml`, `docs/AI_HANDOFF.md`, `docs/CHANGELOG_AI.md`,
  `docs/DATA_FLOW.md`, `docs/FEATURE_MAP.md`, `docs/RUNBOOK.md`,
  `src/okx_quant/data/external_clients/deribit_option_flow.py`,
  `tests/unit/test_deribit_option_flow.py`, and the two 2026-07-30 handoffs.
- What works right now: new optflow ingests retain all inverse trades and
  `trade_id`; the >20-trade regression passes. FRED DGS2/VIXCLS/DTWEXBGS and
  research-only Yahoo `GC=F` are ingested from 2020 onward.
- What does not work / unfinished: the historical full-tape backfill is stopped
  and partial. Only 2,304 BTC hours and 744 ETH hours use
  `all_inverse_trades_in_hour`. BTC aggregate trades now total 12,724,092 versus
  the pre-task 12,724,097 baseline. No restoration source was found, so the
  remaining backfill must not resume without Claude/user direction.

## Decisions made (and why)

- Stopped every background backfill worker as soon as the full-dataset aggregate
  fingerprint diverged — the task makes any aggregate drift a hard stop.
- Did not guess where to add five BTC trades or silently accept the archive
  revision — either action would rewrite evidence without authority.
- Kept `gold_yfinance` explicitly research-only — it is Yahoo `GC=F`, not the
  discontinued FRED/spot-gold input used by the paper.
- Did not add a Change Manifest — `scripts/docs/check_doc_impact.py` reported no
  impact-matrix violation or manifest trigger.

## Open questions / unverified assumptions

- Choose one Deribit path: restore the pre-task aggregates from a DB backup;
  explicitly accept and document the archive revision; or approve a payload-only
  enrichment contract that can disagree with frozen aggregate trade counts.
- Decide whether the unofficial `GC=F` proxy is acceptable for H-036 research.
- No H-031/H-033/H-035/H-036 rerun is authorized by this task.

## Rules in play (preserve verbatim)

- R6.1: No lookahead bias or feature leakage in research or replay.
- R6.2: DB and parquet sources must agree; a source switch must be explicit and
  recorded.
- I51: Deribit option-flow pagination requests explicit descending order and
  moves the next page's inclusive end boundary below the oldest accepted
  millisecond, so a provider's default row order cannot truncate or repeat the
  interval.
- Task immutability rule: any aggregate difference stops the task before bulk
  re-backfill; existing E-064/E-068 evidence must not be retroactively changed.
- Do-not-touch: `research/`, existing `results/**`, ledgers, Stage 2/3 probes,
  strategies/signals/risk/portfolio/execution, DB schema/migrations, and
  demo/shadow/live gates.

## Context to load next (the reading list)

- Source of truth:
  `tasks/2026-07-30-optflow-pertrade-retention-codex-tasks.md`,
  `tasks/2026-07-30-fred-macro-ingestion-codex-tasks.md`,
  `config/external_data.yaml`, and `docs/AI_HANDOFF.md`.
- Owning files: the Market Data Ingestion section in `docs/FEATURE_MAP.md`,
  `src/okx_quant/data/external_clients/deribit_option_flow.py`, and
  `scripts/market_data/backfill_deribit_option_flow.py`.
- Context Pack: no ingestion-specific Context Pack exists; start from
  `docs/CONTEXT_INDEX.md`.

## Checks run

- FRED read-only DGS2 API smoke — 6 rows, values 3.46–3.54, lag check PASS.
- `pytest` targeted ingestion matrix — 25 passed.
- Full unit — 1,036 passed, 1 skipped, 1 unrelated pre-existing failure:
  `test_data_coverage_uses_short_inflight_cache` expects `_memoGet`, while
  `HEAD:frontend/data.js` already uses `_memoGetLarge`.
- Targeted Ruff — PASS.
- `scripts/validate_pipeline.py --check-config-only` — PASS.
- Docs metadata/link/ledger checks — PASS with two pre-existing metadata warnings.
- Advisory doc impact — PASS, no manifest trigger.
- Six-hour pre-flight and six-hour post-hoc Deribit checks — exact
  `value_num`/fields equality and all 3,623 checked trades retained `trade_id`.

## Approvals

- User authorized both ingestion tasks and confirmed the FRED key is in `.env`.
- No approval exists to accept aggregate drift, restore from a specific backup,
  use payload-only mismatch semantics, run H-031/H-033/H-035/H-036, or use the
  gold proxy as accepted research evidence.

## Next action (single, concrete)

- Claude/user chooses the Deribit immutability resolution before any worker is
  restarted.

## Human Learning Notes

A small real-hour sample proved code-path immutability but did not prove source
immutability: Deribit's archive revised unsampled historical trades. Future
enrichment of evidence-bearing rows needs a full aggregate fingerprint or an
update path that structurally cannot overwrite frozen aggregates.
