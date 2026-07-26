---
status: current
type: manifest
owner: codex
created: 2026-07-24
last_reviewed: 2026-07-26
expires: none
superseded_by: null
---

# Change Manifest: Consumer-Time Universe Aliases

## Summary

Define the Binance same-economic-asset alias
`SHIB-USDT-SWAP -> 1000SHIB-USDT-SWAP` as a pure, order-preserving
consumer-time collapse without modifying point-in-time membership history.
After T1 passed, E-059 became the first opted-in consumer.

## Business rule(s) affected

R6.7 data provenance and universe identity.

## Trigger area(s) (DOC_IMPACT_MATRIX)

A5 backtesting; this is an input-identity rule, not a result-schema or
promotion-gate change.

## Files changed

- `backtesting/universe_aliases.py` — exchange-scoped alias table and pure
  order-preserving collapse helper.
- `tests/unit/test_universe_aliases.py` — alias, unrelated-symbol, and byte
  immutability regression.
- `docs/ADR/0015-consumer-time-economic-asset-aliases.md` and
  `docs/ADR/README.md` — durable consumer-time identity decision.
- `docs/DOMAIN_RULES.md`, `docs/INVARIANTS.md`, `docs/FAILURE_MODES.md` —
  R6.7/I50/F53.
- `docs/FEATURE_MAP.md`, `docs/DATA_FLOW.md`, `docs/KNOWN_ISSUES.md` —
  ownership, staged flow, and broader-consumer follow-up.

## Behavior delta

- Before: no repository-owned rule or helper distinguished two selected venue
  symbols representing the same economic asset.
- After: the E-059 Binance consumer maps SHIB to the tradable 1000SHIB
  contract and deduplicates after PIT top-N selection without refilling rank
  N+1. Broader universe consumers remain unchanged.
- Money/risk impact: none. A future opted-in research consumer recomputes its
  effective member-day denominator; no PnL, fee, funding, sizing, fill, or gate
  changes.

## Source-of-truth updates

- research/strategy_synthesis.md: N/A — no strategy assumption changed.
- config/: N/A — the single exchange alias is a code constant; risk and runtime
  config are unchanged.
- ADR: ADR-0015 added because this changes data-provenance identity handling.

## Docs updated (from DOC_IMPACT_MATRIX row)

- [x] `docs/DOMAIN_RULES.md` — R6.7 added.
- [x] `docs/DATA_FLOW.md` — staged consumer-time flow recorded.
- [x] `docs/FEATURE_MAP.md` — helper ownership and immutable-artifact boundary.
- [x] `docs/INVARIANTS.md` — I50 added.
- [x] `docs/FAILURE_MODES.md` — F53 added.
- [x] `docs/KNOWN_ISSUES.md` — broader consumer adoption remains open.
- [x] `docs/GOLDEN_CASES.md` — reviewed; no trading/accounting golden case
  changes.
- [x] ADR-0002/0005 — reviewed; no result schema or validation gate changes.

## Invariants / golden cases

- Invariants checked: I20 remains unchanged; I50 covers alias collapse and
  membership-byte immutability.
- Golden cases affected: none.

## Tests / checks run

- `python -m pytest tests/unit/test_universe_aliases.py -q` — 1 passed.
- `python -m ruff check backtesting/universe_aliases.py tests/unit/test_universe_aliases.py`
  — passed.
- `python -m pytest tests/unit/ -q --tb=short -p no:cacheprovider` — 955
  passed, 1 skipped.
- `python -m ruff check src/ tests/ backtesting/ scripts/` — passed.
- Documentation metadata, feature-map links, ledger consistency, and
  `check_doc_impact.py --strict` — passed.
- Config validation, backtest smoke, and `git diff --check` — passed; the smoke
  is explicitly idealized-fill and not promotion evidence.
- Production membership SHA-256 before/after:
  `9822810321262e76a65bccf18a519ac2f61f05f986bd13b730c0cb3d9e1657c5`.
- Immutable E-058 artifact SHA-256 before/after:
  `a61f58c0c2ea8b539b6cb0896abde6cd50e1154a7bbd59794db11f3b7a275a10`.
- E-059 targeted probe/alias/registry tests — 29 passed; E-059 data
  availability passes at 24,745/24,745 alias-adjusted member-days.

## Risks and rollback

- Risks: consumers other than E-059 can still double-count the alias.
- Rollback: revert the independent T2 commit; the membership parquet and E-058
  artifact require no rollback because neither is modified.

## Approval

- Human approval required: yes — obtained in the 2026-07-24 E-058 repair /
  E-059 task; T1 passed before E-059 wiring/execution.
