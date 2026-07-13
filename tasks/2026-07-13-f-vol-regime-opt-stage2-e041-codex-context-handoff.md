---
status: current
type: handoff
owner: codex
created: 2026-07-13
last_reviewed: 2026-07-13
expires: none
superseded_by: null
---

# Context Handoff: F-VOL-REGIME-OPT Stage 2 / E-041 — 2026-07-13

## Goal (one sentence)

Complete the user-authorized bounded E-041 rerun without changing E-040's
sample, pricing legs, threshold, artifacts, or Stage-3 boundary.

## Current state

- Branch: `codex/pipeline-batch1-stage3`; HEAD at session start: `d046978`.
- In-progress edits: none. E-041 code, artifact, ledgers, maps, state records,
  and handoffs are written and checked.
- E-040/T2: Claude accepted the fail-closed calibration and completed vendor
  report in `tasks/2026-07-13-e040-stage2-claude-review.md`.
- E-041: `probe_status=FAIL_CLOSED`, 0 processed pairs, 0 trials, no K, and no
  pricing verdict. The fixed sample starts 2022-04-01, but DB hourly DVOL starts
  2024-01-01, so the run stopped before any Tardis download.
- Stage 2 has not passed. Stage 3 remains unauthorized and blocked.

## Decisions made (and why)

- Reused `f_vol_regime_opt_stage2.py` rather than duplicating the probe — the
  three authorized deltas are small and E-040 artifacts remain immutable in
  their separate output directory.
- Kept exactly three behavior deltas from E-040: `Content-Length` pre-check to
  compressed bytes-read guard at 2 GiB; daily to hourly DVOL published as-of
  08:00 UTC with no fallback; split probe/pricing statuses.
- Preserved the 0-pair fail-closed record — changing the sample or using daily
  DVOL would violate the approved rerun rather than repair it.

## Open questions / unverified assumptions

- Whether the human wants a separately authorized pre-2024 hourly-DVOL backfill
  is open. No backfill, sample change, or retry is authorized now.

## Rules in play (preserve verbatim)

- I13 / R6.3: trial count is recorded; no hidden trials in selection. E-041 has
  0 trials and no K use; its serialized sampling exactly equals E-040.
- I8 / R5.3 and R6.1: only data published by the decision timestamp may enter
  pricing. Hourly DVOL query requires `published_at <= 08:00 UTC` and fails
  closed without a row; no daily fallback exists.
- I15 / R7.2: no live/shadow/demo claim without all gates passed + human approval.
- Do-not-touch: E-039/E-040 artifacts; `research/*.md`; strategy, signal, risk,
  portfolio, execution, backtesting engine, config gates, differential
  validation, and Stage 3.

## Context to load next (the reading list)

- Source of truth: `tasks/2026-07-13-f-vol-regime-opt-stage2-codex-tasks.md`,
  `tasks/2026-07-13-e040-stage2-claude-review.md`, and
  `results/stage2_probe_20260713_f_vol_regime_opt_r1/stage2_feasibility.json`.
- Owning files: `research/probes/f_vol_regime_opt_stage2.py`,
  `tests/unit/test_f_vol_regime_opt_stage2.py`, `docs/FEATURE_MAP.md`, and
  `docs/DATA_FLOW.md`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md` (no dedicated
  F-VOL context pack exists).

## Checks run

- `...Python312\python.exe research\probes\f_vol_regime_opt_stage2.py` —
  expected fail-closed artifact; exact command/error recorded in JSON.
- Target pytest — `3 passed`; Ruff on probe/test — passed.
- Docs metadata — passed, 0 warnings; feature-map links — passed, 214 paths;
  ledger consistency — passed, 15 H / 41 E / 14 K families.
- Docs impact — passed, 18 changed files, no matrix violations; config check —
  both checks passed; Progress route regressions — `9 passed`.
- Artifact QA — sampling exactly equals E-040; `probe_status=FAIL_CLOSED`;
  `verdict.evaluated=false`; `verdict.status` absent; 0 pairs/downloads/trials/K;
  exactly 3 declared behavior deltas.
- E-040 SHA-256 remained
  `093C26C5...A115` (JSON), `C80AD54D...501B` (CSV), and
  `C91F6E07...0076` (vendor report).

## Approvals

- Obtained: T1/T2 and the bounded T1-R/E-041 rerun with exactly three deltas.
- Not obtained: pre-2024 hourly-DVOL backfill, further retry, purchase, Stage 3,
  options engine/adapter/accounting, or promotion/deployment work.

## Next action (single, concrete)

- Claude reviews E-041's diff and fail-closed artifact; the human then decides
  whether to authorize a separately scoped pre-2024 hourly-DVOL backfill.

## Human Learning Notes

The prior handoff's phrase “history is present through 2026-07-10” hid a
start-date constraint: hourly DVOL has 22,128 rows per symbol but starts only in
2024, while daily DVOL was backfilled to 2021. Coverage claims need both bounds,
not just the latest timestamp and row count.
