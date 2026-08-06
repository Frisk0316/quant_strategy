---
status: current
type: task
owner: codex
created: 2026-08-06
last_reviewed: 2026-08-06
expires: none
superseded_by: null
---

# Codex task: extend the OKX source-aware canonical 1m window back to 2020

Read AGENTS.md first, then execute. Also read docs/ai/JUDGMENT_RUBRICS.md §2
(definition of done) and §5 (quality floor) before reporting completion.

Task: extend the ADR-0014 source-aware OKX BTC/ETH canonical 1m promotion from
its current 2024-01-01 start back to the beginning of the raw OKX history in
`market_klines` (~2020), additively and idempotently, without touching the
Binance-primary canonical layer or any existing result artifact.

Strategy/spec source: `docs/ADR/0014-*.md` (existing promotion policy — this is
a window extension under the same mechanism, not a new policy);
`tasks/2026-08-06-data-inventory.md` (why: the ~898-day crypto overlap is the
binding constraint on every Stage-2 power floor).
Authorization: user, 2026-08-06 — "最高槓桿的一個決策：OKX 2020+ raw 1m →
canonical 升級 這部分也請授權".

Required behavior:

1. Measure first, promote second. Before any write, report per symbol
   (BTC-USDT/ETH-USDT or the raw OKX inst_ids actually present): raw first_ts,
   last_ts, row count, and a gap profile for the pre-2024 window (count and
   largest run of missing minutes). Do NOT assume 2020+ coverage is complete —
   the promotion must record honest coverage, never fabricate missing bars.
2. Reuse the existing promotion path (`scripts/promote_okx_canonical_1m.py`
   and its verifier `scripts/verify_okx_1m_backfill.py`); prefer widening its
   window via CLI/config over new code. Promotion stays additive and
   source-aware exactly as in the 2026-07-17 run.
3. Idempotency: a second identical run changes 0 rows.
4. ADR-0014 gains a dated amendment note recording the window extension (no
   policy change); flag it for Claude/user review in the report.

PERMITTED FILES (only edit these):
- `scripts/promote_okx_canonical_1m.py`, `scripts/verify_okx_1m_backfill.py`
  (only if the window cannot be passed via existing CLI/config)
- their unit tests under `tests/`
- `docs/ADR/0014-*.md` (amendment note), `docs/DATA_FLOW.md`,
  `docs/RUNBOOK.md` (command example), `docs/CHANGELOG_AI.md`
- `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `config/workstreams.yaml`
  (state mirror), plus the session-end handoff file

FORBIDDEN (do not touch):
- src/okx_quant/strategies/ signals/ risk/ portfolio/ execution/
- config/risk.yaml
- `results/**` (all existing artifacts, including E-057)
- `research/**`
- canonical Binance rows (any write path other than the additive OKX
  source-aware layer)
- funding data of any venue: absent pre-2024 OKX funding stays absent — no
  proxy, no substitution (I48 stays fail-closed; H-010 stays shelved)

SCOPE LIMIT: promotion of existing raw OKX 1m candles only; no ingestion of
new external data, no experiment, no re-run of any H/E, no adjacent refactor.

REQUIRED ON COMPLETION:
- List changed files (git diff --stat).
- Run: the promotion verifier plus targeted pytest for touched modules and
  paste output tails.
- Update docs per the AGENTS.md docs-update matrix (or state "n/a: why").
- Standard AGENTS.md completion report, including the honest coverage numbers.

ACCEPTANCE CRITERIA (binary):
- [ ] Pre-write measurement report exists with per-symbol raw first/last/count
      and pre-2024 gap profile.
- [ ] Promotion verifier PASSes: raw↔canonical parity mismatches 0 for the
      extended window; coverage/alignment reported as measured, not assumed.
- [ ] Second identical run changes 0 rows (output pasted).
- [ ] Canonical Binance row counts are unchanged before vs after (query
      output pasted).
- [ ] No file under `results/**` or `research/**` changed (git status pasted).
- [ ] ADR-0014 amendment note added and flagged for review.
- [ ] Diff contains only permitted files.

REPORT ALSO: what this does and does not unlock — it extends the BTC/ETH
research overlap only (≈898 → up to ~2,350 days, subject to measured gaps);
the 30-symbol cross-section remains 2024+; H-010 remains shelved because
pre-2024 OKX funding does not exist. New power floors are recomputed from the
measured post-promotion overlap, not from the theoretical maximum.
