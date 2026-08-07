---
status: current
type: handoff
owner: human
created: 2026-06-12
last_reviewed: 2026-08-06
expires: none
superseded_by: null
---

# Current State

Present-tense snapshot. History: `docs/CHANGELOG_AI.md`. Gaps: `docs/KNOWN_ISSUES.md`.

## Repository

- `main` = `7cc7eb1` (PR #22 merged 2026-08-06: F78 DSN fix +5 tests, weekly DB
  backup, optflow reconciliation, data inventory, two B1-closed admission
  packets). `claude/ops-dsn-fix-and-db-backup` is three commits ahead
  (`5261de0` OKX reverification, `26fd9de` ingest ruling, `df4e75d`
  compression); PR #23 is OPEN for them and awaits review/merge.
- No strategy is promotion/demo/live ready. H-014/F-VOL-REGIME-OPT is the only
  `supported` hypothesis (E-051 + E-052); promotion blocked per R7.2 pending
  >=8 valid shadow journal weeks plus reviews.
- Authority order: config, accepted ADRs, `research/strategy_synthesis.md`,
  `docs/ai_collaboration.md`. No change without an approved task.

## Data

- F78 incident (FIXED via `scripts/_load_dotenv.cmd`): the three DB-writing
  scheduled tasks failed every run 2026-08-03→08-06 on a missing process
  `DATABASE_URL`. 65 hourly `xvenue_opt_iv_*` obs permanently lost; shadow
  journal stalled at 2026-08-03 (second stall). xvenue/liq verified Last Result
  0. No task-failure alerting (KNOWN_ISSUES).
- Weekly backup: `quant_db_backup_weekly` SUN 03:00, S4U/Limited, battery-safe
  → `C:\quant_backups`, keep 2. User ruled 2026-08-07: `market_klines`
  EXCLUDED again — script now excludes BOTH `_hyper_9` and `compress_hyper_14`
  chunk prefixes (compression moved the data). First scheduled run 08-09.
- DB OUTAGE 2026-08-06 ~17:00 → 08-07 09:45 (Docker Desktop down): 16 hourly
  `xvenue_opt_iv_*` obs/dataset permanently lost (on top of F78's 65);
  collection resumed, DB-verified. Caveat: the collector exits 1 on its gap
  alert even when inserts succeed — check the log, not just Last Result.
- Compression enabled 2026-08-06 (`tasks/2026-08-06-db-compression-handoff.md`):
  `market_klines` 51 → 10.1 GB, `external_observations` 11 → 4.8 GB, DB 78 →
  33 GB, 366/535 chunks, 30-day policies, 3 duplicate indexes dropped, counts
  unchanged. Host `ext4.vhdx` did NOT shrink (KNOWN_ISSUES).
- Canonical 30-symbol 1m 2024–2026 candles + funding unchanged. 78 external
  datasets; inventory in `tasks/2026-08-06-data-inventory.md`. Binding
  constraint is the crypto overlap (~898 daily / 128 weekly obs), not history
  depth. `oi_binance_hist_shib` 0 rows is upstream (E-036, no native SHIBUSDT
  on Binance Vision), not a defect; `1000SHIB` passes.
- Recurring-ingest CLOSED 2026-08-06 (user): schedule nothing — unconsumed
  families are re-downloadable archives. `optsurf_deribit_*` (3 rows) deferred;
  1h `oi_binance_*` is an unbackfillable 5m-Vision duplicate, removal candidate.
- ADR-0014 BTC/ETH-only OKX source-aware 1m history verified over
  `[2020-01-01, 2026-06-17)`: 3,396,960 raw/venue rows per symbol, zero gaps or
  mismatches, 1.0 alignment, zero resolved OKX rows; already run in `b40f15b`,
  two 2026-08-06 reruns changed zero rows. Does not extend the 30-symbol
  cross-section or pre-2024 funding.
- Optflow CLOSED: -5 drift was pagination (`5920380`); H-031/H-035 stay blocked.

## Execution / testnet

- ADR-0018 permits testnet-only Deribit execution; NOT running. Phase 2 waits
  on a user trade-scoped testnet key → Codex runner → Claude go/no-go.
- Public-status page LIVE (Pages serving) with its daily 16:30 task; worklog
  page live with 16:45. Security state unchanged from 2026-08-05.
- Scheduled: `quant_{liq_okx_ingest,okx_market_data,h014_shadow_daily,
  xvenue_options_iv,weekly_worklog,private_worklog_daily,public_status_daily,
  db_backup_weekly}`.

## Hypothesis pipeline

- Candidate Admission Form exercised for the first time
  (`tasks/2026-08-06-vix-cot-candidate-packets.md`): both candidates BLOCKED
  at B1 and CLOSED — 001 VIX-term-structure has only contemporaneous crypto
  evidence (no predictive expected gross); 002 cross-asset COT is user
  data-gated AND its supporting literature (Hung/Liu/Yang 2021) belongs to
  already-refuted H-044/F-CFTC-PARTICIPANT-REGIME. No H-number, trial, or K.
- Stage-2 power floors are computable ex ante: breadth-1 daily/898 obs needs
  ~1.05 net annualized Sharpe; weekly/128 needs ~1.06 (trials=1).
- H-038/E-095 terminal (K 2/2); H-040..H-046 closed. ADR-0016 deferral LIFTED
  2026-08-07 (user, infra only): slice 2 DELIVERED, reviewed
  APPROVE-WITH-FINDINGS, pushed. Dual track: Codex phase 3 (task file
  2026-08-07); Claude literature sweep DONE — 2 admission-worthy candidates
  (S-001 multi-week reversal, S-002 jump-variance XS), macro + derivatives
  axes BARREN (`tasks/2026-08-07-literature-sweep-candidate-shortlist.md`).

## Next actions, in order

Always on: keep Docker/TimescaleDB up — missed collector hours are permanent.

1. TODAY 16:10: confirm the shadow journal gains 2026-08-07. (F78 fix PROVEN
   08-06; xvenue collection confirmed resumed 08-07 10:15.)
2. Merge PR #23 (6 commits: three pre-existing + ops/backup + slice 2 +
   state).
3. SUN 08-09 03:00: confirm first scheduled backup run (Last Result 0,
   excluded dump present in `C:\quant_backups`).
4. Codex executes phase 3; Claude builds S-001/S-002 admission packets.
5. DEFERRED by user 2026-08-07 (cannot log into Deribit): testnet key →
   Codex runner → Claude Phase-2 go/no-go.

Related: `docs/AI_HANDOFF.md`, `docs/KNOWN_ISSUES.md`, `config/workstreams.yaml`, `tasks/2026-08-06-ops-fix-candidate-closure-handoff.md`.
