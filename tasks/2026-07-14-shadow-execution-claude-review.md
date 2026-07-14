---
status: current
type: review
owner: claude
created: 2026-07-14
last_reviewed: 2026-07-14
expires: none
superseded_by: null
---

# Claude Review: H-014 shadow-execution layer (ADR-0011 v1) — 2026-07-14

Scope: Codex deliverables under
`tasks/2026-07-14-deribit-shadow-execution-codex-tasks.md` (T1–T4).
Verdict: **ACCEPTED with two findings (one measured-immaterial deviation with
a required test follow-up, one robustness gap). Safety boundary is clean.**

## Independently verified (not taken from the report)

- All 17 shadow unit tests + 6 golden accounting tests pass (re-run).
- Safety boundary read line-by-line: allow-listed public client (4 read-only
  methods, anything else raises); config fails closed on non-shadow mode,
  non-public URL, credential-shaped keys, or any frozen-constant drift
  (ivp 85 / z 0.5 / 1/30 / cap 1.0 / R8.4 fees — with runtime drift checks
  against the IMPORTED research fee functions); no order path exists;
  `live_trading_approved` is hardcoded false in the report.
- R8.3 in code: naked-put rejection requires covering long puts strictly
  below the short strike at ≥ units; unit cap enforced twice (intent + set
  validation). Accounting (settle/fees/marks) imported from the research
  module, not copied — golden tests pin both.
- Journal: append-only JSONL, fsync, deterministic event-id dedupe,
  schema-validated on load; live journal inspected — the two pre-guard smoke
  records carry stale signal days and are excluded by the report
  (`ignored_stale_signal_records: 2`); the valid cycle's records have exact
  prior-day signals. Exit criteria honestly report 0.14 weeks.

## Findings

1. **Signal-input deviation, measured immaterial — test follow-up REQUIRED.**
   The daily-close SQL groups candles into 08:00→08:00 UTC sessions
   (`ts − INTERVAL '8 hours'`), while the ratified E-039/E-051/E-052 series
   uses midnight-UTC daily closes. I compared the shadow DB path against the
   immutable E-039 series over 1,570 real common days: ivp identical
   (DVOL-only), |Δz| mean 0.03 / max 0.30, RICH(85/0.5) flag flips
   **BTC 0, ETH 3 (0.19%)** — operationally immaterial, and the 08:00
   session aligns with option expiry mechanics. ACCEPTED as a documented
   convention, BUT: `test_signal_reproduces_research_series_on_five_days`
   is tautological (it feeds one dict to `build_series` and to its own
   delegation wrapper) and cannot catch input-shape drift like this. Required
   follow-up: replace/augment it with a fixture-based DB-path comparison
   against recorded research-series values, and document the 08:00 session
   convention in the module brief/config comment.
2. **MINOR robustness:** `build_intent_legs`/`validate_intent_set` errors
   (sparse chain, no candidates, inverted strikes) propagate and abort the
   whole cycle instead of journaling a `missed_entry`/`rejected` record —
   such days would leave no audit trail. Suggest catch-and-journal.
3. Positive notes: stale-DB fail-closed guard (exact prior-day signal
   required); cap rejections excluded from the missed-entry denominator;
   distinct-ISO-week counting prevents sparse-span gaming of the 8-week gate.

## Ops reality for the 8-week gate

The staleness guard requires DVOL + candles ingested through the prior day —
with forward schedulers unregistered (standing user decision), this means a
manual daily ingestion + cycle run. Decision for the user: approve the
scheduled task (RUNBOOK-documented, kill = delete task) or accept the manual
cadence; missed days simply don't count toward the eight distinct weeks.

## Conditions

Finding 1's test follow-up and finding 2's catch-and-journal are review
conditions on Codex (non-blocking for continued manual cycles; blocking
before any scheduler approval request).
