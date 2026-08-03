---
status: current
type: handoff
owner: codex
created: 2026-08-02
last_reviewed: 2026-08-02
expires: none
superseded_by: null
---

# Context Handoff: OKX public market-data accumulation — 2026-08-02

## Goal (one sentence)
Continuously accumulate OKX BTC/ETH Spot and SWAP public books, trades, and funding on the user's Windows workstation without credentials or orders.

## Current state
- Branch: `feature/deribit-moneyness-hypotheses`.
- In-progress edits: existing dirty Demo-execution work plus this collector/task/docs slice.
- What works: four-symbol public WebSocket smoke persisted all three data kinds; `quant_okx_market_data` is registered and running as a Limited/S4U startup task.
- Unfinished: retention/import is manual; Demo strategy execution remains separate and non-atomic across funding legs.

## Decisions made (and why)
- Reused `scripts/stream_orderbook.py` and native Task Scheduler to minimize new machinery.
- Kept chunk files and a 10 GiB reserve because one ever-growing Parquet file is unsafe for a long-running workstation collector.

## Rules in play (preserve verbatim)
- Invariants touched: I61 — public-only, bounded chunks, 10 GiB disk reserve.
- Domain rules touched: none.
- Do-not-touch: strategies, risk, execution, API credentials, mode/gates, research, existing results.

## Context to load next (the reading list)
- Source of truth: `config/settings.yaml`, `docs/RUNBOOK.md`, `docs/DATA_FLOW.md`.
- Owning files: `scripts/stream_orderbook.py`, `scripts/market_data/run_okx_market_data_collector.cmd`.
- Context Pack: none exists for runtime collection.

## Checks run
- `pytest tests/unit/test_stream_orderbook.py -q` — pass.
- Ruff on collector/test — pass.
- Real four-symbol OKX public WebSocket smoke — books/trades/funding persisted.

## Approvals
- User approved creating the continuous public-data task and its UAC-backed S4U registration in this session.

## Next action (single, concrete)
- Monitor `logs/okx_market_data_collector.log` and free disk after the first full day, then choose a retention/import policy from measured growth.

## Human Learning Notes
Task Scheduler's `267009` is the normal “currently running” code. Interactive tasks received the Codex test terminal's Ctrl+C, so this host uses S4U/Limited startup execution; ordinary network failures are handled inside the collector reconnect loop.
