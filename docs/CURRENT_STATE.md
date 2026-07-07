---
status: current
type: handoff
owner: human
created: 2026-06-12
last_reviewed: 2026-07-04
expires: none
superseded_by: null
---

# Current State

A small, always-current snapshot a session can trust on a cold start. Keep this
short and present-tense; history goes to `docs/CHANGELOG_AI.md`, backlog goes to
`docs/KNOWN_ISSUES.md`.

## Snapshot

- Current branch: `codex/pipeline-batch1-stage3`, working tree has uncommitted
  Turtle follow-up changes plus the pipeline next-candidate probe/docs pass;
  user requested commit and push after verification.
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
- **`F-OI-POSITIONING` (`H-012`/`E-034`/`E-036`) Stage-2 data availability PASS:**
  Claude/user signed off the Stage-1 spec on 2026-07-04. Codex then backfilled
  Binance Vision 5m OI for the PIT universe using `oi_binance_hist_<base>`
  datasets and ran the extended PIT-aware probe. E-036 passes the breadth gate:
  31 OI-good symbols vs `min_good_symbols=10`. `SHIB-USDT-SWAP` is the only
  failed symbol because Binance Vision native `SHIBUSDT` metrics zips are
  absent; `1000SHIB-USDT-SWAP` is separate and passes. This unlocks only the
  Stage-3 preflight/build task; no strategy verdict, WF/CPCV, checkpoint,
  promotion, or live claim exists.
- **`F-XVENUE-LEADLAG` (`H-010`/`E-035`) remains data-blocked:** Binance
  BTC/ETH 1m coverage is complete, but OKX BTC/ETH 1m rows remain 0 with 0
  aligned rows. The existing OKX ingest command was attempted, but sandbox
  network failed with `WinError 10013` and the escalated rerun was rejected by
  the approval/usage layer, so backfill was not resumed.
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
- `F-OI-POSITIONING` next action is Task B in
  `tasks/2026-07-04-f-oi-positioning-stage3-codex-plan.md`: run the family
  minting preflight vs F-FUNDING-XS-DISPERSION first, and stop for review on
  ASSIGN/SKIP_RECOMMENDED.
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
