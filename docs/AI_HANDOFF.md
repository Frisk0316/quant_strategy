---
status: current
type: handoff
owner: human
created: 2026-05-11
last_reviewed: 2026-07-03
expires: none
superseded_by: null
---

# AI Handoff

Cross-session memory for Claude and Codex. Keep this file current-state only;
move completed session history to `docs/CHANGELOG_AI.md` and durable gaps to
`docs/KNOWN_ISSUES.md`.

## Current Goal

Codex completed `tasks/2026-07-03-project-maintenance-tasks.md` in the user
requested order: M1 -> M2 -> M3/M4 -> M5.

Current status:

- M1 CI consistency is implemented and committed in `df96682`.
- The 2026-07-03 Claude handoff/task docs are preserved in `79c1ddc`, satisfying
  the M2 precondition before this slimming pass.
- M2 docs/governance slimming is committed in `0191c1d`.
- M3 no-DB backtest smoke fixture is committed in `2dea608`.
- M4 monitoring unit tests and M5 stocks Option A mapping are committed in
  `5eb71f8`.

2026-07-03 Claude review of M1–M5: **M1/M3/M4/M5 ACCEPTED, M2 PARTIAL —
remediation task M2-R1 added** to
`tasks/2026-07-03-project-maintenance-tasks.md`. Verification was independent,
not self-report: ruff full scope passed; unit suite 576 passed; root synthetic
tests 32 passed; lab suite 18 passed; every `frontend/*.js` passed
`node --check`; docs checks passed; `scripts/smoke/backtest_smoke.py` ran in
11.6s with 2 fills, and the reviewer reproduced the broken-fixture probe
(corrupt close → exit 1, restore → exit 0); aggregate diff `a688de1..4c7afd9`
touched no forbidden file. M2 finding: `0191c1d` slimmed AI_HANDOFF but did
NOT migrate the deleted 2026-06-24→07-01 history into CHANGELOG_AI (entries
jump 06-23 → 07-02; spot-check numbers C2 DSR 0.0041 / WF -1.5093 absent) and
dropped two still-valid KNOWN_ISSUES operational caveats (K-budget table
human-maintained staleness; family-cumulative registry row wording / max-row
parser fallback). Nothing is irrecoverable — source text is at
`git show 0191c1d^:docs/AI_HANDOFF.md` — but CHANGELOG_AI as durable readable
history has a hole until M2-R1 lands. Minor non-blocking notes: the metrics
test is call-only smoke (no value read-back); Makefile `FRONTEND_JS` and the
`frontend-check` lines remain two hand-maintained lists that can drift again.

Pipeline improvement work P1-P8 is separate from the maintenance stream. Codex
implemented P1-P8 in the working tree: funding backfill tooling, literature
abstract/session-scoring gates, refuted-family twist gating, feedback ranking
tags with I30 accounting, OKX liquidation forward accumulation, advisory
`--reprobe`, funnel metrics, and Binance Vision OI parsing. These pipeline
edits are not owned by the maintenance task.

