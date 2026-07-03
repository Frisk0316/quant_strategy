---
status: current
type: plan
owner: human
created: 2026-06-17
last_reviewed: 2026-06-30
expires: none
superseded_by: null
---

# Multi-Venue Instrument Specs (P1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Ownership:** This plan is written by Claude (planning) for **Codex** (implementation). It touches trading-core (`backtesting/`) and DB schema — both gated. Do not start until ADR-0007 is approved by the user and a permitted-files task is issued. Authority: [docs/ADR/0007-multi-venue-instrument-specs.md](../../ADR/0007-multi-venue-instrument-specs.md) and the Change Manifest [docs/change_manifests/2026-06-17-multi-venue-instrument-specs.md](../../change_manifests/2026-06-17-multi-venue-instrument-specs.md).

**Goal:** Resolve a swap's `ct_val` from the run's chosen exchange (Binance/OKX) via a new `venue_instrument_specs` table, tag ct_val provenance with that exchange, and keep the source-provenance gate consistent — so a venue-correct DB-backed provenance PASS becomes producible.

**Architecture:** Venue is a single run-level attribute (`cfg.storage.primary_exchange`, already exists). A new `venue_instrument_specs(exchange, symbol)` table holds per-venue `ct_val/lot/tick/min`. `ReplayBacktestEngine` resolves ct_val by `(exchange, symbol)`; the OKX-only YAML registry is used as fallback **only when `exchange == "okx"`**. The provenance block gains an `exchange` tag (shape otherwise unchanged); `differential_validation` surfaces it and scopes `db_parity` to that exchange. Per-venue fee/funding (P2), live execution + native-symbol mapping (P3), and automated spec sync are **out of scope**.

**Tech Stack:** Python 3.12, pytest, asyncpg, TimescaleDB/Postgres, FastAPI, vanilla-JS frontend. Test runner path: `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest`.

---

## Pre-flight

- [ ] **Read authority docs** — `docs/ADR/0007-multi-venue-instrument-specs.md`, the Change Manifest, `AGENTS.md` do-not-touch list, `docs/DOC_IMPACT_MATRIX.md` rows A2/A5/A6/A9.
- [ ] **Branch** — `git checkout -b codex/impl-multi-venue-instrument-specs` off the approved base. Do not work on `claude/design-multi-venue`.
- [ ] **Baseline tests green before changes** — Run: `& 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' -m pytest tests/unit/test_differential_validation.py tests/unit/test_source_provenance_validation.py -q` → Expected: all PASS. If not, stop and report.
- [ ] **Do not touch:** `src/okx_quant/strategies/`, `src/okx_quant/signals/`, `src/okx_quant/risk/`, `src/okx_quant/portfolio/`, `config/risk.yaml`, existing `results/**` artifacts.

---

## Task 1: `venue_instrument_specs` table + seed

**Files:**
- Create: `sql/migrations/0011_venue_instrument_specs.sql`
- Create: `sql/seed_venue_instrument_specs.sql`

- [ ] **Step 1: Write the migration**

`sql/migrations/0011_venue_instrument_specs.sql`:

```sql
-- Per-venue instrument specs. Keyed by (exchange, canonical symbol).
-- ct_val is the contract multiplier used by PnL/notional/sizing; it is a
-- property of the EXECUTION VENUE, not of the price-data source. See ADR-0007.
CREATE TABLE IF NOT EXISTS venue_instrument_specs (
    exchange    TEXT NOT NULL,
    symbol      TEXT NOT NULL,            -- canonical symbol, e.g. BTC-USDT-SWAP
    ct_val      DOUBLE PRECISION NOT NULL CHECK (ct_val > 0),
    lot_size    DOUBLE PRECISION NOT NULL CHECK (lot_size > 0),
    tick_size   DOUBLE PRECISION NOT NULL CHECK (tick_size > 0),
    min_size    DOUBLE PRECISION NOT NULL CHECK (min_size > 0),
    source      TEXT NOT NULL DEFAULT 'db',   -- provenance label; 'db' = verified upstream
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (exchange, symbol)
);
```

