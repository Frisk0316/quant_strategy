---
status: current
type: task
owner: claude
created: 2026-07-23
last_reviewed: 2026-07-23
expires: 2026-10-23
superseded_by: null
---

# Codex Task: Free-data scouting for F-TAKER-FLOW + candidates 2/3

User-authorized 2026-07-23 (free sources first). Read-only scouting +
one bounded ingestion-capture check. NO strategy code, NO probe, NO
experiment record — data facts only, reported for Claude/user decisions.

## Filled Implementation template

```text
Task: Establish the data facts that gate the F-TAKER-FLOW Stage-2 probe and
the liquidation/term-structure Stage-1 decisions.

Strategy/spec source: docs/superpowers/specs/2026-07-23-f-taker-flow-hypothesis.md
  ("Kill criteria" data-availability section); docs/DATA_FLOW.md.

Required behavior (three scouting questions, in order):

S1. taker_buy_volume in-house status (blocks the CVD probe):
- Check whether market_klines.raw_payload already preserves the Binance
  kline taker_buy_base/taker_buy_quote fields for the 30-symbol universe
  (sample rows across 2024-2026 + BTC/ETH 2020+). If YES: report the exact
  JSON path and per-year field coverage — capture becomes a parse/backfill
  from existing rows, zero re-download.
- If NO: report which windows need re-download from Binance Vision daily
  kline zips (they include the taker columns), with file-count/size
  estimate. Do not download anything.
- Either way: propose (report-only) the minimal schema addition for storing
  the column (e.g. one nullable numeric column or an external_observations
  dataset), with pros/cons in <=10 lines.

S2. Binance Vision liquidation snapshots (candidate 2 gate):
- Determine actual availability start date, symbol coverage, and file
  format/row semantics for USDT-M liquidationSnapshot daily files.
  Metadata-only checks (directory listings / a HEAD request pattern
  documented for a human to run if network is sandbox-blocked — in that
  case output the exact commands and mark UNCONFIRMED, do not fabricate).
- Report expected event counts per symbol per year if a sample file is
  already available locally; otherwise mark UNCONFIRMED.

S3. Delivery-futures klines for term structure (candidate 3 gate):
- Same metadata-only treatment: quarterly contract kline availability on
  Binance Vision (symbols, start years, current+historical contract naming).
- Additionally compute (from EXISTING in-house data only) the distinctness
  pre-estimate Claude needs: daily correlation between BTC/ETH perp
  annualized-funding proxy and any in-house basis-like series if one exists;
  if no such series exists in-house, state that the pre-estimate requires
  the download first (mark UNCONFIRMED, recommend order of operations).

PERMITTED FILES (only edit these):
- scripts/scout_free_datasets.py        (new, read-only queries + report)
- tasks/2026-07-23-free-data-scout-report.md (new, the findings report)
- tests/unit/test_scout_free_datasets.py (new, minimal: SKIP-without-DSN +
  raw_payload parse function unit test)

FORBIDDEN (do not touch):
- Any ingestion/schema change (S1 proposes only, implements nothing)
- Any network download (document commands for human execution instead)
- research/, ledgers, results/**, src/okx_quant/** trading core,
  config/risk.yaml, strategy or probe code

SCOPE LIMIT: facts and commands only. The follow-up ingestion-capture task
(if S1 says re-download or schema change is needed) is a SEPARATE task
requiring Claude review of this report first.

ACCEPTANCE CRITERIA (binary):
- [ ] S1 answers YES/NO on raw_payload taker fields with sampled evidence
      (row counts per year, JSON path), or documents exactly why it cannot.
- [ ] S2/S3 report availability facts with every network-dependent claim
      either verified locally or marked UNCONFIRMED with the exact human
      command to verify — zero fabricated dates.
- [ ] Report file distinguishes FACT / UNCONFIRMED / RECOMMENDATION in
      separate sections.
- [ ] Tests green; diff contains only permitted files.

REPORT: the report file path, test tail, and a 5-line summary of which
gates (CVD probe / liquidation spec / term-structure spec) are open,
blocked, or need the human network step.
```
