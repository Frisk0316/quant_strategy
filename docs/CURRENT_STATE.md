---
status: current
type: handoff
owner: human
created: 2026-06-12
last_reviewed: 2026-07-11
expires: none
superseded_by: null
---

# Current State

A small, always-current snapshot a session can trust on a cold start. Keep this
short and present-tense; history goes to `docs/CHANGELOG_AI.md`, backlog goes to
`docs/KNOWN_ISSUES.md`.

## Snapshot

- Current branch: `codex/pipeline-batch1-stage3`, working tree has uncommitted
  Turtle optional UI polish, the pipeline next-candidate probe/docs pass, and
  Deribit ingestion/frontend work; commit and push only on explicit user request.
- Repo maintenance (M1-M5 + M2-R1) is fully committed and closed:
  `df96682`/`79c1ddc`/`0191c1d`/`2dea608`/`5eb71f8`/`21cc3c9`.
- Strategy research pipeline P1-P9 is fully committed:
  `dfc7af8`/`6997aba`/`14976d4` plus an in-progress commit for P9 (DB-sourced
  universe membership) and the first Stage-1 spec produced from the
  taxonomy path.
- P9 merge-blocker fix is in the working tree: universe membership candle
  timestamps are normalized before daily membership math, with regression
  coverage for `datetime64[us]` vs `datetime64[s]` source parity.
- **`F-FUNDING-XS-DISPERSION` (`H-009`) first full pipeline cycle complete
  (E-031):** distinctness MINT (corr 0.138 vs the real C2 reference),
  pre-registered 4-combo fold-refit WF/CPCV — WF 1.1812 / CPCV 0.9553 /
  DSR=PSR 0.9346 — checkpoint① FAIL on the 0.95 gate only. **Verdict
  (user-ratified 2026-07-04): KEEP as `testing`, not refuted**; no
  chase-the-gate retry (any retry needs ex-ante rationale, burns K 0/2,
  accumulates n_trials). No promotion/live claim.
- **Turtle (海龜) platform integration ACCEPTED and usable (2026-07-04,
  manual pass complete):** golden parity passes on 898 REAL BTC-USDT-SWAP
  daily bars against the verbatim polars reference (17 columns exact / rtol
  1e-9; `tests/fixtures/turtle/`); DB-backed end-to-end API smoke passed
  (manual-param run, 2-free-param sweep with surface.html, invest_pct-axis
  sweep with equity_curves.csv), fixing one Timestamp-serialization bug
  found by the smoke. Full unit suite 599 passed. Research-only standalone
  runner; manual parameter tuning works from the frontend. Follow-up Codex
  pass fixed Turtle trade markers for numeric-string epochs and
  symbol-filtered endpoint calls (`212 markers` in browser check), made
  Turtle risk/execution/`fill_all_signals` ignores explicit, added
  CI-portable verbatim-reference golden coverage plus sweep parity validation,
  and polished surface.html fixed-param/hover text. Claude review re-run
  (E-033): Tier A AND Tier B both PASS — the user reference CSV is exactly
  reproduced from the repo fixture (E-032's mismatch was input date range,
  not data provenance).
- Turtle optional UI polish is complete in the working tree: warmup hints use
  current Turtle enter terms, `invest_pct` sweep rows are treated as
  backend-returned fractions, and heatmap cells expose exact x/y/value on
  hover/click. This is display-only; no strategy, risk, gate, backend semantic,
  or artifact change.
- **`F-OI-POSITIONING` (`H-012`/`E-034`/`E-036`/`E-037`) Stage-3 checkpoint
  complete, promotion blocked:** Claude/user signed off the Stage-1 spec on
  2026-07-04; E-036 passed PIT-universe OI data breadth with 31 OI-good
  symbols. E-037 Task B then ran family-minting vs F-FUNDING-XS-DISPERSION
  (`MINT`, max abs corr 0.050384, review item `mechanism_novelty`) and the
  pre-registered 4-combo fold-refit WF/CPCV grid. Result: WF OOS Sharpe
  0.6034, CPCV OOS Sharpe 0.7240, DSR 0.7220, PSR 0.8484; checkpoint1 auto
  FAILs only the DSR/PSR >= 0.95 gate. n_trials reconciliation, leak flag,
  DSR<=PSR sanity, idealized-fill exclusion, honest portable-block, and ct_val
  checks all PASS. H-012 stays `testing`; STOP for Claude/user checkpoint
  review. No promotion, demo, shadow, or live claim.
