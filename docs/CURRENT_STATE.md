---
status: current
type: handoff
owner: human
created: 2026-06-12
last_reviewed: 2026-07-03
expires: none
superseded_by: null
---

# Current State

A small, always-current snapshot a session can trust on a cold start. Keep this
short and present-tense; history goes to `docs/CHANGELOG_AI.md`, backlog goes to
`docs/KNOWN_ISSUES.md`.

## Snapshot

- Current branch: `codex/pipeline-batch1-stage3`, working tree clean.
- Repo maintenance (M1-M5 + M2-R1) is fully committed and closed:
  `df96682`/`79c1ddc`/`0191c1d`/`2dea608`/`5eb71f8`/`21cc3c9`.
- Strategy research pipeline P1-P9 is fully committed:
  `dfc7af8`/`6997aba`/`14976d4` plus an in-progress commit for P9 (DB-sourced
  universe membership) and the first Stage-1 spec produced from the
  taxonomy path.
- **`F-FUNDING-XS-DISPERSION` (`H-009`) Stage-2 `data_availability` now
  PASSES** (E-030) — the first taxonomy-sourced candidate to clear this gate.
  Root cause of the earlier FAIL: `build_universe_membership.py` derived PIT
  eligibility from a thin local-parquet mirror (median 2 eligible/day);
  rebuilt from `canonical_candles` via a new `--source db` path, median is
  now 28. `stage2_status` stays FAIL — `distinctness` (vs `F-FUNDING-CARRY`)
  and `cost_after_edge` are the explicit next Codex step, per
  `docs/superpowers/specs/2026-07-04-f-funding-xs-dispersion-hypothesis.md`.
- OKX liquidation forward-accumulation runs every 2h via Windows Task
  Scheduler (`quant_liq_okx_ingest`, Interactive-only).

## Active Warnings

- No strategy, risk, portfolio, execution, deployment gate, or existing
  result artifact was changed by any of the above; no live/demo/shadow
  readiness is claimed.
- `research/strategy_synthesis.md`, `docs/backtest_live_parity_plan.md`, and
  `config/` remain truth sources for strategy/config behavior.

## Current Gaps

- `make` is unavailable in the current Windows sandbox; use the Python
  equivalents (`scripts/docs/check_doc_metadata.py`,
  `scripts/docs/check_feature_map_links.py`,
  `scripts/docs/check_doc_impact.py --strict`) or `pytest` directly.
- `quant_liq_okx_ingest` is Interactive-only (runs only while logged on); the
  measured OKX public REST retention window is hours-scale (BTC ~14h, ETH
  ~5h), so extended logout gaps will drop liquidation events.
- 4 point-in-time-eligible symbols under the rebuilt universe
  (`CC`/`FIL`/`M`/`SHIB`-USDT-SWAP) have no funding history backfilled yet;
  not required for the current Stage-2 pass, only if a later grid needs them.
- `src/okx_quant/stocks/` is kept as a docs-mapped research-only sandbox
  (M5 Option A); it is not wired into crypto replay, UI, API, or deployment
  gates.

## How to Update

Overwrite this snapshot when it goes stale. Do not append history.

Related: `docs/AI_HANDOFF.md`, `docs/CHANGELOG_AI.md`, `docs/KNOWN_ISSUES.md`,
`docs/CONTEXT_INDEX.md`, and `docs/CONTEXT_BUDGET.md`.