- [ ] **Step 2: Write the seed**

`sql/seed_venue_instrument_specs.sql`. Values: OKX BTC-USDT-SWAP ct_val=0.01, OKX ETH-USDT-SWAP ct_val=**0.1** (NOT 0.01 — the YAML registry is wrong here); Binance USDT-M perps trade in base units so ct_val=1.0. **Verify each value against the venue's official instrument spec before applying** (OKX `/api/v5/public/instruments`; Binance `/fapi/v1/exchangeInfo`). lot/tick/min below are starting values from the OKX registry + Binance defaults — confirm them.

```sql
INSERT INTO venue_instrument_specs (exchange, symbol, ct_val, lot_size, tick_size, min_size, source) VALUES
  ('okx',     'BTC-USDT-SWAP', 0.01, 0.01,  0.1,  0.01, 'db'),
  ('okx',     'ETH-USDT-SWAP', 0.1,  0.01,  0.01, 0.01, 'db'),
  ('binance', 'BTC-USDT-SWAP', 1.0,  0.001, 0.1,  0.001, 'db'),
  ('binance', 'ETH-USDT-SWAP', 1.0,  0.001, 0.01, 0.001, 'db')
ON CONFLICT (exchange, symbol) DO UPDATE SET
  ct_val = EXCLUDED.ct_val, lot_size = EXCLUDED.lot_size,
  tick_size = EXCLUDED.tick_size, min_size = EXCLUDED.min_size,
  source = EXCLUDED.source, updated_at = NOW();
```

- [ ] **Step 3: Apply against the dev DB and verify**

Run (PowerShell, DSN in `$env:DATABASE_URL`):
`psql $env:DATABASE_URL -f sql/migrations/0011_venue_instrument_specs.sql; psql $env:DATABASE_URL -f sql/seed_venue_instrument_specs.sql; psql $env:DATABASE_URL -c "SELECT exchange,symbol,ct_val FROM venue_instrument_specs ORDER BY 1,2;"`
Expected: 4 rows, OKX ETH = 0.1, Binance both = 1.0.

- [ ] **Step 4: Commit**

```bash
git add sql/migrations/0011_venue_instrument_specs.sql sql/seed_venue_instrument_specs.sql
git commit -m "feat(db): add venue_instrument_specs table + seed (ADR-0007 P1)"
```

---

## Task 2: Exchange-aware ct_val resolution

**Files:**
- Modify: `backtesting/replay.py` — `_load_db_instrument_specs` (953), `_resolve_swap_ct_val` (1026), `_fallback_swap_ct_val` (1062), `_default_instrument_specs` (916).
- Test: `tests/unit/test_replay_ct_val_resolution.py` (create)

The resolver gains an `exchange` parameter. The OKX-only YAML registry is consulted **only when `exchange == "okx"`** — for other venues, an unseeded symbol must raise (forcing authoritative seeding, never a silently-wrong OKX fallback). `exchange` defaults to `"okx"` to preserve every existing caller/test exactly.

- [ ] **Step 1: Write the failing test**

`tests/unit/test_replay_ct_val_resolution.py`:

```python
import pytest
from backtesting.replay import ReplayBacktestEngine as E


def test_db_specs_win_and_report_db():
    db = {"BTC-USDT-SWAP": {"ct_val": 0.01}}
    assert E._resolve_swap_ct_val("BTC-USDT-SWAP", "okx", db) == (0.01, "db")


def test_binance_base_unit_must_be_seeded_not_okx_fallback():
    # No db spec + binance: must NOT fall back to OKX registry/hardcoded.
    with pytest.raises(ValueError):
        E._resolve_swap_ct_val("BTC-USDT-SWAP", "binance", None)


def test_binance_seeded_value_used():
    db = {"BTC-USDT-SWAP": {"ct_val": 1.0}}
    assert E._resolve_swap_ct_val("BTC-USDT-SWAP", "binance", db) == (1.0, "db")


def test_okx_registry_fallback_still_works():
    # BTC-USDT-SWAP exists in config/instrument_specs.yaml at 0.01.
    val, src = E._resolve_swap_ct_val("BTC-USDT-SWAP", "okx", None)
    assert (val, src) == (0.01, "registry")


def test_default_exchange_is_okx_for_backcompat():
    val, src = E._resolve_swap_ct_val("BTC-USDT-SWAP", db_specs=None)
    assert src == "registry" and val == 0.01
```

