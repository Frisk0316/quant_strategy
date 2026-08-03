---
status: current
type: handoff
owner: human
created: 2026-06-12
last_reviewed: 2026-08-03
expires: none
superseded_by: null
---

# Current State

Short present-tense snapshot. History belongs in `docs/CHANGELOG_AI.md`; durable
gaps belong in `docs/KNOWN_ISSUES.md`.

## Repository

- Working branch `feature/deribit-moneyness-hypotheses`; local and origin are
  both at `c9fa77b` with a clean tree. Merge to `main` is pending human review.
  PR #9 already merged at `b378e16`.
- No strategy is promotion/demo/live ready. H-014/F-VOL-REGIME-OPT stays the
  only `supported` hypothesis (E-051 + E-052 double pass); promotion blocked
  per R7.2 pending >=8 valid shadow journal weeks plus reviews.
- Authority order: config, accepted ADRs, `research/strategy_synthesis.md`,
  `docs/ai_collaboration.md`. Do not touch strategy/signal/risk/execution
  behavior, results, DB schema, or gates without an approved task.

## Data (canonical + external)

- Canonical 30-symbol 1m 2024–2026 candles + funding unchanged. Deribit DVOL
  hourly to 2021-03-24, RV30 to 2018/2019, option surface/flow with moneyness
  buckets from 2024-01-01.
- Deribit option-flow hourly rows retain the FULL inverse-trade tape
  (count-invariant pagination + payload-only upsert, `5920380`); the pre-fix
  first-20 sample limit is closed for re-ingested ranges.
- `external_observations` holds: FRED DGS2/VIXCLS/DTWEXBGS (~1,640 rows each,
  2020+) + research-only Yahoo GC=F gold proxy; CFTC COT weekly TFF (ES/10Y/
  DXY/gold 2006+, CME BTC 2018+, CME ETH 2021+) with release-time
  `published_at`; Cboe VIX 1990+ and VIX9D/3M/6M term structure (put/call
  archive ends 2019-10-04, no substitute). All DB-verified 2026-08-02.
- H-039/F-XVENUE-OPT-IV collector ACTIVE: six hourly
  `xvenue_opt_iv_{okx,bybit,deribit}_{btc,eth}` datasets since 2026-08-02 via
  task `quant_xvenue_options_iv` (hourly :15); IV normalization verified (BTC
  30d ATM within 0.2 vol pts). DEPENDENCY: Docker+TimescaleDB must stay up,
  missed hours are lost. Stage 2 blocked until >=270 daily obs (~2027-05).
- NAAIM weekly exposure history 2006–2026 archived at
  `data/external_raw/naaim/` (source paywalled 2026-08-01).

## Execution / testnet

- ADR-0018 exception: Deribit testnet adapter is signal-driven (testnet only,
  no live gate claimed). Binance Spot/USD-M Demo and OKX Demo connectivity
  smokes green with trade-scoped no-withdrawal keys. Live/shadow gates
  unchanged; H-014 live block stays disabled.
- Security hardening is complete through `c9fa77b`: Telegram commands fail
  closed, remote API binds require auth, pair deletion is contained, job status
  omits DSNs, Compose secrets are required, credentials are `SecretStr` and
  redacted in logs/errors, and demo keys are isolated. No trading rule or
  deployment gate changed.
- Scheduled tasks: `quant_liq_okx_ingest`, `quant_okx_market_data`,
  `quant_h014_shadow_daily`, `quant_xvenue_options_iv`, `quant_weekly_worklog`
  (SUN 21:07, headless Claude writes `docs/worklogs/`; `scripts/worklog/`).

## Hypothesis pipeline

- 2026-07-29 slate H-030..H-037 resolved: all refuted/merged/data-blocked
  except H-038 residual mean-reversion (only Stage-2 qualifier, not yet run).
- H-033 (FOMC drift) and H-036 (cross-asset risk) are DATA-UNBLOCKED by the
  FRED landing; Stage-2 reruns await explicit user authorization, including
  the GC=F-as-gold-proxy ruling for H-036. Data-blocked rows consumed no K.
- H-039 registered `proposed / data-blocked (accumulating)`; Tardis paid
  backfill declined 2026-08-02. Zero trials, K 0/2.
- ADR-0016 full-round infra (8 new mechanisms + 2 iterations, >=10 frozen)
  remains target authority, not implemented.

## Next actions, in order

1. User: authorize H-033/H-036 Stage-2 reruns (and rule on GC=F proxy);
   then Codex runs the pre-registered probes.
2. User: decide whether H-038 residual mean-reversion Stage-2 proceeds.
3. Keep the H-014 manual shadow cycle counting valid weeks; Claude
   execution/risk review continues; no live enablement.
4. Merge decision for `feature/deribit-moneyness-hypotheses` into `main`.
5. Keep Docker/TimescaleDB running for the hourly collector; investigate any
   `xvenue_options_snapshot.log` gap alert same-day.
6. ADR-0016 slices before the next full strategy-finding round.
7. `tasks/2026-08-03-project-optimization-codex-plan.md`: all ungated items
   (F1, WS-A, B1-B5, E1-E2) APPROVED and pushed. Only WS-C/F2 remain — per-item
   authorization + Change Manifest each; do NOT authorize WS-C as one batch.

Related: `docs/AI_HANDOFF.md`, `docs/KNOWN_ISSUES.md`, `config/workstreams.yaml`,
`tasks/2026-08-03-worklog-automation-verification-handoff.md`.
