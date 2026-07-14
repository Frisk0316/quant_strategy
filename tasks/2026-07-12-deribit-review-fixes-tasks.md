---
status: archived
type: task
owner: codex
created: 2026-07-12
last_reviewed: 2026-07-12
expires: none
superseded_by: null
---

# Deribit Review Fixes (R1-R5) + D4 Backfill Resume

Task: Land the fixes from Claude's ACCEPT-WITH-FIXES review of the Deribit
D1-D5 pass, in the review's mandated order, then resume the D4 option-flow
full backfill to completion.

Strategy/spec source: `tasks/2026-07-11-deribit-ingestion-review.md`
(authoritative fix list — read it in full first);
original task spec `tasks/2026-07-11-deribit-data-ingestion-tasks.md`.

Required behavior (R1 example): an as-of join at 10:30 UTC must NOT see the
10:00-11:00 optflow/dvol_1h bucket. After the fix that bucket carries
`published_at = 11:00` (bucket END), so `data_loader.py`'s PIT guard
excludes it until 11:00.

ORDER (do not reorder; review §Ordering):
1. R1 BLOCKER — `published_at = bucket_end` for `optflow_deribit_*` and
   `dvol_deribit_*_1h` in the clients; one-off relabel of existing DB rows
   in place (row counts must not change); document the aggregate labeling
   convention in DATA_FLOW.md; update pinned tests; add FAILURE_MODES entry
   plus a guarding assertion/test. Daily DVOL: fix alongside or record the
   ≤24h caveat explicitly in DATA_FLOW.md.
2. R2 — backfill checkpoint must survive a failed chunk: only advance
   `cursor_time` on success; failure status must not clobber the cursor.
   Add a resume-after-failure test.
3. R3 — raise on non-hour-aligned `--start/--end/--chunk-days`.
4. Resume the D4 full backfill (BTC from 2024-02-07, ETH from 2024-02-01,
   through now) with checkpoints; report final row counts and gap scan.
5. R4 — DVOLClient: same ≤5 req/s throttle + 429/10028 backoff as the other
   three clients, with test.
6. R5 minors (batch, review §R5 a-g): relax fail_on_empty_fetch for
   backfill; fix `--dataset` append-with-default; emit exclusion-count row
   for USDC-only hours or record the drop; DATA_FLOW lines for max-pain
   interpretation and funding observed_at assumption; optional D5
   dataset-id check and frontend stale-fetch seq guard; RUNBOOK forward
   -ingest scheduling for funding/dvol_1h/optflow.

PERMITTED FILES (only edit these):
- src/okx_quant/data/external_clients/deribit_option_flow.py,
  deribit_dvol.py, deribit_option_surface.py, deribit_funding.py
- src/okx_quant/data/external_store.py (only if relabel/guard needs it)
- scripts/market_data/backfill_deribit_option_flow.py,
  snapshot_deribit_options.py, ingest_external.py
- one new one-off relabel script under scripts/market_data/
- src/okx_quant/api/routes_data.py, frontend/view-config.js,
  frontend/data.js (R5f only)
- config/external_data.yaml (only if labeling convention needs a knob)
- tests/unit/test_deribit_*.py, tests/unit/test_routes_data_external_series.py
- docs/DATA_FLOW.md, docs/FAILURE_MODES.md, docs/RUNBOOK.md

FORBIDDEN (do not touch):
- src/okx_quant/strategies/, signals/, risk/, portfolio/, execution/,
  config/risk.yaml
- backtesting/ (including data_loader.py — the PIT guard is correct; fix
  the labels, not the guard) and all turtle files
- Existing result artifacts under results/

SCOPE LIMIT: fixes listed in the review only; no adjacent refactoring.
The deribit work is still uncommitted in the working tree — build on it,
do not revert it. Do not touch the uncommitted OI-positioning files.

REQUIRED ON COMPLETION:
- git diff --stat; run `python -m pytest tests/unit -q` full suite and the
  targeted deribit tests; paste tails.
- DB evidence: relabeled row counts per dataset, D4 final coverage
  (rows/ccy, first/last ts, gaps >1h), pasted query output.
- Update docs per AGENTS.md matrix; session + context handoff files are
  MANDATORY this time (the large-sweep session skipped them).
- Commit only if the user asks in-session.

ACCEPTANCE CRITERIA (binary):
- [ ] Unit test pins `published_at == bucket_end` for optflow and dvol_1h.
- [ ] DB relabel done in place; per-dataset row counts unchanged; 0 gaps
      >2h re-confirmed by query after relabel.
- [ ] Failed-chunk resume test: cursor stays at last success (not
      2024-01-01).
- [ ] Non-hour-aligned bounds raise (test).
- [ ] D4 backfill complete 2024-01-01 → run date for BTC and ETH, evidence
      pasted.
- [ ] DVOL throttle/backoff test passes.
- [ ] DATA_FLOW.md states labeling convention + funding/max-pain notes;
      FAILURE_MODES.md has the new PIT-labeling entry.
- [ ] Full unit suite green; diff contains only permitted files.

REPORT: per template §2 plus: which R5 items were deferred (if any) and why;
confirmation that H-013 Stage-1 is unblocked (R1 landed + data re-scanned).
