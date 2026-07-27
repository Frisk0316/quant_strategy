---
status: current
type: handoff
owner: codex
created: 2026-07-24
last_reviewed: 2026-07-24
expires: none
superseded_by: null
---

# Context Handoff: E-058 repair / E-059 reprobe blocked on T1 — 2026-07-24

## Goal (one sentence)

Repair only the frozen E-058 data inputs, then run the identically contracted
E-059 Stage-2 reprobe after T1 verification, stopping at H-022 `testing` only if
all four checks pass and never entering Stage 3.

## Current state

- Branch: `feature/h014-e052-shadow`.
- Last known good commit / state: T2 is committed at `8fac3f7`; E-058 remains
  immutable at SHA-256
  `a61f58c0c2ea8b539b6cb0896abde6cd50e1154a7bbd59794db11f3b7a275a10`.
- In-progress edits (files): state-only handoff updates in
  `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, and
  `config/workstreams.yaml`; unrelated pre-existing dirty changes coexist and
  must remain untouched.
- What works right now: the T2 pure consumer-time alias helper, R6.7, I50, F53,
  ADR-0015, Change Manifest, and regression test all pass. The membership
  parquet is byte-identical at SHA-256
  `9822810321262e76a65bccf18a519ac2f61f05f986bd13b730c0cb3d9e1657c5`.
- What does not work / unfinished: T1 is `NEEDS-HUMAN`. The sandbox Binance
  preflight returned no rows, so no ingest was attempted because the existing
  client can turn a network failure into an empty response. ETHUSDT remains
  0/1,293,120 required raw minutes. T3 is not started: E-059 is neither
  registered nor run, and the alias helper is deliberately not wired into the
  taker-flow probe.
- T1 baseline: 898 expected days (2024: 366/527,040 minutes; 2025:
  365/525,600; 2026 through 2026-06-16: 167/240,480). The pre-ingest non-ETH
  symbol-count snapshot SHA-256 is
  `c2b7bf0313b30ae203548e718d91621d33f98c6c6c3475970a05ffc597146858`.

## Decisions made (and why)

- Keep the PIT membership parquet immutable and collapse aliases only in an
  explicitly opted-in consumer after PIT top-30 selection — because the source
  artifact is historical evidence and aliasing changes economic identity, not
  venue membership.
- Preserve first-seen order, map Binance
  `SHIB-USDT-SWAP -> 1000SHIB-USDT-SWAP`, deduplicate once, and do not refill
  from rank 31 — because refilling would silently change the frozen universe
  contract.
- Do not wire the helper into `backtesting/taker_flow_probe.py` in T2 — because
  that wiring is the sole E-059 execution-code change and T3 is gated on a
  verified T1 PASS.
- Do not run `ingest.py` after the empty sandbox preflight — because a swallowed
  network error could create a misleading zero-row success/checkpoint.

## Open questions / unverified assumptions

- Human network access can retrieve Binance USD-M perpetual ETHUSDT 1m klines
  for `[2024-01-01T00:00:00Z, 2026-06-17T00:00:00Z)`.
- The post-ingest database will contain 898/898 parseable member-days and
  exactly 1,293,120 ETHUSDT rows whose raw payload array has 12 slots.
- All non-ETH raw row counts will retain the baseline snapshot hash above.

## Rules in play (preserve verbatim)

- Invariants touched: I50 — membership bytes are immutable; alias collapse is
  exchange-scoped, order-preserving, consumer-time, post-selection, and cannot
  refill rank N+1.
- Domain rules touched: R6.7.
- Do-not-touch: `research/`; the membership parquet; all E-058 artifact bytes;
  existing backtest result artifacts; live/shadow/demo/deployment gates;
  strategy, risk, PnL, fee, funding, sizing, and fill assumptions; Stage 3;
  unrelated dirty working-tree files.

## Context to load next (the reading list)

- Source of truth:
  `tasks/2026-07-24-e058-repair-e059-codex-tasks.md`,
  `tasks/2026-07-24-e058-claude-review.md`,
  `docs/ai_collaboration.md`, `research/strategy_synthesis.md`,
  `docs/ADR/0015-consumer-time-economic-asset-aliases.md`, and
  `docs/change_manifests/2026-07-24-consumer-time-universe-aliases.md`.
- Owning files / MODULE_BRIEFS: `scripts/market_data/ingest.py`,
  `backtesting/taker_flow_probe.py`,
  `backtesting/pipeline_stage2_registry.py`,
  `backtesting/universe_aliases.py`, `docs/EXPERIMENT_REGISTRY.md`, and
  `docs/HYPOTHESIS_LEDGER.md`.
- Context Pack: no task-specific pack exists; start from
  `docs/CONTEXT_INDEX.md` and `docs/CONTEXT_PACKS/README.md`.

## Checks run

- `python -m pytest tests/unit/test_universe_aliases.py -q` — 1 passed.
- `python -m pytest tests/unit/ -q --tb=short -p no:cacheprovider` — 955
  passed, 1 skipped.
- `python -m ruff check src/ tests/ backtesting/ scripts/` — passed.
- Docs metadata, feature-map links, ledger consistency, and
  `scripts/docs/check_doc_impact.py --strict` — passed.
- Config validation, backtest smoke, and `git diff --check` — passed; the
  idealized-fill smoke is not promotion evidence.
- Membership and E-058 SHA-256 checks before/after T2 — byte-identical.

## Approvals

- Human approval obtained for T1/T2 and the conditional T3 sequence in the task
  file. Human execution is now required for T1 network access. No approval
  exists for Stage 3, promotion, deployment, or any change to the frozen E-058
  artifact.

## Next action (single, concrete)

- From the repository root on a network-enabled host, first run:

  `& 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' -c "from okx_quant.data.exchange_clients.binance_public import BinancePublicClient; c=BinancePublicClient(timeout=5); rows=c.get_klines('ETHUSDT','1m',start_ms=1704067200000,end_ms=1704067259999,limit=1,market_type='futures'); c.close(); print({'rows':len(rows),'first_ts_ms':rows[0]['ts_ms'] if rows else None,'raw_slots':len(rows[0]['raw_payload']['raw']) if rows else None})"`

  Continue only if it prints `rows: 1` and `raw_slots: 12`, then run:

  `& 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' scripts\market_data\ingest.py --exchange binance --dataset klines_1m --symbols ETHUSDT --start 2024-01-01T00:00:00Z --end 2026-06-17T00:00:00Z --direction backward`

  Return both command outputs to Codex for the T1 database verification.

## Human Learning Notes

The existing Binance public client logs a fetch error and returns an empty list
on network failure, so an ingest run without a one-row/12-slot preflight can
look superficially successful while restoring nothing. Also, the current
forward checkpoint is beyond the requested window, so this repair must use
`--direction backward`.