- **`F-XVENUE-LEADLAG` (`H-010`/`E-035`) remains data-blocked:** Binance
  BTC/ETH 1m coverage is complete, but OKX BTC/ETH 1m rows remain 0 with 0
  aligned rows. The existing OKX ingest command was attempted, but sandbox
  network failed with `WinError 10013` and the escalated rerun was rejected by
  the approval/usage layer, so backfill was not resumed.
- OKX liquidation forward-accumulation runs every 2h via Windows Task
  Scheduler (`quant_liq_okx_ingest`, Interactive-only).
- **Deribit data ingestion/frontend implementation is complete pending Claude research review (2026-07-11):**
  D2 hourly DVOL and D1 Deribit funding are implemented and backfilled for
  BTC/ETH through 2026-07-10 23:00 UTC; D3 option-surface snapshot ingestion
  is implemented and one live BTC/ETH snapshot was stored, but the Windows
  scheduled task is intentionally not registered. D5 external-series API and
  the Run Backtest Derivatives context card are implemented and browser-verified
  with `dvol_deribit_btc_1h`. D4 option-flow pilot passed January 2024 with
  744 rows per currency; the full 2024-01-01->2026-07-11 backfill completed
  with `optflow_deribit_btc` 22,126 rows and `optflow_deribit_eth` 22,125 rows,
  no gaps over 6h. Claude review fixes R1-R5 are applied in the working tree.
- Market Data Coverage timeout fix is in the working tree: external coverage
  uses per-dataset indexed aggregation instead of a full joined aggregate.
  Real-DB in-process response time is 2.23 seconds for 133 rows; the currently
  running localhost endpoint now returns HTTP 200 in 2.33 seconds after the
  stale duplicate server was stopped.
- Demo private WebSocket credentials currently fail OKX login with `60005
  Invalid apiKey`. The handler now treats authentication failure as terminal,
  logs the actual code once, and does not consume reconnect-breaker attempts.
  A valid Demo Trading API key is required before restarting trading-engine mode;
  frontend/backtest/data-only work can use `scripts/run_server.py`.
- External export now refreshes only selected `yahoo_finance` datasets. DB-only
  selections download existing rows directly and no longer report the misleading
  `0 refreshed, 43 skipped` status.

## Active Warnings

- No strategy, risk, portfolio, execution, deployment gate, or existing
  result artifact was changed by any of the above; no live/demo/shadow
  readiness is claimed.
- `research/strategy_synthesis.md`, `docs/backtest_live_parity_plan.md`, and
  `config/` remain truth sources for strategy/config behavior.

## Current Gaps

- Deribit re-review verdict (Claude, 2026-07-12): **ACCEPT** — R1–R5 fixes
  verified in code and DB (relabel 100%: all optflow/dvol_1h rows have
  `published_at = observed_at + 1h`; D4 backfill complete, no >6h gaps).
  H-013 (`F-VRP-TIMING`) Stage-1 drafting is unblocked. Follow-ups in
  `tasks/2026-07-11-deribit-ingestion-review.md`: user registers RUNBOOK
  schtasks (D3 snapshot + forward ingest) or the new series go stale; empty
  daily `dvol_deribit_*` config datasets need an ingest-or-retire decision.
- One failing test at committed HEAD, NOT Deribit-related:
  `test_turtle_invest_pct_result_rows_use_fraction_unit` — `4ac9a41`
  reintroduced the `n > 1 ? n / 100 : n` heuristic (view-config.js:172) that
  `61f04e2`'s test bans. Turtle workstream must reconcile function vs test.
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
- `F-OI-POSITIONING` next action is Claude/user checkpoint review for E-037:
  verdict, retry-vs-new-family judgment, leak-lag spot check, and portable
  validation block review. Do not start retry/adapter/demo/shadow/live work
  before that review.
- `F-XVENUE-LEADLAG` cannot progress until OKX BTC-USDT-SWAP and
  ETH-USDT-SWAP 1m canonical candles are backfilled outside the current network
  sandbox and the Stage-2 probe is rerun.
- `src/okx_quant/stocks/` is kept as a docs-mapped research-only sandbox
  (M5 Option A); it is not wired into crypto replay, UI, API, or deployment
  gates.

## How to Update

Overwrite this snapshot when it goes stale. Do not append history.

Related: `docs/AI_HANDOFF.md`, `docs/CHANGELOG_AI.md`, `docs/KNOWN_ISSUES.md`,
`docs/CONTEXT_INDEX.md`, and `docs/CONTEXT_BUDGET.md`.
