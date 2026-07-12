---
status: archived
type: review
owner: claude
created: 2026-07-11
last_reviewed: 2026-07-11
expires: 2026-10-11
superseded_by: null
---

# Claude Review: Deribit D1–D5 Implementation — 2026-07-11

Scope: Codex's Deribit pass per `tasks/2026-07-11-deribit-data-ingestion-tasks.md`.
Method: two independent review agents (data layer; API/frontend/docs) + one
verifier that ran tests and DB queries. Handoffs cross-checked against diffs.

## Verdict: ACCEPT-WITH-FIXES

Implementation quality is high, handoffs are honest (D4 incompleteness
self-disclosed and matches DB state exactly), all 637 unit tests pass, DB
coverage claims confirmed by query. One finding is disqualifying for research
use of the new hourly datasets; three majors gate the D4 full-backfill resume.

## Verified green

- Tests: targeted 15/15; full suite 637 passed. node --check 3/3. Docs
  metadata + feature-map link checks pass. check_doc_impact --strict: 0.
- DB (queried): dvol_*_1h 22,128 rows/ccy; funding_* 22,127 rows/ccy, both
  2024-01-01→2026-07-10 23:00Z, 0 gaps >2h; optsurf 1 snapshot/ccy; optflow
  ETH 744 rows (pilot exact), BTC 888 (through 2024-02-06), full run
  checkpointed-incomplete as disclosed.
- Scope: no forbidden-path edits; config/ingest changes purely additive;
  D5 endpoint parameterized SQL, empty-safe; charts.js NOT touched (Turtle
  hunks are the earlier session); Change-Manifest skip recorded vs A7/A8.
- D4 imbalance formula and inverse-only exclusion match the pre-registered
  spec verbatim; UTC handling and pagination guards correct and tested.

## R1 — BLOCKER (before any research/H-013 use of hourly datasets)

`optflow_deribit_*` and `dvol_deribit_*_1h` aggregate information through
bucket END but set `observed_at = published_at =` bucket START
(`deribit_option_flow.py:147,192-193`; dvol client diff). The replay PIT
guard keys on `published_at` (`backtesting/data_loader.py:746-768`), so an
as-of join leaks up to 1h of future data. Fix: `published_at = bucket_end`
for both datasets, relabel existing DB rows in place, state the aggregate
labeling convention in DATA_FLOW.md, update the pinned tests, add a
FAILURE_MODES entry + guarding assertion. (Daily DVOL has the same
pre-existing ≤24h issue — fix alongside or record explicitly.)

## R2/R3 — MAJOR (before resuming the D4 full backfill)

- R2 checkpoint poisoning: a failed chunk upserts `status='failed'` over the
  single backfill checkpoint row and `_checkpoint_cursor` only trusts
  `success` → `--resume` restarts from 2024-01-01 after any exhausted retry
  (`backfill_deribit_option_flow.py:76-78,190-198`). Preserve the last
  successful cursor (e.g. only advance cursor_time on success; keep failure
  in status without clobbering cursor). Add a resume-after-failure test.
- R3 no hour-alignment guard: non-aligned `--start/--end/--chunk-days` create
  partial-hour aggregates that the row-replacing upsert stores as full hours
  and resume never repairs. Raise on non-hour-aligned bounds.

## R4 — MAJOR

`DeribitDVOLClient` gained multi-page loops but has no throttle and no
429/10028 retry (violates the task file's shared ≤5 req/s + backoff rule that
the other three clients honor). Add the same throttle/retry.

## R5 — MINOR (batchable)

a. `fail_on_empty_fetch=true` on optflow backfill chunks aborts legitimately
   empty windows (task allowed empty backfill windows) — relax for backfill.
b. `snapshot_deribit_options.py --dataset` uses `action="append"` with a
   non-empty default → single-dataset runs impossible.
c. Hours with only USDC-linear trades emit no row, silently dropping the
   exclusion count.
d. D3 max pain pools all expiries into one ladder — defensible for the
   one-row-per-currency design, but record the interpretation in DATA_FLOW
   before research use; all-None creation_timestamps → ValueError edge.
e. D1 funding `observed_at` = accrual-period end is PIT-safe but the
   assumption is documented nowhere — add one line to DATA_FLOW.
f. D5 endpoint: no dataset_id existence check (unknown id ≡ empty series) and
   no SQL-side LIMIT (fine at current sizes); frontend card has a stale-fetch
   race (no seq/abort guard).
g. RUNBOOK schedules only the D3 snapshot — funding/dvol_1h/optflow forward
   ingest has no scheduled run, so the series go stale after backfill.

## Ordering

R1→R3 first (R1 includes DB relabel), then resume the D4 full backfill, then
R4/R5. No promotion/live claim; H-013 Stage-1 work stays blocked until R1
lands and the relabeled data is re-scanned.

---

## Re-review of the fix pass — 2026-07-12: ACCEPT

Method: fix-verification agent (code diffs vs R1–R5) + fresh verifier
(tests, docs checks, read-only DB queries).

- **R1 FIXED and DB-confirmed:** `published_at = bucket_end` in code with
  pinned tests; DATA_FLOW states the aggregate labeling convention;
  FAILURE_MODES F26 added. DB scan: optflow_btc 22,126/22,126 and
  dvol_btc_1h 22,128/22,128 rows ALL satisfy `published_at = observed_at+1h`
  (oldest and newest rows checked); funding rows unchanged (`=`) as intended.
  Legacy daily dvol datasets have zero rows in this DB, so no relabel needed.
- **R2/R3/R4 FIXED** with tests (cursor preserved on failed chunks via SQL
  CASE; non-hour-aligned bounds raise; DVOL client throttles 0.2s/page and
  retries 429/10028).
- **R5a–g all FIXED** (empty backfill chunks advance; `--dataset` argparse;
  USDC-only exclusion rows; max-pain interpretation documented + None-edge;
  funding PIT note; endpoint 404 on unknown dataset + 5,000-point cap +
  frontend stale-fetch guard; RUNBOOK forward-ingest schedules).
- **D4 full backfill CONFIRMED by DB:** optflow 22,126 (BTC) / 22,125 (ETH)
  rows, 2024-01-01→2026-07-10 23:00Z, zero gaps >6h (max 2h). optsurf has
  1 row/ccy by design (D3 snapshot-only; scheduled task awaits user).
- Tests: Deribit-targeted 21/21 pass; docs metadata/link/impact checks pass;
  node --check 3/3. Full suite: 653 passed + **1 failure NOT attributable to
  Deribit**: `test_turtle_invest_pct_result_rows_use_fraction_unit` fails at
  committed HEAD (the banned `n > 1 ? n / 100 : n` heuristic exists in
  `turtleFixedInvestPctParam`, view-config.js:172, in HEAD; the Deribit
  working-tree diff is +99 insertion-only lines for the Derivatives card) —
  Turtle-workstream self-inconsistency between `61f04e2` and `4ac9a41`.

Follow-ups (non-blocking, owner in parens): fix the Turtle heuristic/test
contradiction at HEAD (Turtle stream); decide ingest-or-retire for the empty
daily `dvol_deribit_btc/eth` config datasets (hourly supersedes them); user
registers the RUNBOOK schtasks for D3 snapshots + forward ingest, else the
series go stale; optionally record the one-off relabel command in
CHANGELOG_AI for reproducibility.

**H-013 (`F-VRP-TIMING`) Stage-1 drafting is now unblocked.**
