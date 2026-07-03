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

Both tracked streams are complete and committed as of 2026-07-04. Full
narrative history moved to `docs/CHANGELOG_AI.md` (see "2026-07-03 - M2-R1
Reviewed, Accepted, And Committed" and "2026-07-03/04 - Pipeline P1-P9 Full
Cycle + First Stage-1 Spec From Taxonomy").

**Repo maintenance (M1-M5 + M2-R1):** all committed (`df96682`, `79c1ddc`,
`0191c1d`, `2dea608`, `5eb71f8`, `21cc3c9`). Claude-reviewed and accepted on
independent re-verification. No outstanding action.

**Strategy research pipeline (P1-P9):** all committed (`dfc7af8`, `6997aba`,
`14976d4`, and the in-progress P9 + Stage-1 spec commit). Result:
`F-FUNDING-XS-DISPERSION` (`H-009`) is the first taxonomy-sourced candidate
to clear Stage-2 `data_availability` (E-030: 32 eligible symbols, 28 good,
breadth min 24/median 27 vs threshold 10). `stage2_status` stays FAIL —
`distinctness` (vs `F-FUNDING-CARRY`) and `cost_after_edge` have not run.
Stage-1 spec with the full mechanism-distinctness argument:
`docs/superpowers/specs/2026-07-04-f-funding-xs-dispersion-hypothesis.md`.

**Next action (Codex):** run the family-minting distinctness checker for
`F-FUNDING-XS-DISPERSION` vs the `F-FUNDING-CARRY` reference signal first;
then implement Stage 3 by reusing `xs_momentum_backtest.py`'s PIT-universe
loader, corrected vol-targeting, and leak-fixed daily-shift as the skeleton
(swap the ranking signal to trailing funding APR); pre-registered grid = 4
combos (`L in [7,14] days, Q in [0.20,0.30]`); stop at checkpoint (1); no
adapter/promotion/demo/shadow/live claim without Claude/user review of the
Stage-3 evidence.

**Known pending items (not blocking, tracked in KNOWN_ISSUES/RUNBOOK):**
liquidation ingest (`quant_liq_okx_ingest`) is Interactive-only (runs only
while logged in) — an unattended/service mode is a separate decision if
needed; the 4 point-in-time-eligible symbols with zero funding history
(`CC`/`FIL`/`M`/`SHIB`-USDT-SWAP) can be backfilled the same way as the
other 28 if a later grid needs them.

## Current Branch

- Branch: `codex/pipeline-batch1-stage3`.
- Recent commits: `df96682` (M1), `79c1ddc` (7/3 handoff preservation),
  `0191c1d` (M2), `2dea608` (M3), `5eb71f8` (M4/M5), `21cc3c9` (M2-R1),
  `dfc7af8`/`6997aba`/`14976d4` (pipeline P1-P8 + real-data runs + warmup
  window), plus an in-progress commit for P9 + the F-FUNDING-XS-DISPERSION
  Stage-1 spec.
- Working tree is otherwise clean.

## Do Not Touch

Without explicit user approval, do not modify:

- `research/` except explicit user-approved research tasks.
- `results/**` existing artifacts.
- `src/okx_quant/strategies/`, `src/okx_quant/signals/`.
- `src/okx_quant/risk/`, `src/okx_quant/portfolio/`,
  `src/okx_quant/execution/`.
- `config/risk.yaml`, deployment/shadow/demo/live gates, or strategy assumptions.
- Differential-validation implementation unless a current task explicitly lists it.

## Verification Notes

M1-M5 + M2-R1 verification evidence (test counts, docs-check output, smoke
reproduction) moved to `docs/CHANGELOG_AI.md` — that stream is closed. P1-P9
verification evidence (test counts, real-run row counts, doc-impact checks)
is likewise in `docs/CHANGELOG_AI.md`.

`make` remains unavailable in this Windows sandbox; use the equivalent
Python commands (`python scripts/docs/check_doc_metadata.py`,
`python scripts/docs/check_feature_map_links.py`,
`python scripts/docs/check_doc_impact.py --strict`) or `pytest` directly.
Full `make verify` / `make verify-full` still needs an environment with
`make`, TimescaleDB, and required data.

## Next Steps

1. Codex: run the family-minting distinctness checker for
   `F-FUNDING-XS-DISPERSION` vs `F-FUNDING-CARRY`, then implement Stage 3
   per the hand-off in
   `docs/superpowers/specs/2026-07-04-f-funding-xs-dispersion-hypothesis.md`.
2. If a later grid needs the 4 not-yet-backfilled symbols
   (`CC`/`FIL`/`M`/`SHIB`-USDT-SWAP), rerun
   `scripts/market_data/backfill_universe_funding.py` for them.
3. Decide whether the `quant_liq_okx_ingest` Windows task needs an
   unattended/service mode (currently Interactive-only).

## Open Questions

- None currently open.
