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
  packets). `claude/ops-dsn-fix-and-db-backup` is one commit ahead (`5261de0`,
  OKX reverification + ADR-0014 review closure) and needs a new PR.
- No strategy is promotion/demo/live ready. H-014/F-VOL-REGIME-OPT is the only
  `supported` hypothesis (E-051 + E-052); promotion blocked per R7.2 pending
  >=8 valid shadow journal weeks plus reviews.
- Authority order: config, accepted ADRs, `research/strategy_synthesis.md`,
  `docs/ai_collaboration.md`. No change without an approved task.

## Data

- F78 incident (FIXED via `scripts/_load_dotenv.cmd`): the three DB-writing
  scheduled tasks failed every run 2026-08-03→08-06 on a missing process
  `DATABASE_URL`. 65 hourly `xvenue_opt_iv_*` observations permanently lost;
  shadow journal stalled at 2026-08-03 (second stall). xvenue/liq verified Last
  Result 0. No task-failure alerting exists (KNOWN_ISSUES).
- Weekly backup EXISTS: `quant_db_backup_weekly` SUN 03:00, S4U/Limited,
  battery-safe → `C:\quant_backups`, keep 3, `market_klines` excluded. First
  archive 11.6 GB verified (38 external_observations chunks, 0 market_klines).
- Canonical 30-symbol 1m 2024–2026 candles + funding unchanged. 78 external
  datasets; inventory in `tasks/2026-08-06-data-inventory.md`. Binding
  constraint is the crypto overlap (~898 daily / 128 weekly obs), not external
  history depth. `oi_binance_hist_shib` 0 rows is upstream, not a defect —
  Binance Vision has no native SHIBUSDT metrics (E-036); `1000SHIB` passes.
- Recurring-ingest question CLOSED 2026-08-06 (user): schedule nothing — every
  unconsumed family is a re-downloadable archive, topped up on demand when a
  candidate is admitted. Only unreproducible snapshots would earn a timer:
  `optsurf_deribit_*` (3 rows) is deferred, and the 1h `oi_binance_*` series is
  an unbackfillable duplicate of the 5m Vision history — a removal candidate.
- ADR-0014 BTC/ETH-only OKX source-aware 1m history is verified over
  `[2020-01-01, 2026-06-17)`: 3,396,960 raw/venue rows per symbol, zero gaps or
  OHLCV mismatches, 1.0 Binance/OKX alignment, and zero resolved OKX rows. The
  extension had already run in `b40f15b`; two 2026-08-06 reruns changed zero
  rows. This does not extend the 30-symbol cross-section or pre-2024 funding.
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
2. Open a PR for `5261de0` (OKX reverification + ADR-0014 review closure).
3. Deribit testnet key (test.deribit.com; trade read_write, wallet none/read)
   → Codex runner → Claude Phase-2 go/no-go.

Related: `docs/AI_HANDOFF.md`, `docs/KNOWN_ISSUES.md`, `config/workstreams.yaml`, `tasks/2026-08-06-ops-fix-candidate-closure-handoff.md`.
