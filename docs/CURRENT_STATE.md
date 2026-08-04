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

- Working branch `feature/deribit-moneyness-hypotheses`, pushed through
  `3e7d26f` and 52 commits ahead of `origin/main`, which already holds PRs
  #9/#14/#16/#18. PR #19 is open and MERGEABLE; merging is the human's.
- No strategy is promotion/demo/live ready. H-014/F-VOL-REGIME-OPT stays the
  only `supported` hypothesis (E-051 + E-052 double pass); promotion blocked
  per R7.2 pending >=8 valid shadow journal weeks plus reviews.
- Authority order: config, accepted ADRs, `research/strategy_synthesis.md`,
  `docs/ai_collaboration.md`. No strategy/signal/risk/execution behavior,
  results, schema, or gate changes without an approved task.

## Data (canonical + external)

- Canonical 30-symbol 1m 2024–2026 candles + funding unchanged. Deribit DVOL
  hourly to 2021-03-24, RV30 to 2018/2019, surface/flow with moneyness buckets
  from 2024-01-01; flow retains the FULL inverse tape since `5920380` (the
  pre-fix first-20 limit is closed for re-ingested ranges only).
- `external_observations` holds FRED DGS2/VIXCLS/DTWEXBGS 2020+ (research-only
  Yahoo GC=F gold proxy alongside), CFTC COT weekly TFF with release-time
  `published_at`, and Cboe VIX + VIX9D/3M/6M (put/call ends 2019-10-04, no
  substitute). DB-verified 2026-08-02. NAAIM weekly is archived at
  `data/external_raw/naaim/` (source paywalled 2026-08-01).
- H-039/F-XVENUE-OPT-IV collector ACTIVE: six hourly
  `xvenue_opt_iv_{okx,bybit,deribit}_{btc,eth}` datasets since 2026-08-02 via
  task `quant_xvenue_options_iv`. DEPENDENCY: Docker+TimescaleDB must stay up,
  missed hours are lost. Stage 2 blocked until >=270 daily obs (~2027-05).

## Execution / testnet

- ADR-0018 exception: Deribit testnet adapter is signal-driven (testnet only,
  no live gate claimed). Binance Spot/USD-M Demo and OKX Demo smokes green on
  trade-scoped no-withdrawal keys. Gates unchanged; H-014 live block disabled.
- Security hardening is complete through `c9fa77b` (fail-closed Telegram, authed
  remote binds, contained pair deletion, DSN-free job status, required Compose
  secrets, `SecretStr` credentials, isolated demo keys). Details in AI_HANDOFF.
- Scheduled tasks: `quant_liq_okx_ingest`, `quant_okx_market_data`,
  `quant_h014_shadow_daily`, `quant_xvenue_options_iv`, `quant_weekly_worklog`.

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

Background, always on: keep Docker/TimescaleDB up (missed collector hours are
unrecoverable) and let the H-014 shadow cycle keep counting. No live enablement.

1. User: merge PR #19 (`feature/deribit-moneyness-hypotheses`, MERGEABLE).
   `origin/main` already holds PRs #14/#16/#18; do not push `main` directly.
2. User: follow the RUNBOOK to create the three-file orphan `public-status`
   worktree, enable GitHub Pages, verify the first public page, and register the
   daily refresh task. The implementation is complete but not published.
3. Codex: `tasks/2026-08-04-h038-residual-meanrev-stage2-codex-tasks.md`.
   AUTHORIZED 2026-08-04. Terminal for F-S5 (K to 2/2) whatever the outcome;
   breadth must be derived from realized positions, never declared (I68).
4. Codex: `tasks/2026-08-04-wsc-c3-c5-c10-codex-tasks.md`. AUTHORIZED
   2026-08-04 for C3/C5/C10 only — one commit and one Change Manifest each.
   C1/C2/C4/C6/C7/C8/C9/C11 and F2 remain ungated.
5. ADR-0016 deferred by user decision 2026-08-04. Reason recorded as I68 plus
   the `docs/ai/LESSONS.md` funnel diagnosis: across 38 Stage-2 artifacts the
   first failing check is `data_availability` 16 times and 11 of ~20 candidates
   reaching the power check have negative or zero Sharpe. The binding
   constraint is candidate input quality, not gate strictness.

Related: `docs/AI_HANDOFF.md`, `docs/KNOWN_ISSUES.md`, `config/workstreams.yaml`, `tasks/2026-08-04-public-status-and-decision-batch-handoff.md`.
