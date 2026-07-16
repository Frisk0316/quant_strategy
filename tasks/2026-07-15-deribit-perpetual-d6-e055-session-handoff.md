---
status: current
type: handoff
owner: codex
created: 2026-07-15
last_reviewed: 2026-07-15
expires: none
superseded_by: null
---

# Session Handoff: Deribit perpetual D6 and H-021 E-055 - 2026-07-15

## Implementation summary

Added the minimal credential-free Deribit public client and wired it into the
existing market-data CLI for native BTC/ETH perpetual 1m candles. Completed the
historical backfill and a forward top-up, verified continuous venue provenance
and public-API parity, then emitted E-055 with the exact frozen H-021 Stage-2
window, grid, thresholds, and costs. Gate 1 now passes, but the robust cost gate
still fails, so the run stopped before every Stage-3/PnL surface.

## Diff scope

- Files added: `src/okx_quant/data/exchange_clients/deribit_public.py`,
  `tests/unit/test_deribit_public_client.py`, and the two D6/E-055 handoffs.
- Files changed: `scripts/market_data/ingest.py`, `docs/DATA_FLOW.md`,
  `docs/RUNBOOK.md`, `docs/FEATURE_MAP.md`, `docs/HYPOTHESIS_LEDGER.md`,
  `docs/EXPERIMENT_REGISTRY.md`, `docs/AI_HANDOFF.md`,
  `docs/CURRENT_STATE.md`, `docs/CHANGELOG_AI.md`, and
  `config/workstreams.yaml`.
- Files deleted: none.

## Business-rule change?

- No. Existing provenance and Stage-2 rules were applied without changing a
  formula, threshold, gate, or policy. `DOC_IMPACT_MATRIX` was checked; A11
  feature/navigation docs and the experiment/current-state records were
  updated. No Change Manifest or ADR is required for D6/E-055.

## Source-of-truth updates

- research/strategy_synthesis.md: N/A; forbidden and untouched.
- config/: `config/workstreams.yaml` current-state text only; no runtime or gate
  value changed.
- ADR: N/A; no accounting or major rule decision was made.

## Experiments

- HYPOTHESIS_LEDGER entries: H-021 linked to E-055; family trials remain 8 and
  K remains 0/2.
- EXPERIMENT_REGISTRY entries: E-055, a 0-trial data reprobe with frozen gates.

## Tests / checks run

- `pytest tests/unit/test_deribit_public_client.py tests/unit/test_market_ingest.py tests/unit/test_xvenue_funding_spread_probe.py tests/unit/test_pipeline_stage2_registry.py -q -p no:cacheprovider` - PASS (21 tests).
- `ruff check src/ tests/ backtesting/ scripts/` - PASS.
- `scripts/docs/check_doc_metadata.py`, `check_feature_map_links.py`, and
  `check_ledger_consistency.py` - PASS (0 metadata warnings, 229 paths, 22
  hypotheses / 56 experiments / 21 K-budget families).
- `scripts/docs/check_doc_impact.py --strict` - PASS on all 14 changed files;
  `scripts/validate_pipeline.py --check-config-only` - PASS.
- `scripts/smoke/backtest_smoke.py` - PASS; its idealized fixture is explicitly
  not promotion evidence. `git diff --check` - PASS.
- Database coverage query - PASS: 1,333,925 rows per instrument through
  2026-07-15 08:04Z, 0 missing minutes, 0 null OHLC, 0 suspect, exact Deribit
  provenance.
- Six fixed public API/DB OHLC spot checks - PASS with exact equality.

## Docs updated

- `docs/DATA_FLOW.md`, `docs/RUNBOOK.md`, `docs/FEATURE_MAP.md`, both ledgers,
  current-state/handoff surfaces, AI changelog, workstream state, and these two
  standard handoffs.

## Known limitations / risks

- The legacy instrument and raw-candle enums do not name Deribit; this bounded
  path uses legacy `exchange='other'` registration and writes canonical candles
  directly while preserving exact `source_primary='deribit'` provenance.
- E-055 is not full price/basis or inverse-collateral PnL evidence. Stage 2
  remains failed on the robust cost gate and is not promotion evidence.

## Rollback plan

- Revert only the bounded files listed above. If database rollback is required,
  delete only `canonical_candles`/`instrument_bars` rows and checkpoint/job
  records for native `BTC-PERPETUAL` and `ETH-PERPETUAL` with
  `source_primary='deribit'`; do not alter Binance or existing artifacts.

## Context Handoff

- See `tasks/2026-07-15-deribit-perpetual-d6-e055-context-handoff.md`.

## Questions for human review

- None for D6 acceptance. Any future inverse-perpetual accounting/Stage-3 work
  needs an explicit user decision after Claude's review.

## Next recommended task

- Claude reviews D6, the E-055 artifact/hash, frozen-gate equivalence, and the
  no-Stage-3 stop. Do not schedule another H-021 run from this handoff.

## Human Learning Notes (required)

The public chart endpoint's effective response bound makes explicit 5,000-bar
windows safer for deterministic forward checkpoints. Native IDs are required
to preserve venue identity under the canonical key. Most importantly, filling
the data gap did not change the frozen cost conclusion: Gate 1 PASS plus cost
FAIL means stop, not retune and not an implicit Stage-3 licence.
