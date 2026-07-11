---
status: current
type: handoff
owner: human
created: 2026-05-11
last_reviewed: 2026-07-11
expires: none
superseded_by: null
---

# AI Handoff

Cross-session memory for Claude and Codex. Keep this file current-state only;
move completed session history to `docs/CHANGELOG_AI.md` and durable gaps to
`docs/KNOWN_ISSUES.md`.

## Current Goal

Both tracked streams are complete and committed as of 2026-07-04. Full
narrative history moved to `docs/CHANGELOG_AI.md` (see "2026-07-03 - M2-R1
Reviewed, Accepted, And Committed" and "2026-07-03/04 - Pipeline P1-P9 Full
Cycle + First Stage-1 Spec From Taxonomy").

**Repo maintenance (M1-M5 + M2-R1):** all committed (`df96682`, `79c1ddc`,
`0191c1d`, `2dea608`, `5eb71f8`, `21cc3c9`). Claude-reviewed and accepted on
independent re-verification. No outstanding action.

**Strategy research pipeline — first full cycle complete:**
`F-FUNDING-XS-DISPERSION` (`H-009`) went taxonomy idea → Stage-2 data pass
(E-030) → distinctness MINT (max abs corr 0.138 vs the real C2 reference
signal) → pre-registered 4-combo fold-refit WF/CPCV (E-031: WF 1.1812, CPCV
0.9553, DSR=PSR 0.9346) → checkpoint① FAIL on the 0.95 statistical gate
only. **Verdict (Claude review, user-ratified 2026-07-04): KEEP as
`testing`, MINT accepted, not refuted** — a genuinely marginal miss with K
0/2 used, unlike the clean H-006/007/008 refutations. Standing constraint:
no chase-the-gate retry — any retry needs an ex-ante rationale, burns K,
and accumulates family n_trials. No promotion/live claim. Detail:
`docs/CHANGELOG_AI.md` "2026-07-04 - Turtle Manual Pass +
F-FUNDING-XS-DISPERSION Checkpoint Verdict" and the H-009/E-031 ledger rows.

**Pipeline next candidates Codex pass (2026-07-04/05):**
`F-OI-POSITIONING` has the signed-off Stage-1 spec
(`docs/superpowers/specs/2026-07-04-f-oi-positioning-hypothesis.md`), E-036
universe-wide Binance Vision 5m OI Stage-2 data pass, and E-037 Task B
Stage-3 checkpoint evidence. E-037 family-minting vs
`F-FUNDING-XS-DISPERSION` returned provisional `MINT` (max abs corr 0.050384,
human-review item `mechanism_novelty`), then the pre-registered 4-combo grid
ran fold-refit WF/CPCV on 31 OI-good symbols. Result: WF OOS Sharpe 0.6034,
CPCV OOS Sharpe 0.7240, DSR 0.7220, PSR 0.8484. `checkpoint1_auto.json`
FAILS only the DSR/PSR >= 0.95 threshold; n_trials reconciliation, leak flag,
DSR<=PSR sanity, idealized-fill exclusion, honest portable-block, and ct_val
checks all PASS. H-012 stays `testing`; STOP at checkpoint for Claude/user
review. No promotion/demo/shadow/live claim. `F-XVENUE-LEADLAG` was rechecked
in E-035 and remains
data-blocked: Binance has full BTC/ETH 1m coverage but OKX still has 0 rows /
0.0 coverage / 0 aligned rows for both legs. The existing OKX ingest command was
attempted, but sandbox networking failed with `WinError 10013`; the required
escalated rerun was rejected by the approval/usage layer, so the backfill is
**not** resumed from that session. No cross-venue substitution, strategy verdict,
or promotion evidence.

**Turtle (海龜) platform integration — ACCEPTED and usable (2026-07-04,
user-directed manual pass complete):** the reference
`turtle_trading_system_full` is ported as a research-only standalone runner
(daily_winner precedent; no replay/trading-core/gate/deployment changes).
Final state:
- **Golden parity passes on REAL data:** 898 real BTC-USDT-SWAP UTC daily
  bars exported from canonical DB (`tests/fixtures/turtle/daily_ohlc.csv`
  with provenance README); the verbatim polars reference re-run in a scratch
  venv on this fixture (default + cash-gate stress sets) and the pandas
  port matches exactly — 17 columns, ints exact, floats rtol 1e-9, final
  equities 50578.081905 / 12307.892184. The earlier 600-day synthetic
  fixture is superseded and deleted.
- **DB-backed end-to-end API smoke passed** (in-process TestClient against
  the real router + DB, no mocks): manual-param single run
  (invest_pct=0.05, 75 orders, full ADR-0002 artifact set), 2-free-param
  sweep (6 combos → rows.csv + surface.html + result/artifact endpoints),
  invest_pct-axis sweep (equity_curves.csv for the slider scrub UI). The
  smoke caught and fixed one real bug: sweep equity-curve rows carried
  pandas Timestamps and crashed `summary.json` serialization (fixed at
  source with a regression test). Codex independently smoke-tested on a
  temporary 8081 server.
- Full unit suite **599 passed**; frontend node --check green; RF1-RF3 from
  the earlier review round all closed (declarative `turtle` validation
  contract entry [user-approved scope amendment], invest_pct scrub UI +
  5-metric heatmaps, real-fixture parity wiring).
- Follow-up Codex pass complete (2026-07-04): file/DB-backed Turtle
  execution markers now survive numeric-string epoch parsing and
  symbol-filtered marker endpoint calls; browser check on a patched local
  server showed `212 markers` and live `invest_pct` slider sync. Turtle
  risk overrides/execution profile/`fill_all_signals` are explicitly recorded
  as ignored, sweep parity validation has a Tier A PASS, CI has a portable
  verbatim-reference golden subset, and `surface.html` now carries fixed params
  plus metric hover detail. Claude review re-run (E-033) upgraded Tier B to
  PASS: the user reference CSV is exactly reproduced from the repo fixture
  range; E-032's mismatch was input date range, not data provenance.
- Optional Turtle UI polish complete in the working tree (2026-07-08):
  warmup hint now uses the current Turtle enter-term params, sweep result
  `invest_pct` rows are treated as backend-returned fractions without a
  magnitude heuristic, and SVG heatmap cells expose exact x/y/value on hover
  and click. UI/display-only; no backend semantics, strategy, risk, gate, or
  artifact changes.

**Known pending items (not blocking, tracked in KNOWN_ISSUES/RUNBOOK):**
liquidation ingest (`quant_liq_okx_ingest`) is Interactive-only (runs only
while logged in) — an unattended/service mode is a separate decision if
needed; the 4 point-in-time-eligible symbols with zero funding history
(`CC`/`FIL`/`M`/`SHIB`-USDT-SWAP) can be backfilled the same way as the
other 28 if a later grid needs them.

**P9 PR merge blocker fixed in the working tree (2026-07-03):**
`scripts/build_universe_membership.py` now normalizes candle timestamps to
`datetime64[ns]` before daily membership math, so DB and parquet inputs cannot
fail source-parity checks solely because one path stores dates as seconds and
another as microseconds. Regression coverage:
`tests/unit/test_universe_membership.py::test_build_membership_ignores_timestamp_storage_precision`.

**Deribit data workstream implementation complete pending Claude research review (2026-07-11, Codex):**
user sign-off was given 2026-07-11 for
`tasks/2026-07-11-deribit-data-ingestion-tasks.md`. D2 hourly DVOL and D1
funding clients/config are implemented and backfilled for BTC/ETH from
2024-01-01 through 2026-07-10 23:00 UTC with no >2h gaps. D3 option-surface
snapshots are implemented; one live BTC/ETH snapshot was stored, and RUNBOOK
has schtasks registration instructions, but the Windows task was not registered.
D4 option-flow aggregate client/script is implemented; the mandatory 2024-01
pilot passed with 744 rows per currency and no gaps, and the full
2024-01-01->2026-07-11 backfill completed with `optflow_deribit_btc` 22,126
rows and `optflow_deribit_eth` 22,125 rows, first `2024-01-01T00:00:00Z`, last
`2026-07-10T23:00:00Z`, and no gaps over 6h. Claude review fixes R1-R5 are
applied: hourly bucketed Deribit rows publish at bucket end, existing DB rows
were relabeled in place, checkpoint failures preserve the last successful
cursor, backfill bounds must be hour-aligned, DVOL has throttle/retry, and R5
minor API/frontend/docs/parser/edge-case fixes landed.
D5 `GET /api/data/external-series` and the Run Backtest Derivatives context
card are implemented and browser-verified against `dvol_deribit_btc_1h`.
Architecture still uses `external_observations`; no new tables, strategy,
risk, portfolio, execution, deployment gate, or existing result artifact change.
**Claude re-review 2026-07-12: ACCEPT** — R1–R5 verified in code AND DB
(relabel 100%, D4 backfill complete/gap-free, fixes tested; details appended
to `tasks/2026-07-11-deribit-ingestion-review.md`). H-013 Stage-1 drafting is
unblocked. Non-Deribit note: `test_turtle_invest_pct_result_rows_use_fraction_unit`
fails at committed HEAD (`4ac9a41` reintroduced the heuristic `61f04e2`'s test
bans) — Turtle workstream to reconcile.
`F-VRP-TIMING` remains reserved for a future H-013 Stage-1 spec and is not
minted or promotion evidence.

**Market Data Coverage timeout fixed in the working tree (2026-07-12):**
`GET /api/data/coverage` no longer performs one full joined aggregation over
all `external_observations`. It now aggregates per dataset through the existing
`(dataset_id, observed_at)` index. Real-DB in-process timing fell from the
running server's observed 9.41-9.78 seconds to 2.23 seconds for 133 rows, below
the frontend's unchanged 10-second timeout. Restart the existing API process to
load the fix; no schema, data, strategy, config, or deployment gate changed.

**Local runtime follow-up (2026-07-12):** the browser was still reaching a
stale, hung API process bound to `127.0.0.1:8080` while the current engine was
bound separately to `0.0.0.0:8080`. The stale process was stopped; localhost
coverage now returns HTTP 200 in 2.33 seconds. The current demo private-WS login
was independently probed and returns OKX `60005 Invalid apiKey`. Private login
failures are now terminal and log the code once instead of reconnecting until
the local breaker fires. A valid Demo Trading API key is still required; do not
switch to live mode as a workaround.

**External export skipped-count follow-up (2026-07-12):** the frontend no
longer sends every selected DB-only external dataset through the yfinance-only
refresh endpoint. DB-only selections now download existing rows directly and
show `Using existing DB rows`; only selected `yahoo_finance` rows are refreshed.
This removes the misleading `0 refreshed, 43 skipped` result without changing
the exported DB rows or backend refresh contract.

**Claude review of the Deribit pass (2026-07-11): ACCEPT-WITH-FIXES, fixes applied** —
full findings in `tasks/2026-07-11-deribit-ingestion-review.md`. R1-R5 are
implemented in the working tree, but Claude should still review the research
interpretation topics before H-013/F-VRP-TIMING drafting: inverse premium units,
endpoint deviations from the research note, and the observed history-host
rate-limit ceiling from the full run.

## Current Branch

- Branch: `codex/pipeline-batch1-stage3`.
- Recent commits: `df96682` (M1), `79c1ddc` (7/3 handoff preservation),
  `0191c1d` (M2), `2dea608` (M3), `5eb71f8` (M4/M5), `21cc3c9` (M2-R1),
  `dfc7af8`/`6997aba`/`14976d4` (pipeline P1-P8 + real-data runs + warmup
  window), plus an in-progress commit for P9 + the F-FUNDING-XS-DISPERSION
  Stage-1 spec.
- Current working tree contains the Turtle optional polish, the pipeline
  next-candidate probe/docs pass, and the Deribit ingestion/frontend work;
  commit and push only on explicit user request.

## Do Not Touch

Without explicit user approval, do not modify:

- `research/` except explicit user-approved research tasks.
- `results/**` existing artifacts.
- `src/okx_quant/strategies/`, `src/okx_quant/signals/`.
- `src/okx_quant/risk/`, `src/okx_quant/portfolio/`,
  `src/okx_quant/execution/`.
- `config/risk.yaml`, deployment/shadow/demo/live gates, or strategy assumptions.
- Differential-validation implementation unless a current task explicitly lists it.

## Verification Notes

M1-M5 + M2-R1 verification evidence (test counts, docs-check output, smoke
reproduction) moved to `docs/CHANGELOG_AI.md` — that stream is closed. P1-P9
verification evidence (test counts, real-run row counts, doc-impact checks)
is likewise in `docs/CHANGELOG_AI.md`.

`make` remains unavailable in this Windows sandbox; use the equivalent
Python commands (`python scripts/docs/check_doc_metadata.py`,
`python scripts/docs/check_feature_map_links.py`,
`python scripts/docs/check_doc_impact.py --strict`) or `pytest` directly.
Full `make verify` / `make verify-full` still needs an environment with
`make`, TimescaleDB, and required data.

## Next Steps

1. H-009 (`F-FUNDING-XS-DISPERSION`) stays `testing`: no retry without an
   ex-ante rationale (burns K, accumulates n_trials). H-012
   (`F-OI-POSITIONING`) also stays `testing` after E-037: provisional MINT
   accepted by the checker, but checkpoint1 FAILs the statistical gate
   (DSR 0.7220 / PSR 0.8484). Next action is Claude/user checkpoint review:
   verdict, retry-vs-new-family judgment, leak-lag spot check, and portable
   block reason review. No retry, adapter, demo, shadow, or live work is
   justified before that review. `F-XVENUE-LEADLAG` remains blocked until the
   OKX BTC/ETH-USDT-SWAP 1m backfill runs successfully outside this sandbox,
   then rerun the Stage-2 probe.
2. Turtle: usable from the frontend for manual parameter tuning now. Optional
   UI polish is complete in the working tree; no further Turtle work is queued
   unless the user asks. No live/demo/shadow claim.
3. If a later grid needs the 4 not-yet-backfilled symbols
   (`CC`/`FIL`/`M`/`SHIB`-USDT-SWAP), rerun
   `scripts/market_data/backfill_universe_funding.py` for them.
4. Decide whether the `quant_liq_okx_ingest` Windows task needs an
   unattended/service mode (currently Interactive-only).
5. Deribit: Claude reviews the noted premium-currency units, endpoint
   deviations, and history-host rate-limit behavior before drafting the
   F-VRP-TIMING Stage-1 spec (H-013/E-038) for user review. The user may
   register the RUNBOOK Windows scheduled tasks for Deribit forward ingest;
   Codex did not register them.

## Open Questions

- Deribit option-flow premium units: v1 records inverse-only premium in
  `BTC`/`ETH` units and counts USDC-linear exclusions. Claude should confirm the
  research interpretation before signal design.
- Deribit endpoint deviations observed by implementation: DVOL continuation is
  a backward timestamp cursor, funding history returns a capped latest list
  rather than accepting continuation, and option history returns
  `{trades, has_more}`.
- Deribit history host rate limits: pilot/full run worked at <=5 req/s with no
  persistent 429/10028 or undocumented host block; highest observed daily
  option-flow page counts included BTC 63 pages/day (2026-02-05) and ETH 37
  pages/day (2024-03-05). Claude should decide whether this evidence is enough
  for research operations or whether to keep a lower scheduled cadence.
