---
status: current
type: handoff
owner: human
created: 2026-06-12
last_reviewed: 2026-08-05
expires: none
superseded_by: null
---

# Current State

Present-tense snapshot. History: `docs/CHANGELOG_AI.md`. Gaps: `docs/KNOWN_ISSUES.md`.

## Repository

- PRs #19/#20/#21 MERGED, #17 CLOSED; `origin/main` holds H-038/E-094/E-095,
  WS-C C3/C5/C10, worklog generators, public-status. No branch work open.
- No strategy is promotion/demo/live ready. H-014/F-VOL-REGIME-OPT is the only
  `supported` hypothesis (E-051 + E-052); promotion blocked per R7.2 pending
  >=8 valid shadow journal weeks plus reviews.
- Authority order: config, accepted ADRs, `research/strategy_synthesis.md`,
  `docs/ai_collaboration.md`. No behavior, results, schema, or gate change
  without an approved task.

## Data (canonical + external)

- Canonical 30-symbol 1m 2024–2026 candles + funding unchanged. Deribit DVOL
  hourly to 2021-03-24, RV30 to 2018/2019, surface/flow bucketed from
  2024-01-01; flow keeps the FULL inverse tape since `5920380`, but only for
  re-ingested ranges, so no H-031/H-035 rerun is possible pre-2024.
- `external_observations`: FRED DGS2/VIXCLS/DTWEXBGS 2020+ (plus a research-only
  Yahoo GC=F proxy), CFTC COT weekly TFF, Cboe VIX + VIX9D/3M/6M (put/call ends
  2019-10-04, no substitute). DB-verified 2026-08-02. NAAIM archived, paywalled.
- H-039/F-XVENUE-OPT-IV collector ACTIVE: six hourly
  `xvenue_opt_iv_{okx,bybit,deribit}_{btc,eth}` datasets since 2026-08-02.
  Docker+TimescaleDB must stay up — missed hours are lost. Stage 2 blocked to
  >=270 obs (~2027-05); 0 trials, K 0/2, Tardis declined.

## Execution / testnet

- ADR-0018 PERMITS signal-driven Deribit execution on testnet only, but it is
  NOT running: `h014_live.enabled` false, `deribit_live`'s only importer is
  `scripts/h014_live_panic.py`, no H-014 execution task registered. Phase 2
  needs a Deribit testnet key, then a runner, then Claude's go/no-go. Binance
  Spot/USD-M Demo and OKX Demo smokes green on no-withdrawal keys.
- Security hardening complete through `c9fa77b`; WS-C C3/C5/C10 merged (specs
  fail closed; reduce-only + `posSide` reach OKX except spot `tdMode=cash`,
  I70/F75; mids use `OkxBook`). No live/demo/shadow mode or gate changed.
- Scheduled: `quant_{liq_okx_ingest,okx_market_data,h014_shadow_daily,
  xvenue_options_iv,weekly_worklog,private_worklog_daily}`.

## Hypothesis pipeline

- 2026-08-05 input-quality review delivered
  (`tasks/2026-08-05-candidate-input-quality-review.md`): a Candidate Admission
  Form filled before an H-number is assigned, shaped to drop into ADR-0016's
  round manifest unchanged. User ruling: B3 bar is gross/cost >= 2.0. Manual
  review step, not a gate; no Stage-2 schema or verdict changed.
- E-043's artifact self-declares `experiment_id: E-041` — ruled a mislabel
  2026-08-05 (F77); registry row authoritative and annotated, artifact
  byte-identical, I72 fails closed on any new identity disagreement.
- H-038/E-095 complete, F-S5 terminal at K 2/2: the 0.95 gate admitted
  17,271/17,272 member-days and positions measured breadth 5.743875 over 898
  daily returns, then distinctness failed closed (immutable E-014 has no dated
  returns). n_trials 72; no E-096, retune, Stage 3, promotion, deployment.
- 2026-08-02 probe H-040..H-046 (E-077..E-093) CLOSED: H-043/H-044 refuted,
  H-040/H-042 data-blocked, H-041/H-045/H-046 stopped at power FAIL once
  E-091..E-093 rejected their inferred breadth=2. H-045/H-046 supersede
  H-033/H-036 (no rerun, no GC=F ruling). ADR-0016 infra unbuilt.

## Next actions, in order

Always on: keep Docker/TimescaleDB up (missed collector hours are
unrecoverable); let the H-014 shadow cycle count. No live enablement.

1. `origin/public-status` (`329a5d7`) is PUSHED with exactly the three approved
   files, but Pages is NOT serving — `frisk0316.github.io/quant_strategy/` gave
   HTTP 404 on 2026-08-05 while the `quant_worklog` control gave 200. User: set
   Settings > Pages to `public-status` + `/ (root)`, no workflow; re-check the
   URL; then register `quant_public_status_daily`.
2. Worklog page is LIVE (HTTP 200) with its daily 16:45 task; nothing open.
3. WS-C C1/C2/C4/C6/C7/C8/C9/C11 and F2 stay ungated — no implementation
   without per-item authorization and manifests. Claude's advice: authorize
   Phase 1+2 (C6, C11 Layer 1, close_all) only when an order-placing engine is
   about to run; the rest need one to bite.
4. ADR-0016 stays deferred (user, 2026-08-04). The binding constraint is
   candidate input quality, not gate strictness — see I68 and the review.

Related: `docs/AI_HANDOFF.md`, `docs/KNOWN_ISSUES.md`, `config/workstreams.yaml`, `tasks/2026-08-05-governance-reconcile-and-input-quality-handoff.md`.
