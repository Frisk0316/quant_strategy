# Codex Task A — Spot canonical candles for the basis family (S7 gating)

Pipeline: Strategy Research Pipeline batch 1, candidate **S7**.
Spec source: `docs/superpowers/specs/2026-06-25-s7-basis-meanrev-hypothesis.md`
Blocks: S7 Stage 3 only (S5/S6 do not need spot data — see Task B).

## Task

Confirm whether the canonical DB has **spot** candles for `BTC-USDT` and
`ETH-USDT` (Binance, `source_primary='binance'`), 1m base, over the S7 window
(2024-01-01 .. latest common end used by xs_momentum, ~2026-06). If absent or
partial, load them, mirroring the existing Binance ingest path.

## Why

S7 computes `basis = perp_mark / spot - 1`. Perp 1m + funding already exist in
canonical DB; **spot canonical is unconfirmed** (project has been perp-only;
on-disk parquet is only a ~1-month tick mirror). Without spot canonical, the whole
basis family is data-blocked.

## Required behavior

1. **Probe** `canonical_candles` for spot `BTC-USDT`, `ETH-USDT` with
   `source_primary='binance'` over the window; report coverage % and gaps.
2. **Locate-before-edit:** confirm whether `scripts/download_binance_data.py`
   already supports spot (non-`-SWAP`) symbols. If not, extend it minimally to
   fetch Binance spot klines; do not refactor unrelated code.
3. If missing/partial, **download → write parquet + canonical DB** via the existing
   `scripts/_db_writer.py` path (same as the prior Binance gap-fill).
4. **Verify parity:** local parquet vs DB canonical close mismatch count = 0 on a
   sampled day (same check used for the 2024-04-29 Binance 1H gap-fill).
5. Report final coverage; if data truly cannot be obtained, record an explicit
   "data unavailable" finding (S7 stays data-blocked) — do not fake/forward-fill.

## PERMITTED FILES (only edit these)
- `scripts/download_binance_data.py` (minimal spot support if missing)
- `scripts/_db_writer.py` (only if a spot write path is genuinely absent)
- `data/ticks/**` (generated parquet), canonical DB (via the writer)
- `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md` (coverage status on completion)

## FORBIDDEN (do not touch)
- `src/okx_quant/strategies/`, `signals/`, `risk/`, `portfolio/`, `execution/`
- `backtesting/cpcv.py`, `analytics/dsr.py` (n_trials/DSR semantics)
- `config/risk.yaml`, any demo/shadow/live/deployment gate
- existing result artifacts' values
- DB schema changes beyond what the existing writer already does

## SCOPE LIMIT
Only confirm/load spot canonical for BTC-USDT and ETH-USDT. No strategy code, no
backtest. Do not extend the universe beyond these two spot pairs.

## REQUIRED ON COMPLETION
- List changed files.
- Report: spot canonical coverage % for BTC-USDT / ETH-USDT over the window +
  sampled parity result.
- Update handoff/current-state with the spot-data status.
- Commit with `AI-Origin: Codex` trailer.

## ACCEPTANCE CRITERIA
- [ ] Coverage for spot BTC-USDT and ETH-USDT (Binance) over the S7 window is
      reported with a concrete number.
- [ ] If loaded: sampled local-vs-DB close mismatch count = 0; no forward-fill
      across gaps.
- [ ] If unobtainable: explicit data-unavailable finding recorded; S7 marked
      data-blocked in its hypothesis doc / ledger.
- [ ] No strategy/gate/artifact-value/schema change.