- [ ] **Step 2: Run test to verify it fails**

Run: `& 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' -m pytest tests/unit/test_replay_ct_val_resolution.py -v`
Expected: FAIL (TypeError — `_resolve_swap_ct_val` takes no `exchange` arg yet).

- [ ] **Step 3: Implement — update `_resolve_swap_ct_val`**

Replace the signature and registry branch (replay.py:1026-1060):

```python
    @staticmethod
    def _resolve_swap_ct_val(
        symbol: str, exchange: str = "okx", db_specs: dict | None = None
    ) -> tuple[float, str]:
        """Resolve a swap's ctVal for a venue and report provenance.

        Priority: db (venue_instrument_specs) > registry yaml (OKX only) >
        hardcoded BTC/ETH (OKX only) > raise. The YAML registry is OKX-specific;
        for any other exchange an unseeded symbol raises rather than silently
        using OKX values, because ct_val is a per-venue PnL multiplier.
        """
        if db_specs and db_specs.get(symbol, {}).get("ct_val") is not None:
            return float(db_specs[symbol]["ct_val"]), "db"
        if exchange == "okx":
            registry = ReplayBacktestEngine._load_instrument_spec_registry()
            spec = registry.get(symbol)
            if spec and spec.get("ct_val") is not None:
                return float(spec["ct_val"]), "registry"
            if symbol.startswith(("BTC-", "ETH-")):
                logger.warning("ctVal missing; OKX BTC/ETH fallback 0.01", inst_id=symbol)
                return 0.01, "hardcoded_btc_eth"
        raise ValueError(
            f"Missing ctVal for swap '{symbol}' on exchange '{exchange}'. "
            f"Seed venue_instrument_specs(exchange, symbol) or, for OKX, add it to "
            f"config/instrument_specs.yaml."
        )
```

Update `_fallback_swap_ct_val` (1070) to pass exchange through:
`return ReplayBacktestEngine._resolve_swap_ct_val(symbol, exchange)[0]` with signature `_fallback_swap_ct_val(symbol: str, exchange: str = "okx")`.

- [ ] **Step 4: Implement — thread exchange in `_default_instrument_specs` and `_load_db_instrument_specs`**

In `_default_instrument_specs` (916), read the run exchange once and pass it through:

```python
        exchange = str(getattr(self._cfg.storage, "primary_exchange", "okx"))
        db_specs = self._load_db_instrument_specs(exchange)
        ...
        ct_val, source = self._resolve_swap_ct_val(symbol, exchange, db_specs)
        ...
        self._ct_val_sources[symbol] = {"value": ct_val, "source": source, "exchange": exchange}
```

In `_load_db_instrument_specs` (953), accept `exchange` and query the new table:

```python
    def _load_db_instrument_specs(self, exchange: str = "okx") -> dict:
        dsn = getattr(self._cfg.storage, "timescale_dsn", None)
        if not dsn:
            return {}
        # ... existing reachability guard ...
        rows = await conn.fetch(
            "SELECT symbol, ct_val FROM venue_instrument_specs WHERE exchange = $1",
            exchange,
        )
        # build {symbol: {"ct_val": float}} as before
```

Keep the existing graceful `{}`-on-failure behavior (no DSN / unreachable / table absent → registry fallback).

- [ ] **Step 5: Run tests to verify they pass**

Run: `& 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' -m pytest tests/unit/test_replay_ct_val_resolution.py -v`
Expected: 5 PASS.
Then regression: `& 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' -m pytest tests/unit/test_backtesting.py -q` → Expected: PASS (backcompat default `exchange="okx"`).

- [ ] **Step 6: Commit**

```bash
git add backtesting/replay.py tests/unit/test_replay_ct_val_resolution.py
git commit -m "feat(replay): exchange-aware ct_val resolution (ADR-0007 P1)"
```

