---
status: current
type: task
owner: claude
created: 2026-07-24
last_reviewed: 2026-07-24
expires: 2026-10-24
superseded_by: null
---

# Codex Task: E-058 data repair (ETH raw + SHIB identity) then E-059 reprobe

User-authorized 2026-07-24 (recorded in
`tasks/2026-07-24-e058-claude-review.md`). Three sequential sub-tasks; each
gets its own commit. The reprobe is the DATA-GAP-REPAIR path (E-055→D6
precedent): same frozen contract, K unchanged, new experiment record.

## T1 — ETH raw 1m backfill (repair, not new data)

```text
Task: Restore Binance ETHUSDT perp 1m raw rows (with 12-slot raw_payload.raw
arrays) in market_klines for 2024-01-01 -> 2026-06-17.

Method: the EXISTING REST ingestion path (scripts/market_data/ingest.py,
--exchange binance --dataset klines_1m), which is exactly how the other 28
symbols' raw rows were written — no new ingestion code. If the sandbox
blocks network (known WinError 10013 precedent), output the exact command
for the user to run locally and STOP T1 as NEEDS-HUMAN; do not fabricate.

Verify after ingestion (read-only): per-year parseable taker coverage for
ETH-USDT-SWAP == expected member days (reuse the E-058 probe's coverage
query shape); paste counts. Existing rows for other symbols must be
untouched (row counts by symbol before/after pasted).
```

## T2 — SHIB/1000SHIB identity rule (universe integrity)

```text
Task: Resolve the same-asset double-membership without rewriting PIT history.

Rule (Claude-specified, implement exactly): the membership parquet is
IMMUTABLE. Add a documented same-asset alias map (SHIB-USDT-SWAP ->
1000SHIB-USDT-SWAP for exchange=binance) applied at universe-CONSUMPTION
time: consumers collapse aliases to the canonical contract, keeping ONE
member (the tradable one) per economic asset per day. Effective member-day
denominators change accordingly and must be recomputed, not patched.

Scope: a small module/function + the alias table in config or code constant
(NOT config/risk.yaml), consumed by the E-059 probe; a unit test proving
(a) SHIB days collapse into 1000SHIB, (b) no other symbol is affected,
(c) membership parquet bytes unchanged. Document the rule in
docs/DOMAIN_RULES.md (data-provenance section) + the Change Manifest.
Broader adoption by other universe consumers (backtests etc.) is NOT in
scope — record it in docs/KNOWN_ISSUES.md as a follow-up.
```

## T3 — E-059 reprobe (only after T1 verify passes)

```text
Task: Re-run the SAME frozen F-TAKER-FLOW Stage-2 contract as E-059.

Order (registration-before-run, as E-058):
- Commit #1: register E-059 in EXPERIMENT_REGISTRY ex-ante — same frozen
  params/window/thresholds as E-058, reason "data-gap repair reprobe
  (ETH raw restored, SHIB alias rule T2)", K unchanged 0/2, n_trials still
  reserved-not-consumed 4; declare the alias-adjusted universe denominator
  and re-declare R6.6 reference ranges.
- Commit #2: run the probe (reuse backtesting/taker_flow_probe.py; the ONLY
  permitted code change is consuming the T2 alias map); write
  results/e059_taker_flow_stage2_<date>/stage2_feasibility.json + SHA-256.
- Commit #3: outcome sync (ledger/registry/state). If all four checks PASS,
  set H-022 `testing` and STOP — Stage-3 needs separate user authorization.
  Any FAIL: honest reason, no retune, no third probe without new authorization.

FORBIDDEN across all three: touching E-058 artifacts or any existing
results/**, membership parquet mutation, trading core, config/risk.yaml,
Stage-3/grid/DSR work, signal-formula or threshold changes.

ACCEPTANCE (binary): T1 coverage == expected for ETH (pasted); T2 tests
green + parquet byte-identical (hash pasted); E-059 registration precedes
run in git; full unit suite + Ruff + ledger consistency + docs-impact
--strict PASS; artifact hash recorded; diff only in permitted files.

REPORT: per-sub-task status, ETH before/after counts, E-059 four-check
numbers vs E-058, test tails, anything UNCONFIRMED. 完成後交 Claude 審。
```
