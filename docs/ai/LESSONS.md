---
status: current
type: reference
owner: ai
created: 2026-07-03
last_reviewed: 2026-07-03
expires: none
superseded_by: null
---

# Process Lessons (append-only)

Format and rules: `docs/ai/MAINTENANCE.md`. Newest at the bottom. When this
file exceeds 150 lines, follow the compaction trigger.

## 2026-07-03 Session-start reading is the biggest silent cost

Trigger: measured ~2,300–3,500 lines of "required" session-start reading.
Wrong: reading every listed doc up front, or silently skipping some.
Right: read only CURRENT_STATE + your routing-table row; state a reason for
anything extra.
Rule: reading a doc outside your routing row requires a one-line reason.

## 2026-07-03 Claims without pasted output caused false "done" reports

Trigger: recurring pattern of "tests should pass now" with no run.
Wrong: reporting completion from intention instead of evidence.
Right: paste the command output tail, or report "not verified".
Rule: no pasted output = not verified = not done.

## 2026-07-18 Uncommitted multi-delivery trees break ex-ante provability

Trigger: E-057 registration order was unprovable because the spec, task,
registry row, and results all sat uncommitted in one shared working tree
alongside a sibling delivery.
Wrong: running an experiment while its ex-ante registration exists only as
uncommitted working-tree text.
Right: commit the registration (spec + registry row) before the run, and
commit each delivery separately.
Rule: ex-ante means committed-before-run; one delivery = one commit.

## 2026-07-29 A stalled scheduled job blamed on the human was a settings bug

Trigger: the H-014 shadow 8-week clock sat stalled for two weeks. The recorded
diagnosis was "machine off at the 16:10 window", and the advice given to the
user was "keep the laptop on" — which could never have worked.
Wrong: inferring a cause from the failure's shape (missing days, one `^C`) and
writing it into KNOWN_ISSUES without reading the job's own configuration.
Right: `Get-ScheduledTask ... | Select Settings` showed
`DisallowStartIfOnBatteries=True`, `StopIfGoingOnBatteries=True`,
`StartWhenAvailable=False` on a laptop running on battery — the scheduler
refused every trigger (0x800710E0) and never caught up.
Rule: before attributing an automation failure to the operator, read the
automation's configuration and its own result codes. Then check the next layer
too: fixing the scheduler exposed a second blocker (raw candles ran 14 days
ahead of `canonical_candles` because the daily script never promoted), so
"it runs now" is not "it works now" until the end-to-end artifact appears.

## 2026-07-29 Specs frozen against data that was never checked

Trigger: eight literature-backed hypotheses were registered with frozen
signals; five of them (H-031, H-033, H-035, H-036, H-037) turned out to be
unbuildable because the data they name does not exist in this repo — no
per-trade Deribit option tape (optflow stores hourly aggregates with a
20-trade sample), zero FRED rows, and no official CME series.
Wrong: writing a data inventory from memory into the research prompt, then
freezing specs against it. The same session had correctly scouted data before
registering H-028/H-029 and caught a gap that way — the check was skipped for
the bigger slate precisely when it mattered more.
Right: before freezing any spec, run the one query that proves each named
dataset exists at the required granularity and history. It costs minutes; the
omission cost a full build-and-run cycle across five candidates.
Rule: a spec may only name data whose existence, granularity, and date range
have been verified in this session. "The adapter exists" is not "the data is
ingested"; "we have option flow" is not "we have per-trade option flow".

## 2026-08-03 — Verify DB landings, not source fetches; delegate to the format that survives

Trigger: Codex's 2026-07-31 delivery reported "live source evidence" row counts
for 17 datasets, all fetched in-memory from the source APIs while the DB was
down; the numbers looked like ingestion evidence but zero rows had landed.
Wrong: reading a row-count table in a task file as proof of persistence. Source
fetch counts drift within days (COT gained a week, Cboe a day) and say nothing
about upsert semantics, as-of columns, or unit normalization in storage.
Right: acceptance criteria for ingestion must be checked with SQL against the
landed rows (counts, ranges, published_at invariants, derived-field sanity),
which a fresh session did in minutes once the DB was up.
Rule: "fetched=N" is source evidence; only a DB query is landing evidence. An
acceptance box for ingestion may only be ticked from a query against storage.