---

## Task 3: Tag ct_val provenance with the run exchange

**Files:**
- Modify: `backtesting/replay.py` — `_attach_ct_val_provenance` (2187)
- Test: `tests/unit/test_replay_ct_val_provenance_tag.py` (create)

Additive only: keep `ct_val_sources` symbol-keyed and `ct_val_all_authoritative` unchanged; add a run-level `exchange` and per-symbol `exchange`.

- [ ] **Step 1: Write the failing test**

```python
from backtesting.replay import _attach_ct_val_provenance


class _FakeEngine:
    _ct_val_sources = {"BTC-USDT-SWAP": {"value": 1.0, "source": "db", "exchange": "binance"}}


class _Res:
    validation = {}


def test_provenance_carries_run_exchange():
    r = _Res()
    _attach_ct_val_provenance(r, _FakeEngine())
    assert r.validation["ct_val_all_authoritative"] is True
    assert r.validation["exchange"] == "binance"
    assert r.validation["ct_val_sources"]["BTC-USDT-SWAP"]["exchange"] == "binance"
```

- [ ] **Step 2: Run to verify it fails**

Run: `& 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' -m pytest tests/unit/test_replay_ct_val_provenance_tag.py -v`
Expected: FAIL (KeyError `exchange`).

- [ ] **Step 3: Implement**

In `_attach_ct_val_provenance` (replay.py:2201), extend the payload:

```python
    run_exchanges = {info.get("exchange") for info in sources.values() if info.get("exchange")}
    payload = {
        "ct_val_sources": {
            sym: {"value": info.get("value"), "source": info.get("source"),
                  "exchange": info.get("exchange")}
            for sym, info in sources.items()
        },
        "ct_val_all_authoritative": len(non_authoritative) == 0,
        "ct_val_non_authoritative_symbols": sorted(non_authoritative.keys()),
        "ct_val_gate_passed": len(non_authoritative) == 0,
        # Single-venue-per-run (ADR-0007): one exchange expected; join if mixed.
        "exchange": next(iter(run_exchanges)) if len(run_exchanges) == 1 else "+".join(sorted(map(str, run_exchanges))),
    }
```

- [ ] **Step 4: Run to verify it passes**

Run: `& 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' -m pytest tests/unit/test_replay_ct_val_provenance_tag.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backtesting/replay.py tests/unit/test_replay_ct_val_provenance_tag.py
git commit -m "feat(replay): tag ct_val provenance with run exchange (ADR-0007 P1)"
```

---

## Task 4: Gate surfaces exchange + scopes DB parity (the co-update)

**Files:**
- Modify: `backtesting/differential_validation.py` — `_validate_ct_val_provenance` (1380), `_source_data_validation` (581), `_db_parity_validation` (~2109).
- Test: extend `tests/unit/test_differential_validation.py`

ADR-0007 requires this gate to be co-updated in the **same change** as the provenance shape. Shape stays compatible (still reads `ct_val_all_authoritative`); add the venue tag to the gate output and scope `db_parity` to the run exchange.

- [ ] **Step 1: Write the failing test** (add to `tests/unit/test_differential_validation.py`)

```python
def test_ct_val_provenance_surfaces_run_exchange():
    from backtesting.differential_validation import _validate_ct_val_provenance

    class _Bundle:
        symbols = ["BTC-USDT-SWAP"]
        result = {"validation": {"ct_val_all_authoritative": True,
                                  "exchange": "binance",
                                  "ct_val_sources": {"BTC-USDT-SWAP": {"value": 1.0, "source": "db"}}}}
    out = _validate_ct_val_provenance(_Bundle())
    assert out["status"] == "PASS"
    assert out["exchange"] == "binance"
```

- [ ] **Step 2: Run to verify it fails**

Run: `& 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' -m pytest tests/unit/test_differential_validation.py::test_ct_val_provenance_surfaces_run_exchange -v`
Expected: FAIL (KeyError `exchange`).

- [ ] **Step 3: Implement — surface exchange in `_validate_ct_val_provenance`**

