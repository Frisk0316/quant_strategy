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

- PR #22 OPEN (`claude/ops-dsn-fix-and-db-backup`, 7 commits): F78 DSN fix for
  the three DB-writing scheduled wrappers (+5 tests), weekly TimescaleDB
  backup, stale optflow-decision reconciliation, data inventory, and two
  Candidate Admission Form packets with user rulings and B1 closure. `main`
  otherwise unchanged from 2026-08-05.
- No strategy is promotion/demo/live ready. H-014/F-VOL-REGIME-OPT is the only
  `supported` hypothesis (E-051 + E-052); promotion blocked per R7.2 pending
  >=8 valid shadow journal weeks plus reviews.
- Authority order: config, accepted ADRs, `research/strategy_synthesis.md`,
  `docs/ai_collaboration.md`. No change without an approved task.

## Data

- F78 incident: `quant_xvenue_options_iv`, `quant_liq_okx_ingest`, and
  `quant_h014_shadow_daily` failed every run 2026-08-03→08-06 on a missing
  process `DATABASE_URL`. 65 hourly `xvenue_opt_iv_*` observations are
  permanently lost; the shadow journal stalled at 2026-08-03 (second stall).
  Fixed via `scripts/_load_dotenv.cmd`; xvenue/liq verified Last Result 0
  through Task Scheduler. No task-failure alerting exists (KNOWN_ISSUES).
- Weekly backup EXISTS: `quant_db_backup_weekly` SUN 03:00, S4U/Limited,
  battery-safe → `C:\quant_backups`, keep 3, `market_klines` excluded. First
  archive 11.6 GB verified (38 external_observations chunks, 0 market_klines).
- Canonical 30-symbol 1m 2024–2026 candles + funding unchanged. 78 external
  datasets; inventory in `tasks/2026-08-06-data-inventory.md`. Binding
  constraint is the crypto overlap (~898 daily / 128 weekly obs), not external
  history depth. Defects: `oi_binance_hist_shib` 0 rows; `optsurf_deribit_*`
  3 rows, no scheduler. Only 3 external families have recurring ingest.
- Optflow decision CLOSED: the -5 drift was pagination (`5920380`), not an
  archive revision; resuming 2024+ enrichment is optional and does not unblock
  H-031/H-035 (pre-2024 tape is not served).

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
- H-038/E-095 terminal (K 2/2); H-040..H-046 closed; ADR-0016 deferred under
  I68. The 8/2/10 round contract is unmet; new candidates enter only through
  the admission form, data-first.

## Next actions, in order

Always on: keep Docker/TimescaleDB up — missed collector hours are permanent.

1. TODAY 16:10: confirm `quant_h014_shadow_daily` completes (Last Result 0,
   journal gains 2026-08-06) — end-to-end proof of the F78 fix.
2. User reviews/merges PR #22.
3. AUTHORIZED 2026-08-06 (user): OKX raw 2020+ 1m → canonical promotion.
   Codex executes `tasks/2026-08-06-okx-2020-canonical-promotion-codex-tasks.md`
   (measure-first, additive, idempotent; BTC/ETH overlap only; H-010 stays
   shelved — no pre-2024 OKX funding). Claude reviews the delivery.
4. Deribit testnet key (test.deribit.com; trade read_write, wallet none/read)
   → Codex runner → Claude Phase-2 go/no-go.
5. Decide the recurring ingest schedule for Cboe/COT/FRED — the live-path
   prerequisite for any external-data candidate.

Related: `docs/AI_HANDOFF.md`, `docs/KNOWN_ISSUES.md`, `config/workstreams.yaml`, `tasks/2026-08-06-ops-fix-candidate-closure-handoff.md`.