## 2026-08-04 — The candidate funnel is failing at the input, not at the gate

Trigger: 38 Stage-2 artifacts were tabulated after the user asked why every
candidate keeps failing. The failure profile is not "the gate is too strict".

Measured, across all 38 `stage2_feasibility.json` files:
- First failing check: `data_availability` 16, `cost_after_edge` 8,
  `distinctness` 2, `statistical_power` 2. **Nearly half never produce a return
  series at all** — a spec, a runner, and an immutable artifact are built before
  anyone confirms the data supports the mechanism.
- Of the ~20 that reach the power check, **11 have negative or zero plausible
  Sharpe** (H-030 -97.31, H-034 -0.97, xs_salience -0.61, H-029 -0.47, ...).
  A negative Sharpe fails any floor; loosening the gate changes nothing.
- Only one candidate ever passed all four cleanly on honest inputs
  (`f-funding-xs-dispersion-retry1`, 0.9687 vs 0.8113) and it reached Stage 3
  at DSR 0.8305 / PSR 0.9166. Three others "passed" on an assumed `breadth=2`
  and were retracted by E-092/E-093 when breadth was not derived from realized
  positions.

Wrong: treating low pass rates as evidence that the gates or the cost model
need revisiting, and building round-infrastructure to push more candidates
through the same funnel faster.
Right: the binding constraints are upstream — (a) data existence is confirmed
after registration instead of before, (b) `breadth` is declared rather than
derived, (c) no ex-ante gross-edge estimate is required, so mechanisms whose
gross capture is an order of magnitude below cost (H-010 1.3636 bps vs 8.0 bps;
H-030 8 bps/event) still get built.
Rule: before a candidate gets an H-number it must carry three verified numbers:
the DB-confirmed row count/range for every named dataset, the expected gross
capture per event in bps against the cost per event in bps, and the breadth its
realized position series can support. Fail closed to breadth=1. A candidate
that cannot supply all three is not execution-ready and does not count toward
an ADR-0016 sealed manifest.

## 2026-08-04 Pre-registered checks against artifacts nobody opened

Trigger: F-S5 burned both K retries on contract errors — E-094's coverage
gate had no provenance, and E-095's distinctness check required a dated
return series that immutable E-014 visibly does not contain. The mechanism
ran once (898 daily returns, breadth 5.74) and was never statistically
evaluated; the impasse was knowable by opening one JSON before sealing the
task contract.
Wrong: writing a Stage-2 contract that names a reference artifact without
verifying the artifact holds the exact series/fields the check consumes.
Right: before pre-registering any check, open every referenced artifact and
confirm the required inputs exist (E-025's dated regeneration was the known
remedy and was never invoked); a structurally unmeetable check is a contract
error to refuse before the run, per the I49 pattern.
Rule: a task contract may only reference artifact inputs the author has
verified exist, and thresholds it can give provenance for; anything else
blocks registration, not the family's K budget.

## 2026-08-05 Handoff re-advertised completed work as pending

Trigger: a session-start status read produced three "next actions" that were
already done — the ADR-0017 H-014 fix-wave re-review (recorded clean inside
`tasks/2026-07-28-h014-live-execution-claude-review.md` itself, in a section
appended below the original verdict), the H-032/H-034 family reassignment
(ruled and written into `docs/HYPOTHESIS_LEDGER.md`), and the WS-A A6 / WS-B
B2-B5 audit items (landed, with `AI_HANDOFF.md` contradicting itself 80 lines
apart). Acting on them would have re-run two reviews and one ruling.
Wrong: recording an outcome only where the work happened (the review file, the
ledger) and leaving the request that spawned it standing in the handoff.
Right: closing a handoff item is part of the work, not a session-end chore.
When an outcome lands in a ledger or review file, strike the originating line
in `docs/AI_HANDOFF.md` in the same pass and cite where the evidence now lives.
Rule: every "next action" / "open decision" line names the artifact that will
close it; before acting on one, check that artifact first — a still-open line
is a claim about state, not evidence of it.
