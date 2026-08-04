---
status: current
type: manifest
owner: codex
created: 2026-08-02
last_reviewed: 2026-08-02
expires: none
superseded_by: null
---

# Change Manifest: paper-data limited probe

## Summary

Add the minimum adapters and deterministic research runner needed to ingest
paper-motivated public data and execute a seven-candidate limited probe. The
round is explicitly incomplete under ADR-0016 and cannot promote a strategy.
The post-run ADR-0013 audit invalidated three mechanically reported Stage-2
power passes; all seven governance-effective outcomes stop at Stage 2.

## Business rule(s) affected

- R3.1-R3.4 funding sign, settlement aggregation, and venue provenance.
- R5.3 and R6.1 closed-information and execution lag.
- R6.2 and R6.4 external-data provenance and quality.
- R6.3, R6.8, R6.9, and R7.4 power, honest trial counts, round labeling, and
  deterministic evidence.
- No global fee, funding, sizing, threshold, demo, shadow, promotion, or live
  policy is changed.

## Trigger area(s) (DOC_IMPACT_MATRIX)

- A5 backtesting workflow.
- External-data ingestion/config path reviewed under the data-flow matrix.

## Files changed

- `config/external_data.yaml` — register Wikimedia and Coin Metrics research datasets.
- `src/okx_quant/data/external_clients/` — minimal public-source adapters.
- `scripts/market_data/ingest_external.py` — dispatch the registered adapters.
- `backtesting/paper_signal_probe.py` — frozen signal/PnL/Stage-2 logic.
- `scripts/run_paper_signal_limited_probe.py` — hash-bound, fail-closed execution and artifacts.
- `src/okx_quant/data/external_clients/binance_oi.py`, `src/okx_quant/data/external_store.py` — deduplicate repeated boundary keys before durable write/accounting.
- `tests/unit/` — source parsing, publication lag, funding/cost, salience, and stop-rule checks.
- `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md` — H-040 through H-046 and E-077 onward.
- `docs/INVARIANTS.md`, `docs/FAILURE_MODES.md` — publication-time macro guard discovered during locate-before-edit.
- New spec, receipt, immutable results, governance audit, portable report, and session handoffs for this run.

## Behavior delta

- Before: no integrated Wikimedia/Coin Metrics daily research data and no
  deterministic paper-signal limited-probe runner.
- After: selected public series can be idempotently stored in
  `external_observations`; seven frozen candidates receive terminal Stage-2
  artifacts. The repaired runner requires an explicit, finite, positive
  independently justified `power_breadth` before receipt/database access and
  never infers it from active trading legs.
- Immutable-run distinction: H-041/H-045/H-046 physically generated Stage 3,
  but the ADR-0013 breadth audit makes those artifacts diagnostic-only and
  governance-inadmissible. Their observed family trials remain counted.
- Money/risk impact: research PnL now charges Binance funding settlement sums
  and 4 bps per one-way turnover. Runtime/live behavior is unchanged.

## Source-of-truth updates

- `research/strategy_synthesis.md`: N/A — Claude-owned and not modified.
- `config/`: external dataset registry only; no runtime strategy enablement.
- ADR: N/A — ADR-0013 and ADR-0016 are enforced without changing policy.

## Docs updated (from DOC_IMPACT_MATRIX row)

- [x] `docs/DOMAIN_RULES.md` — reviewed; existing R3/R5/R6/R7 rules are unchanged.
- [x] `docs/INVARIANTS.md` — I62 publication/t+1/bounded fill, I63 batch-key dedupe, I64 explicit pre-DB power breadth.
- [x] `docs/FAILURE_MODES.md` — F65 macro join/coverage, F66 boundary duplicates, F67 active-leg breadth inference.
- [x] `docs/GOLDEN_CASES.md` — reviewed; no engine/live accounting golden case changes.
- [x] `docs/DATA_FLOW.md` — reviewed; dirty in another session, so this run records the new path in its spec/report/handoff instead of overwriting it.
- [x] `docs/FEATURE_MAP.md` — reviewed; no supported user-facing/runtime feature changes.

## Invariants / golden cases

- Invariants checked: I4, I23, I42, I52, I53, I54, I58, I59, I62, I63, I64.
- Golden cases affected: none; this is research-only.

## Tests / checks run

- `python -m pytest tests/unit/test_paper_signal_probe.py tests/unit/test_public_research_clients.py tests/unit/test_external_clients.py tests/unit/test_external_store.py -q -p no:cacheprovider` — 24 passed.
- Targeted `python -m ruff check ...` over changed Python/tests — passed.
- `python scripts/validate_pipeline.py --check-config-only` — passed.
- Docs metadata/feature-map/ledger/impact checks — passed; metadata emitted two pre-existing warnings.
- `python scripts/smoke/backtest_smoke.py` — passed; idealized fixture is not promotion evidence.
- Portable report verifier — passed 21 blocks, 2 charts, 5 tables, 3 metrics at 1440/390 with source interaction.

## Risks and rollback

- Risks: alternative-data publication timing, noncommercial source licenses,
  small/sparse event samples, limited futures-universe breadth, and research
  proxies or governance-invalid diagnostic Stage 3 being misread as deployable evidence.
- Rollback: revert only the files listed above. DB rows use new isolated dataset
  IDs and do not overwrite other series; deletion is not part of this task and
  would require explicit user approval.

## Approval

- Human approval required: yes for this research experiment; obtained through
  the user's 2026-08-02 request. No deployment approval was requested or obtained.