2026-07-03 Claude review of P1-P8: **APPROVED with one required fix.**
Independently reran the test battery (88 pipeline unit tests + 18 lab tests
passed, a superset of Codex's reported 76; docs metadata 0 warnings),
confirmed no forbidden file changed (trading-core, durable ledgers, gates,
Stage-2 thresholds, existing `results/**` — the only results diff is
Claude's own pre-existing Stage-1 SKIP note), and verified
acceptance-mapped tests exist (ssrn-6609698 refuted-family regression,
byte-identical reprobe idempotency, fail-closed missing-hypothesis-id,
placeholder-score rejection, review-bundle firewall, feedback-spawned
n_trials reconciliation). **Required fix before commit / first real
liquidation ingest:** `liq_okx_eth` in
`scripts/market_data/ingest_external.py` hardcodes `contract_value: 0.01`,
but OKX `ETH-USDT-SWAP` ct_val is **0.1** (ADR-0007,
`sql/seed_venue_instrument_specs.sql`); OKX liquidation details carry only
`sz`/`bkPx`, so the computed-notional path always applies → ETH liquidation
notional would be understated 10x. Fix 0.01→0.1 (or read from the seed/spec
source) plus a regression test. No real data was poisoned (no DB ingest has
run yet). Claude answers to Codex's open questions: OKX-only REST is
accepted for P5 (Binance WS daemon stays deferred as the task specified);
`stage2_pass_on_reprobe` stays as-is (it is NOOP — promotion to Stage-3
remains a human decision); `twist_evidence` stays in `notes` for now (a
`PaperScoring` schema change was out of task scope).

2026-07-03 Claude (user-authorized execution): the required fix and all
real-data acceptance items are now DONE. ETH ct_val fixed 0.01→0.1 with a
seed-SQL-pinned regression test; P1-P8 committed as `dfc7af8` (35 files,
separate from maintenance); `check_doc_impact.py --strict` passed on 35
staged files. Real runs against DB+network: **P1** funding backfill wrote
66,041 rows for all 22 point-in-time union symbols, 8H coverage 0 gaps
2024-01-01→2026-07-02 (`results/stage2_reprobe_20260703_funding/
funding_coverage.json`); **P8** Binance Vision OI history ingested
262,814 rows each for BTC/ETH (5m, 2024-01-01→2026-07-02, only the
unpublished latest day missing) — F-OI-POSITIONING is no longer
data-blocked; **P5** first OKX liquidation ingest landed 1,600 rows each
for BTC/ETH, and the measured REST retention window is only **hours**
(BTC ≈13.9h, ETH ≈5.3h at the 1,600-row cap), so lossless forward
accumulation needs a 2-4h ingest cadence — scheduling that is a pending
user decision. **P6 reprobe** ran for real on taxonomy_002: funding
candidate FAIL→FAIL with improved metrics (good_symbols 5→7) appended
append-only; xvenue unchanged (OKX 1m still ~5,220 rows vs 1.29M/leg).
**New root cause found:** the funding-breadth FAIL is no longer a funding
data problem — `build_universe_membership.py` reads only the thin local
parquet mirror, so `eligible` is an artifact (median 2 eligible/day;
BTC/ETH eligible 61 days vs MEME 657). A DB-rebuilt diagnostic universe
(scratch, non-destructive) gives median 29 eligible/day and the probe then
reads good_symbols 28/10 ✓, median_daily_ready 27/10 ✓, failing only
min-breadth on the 2024-01 warmup edge
(`results/stage2_reprobe_20260703_funding_dbuniverse/`). This same
artifact underlies E-028's universe=8 and H-004/S5's no-grid-activity.
Follow-ups: **P9** (membership builder DB source + shared parquet rebuild)
added to `tasks/2026-07-03-pipeline-improvement-tasks.md`; the
warmup-window edge (first ~30 days can never reach breadth 10) is a
Stage-2 window spec decision needing user approval + manifest — thresholds
were NOT touched. Taxonomy data statuses updated for F-OI-POSITIONING
(available), F-LIQUIDATION-CASCADE (partial), F-FUNDING-XS-DISPERSION
(available-pending-universe-fix). One tooling fix: backfill script sys.path
lacked repo root, so its Stage-2 reprobe step failed on first real run;
fixed one-line, probe rerun via the registry CLI.

## Current Branch

- Branch: `codex/pipeline-batch1-stage3`.
- Recent commits: `df96682` (M1), `79c1ddc` (7/3 handoff preservation),
  `0191c1d` (M2), `2dea608` (M3), `5eb71f8` (M4/M5).
- Working tree also contains unrelated pre-existing pipeline changes; do not
  overwrite or sweep-commit them.

## Do Not Touch

Without explicit user approval, do not modify:

- `research/` except already-existing uncommitted pipeline work owned elsewhere.
- `results/**` existing artifacts.
- `src/okx_quant/strategies/`, `src/okx_quant/signals/`.
- `src/okx_quant/risk/`, `src/okx_quant/portfolio/`,
  `src/okx_quant/execution/`.
- `config/risk.yaml`, deployment/shadow/demo/live gates, or strategy assumptions.
- Differential-validation implementation unless a current task explicitly lists it.

## Completed Scope

M1 changed only CI/static-check docs surface:
`.github/workflows/ci.yml`, `Makefile`, `docs/KNOWN_ISSUES.md`.

M2 may change only:
`docs/AI_HANDOFF.md`, `docs/CHANGELOG_AI.md`, `docs/CURRENT_STATE.md`,
`docs/KNOWN_ISSUES.md`, `STATUS.md`, `config/workstreams.yaml`.

M3 may change only:
`scripts/smoke/backtest_smoke.py`, `tests/fixtures/backtest_smoke/**`,
`Makefile`, `docs/KNOWN_ISSUES.md`, `docs/RUNBOOK.md`.

M4 may change only:
`tests/unit/test_monitoring.py`, `docs/FEATURE_MAP.md`.

M5 Option A may change only:
`docs/FEATURE_MAP.md`, `src/okx_quant/stocks/__init__.py`.

## Verification Notes

M1 local evidence:

- `ruff check src tests backtesting scripts` passed.
- `pytest tests/unit -q` passed: 555 tests.
- `pytest tests/test_daily_winner_backtest.py tests/test_ohlcv_rotation.py -q`
  passed: 32 tests.
- `pytest research/crypto-alpha-lab/tests -q -p no:cacheprovider` passed:
  18 tests.
- `make frontend-check` could not run because `make` is unavailable in this
  Windows sandbox; each `node --check` command from the target passed manually.

M2 local evidence:

- `python scripts/docs/check_doc_metadata.py`
- `python scripts/docs/check_feature_map_links.py`

M3-M5 local evidence:

- `python scripts/smoke/backtest_smoke.py` passed: replay smoke emitted 2 fills
  and verified `result.json`, `metrics.json`, and `fills.csv` in a temp dir.
- Temporary broken-fixture probe made `scripts/smoke/backtest_smoke.py` fail with
  exit 1, then the fixture was restored and the smoke passed again.
- `pytest tests/unit/test_monitoring.py -v` passed: 4 tests.
- `pytest tests/unit -q` passed: 575 tests.
- `ruff check scripts/smoke/backtest_smoke.py tests/unit/test_monitoring.py src/okx_quant/stocks/__init__.py`
  passed.
- `python scripts/docs/check_doc_metadata.py` passed.
- `python scripts/docs/check_feature_map_links.py` passed.
- `pytest tests/unit/test_stock_system.py -q` passed: 5 tests.
- `make backtest-smoke` and `make docs-check` could not run because `make` is
  unavailable in this Windows sandbox; equivalent Python commands passed.

## Next Steps

1. Claude/human review the M1-M5 maintenance commits and the two handoff files.
2. Review the separate pipeline P1-P8 dirty worktree; do not sweep-commit it
   with maintenance changes.
3. Run full `make verify` / `make verify-full` only in an environment where
   `make`, TimescaleDB, and required data are available.

## Open Questions

- Which dirty pipeline changes are intended for a later P1-P8 commit versus
  already superseded scratch work?
