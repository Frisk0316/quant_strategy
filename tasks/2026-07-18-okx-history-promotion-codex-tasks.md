---
status: archived
type: task
owner: claude
created: 2026-07-18
last_reviewed: 2026-08-06
expires: 2026-10-18
superseded_by: null
---

# Codex Task: Promote 2020-2023 OKX raw history into venue canonical layer

User-authorized 2026-07-18 (recorded in
`tasks/2026-07-17-abc-delivery-claude-review.md`). Extends the ADR-0014
source-aware promotion (commit `4aadf4f`, Claude-reviewed APPROVE) from the
frozen window back to the start of raw OKX coverage. This is the prerequisite
for the H-010 Stage-1 spec's long-window power budget (min detectable Sharpe
1.06@breadth1 vs 1.72 on the short window).

## Filled Implementation template

```text
Task: Widen the OKX BTC/ETH 1m venue-canonical promotion to cover
2020-01-01 -> 2024-01-01 (end exclusive), completing continuous coverage
2020-01-01 -> 2026-06-17 in venue_canonical_candles.

Strategy/spec source: docs/ADR/0014-source-aware-canonical-candles.md;
  scripts/promote_okx_canonical_1m.py; change manifest
  docs/change_manifests/2026-07-17-source-aware-canonical-candles.md.

Required behavior:
- Parameterize the promotion script with explicit --start/--end (ISO dates,
  end exclusive), defaults unchanged (current frozen window) so the prior
  invocation stays reproducible. Symbols/bar/source stay hardcoded.
- Run the promotion for 2020-01-01 -> 2024-01-01. Expected upsert scale:
  raw market_klines OKX rows in that window (~2.1M/leg); report the exact
  before/after counts.
- Re-run idempotence check: second identical run changes 0 rows.
- Extend scripts/verify_okx_1m_backfill.py (or its invocation) to verify the
  FULL promoted range 2020-01-01 -> 2026-06-17: venue rows == raw rows for
  the window, mismatch 0. Raw gaps, if any, are reported as gaps — never
  filled from Binance (I19).
- Resolved canonical_candles must be untouched: row counts by source_primary
  identical before/after (paste both).

PERMITTED FILES (only edit these):
- scripts/promote_okx_canonical_1m.py       (add --start/--end)
- scripts/verify_okx_1m_backfill.py         (full-range verification mode)
- tests/unit/test_venue_canonical_promotion.py (extend)
- docs/RUNBOOK.md                            (record the wide-window commands)
- docs/change_manifests/2026-07-17-source-aware-canonical-candles.md
  (append the executed wide-window result — same manifest, same rule change)

FORBIDDEN (do not touch):
- canonical_candles resolved table contents; any DELETE/UPDATE of existing rows
- src/okx_quant/** except none needed; migrations (schema is already in place)
- research/, ledgers, existing results/**, config/risk.yaml
- Cross-venue substitution of any kind (I19)

SCOPE LIMIT: window widening + verification only. No new schema, no new
consumers, no H-010 research work of any kind.

ACCEPTANCE CRITERIA (binary):
- [ ] Promotion runs for 2020-01-01->2024-01-01; venue rows == raw rows 1:1
      for that window per symbol (exact counts pasted).
- [ ] Second run changes 0 rows (output pasted).
- [ ] Full-range verify passes 2020-01-01->2026-06-17 with mismatch 0;
      any raw gaps listed explicitly, not filled.
- [ ] canonical_candles per-source counts identical before/after (pasted).
- [ ] Default (no-flag) script invocation behavior unchanged; test covers the
      new flags; pytest tail pasted.
- [ ] Diff contains only permitted files.

REPORT: changed files, test tail, per-window row counts, raw gap list,
before/after resolved-table counts, anything UNCONFIRMED.
```

## Reviewer notes (Claude)

- Raw OKX coverage starts 2020-01-01 but early months may have listing-era
  gaps; report them honestly — the H-010 spec's n_obs budget already
  discounts warmup. Gaps are facts, not failures.
- Fresh-verifier check per docs/ai/MODEL_DISPATCH.md after delivery.
