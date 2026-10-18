---
status: current
type: handoff
owner: claude
created: 2026-08-06
last_reviewed: 2026-08-06
expires: none
superseded_by: null
---

# Session Handoff: TimescaleDB compression + full backup — 2026-08-06

## Goal and implementation summary

Answer "why is the repo 1.8 GB but the dump 11.6 GB", then shrink the 78 GB DB
without deleting anything a strategy might need. `market_klines` (51 GB) and
`external_observations` (11 GB) had compression off while the three candle
hypertables already used it. Enabled columnstore on both, backfill-compressed
every chunk older than 30 days, added policies, and dropped three btree indexes
that were prefix-duplicates of existing PK/unique keys. DB 78 → 33 GB, and the
backup script's `market_klines` exclusion stopped paying for itself.

## State, diff scope, business rule

- Branch `claude/ops-dsn-fix-and-db-backup`; seven files in this commit.
- Added: this file. Deleted: none. Changed: `scripts/backup_db.ps1`,
  `docs/CURRENT_STATE.md`, `docs/AI_HANDOFF.md`, `docs/KNOWN_ISSUES.md`,
  `docs/CHANGELOG_AI.md`, `docs/ai/LESSONS.md`. The matching `docs/RUNBOOK.md`
  edit was swept into `5261de0` by a concurrent commit, not by this session.
- DB (not in git): compression settings, policies 1006/1007, 120 chunks
  compressed, 3 indexes dropped. DB healthy, counts verified, policies armed.
  Unfinished: host `ext4.vhdx` reclaim.
- Not a business-rule change — storage layout only, no Change Manifest,
  DOC_IMPACT_MATRIX not triggered. `research/`, `config/`, ADR,
  HYPOTHESIS_LEDGER, EXPERIMENT_REGISTRY, `config/workstreams.yaml`: all N/A.

## Decisions made (and why)

- Compress, don't delete — the other three hypertables already achieved
  5.2x/7.8x/6.1x in this same DB, so the ratio was measured, not guessed.
- `raw_payload` deliberately kept despite being ~16 GB of literal duplication of
  the typed OHLCV columns: it is the provenance record guarded by
  `tests/unit/test_source_provenance_validation.py`, and compression made it cheap.
- Settings copied from the existing policies, not tuned; 30 symbols and 77
  datasets are safe segment cardinalities.
- Full backup over the exclusion — a partial dump needs a Binance/OKX re-ingest.
  `Keep` 3 → 2, `MinFreeGB` 20 → 45 to fit the larger archive.

## Checks run

- Trial compress `_hyper_9_358_chunk`: 532 MB → 109 MB, 4.9x, 7.57s.
- Backfill: 82 `market_klines` chunks 10m10s; 37 `external_observations` 1m23s.
- `EXPLAIN` after: `ColumnarScan` + segmentby pushdown, no seq-scan regression.
- Counts after three Docker restarts: `market_klines` 101,626,636 rows
  `[2020-01-01, 2026-08-03]`; `external_observations` 7,765,017 rows
  `[1990-01-02, 2026-08-06]` — unchanged bar normal new writes.
- `pg_restore --list` on the 19.2 GB dump: 84 `_hyper_9_` + 38 `_hyper_11_` +
  366 `compress_hyper_` entries. 366/535 chunks compressed, 5 policies armed.
- `docs-check` (metadata, feature-map links, ledger consistency) passed.

## Known limitations / risks

- `ext4.vhdx` still 127.5 GB for 46 GB of content. Sparse is on so future
  deletes return space; the historical allocation needs an `fstrim` blocked by
  Docker's mount-namespace isolation (KNOWN_ISSUES). C: free went 95 → 88.3 GB
  this session (the bigger dump) — the 45 GB is future headroom.
- Docker's engine hung after a `wsl --shutdown` cycle; needed all
  `com.docker.backend` / `Docker Desktop` processes killed. DB verified intact.
- `docs/ai/LESSONS.md` is 217 lines, past its 150-line compaction trigger.
  Pre-existing (198 before this session); not actioned here.

## Rollback, rules, approvals, next action

- Rollback: `SELECT decompress_chunk(c) FROM show_chunks('<table>') c;` then
  `remove_compression_policy` and `ALTER TABLE ... SET (timescaledb.compress =
  false)` (needs ~50 GB free); recreate the three btrees from this file's git
  history; `git checkout` the prior script/doc blobs.
- Untouched: `src/okx_quant/{strategies,signals,risk,portfolio,execution}/`,
  `config/risk.yaml`, `results/**`, `research/**`. No gate moved; no
  live/shadow/demo readiness claimed.
- User approved in order: trial compress, full backfill, index drops,
  backup-script change, vhdx reclaim attempt, wrap-up.
- Next: open the PR `5261de0` still needs. Next
  session reads `docs/RUNBOOK.md` "Database Backup" + `scripts/backup_db.ps1`.
- Open question: keep the 19.2 GB full dump, or re-exclude `market_klines` (now
  ~10 GB compressed; dump falls to ~9 GB, returning ~10 GB of C:)?

## Human Learning Notes

Freeing space inside a containerized DB does not return disk to the host. The DB
shrank 45 GB and the Windows free-space number got *worse* — the saving was real
but trapped in a VHDX that only grows. Report the number the user can measure,
not the one the tool prints. Same trap on the weekly backup: it is sized by the
dump, not the DB, so compressing made the backup bigger once the exclusion came
off. Second gotcha: TimescaleDB's `before/after_compression_total_bytes` exclude
TOAST and under-report ~10x on jsonb tables; use `hypertable_detailed_size`.