In each return of `_validate_ct_val_provenance` (differential_validation.py:1385-1398) add `"exchange": (validation.get("exchange") if isinstance(validation, dict) else None)`. Do not change PASS/FAIL logic.

- [ ] **Step 4: Implement — scope `db_parity` to the run exchange**

In `_db_parity_validation` (~2109), when selecting canonical candles for the parity comparison, filter to the run's exchange where the canonical store records source/exchange. Read the exchange from `bundle.result["validation"].get("exchange")`. If the canonical candle store cannot be filtered by exchange in the current schema, keep current behavior but add `"exchange": <run exchange>` to the check output and a `reason` noting the parity source was not exchange-filtered. (Document this limitation in the Change Manifest rather than expanding schema here.)

- [ ] **Step 5: Run targeted + full validation suite**

Run: `& 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' -m pytest tests/unit/test_differential_validation.py tests/unit/test_source_provenance_validation.py -q`
Expected: all PASS (existing + new).

- [ ] **Step 6: Commit**

```bash
git add backtesting/differential_validation.py tests/unit/test_differential_validation.py
git commit -m "feat(validation): surface run exchange + scope db_parity (ADR-0007 P1)"
```

---

## Task 5: Select the venue from API + frontend

**Files:**
- Modify: `src/okx_quant/api/routes_backtest.py` — backtest request model + the job builder that constructs `AppConfig`.
- Modify: `frontend/view-config.js` — add a venue selector control.
- Test: extend the existing API test for routes_backtest (locate `tests/unit/test_*routes*` or the api smoke test).

- [ ] **Step 1: Write the failing test** — assert a backtest request accepting `exchange="binance"` sets `cfg.storage.primary_exchange`. Locate the existing request model (search `routes_backtest.py` for the Pydantic request class) and the helper that builds `AppConfig`; add a field `exchange: Literal["binance","okx"] = "binance"` and a test that the built cfg carries it. Expected: FAIL before wiring.

- [ ] **Step 2: Implement — request field → cfg**

Add `exchange` to the request model (default `"binance"`, allowed `binance`/`okx` for P1). In the job builder, set it via `cfg = cfg.model_copy(); cfg.storage = cfg.storage.model_copy(update={"primary_exchange": req.exchange})` (match the existing `_resolve_candle_backend` pattern in the file). Add `binance`/`okx` to any allowed-set validation.

- [ ] **Step 3: Frontend selector**

In `frontend/view-config.js`, add a `<select>` (label "Exchange", options Binance / OKX, default Binance) following the existing universe/bar control pattern, and include its value as `exchange` in the run-backtest request payload. Add a one-line note in `StrategyParams` help text.

- [ ] **Step 4: Verify**

Run API test: `& 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' -m pytest <located api test> -v` → PASS.
Run: `node --check frontend/view-config.js` → no syntax errors.

- [ ] **Step 5: Commit**

```bash
git add src/okx_quant/api/routes_backtest.py frontend/view-config.js tests/unit/<api test>
git commit -m "feat(api,ui): per-run exchange selection (ADR-0007 P1)"
```

---

## Task 6: Convergence golden case, docs, manifest, and final verification

**Files:**
- Modify: `docs/GOLDEN_CASES.md`, `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md`, `docs/DOMAIN_RULES.md`, `docs/DATA_FLOW.md`, `docs/INVARIANTS.md`, `docs/ai_collaboration.md`, `docs/UI_MAP.md`, `docs/FEATURE_MAP.md`, `docs/KNOWN_ISSUES.md`, `config/instrument_specs.yaml` (header note), the Change Manifest.
- Test: `tests/unit/test_multi_venue_convergence.py` (create)

- [ ] **Step 1: Convergence golden case (the ADR-0007 acceptance criterion)**

