# Context + Session Handoff: Deribit data research & Codex task plan — 2026-07-11

## Goal (one sentence)
Survey Deribit's public API, design ingestion that fits the existing external-
data architecture, propose strategy candidates using Deribit data + existing
OHLCV, and hand Codex a reviewed task list.

## Implementation summary
Claude session, docs-only. Four subagents (3 repo scouts + 1 web researcher)
gathered context; Claude wrote a research doc (API survey, design-space
expansion, ranked candidates) and a 5-task Codex plan; a fresh verifier agent
reviewed both against the repo (0 blockers, 2 minors: one fixed, one noted).
No code, strategy, risk, gate, or artifact change.

## Current state / diff scope
- Branch: `codex/pipeline-batch1-stage3` (unchanged; pre-existing uncommitted
  Turtle/pipeline edits from other sessions left untouched).
- Files added: `research/deribit_data_strategy_research.md`,
  `tasks/2026-07-11-deribit-data-ingestion-tasks.md`, this handoff.
- Files changed: `docs/CURRENT_STATE.md`, `docs/AI_HANDOFF.md`,
  `config/workstreams.yaml` (new "Deribit derivatives data" workstream).
- Files deleted: none.
- Works now: plan is complete and reviewed. Unfinished: everything D1–D5 (not
  started — blocked on user sign-off).

## Decisions made (and why)
- Extend the existing `external_observations` adapter pattern (Option A) —
  because `DeribitDVOLClient` + config + coverage UI + Stage-2 read path
  already exist; would change if a candidate needs per-trade/full-surface
  history (then new tables or Tardis import via ADR).
- Store options tape as hourly aggregates, not raw trades — row-volume sanity;
  aggregate definitions pre-registered in the task spec to kill researcher
  degrees of freedom.
- Start options-surface snapshots now (D3) — greeks/OI/IV history is not
  backfillable; the PIT clock only starts when collection starts.
- Top strategy candidate `F-VRP-TIMING` (DVOL − realized vol timing);
  `F-DERIBIT-OPTIONFLOW` second after D4 lands. No hypothesis minted yet.

## Business-rule change?
No. Data ingestion + display plan only. DOC_IMPACT_MATRIX has no clean row for
new external-data clients (verifier finding); task list instructs Codex to
check it and manifest conditionally — consider adding a matrix row later.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A (untouched; new doc is standalone).
- config/: `config/workstreams.yaml` only. ADR: none (no rule change yet).

## Experiments
- HYPOTHESIS_LEDGER: none (H-013 reserved as next free, not written).
- EXPERIMENT_REGISTRY: none (E-038 next free).

## Rules in play (preserve verbatim)
- "Never claim live/shadow/demo readiness"; no promotion claims made.
- Do-not-touch: strategies/signals/risk/portfolio/execution, config/risk.yaml,
  results/**, differential validation, existing migrations (schema used as-is).
- `observed_at` = market event time UTC (external-data invariant).

## Tests / checks run
- None applicable (docs-only; no code). Verifier agent re-read all cited repo
  paths/classes/config keys: confirmed accurate. Deribit live-API claims rest
  on the research agent's 2026-07-11 probes (not re-verifiable offline).

## Docs updated
docs/CURRENT_STATE.md, docs/AI_HANDOFF.md, config/workstreams.yaml. Note:
CURRENT_STATE.md was already >90 lines from prior sessions; only appended,
did not trim other sessions' uncommitted content.

## Known limitations / risks
- history.deribit.com rate limits undocumented; D4 runtime is a guess.
- 2-symbol breadth for F-VRP-TIMING makes the DSR/PSR 0.95 gate hard.
- D3 snapshots are Interactive-only under Task Scheduler (same gap as
  quant_liq_okx_ingest).

## Rollback plan
Delete the two new docs + this file; revert the three appended edits
(git diff shows them as isolated hunks).

## Approvals
Human approval NEEDED and not yet obtained: sign-off on
`tasks/2026-07-11-deribit-data-ingestion-tasks.md` before Codex starts.

## Context to load next
`research/deribit_data_strategy_research.md` → the task list → for Codex:
docs/DATA_FLOW.md external section, `src/okx_quant/data/external_clients/`,
`scripts/market_data/ingest_external.py`, `config/external_data.yaml`.

## Next action (single, concrete)
User reviews and signs off the D1–D5 task list; then dispatch Codex on D1.

## Questions for human review
- Approve D1–D5 scope? Approve starting D3 snapshot collection now?
- Is F-VRP-TIMING the right first Stage-1 spec once data lands?

## Human Learning Notes (required)
- Deribit's real asymmetry: DVOL/funding/trade tape are deep + free
  (history.deribit.com serves the full options tape, no auth), but the IV
  surface/greeks/OI have NO REST history — forward accumulation is the only
  way, so snapshot collection is urgent even before any strategy decision.
- The repo already had a Deribit foothold (daily DVOL) — extending beat
  designing anything new; the whole "architecture" is config + two adapters.
- Fresh-verifier review caught only wording-level issues, largely because the
  plan cited scout-verified paths instead of remembered ones — the
  scout-then-cite discipline is what made the plan land clean.
