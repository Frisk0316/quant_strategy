---
status: current
type: handoff
owner: human
created: 2026-06-12
last_reviewed: 2026-08-04
expires: none
superseded_by: null
---

# Current State

Short present-tense snapshot. History belongs in `docs/CHANGELOG_AI.md`; durable
gaps belong in `docs/KNOWN_ISSUES.md`.

## Repository

- Working branch `feature/deribit-moneyness-hypotheses`; local and origin are
  both based at `c9fa77b`. The public-status implementation and its previously
  authorized planning/state edits are uncommitted; merge remains a human
  decision. PR #9 already merged at `b378e16`.
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
  first-20 limit is closed for re-ingested ranges.
- `external_observations` holds FRED DGS2/VIXCLS/DTWEXBGS (~1,640 rows each,
  2020+) + research-only Yahoo GC=F gold proxy; CFTC COT weekly TFF (ES/10Y/
  DXY/gold 2006+, CME BTC 2018+, ETH 2021+) with release-time `published_at`;
  Cboe VIX 1990+ and VIX9D/3M/6M (put/call ends 2019-10-04, no substitute).
  All DB-verified 2026-08-02. NAAIM weekly 2006–2026 is archived at
  `data/external_raw/naaim/` (source paywalled 2026-08-01).
- H-039/F-XVENUE-OPT-IV collector ACTIVE: six hourly
  `xvenue_opt_iv_{okx,bybit,deribit}_{btc,eth}` datasets since 2026-08-02 via
  task `quant_xvenue_options_iv` (hourly :15); IV normalization verified (BTC
  30d ATM within 0.2 vol pts). DEPENDENCY: Docker+TimescaleDB must stay up,
  missed hours are lost. Stage 2 blocked until >=270 daily obs (~2027-05).

## Execution / testnet

- ADR-0018 exception: Deribit testnet adapter is signal-driven (testnet only,
  no live gate claimed). Binance Spot/USD-M Demo and OKX Demo connectivity
  smokes green with trade-scoped no-withdrawal keys. Live/shadow gates
  unchanged; H-014 live block stays disabled.
- Security hardening is complete through `c9fa77b`: Telegram fails closed,
  remote API binds require auth, pair deletion is contained, job status omits
  DSNs, Compose secrets are required, credentials are `SecretStr` and redacted,
  and demo keys are isolated. No trading rule or deployment gate changed.
- Scheduled tasks: `quant_liq_okx_ingest`, `quant_okx_market_data`,
  `quant_h014_shadow_daily`, `quant_xvenue_options_iv`, `quant_weekly_worklog`
  (SUN 21:07, headless Claude writes `docs/worklogs/`; `scripts/worklog/`).

## Hypothesis pipeline

- 2026-07-29 slate H-030..H-037 resolved: all refuted/merged/data-blocked
  except H-038 residual mean-reversion (only Stage-2 qualifier, not yet run).
- 2026-08-02 paper-data probe H-040..H-046 (E-077..E-093) is CLOSED: H-043/H-044
  refuted, H-040/H-042 data-blocked, H-041/H-045/H-046 stopped at Stage-2 power
  FAIL once E-091..E-093 rejected their inferred breadth=2. H-045/H-046 are the
  publication-safe supersessions of H-033/H-036 (family trial 1, K 0/2), so no
  H-033/H-036 rerun and no GC=F gold-proxy ruling is pending.
- H-039 registered `proposed / data-blocked (accumulating)`; Tardis paid backfill
  declined 2026-08-02. Zero trials, K 0/2. ADR-0016 full-round infra
  (8 new mechanisms + 2 iterations, >=10 frozen) is target authority, unbuilt.

## Next actions, in order

Reordered 2026-08-04 by user request. Always-on background: keep Docker/
TimescaleDB up (missed collector hours are unrecoverable) and let the H-014
shadow cycle keep counting weeks. No live enablement.

1. Merge decision for `feature/deribit-moneyness-hypotheses` into `main`.
2. User: follow the RUNBOOK to create the three-file orphan `public-status`
   worktree, enable GitHub Pages, verify the first public page, and register the
   daily refresh task. The implementation is complete but not published.
3. User: H-038 residual mean-reversion Stage-2 go/no-go. It consumes F-S5
   K 2/2, so a fail closes that family permanently.
4. `tasks/2026-08-03-project-optimization-codex-plan.md`: only WS-C/F2 remain —
   per-item authorization + Change Manifest each, never as one batch.
5. ADR-0016 slices before the next full strategy-finding round.

Related: `docs/AI_HANDOFF.md`, `docs/KNOWN_ISSUES.md`, `config/workstreams.yaml`,
`tasks/2026-08-03-worklog-automation-verification-handoff.md`.