Write `tests/unit/test_multi_venue_convergence.py`: run the same strategy/params/data twice through the replay engine with `primary_exchange="okx"` (ct_val 0.01) vs `primary_exchange="binance"` (ct_val 1.0), using injected `instrument_specs` (config_override) so no DB is needed, and assert `total_return` / `sharpe` are equal within a tolerance that only admits lot-rounding (e.g. `abs(a-b) < 1e-6` on returns for a notional far above min lot). This encodes "ct_val cancels under notional sizing". Run it; Expected: PASS. If it FAILS, sizing is not purely notional somewhere — stop and report (do not loosen the tolerance to hide it).

- [ ] **Step 2: Record the hypothesis + golden case**

Add a `docs/HYPOTHESIS_LEDGER.md` entry ("cross-venue PnL converges because ct_val cancels under notional sizing"; status: confirmed by the Step 1 test) and a `docs/GOLDEN_CASES.md` row pointing at the test. Add an `docs/INVARIANTS.md` line: "a SWAP run's ct_val authoritative source must match the run's execution venue".

- [ ] **Step 3: Update business-rule + flow docs**

`docs/DOMAIN_RULES.md`: ct_val provenance is per-venue. `docs/DATA_FLOW.md`: venue_instrument_specs in the resolution path. `docs/ai_collaboration.md`: ct_val gate evidence is venue-tagged. `docs/UI_MAP.md` + `docs/FEATURE_MAP.md`: exchange selector ownership. `docs/KNOWN_ISSUES.md`: close the "ct_val only from registry" gap; note any db_parity exchange-filter limitation from Task 4 Step 4. `config/instrument_specs.yaml`: header note that it is the OKX fallback only and that authoritative per-venue values live in `venue_instrument_specs`.

- [ ] **Step 4: Fill in the Change Manifest**

In `docs/change_manifests/2026-06-17-multi-venue-instrument-specs.md`: complete Files changed, Tests run (commands + results), tick the docs checkboxes, and set Approval-obtained.

- [ ] **Step 5: Final verification**

Run, in order, and paste real output into the manifest:
- `& 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' -m pytest tests/unit/test_replay_ct_val_resolution.py tests/unit/test_replay_ct_val_provenance_tag.py tests/unit/test_differential_validation.py tests/unit/test_source_provenance_validation.py tests/unit/test_multi_venue_convergence.py -q` → all PASS.
- `& 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' scripts/docs/check_doc_metadata.py` → passes (≤ pre-existing warnings).
- `& 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' scripts/docs/check_doc_impact.py` → business-rule change has a manifest.
- **End-to-end PASS proof:** seed applied (Task 1), then
  `$env:DIFF_VALIDATION_ENABLE_DB_PARITY="1"; $env:DIFF_VALIDATION_DB_DSN="<dsn>"; & 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' scripts/run_source_provenance_validation.py --run-id <fresh binance BTC run> --engines vectorbt,backtrader`
  → exit 0 (PASS) with `ct_val_provenance` source `db` and `exchange: binance`. This closes Codex's open "which saved run" question with a venue-correct run.

- [ ] **Step 6: Commit + flip ADR status**

After user approval, set ADR-0007 Status to `Accepted` and commit:

```bash
git add docs/ tests/unit/test_multi_venue_convergence.py config/instrument_specs.yaml
git commit -m "docs(adr-0007): accept multi-venue specs; convergence golden case + manifest (P1)"
```

---

## Out of scope (do not implement here)

- Per-venue fee/funding precision (P2) — separate ADR/Manifest.
- Per-venue live execution adapters + native-symbol mapping (P3).
- Automated per-venue spec sync (later phase; the table is sync-ready).
- Cross-venue trading within one run (rejected in ADR-0007).
- Bybit pairs (table supports it; seed when a Bybit pair goes into use).

## Self-review notes

- Spec coverage: ADR-0007 decisions 1–5 map to Tasks 2 (resolution/venue-aware), 1 (table), 3 (provenance tag), 4 (gate co-update), 5 (run-level exchange via existing `primary_exchange`); convergence consequence → Task 6 Step 1.
- Backcompat: `exchange="okx"` default on `_resolve_swap_ct_val`/`_fallback_swap_ct_val` preserves all current callers/tests.
- Risk: if Task 6 Step 1 convergence test fails, a non-notional sizing path exists — report, do not mask.
