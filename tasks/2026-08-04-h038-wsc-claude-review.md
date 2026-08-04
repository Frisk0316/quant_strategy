---
status: current
type: task
owner: claude
created: 2026-08-04
last_reviewed: 2026-08-04
expires: none
superseded_by: null
---

# Claude review — H-038/E-094 + WS-C C3/C5/C10 (2026-08-04)

Reviewed commits `c37bfd3`, `b08011c`, `8760140`, `fb5eed5`, `bbf3b27` against
`3e7d26f`. Protocol: `docs/CRITIQUE_PROTOCOL.md` (severity / claim / evidence /
smallest fix).

**Verdict: WS-C APPROVE-WITH-FINDINGS. H-038/E-094 BLOCKED — one blocker that
needs a user ruling before the terminal K 2/2 record stands.**

---

## BLOCKER 1 — an unprovenanced 100% data gate permanently closed F-S5

**Claim.** The probe requires `member_day_coverage == 1.0`. That threshold has no
provenance in the spec, in E-014, in any precedent probe, or in INVARIANTS, and
it is stricter than every comparable rule in this repository. It is the sole
cause of the terminal outcome.

**Evidence.**
- `backtesting/s5_residual_meanrev_probe.py:256` writes
  `"required_member_day_coverage": 1.0` as an inline literal — not a named
  constant, with no provenance field beside it.
- The only precedent Stage-2 probe sets `MIN_MEMBER_DAY_COVERAGE = 0.95`
  (`backtesting/taker_flow_probe.py:27`).
- Invariant I11 requires data coverage **≥ 80%** before a dated replay starts
  (R6.2, `docs/INVARIANTS.md:33`).
- Measured coverage was `0.9999421028253821` — 17,271 of 17,272 PIT member-days.
  It clears 0.95 and 0.80 comfortably and fails only against 1.0.
- The single cause is one symbol-day: `SOL-USDT-SWAP` on 2026-01-01 held 1,439
  of 1,440 expected minute rows (`results/h038_stage2_20260804/
  stage2_feasibility.json`, `missing_member_days`).
- Consequence: distinctness, cost, and power are all `NOT_EVALUATED`;
  `n_obs = 0`, `plausible_net_sharpe = null`, `correlation = null`. F-S5 is
  recorded terminal at K 2/2 and "permanently closed" with **zero evidence
  about the mechanism**.

**My share of this.** The task file I wrote said "任何缺口 fail closed，不得以鄰近
標的替代". I meant "do not substitute another symbol's data"; it can fairly be read
as "any gap aborts". Codex implemented the stricter reading. The ambiguity is
mine, not Codex's — its execution was faithful and its reporting honest.

**Why fixing this is not gate-chasing.** Gate-chasing is loosening a statistical
gate after seeing a near-miss. Here no outcome exists to chase: every downstream
metric is null and `n_obs` is 0. The disputed value is a *data admissibility
precondition*, set above every repo precedent without provenance, that prevented
any measurement from occurring. I49 already establishes the pattern — a
structurally unmeetable contract is refused as a contract error, never reported
as a data-conditional measurement.

**The specific irony.** H-038 was authorized because E-014's failure was recorded
as "a data-universe artifact, not strategy refutation or support". E-094 closed
the family on another data-universe artifact. The mechanism has still never been
tested.

**Suggested resolution — user's ruling required, I did not change the ledger.**
Recommended: treat E-094 as a contract error rather than a verdict. Keep its
artifact immutable as the record, restore F-S5 to K 1/2, and rerun once as E-095
with the precedent 0.95 threshold plus an explicit provenance field naming where
the number comes from. Alternative if you prefer the strict reading: accept the
close as recorded, and note in the ledger that no mechanism evidence was
produced. Either is defensible; silently leaving a 1.0 literal with no
provenance as the reason a family died is not.

**Unverified.** I could not confirm the SOL minute gap against the DB —
`psycopg` is absent from this environment. The finding does not depend on it.

---

## MAJOR 1 — C3 sends `reduceOnly`/`posSide` on SPOT cash orders

**Claim.** The reduce-only flags are attached regardless of instrument type. A
SPOT exit carries `reduceOnly` and `posSide` alongside `tdMode=cash`, which OKX
does not accept for cash orders, so the close is rejected — the opposite of what
C3 was authorized to fix.

**Evidence.**
- `src/okx_quant/execution/broker.py:97-101` attaches both keys whenever
  `order.get("reduce_only")` is truthy, with no instrument-type branch.
- `src/okx_quant/portfolio/portfolio_manager.py:211`:
  `use_long_flat_close_sizing = is_long_flat and action == "exit" and
  reduces_position` — nothing restricts it to SWAP.
- `src/okx_quant/strategies/external_features.py:121` emits `"mode":
  "long_flat"`, and `config/settings.yaml:7-9` configures `BTC-USDT` /
  `ETH-USDT` spot symbols, so the path is reachable.
- `tests/unit/test_wsc_trade_safety.py:34` sets `spot_symbols=[]`, so the new
  suite never exercises it.

**Smallest fix.** Attach the two keys only when `td_mode != "cash"`, and add one
test asserting a spot reduce-only order sends neither key.

---

## Accepted without findings

- **C5** is correct and does what was asked: the `0.01` / `1.0` fabrications are
  gone, `instr["ctVal"]` is read directly, values route through the **existing**
  `validate_ct_val` rather than a parallel check, a `code != "0"` guard and a
  `missing_specs` check were added, and the old warn-and-default `except` now
  raises. The BTC/ETH special case is removed from `_fallback_ct_val`.
- **C10** is correct. I checked the one regression I suspected — gating
  `exec_handler.on_market` behind `book is not None` could have stopped fill
  generation — and it is unfounded: `market_data_handler.py:54` pre-creates an
  `OkxBook` for every subscribed symbol, so the guard never fires for a
  subscribed instrument.
- Governance bookkeeping is complete: four Change Manifests, `docs-impact
  --strict` passes over 32 changed files, and the ledgers record K 2/2 with an
  F-S5 K-budget row.

## Checks I ran

`pytest tests/unit -q` → **1142 passed, 1 skipped**. Targeted
`test_wsc_trade_safety` + `test_s5_residual_meanrev_probe` +
`test_execution_flow` + `test_pipeline_stage2_registry` → 63 passed.
`DOC_IMPACT_BASE=3e7d26f check_doc_impact.py --strict` → pass.
Not run: integration suite, backtest smoke, any DB-backed or browser check.

## Required response

Per `docs/CRITIQUE_PROTOCOL.md` the author must answer every blocker/major
explicitly. BLOCKER 1 needs the user's K ruling first; MAJOR 1 is Codex's to fix
under the existing C3 authorization and manifest.
