---
status: current
type: handoff
owner: human
created: 2026-05-11
last_reviewed: 2026-07-04
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
`F-OI-POSITIONING` now has the signed-off Stage-1 spec
(`docs/superpowers/specs/2026-07-04-f-oi-positioning-hypothesis.md`) and a
universe-wide Binance Vision 5m OI Stage-2 data pass. E-034 first passed the
BTC/ETH seed probe; E-036 then backfilled PIT-universe datasets
`oi_binance_hist_<base>` and ran the extended PIT-aware probe:
31 OI-good symbols pass the `>=10` breadth gate. `SHIB-USDT-SWAP` is the only
failed symbol because Binance Vision native `SHIBUSDT` metrics zips are absent;
`1000SHIB-USDT-SWAP` is separate and passes. Stage-3 is now unblocked only for
the preflight/build in `tasks/2026-07-04-f-oi-positioning-stage3-codex-plan.md`
Task B; no distinctness, WF/CPCV, checkpoint, promotion, demo, shadow, or live
claim has run. `F-XVENUE-LEADLAG` was rechecked in E-035 and remains
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

## Current Branch

- Branch: `codex/pipeline-batch1-stage3`.
- Recent commits: `df96682` (M1), `79c1ddc` (7/3 handoff preservation),
  `0191c1d` (M2), `2dea608` (M3), `5eb71f8` (M4/M5), `21cc3c9` (M2-R1),
  `dfc7af8`/`6997aba`/`14976d4` (pipeline P1-P8 + real-data runs + warmup
  window), plus an in-progress commit for P9 + the F-FUNDING-XS-DISPERSION
  Stage-1 spec.
- Current session finalization request covers the Turtle follow-up work plus
  the pipeline next-candidate probe/docs pass; commit and push on user request.

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
   ex-ante rationale (burns K, accumulates n_trials). Next candidate handoff:
   `F-OI-POSITIONING` has signed-off Stage-1 plus E-036 universe OI data PASS
   (31 good symbols); run Task B Stage-3 preflight/build next, starting with
   family minting vs the F-FUNDING-XS-DISPERSION reference and stopping on
   ASSIGN/SKIP_RECOMMENDED. `F-XVENUE-LEADLAG` remains blocked until the OKX
   BTC/ETH-USDT-SWAP 1m backfill runs successfully outside this sandbox, then
   rerun the Stage-2 probe.
2. Turtle: usable from the frontend for manual parameter tuning now.
   Optional polish only (heatmap hover/click, warmup hint, invest_pct unit
   convention) — schedule if the user asks.
3. If a later grid needs the 4 not-yet-backfilled symbols
   (`CC`/`FIL`/`M`/`SHIB`-USDT-SWAP), rerun
   `scripts/market_data/backfill_universe_funding.py` for them.
4. Decide whether the `quant_liq_okx_ingest` Windows task needs an
   unattended/service mode (currently Interactive-only).

## Open Questions

- None currently open.
