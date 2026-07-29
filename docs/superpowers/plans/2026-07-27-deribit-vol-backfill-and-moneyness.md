# Deribit Vol Backfill + Option Moneyness Buckets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** (1) Backfill long history for hourly Deribit vol series (DVOL 1h to 2021-03-24, derived RV30 to 2018/2019) since `hv_deribit_*_1h` cannot be backfilled; (2) add ATM/ITM/OTM moneyness bucketing to the option-surface and option-flow adapters and re-ingest option-flow history with the new fields.

**Architecture:** No new data sources. Backfills are runs of the existing `scripts/market_data/ingest_external.py` CLI (it already accepts `--dataset/--start/--end` and upserts into `external_observations`). Moneyness is a pure helper (`strike` vs index price) added to `deribit_option_surface.py`, used by both the surface adapter (current-chain snapshot buckets) and the flow adapter (per-trade classification via each trade's `index_price`).

**Tech Stack:** Python 3.11+, httpx, asyncpg, pytest, click. TimescaleDB (table `external_observations`, unique on `(dataset_id, observed_at)`, upsert overwrites fields). Windows host.

## Global Constraints

- Windows: **no `make`** — run pytest directly: `python -m pytest tests/unit/<file> -v`.
- Working tree currently has uncommitted in-flight changes to `src/okx_quant/data/external_clients/deribit_dvol.py`, `config/external_data.yaml`, and related tests (Deribit RV30 work, see `tasks/2026-07-27-deribit-rv30-*`). **Precondition: start only from a clean `git status --short` for these files** (in-flight work committed). If dirty, stop and ask the user.
- Branch: create `feature/deribit-vol-backfill-moneyness` from the branch the user designates at session start (default: current feature branch after it is clean).
- No Change Manifest / ADR needed: `src/okx_quant/data/external_clients/` and `scripts/market_data/` are not in any `Manifest? = Yes` row of `docs/DOC_IMPACT_MATRIX.md`. Docs to update: `docs/DATA_FLOW.md` + `config/external_data.yaml` notes (Task 6).
- Do not modify existing backtest result artifacts. Do not touch `src/okx_quant/{strategies,signals,risk,portfolio,execution}/`.
- Commit messages end with: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- All timestamps UTC. `--start/--end` accept ISO 8601 (`_parse_dt` at `scripts/market_data/ingest_external.py:87` uses `datetime.fromisoformat`, `Z` OK).

## Verified API facts (measured 2026-07-27, do not re-derive)

| Fact | Value |
| --- | --- |
| `public/get_historical_volatility` (feeds `hv_deribit_*_1h`) | rolling ~16-day window only (384 hourly rows), no pagination → **backfill impossible**, accumulate forward only |
| Hourly DVOL (`get_volatility_index_data`, resolution 3600) | BTC **and** ETH data from **2021-03-24 00:00 UTC**; pages 1000 rows via continuation (client already handles) |
| BTC-PERPETUAL 1h chart (`get_tradingview_chart_data`) | from **2018-08-14** → first full 720h RV30 row ≈ **2018-09-14** |
| ETH-PERPETUAL 1h chart | from **2019-03-14** → first RV30 row ≈ **2019-04-14** |
| `history.deribit.com` option trades | available back to ≥ 2019-04, each trade has `instrument_name`, `iv`, `index_price` |

DB access for verification snippets: DSN is `storage.timescale_dsn` in `config/settings.yaml` (may contain env placeholders — expand with `os.path.expandvars` if needed).

---

### Task 1: Backfill hourly DVOL (BTC + ETH) to 2021-03-24

**Files:** none created/modified — ingestion runs only.

**Interfaces:**
- Consumes: existing `DeribitDVOLClient` paging + `ingest_external.py` CLI.
- Produces: `external_observations` rows for `dvol_deribit_btc_1h` / `dvol_deribit_eth_1h` from 2021-03-24 to now (~47k rows each).

- [ ] **Step 1: Dry-run**

Run: `python scripts/market_data/ingest_external.py --dataset dvol_deribit_btc_1h --start 2021-03-24T00:00:00Z --dry-run`
Expected: one `[dry-run]` line showing adapter `deribit_dvol`, start `2021-03-24 00:00:00+00:00`.

- [ ] **Step 2: Run both backfills** (~47 paged requests each, minutes)

```powershell
python scripts/market_data/ingest_external.py --dataset dvol_deribit_btc_1h --start 2021-03-24T00:00:00Z
python scripts/market_data/ingest_external.py --dataset dvol_deribit_eth_1h --start 2021-03-24T00:00:00Z
```

Expected: inserted/updated counts in the tens of thousands per dataset.

- [ ] **Step 3: Verify coverage**

Save as `verify_backfill.py` in the scratchpad directory (reused by Tasks 2 and 5):

```python
import asyncio, os, sys, asyncpg, yaml

dsn = os.path.expandvars(yaml.safe_load(open("config/settings.yaml"))["storage"]["timescale_dsn"])

async def main(datasets):
    conn = await asyncpg.connect(dsn)
    for ds in datasets:
        r = await conn.fetchrow(
            "select min(observed_at) as lo, max(observed_at) as hi, count(*) as n "
            "from external_observations where dataset_id=$1", ds)
        print(ds, r["lo"], r["hi"], r["n"])
    await conn.close()

asyncio.run(main(sys.argv[1:]))
```

Run: `python <scratchpad>\verify_backfill.py dvol_deribit_btc_1h dvol_deribit_eth_1h`
Expected: `lo` = 2021-03-24 for both; `n` ≥ 45000; no commit (nothing changed in repo).

---

### Task 2: Backfill rv30 RV series + calibrate against official HV

**Files:** none created/modified — ingestion runs + one recorded comparison (numbers land in config notes in Task 6).

**Interfaces:**
- Consumes: existing `DeribitRealizedVolatilityClient` (window prefetch is internal: it fetches `start - window_hours` itself).
- Produces: `rv30_deribit_btc_1h` from ~2018-09-14, `rv30_deribit_eth_1h` from ~2019-04-14; calibration numbers (corr, mean diff vs `hv_deribit_*_1h`) for Task 6.

- [ ] **Step 1: Run backfills** (~14 chart pages each, minutes)

```powershell
python scripts/market_data/ingest_external.py --dataset rv30_deribit_btc_1h --start 2018-09-14T00:00:00Z
python scripts/market_data/ingest_external.py --dataset rv30_deribit_eth_1h --start 2019-04-14T00:00:00Z
```

- [ ] **Step 2: Verify coverage**

Run: `python <scratchpad>\verify_backfill.py rv30_deribit_btc_1h rv30_deribit_eth_1h`
Expected: BTC `lo` ≈ 2018-09-14, ETH `lo` ≈ 2019-04-14 (first row may shift a few hours on gaps — that is fine); `hi` = current hour.

- [ ] **Step 3: Calibration query (RV30 vs official HV over the ~16-day overlap)**

Add to a scratch python (same DSN pattern as `verify_backfill.py`), one query per currency:

```sql
select corr(h.value_num, r.value_num) as corr,
       avg(h.value_num - r.value_num)  as mean_diff,
       count(*) as n
from external_observations h
join external_observations r on r.observed_at = h.observed_at
where h.dataset_id = 'hv_deribit_btc_1h'
  and r.dataset_id = 'rv30_deribit_btc_1h';
```

Expected: `n` > 200, `corr` > 0.9. If corr < 0.9, report the numbers to the user before proceeding — do not "fix" the RV formula (Deribit's HV uses its own estimator; a level offset is expected, a low correlation is not). Record corr/mean_diff/n for both currencies — Task 6 writes them into the yaml notes.

---

### Task 3: `moneyness_bucket` helper + surface bucket aggregates (TDD)

**Files:**
- Modify: `src/okx_quant/data/external_clients/deribit_option_surface.py`
- Test: `tests/unit/test_deribit_option_surface.py`

**Interfaces:**
- Produces (used by Task 4):
  - `moneyness_bucket(option_type: str, strike: float | None, index_price: float | None, atm_band: float = 0.025) -> str | None` — returns `"atm" | "itm" | "otm"` or `None` when unclassifiable.
  - `ATM_BAND = 0.025` module constant.
  - New keys inside surface rows' `fields`: `moneyness_atm_band`, `atm_call_oi`, `atm_put_oi`, `itm_call_oi`, `itm_put_oi`, `otm_call_oi`, `otm_put_oi`, `atm_mark_iv`, `otm_put_mark_iv`, `otm_call_mark_iv`, `otm_skew_mark_iv` (all floats; IV keys `None` when bucket empty).

- [ ] **Step 1: Write failing tests for the pure helper**

Append to `tests/unit/test_deribit_option_surface.py`:

```python
from okx_quant.data.external_clients.deribit_option_surface import moneyness_bucket


def test_moneyness_bucket_classification():
    spot = 100_000.0
    # ATM band is +/-2.5% of spot
    assert moneyness_bucket("C", 100_000.0, spot) == "atm"
    assert moneyness_bucket("P", 102_500.0, spot) == "atm"   # exactly on band edge
    assert moneyness_bucket("C", 97_500.0, spot) == "atm"
    # Calls: strike below spot is ITM, above is OTM
    assert moneyness_bucket("C", 90_000.0, spot) == "itm"
    assert moneyness_bucket("C", 120_000.0, spot) == "otm"
    # Puts: mirrored
    assert moneyness_bucket("P", 120_000.0, spot) == "itm"
    assert moneyness_bucket("P", 90_000.0, spot) == "otm"


def test_moneyness_bucket_unclassifiable_inputs():
    assert moneyness_bucket("C", None, 100.0) is None
    assert moneyness_bucket("C", 100.0, None) is None
    assert moneyness_bucket("C", 100.0, 0.0) is None
    assert moneyness_bucket("X", 100.0, 100.0) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_deribit_option_surface.py -v -k moneyness`
Expected: FAIL — `ImportError: cannot import name 'moneyness_bucket'`.

- [ ] **Step 3: Implement the helper**

Add to `deribit_option_surface.py` (module level):

```python
ATM_BAND = 0.025  # |strike/spot - 1| <= band counts as at-the-money


def moneyness_bucket(
    option_type: str,
    strike: Optional[float],
    index_price: Optional[float],
    atm_band: float = ATM_BAND,
) -> Optional[str]:
    """Classify an option strike vs current index price: atm / itm / otm."""
    if strike is None or index_price is None or index_price <= 0:
        return None
    if option_type not in {"C", "P"}:
        return None
    m = strike / index_price - 1.0
    if abs(m) <= atm_band:
        return "atm"
    if option_type == "C":
        return "itm" if m < 0 else "otm"
    return "itm" if m > 0 else "otm"
```

- [ ] **Step 4: Run helper tests to verify they pass**

Run: `python -m pytest tests/unit/test_deribit_option_surface.py -v -k moneyness`
Expected: 2 PASS.

- [ ] **Step 5: Write failing integration test for surface bucket fields**

First read the existing fake-chain fixture in `test_deribit_option_surface.py` (`test_option_surface_aggregate_math_and_snapshot_shape`) and reuse its row keys. The adapter reads per-instrument `instrument_name`, `open_interest`, `mark_iv`, and spot from `estimated_delivery_price` (see `deribit_option_surface.py:67-115`) — the fixture below assumes those keys; align it with the existing fixture if it differs:

```python
def test_option_surface_moneyness_bucket_fields(monkeypatch):
    client = DeribitOptionSurfaceClient()
    spot = 100_000.0
    chain = [
        # name, oi, iv  -> bucket for spot 100k
        ("BTC-26DEC26-100000-C", 10.0, 50.0),  # atm call
        ("BTC-26DEC26-80000-C", 5.0, 60.0),    # itm call
        ("BTC-26DEC26-120000-C", 2.0, 70.0),   # otm call
        ("BTC-26DEC26-120000-P", 4.0, 55.0),   # itm put
        ("BTC-26DEC26-80000-P", 8.0, 80.0),    # otm put
    ]
    rows = [
        {
            "instrument_name": name,
            "open_interest": oi,
            "mark_iv": iv,
            "estimated_delivery_price": spot,
            "creation_timestamp": 1_700_000_000_000,
        }
        for name, oi, iv in chain
    ]
    monkeypatch.setattr(client, "_get", lambda params: {"result": rows})
    fields = client.fetch(currency="BTC")[0]["fields"]

    assert fields["moneyness_atm_band"] == 0.025
    assert fields["atm_call_oi"] == 10.0
    assert fields["itm_call_oi"] == 5.0
    assert fields["otm_call_oi"] == 2.0
    assert fields["atm_put_oi"] == 0.0
    assert fields["itm_put_oi"] == 4.0
    assert fields["otm_put_oi"] == 8.0
    assert fields["atm_mark_iv"] == 50.0            # single atm instrument
    assert fields["otm_put_mark_iv"] == 80.0
    assert fields["otm_call_mark_iv"] == 70.0
    assert fields["otm_skew_mark_iv"] == 80.0 - 70.0
```

- [ ] **Step 6: Run it to verify it fails**

Run: `python -m pytest tests/unit/test_deribit_option_surface.py::test_option_surface_moneyness_bucket_fields -v`
Expected: FAIL with `KeyError: 'moneyness_atm_band'` (or fixture-key mismatch — fix the fixture to match the adapter's actual reads before proceeding).

- [ ] **Step 7: Implement bucket aggregation in the surface adapter**

In the existing per-instrument loop (where `put_oi`/`call_oi` accumulate and `option_type`/`strike`/`mark_iv` are parsed), collect per-bucket sums, then merge into `fields`. Self-contained aggregation:

```python
def _aggregate_moneyness(
    entries: list[tuple[str, Optional[float], float, Optional[float]]],
    index_price: Optional[float],
) -> dict[str, Any]:
    """entries: (option_type, strike, open_interest, mark_iv) per instrument."""
    oi_sums = {f"{b}_{s}_oi": 0.0 for b in ("atm", "itm", "otm") for s in ("call", "put")}
    iv_keys = ("atm", "otm_put", "otm_call")
    wnum = dict.fromkeys(iv_keys, 0.0); wden = dict.fromkeys(iv_keys, 0.0)
    unum = dict.fromkeys(iv_keys, 0.0); uden = dict.fromkeys(iv_keys, 0.0)
    for option_type, strike, oi, mark_iv in entries:
        bucket = moneyness_bucket(option_type, strike, index_price)
        if bucket is None:
            continue
        side = "call" if option_type == "C" else "put"
        oi_sums[f"{bucket}_{side}_oi"] += oi
        iv_key = "atm" if bucket == "atm" else (f"otm_{side}" if bucket == "otm" else None)
        if iv_key and mark_iv is not None:
            wnum[iv_key] += mark_iv * oi
            wden[iv_key] += oi
            unum[iv_key] += mark_iv
            uden[iv_key] += 1.0
    def _iv(key: str) -> Optional[float]:
        if wden[key] > 0:
            return wnum[key] / wden[key]
        if uden[key] > 0:  # ponytail: zero-OI bucket falls back to plain mean
            return unum[key] / uden[key]
        return None
    out: dict[str, Any] = {"moneyness_atm_band": ATM_BAND, **oi_sums}
    out["atm_mark_iv"] = _iv("atm")
    out["otm_put_mark_iv"] = _iv("otm_put")
    out["otm_call_mark_iv"] = _iv("otm_call")
    out["otm_skew_mark_iv"] = (
        out["otm_put_mark_iv"] - out["otm_call_mark_iv"]
        if out["otm_put_mark_iv"] is not None and out["otm_call_mark_iv"] is not None
        else None
    )
    return out
```

Simplify the double-branch weight logic if you can express "OI-weighted, unweighted fallback when total bucket OI is zero" more cleanly — behavior over form. Wire-up: build `entries` in the existing loop, call once after it, `fields.update(_aggregate_moneyness(entries, spot_index))`.

- [ ] **Step 8: Run the full surface test file**

Run: `python -m pytest tests/unit/test_deribit_option_surface.py -v`
Expected: all PASS (including the 3 pre-existing tests — the new fields must not break the existing snapshot-shape assertions; if a pre-existing test asserts the exact `fields` key set, extend that assertion).

- [ ] **Step 9: Commit**

```powershell
git add src/okx_quant/data/external_clients/deribit_option_surface.py tests/unit/test_deribit_option_surface.py
git commit -m "feat(data): add ATM/ITM/OTM moneyness buckets to Deribit option surface"
```

(with the Co-Authored-By trailer from Global Constraints)

---

### Task 4: Moneyness bucket fields in option flow (TDD)

**Files:**
- Modify: `src/okx_quant/data/external_clients/deribit_option_flow.py`
- Test: `tests/unit/test_deribit_option_flow.py`

**Interfaces:**
- Consumes: `moneyness_bucket` from `deribit_option_surface` (Task 3 signature).
- Produces new keys in flow rows' `fields`: `moneyness_atm_band`, `atm_premium`, `itm_premium`, `otm_premium`, `atm_trades`, `itm_trades`, `otm_trades`, `otm_put_buy_amt`, `otm_call_buy_amt`, `unbucketed_trade_count`.

- [ ] **Step 1: Write failing test**

Read the existing fake-trade fixtures in `tests/unit/test_deribit_option_flow.py` first and reuse their trade-dict keys. Then append (invariant-style so it does not depend on the premium formula):

```python
def test_option_flow_moneyness_bucket_fields(monkeypatch):
    client = DeribitOptionFlowClient()
    ts = 1_700_000_000_000  # all in one hour bucket
    trades = [
        # atm call buy, itm put buy, otm put buy, otm call sell
        {"instrument_name": "BTC-26DEC26-100000-C", "timestamp": ts, "direction": "buy",
         "amount": 1.0, "price": 0.05, "iv": 50.0, "index_price": 100_000.0},
        {"instrument_name": "BTC-26DEC26-120000-P", "timestamp": ts + 1, "direction": "buy",
         "amount": 1.0, "price": 0.2, "iv": 55.0, "index_price": 100_000.0},
        {"instrument_name": "BTC-26DEC26-80000-P", "timestamp": ts + 2, "direction": "buy",
         "amount": 2.0, "price": 0.01, "iv": 80.0, "index_price": 100_000.0},
        {"instrument_name": "BTC-26DEC26-120000-C", "timestamp": ts + 3, "direction": "sell",
         "amount": 1.0, "price": 0.02, "iv": 70.0, "index_price": 100_000.0},
    ]
    monkeypatch.setattr(
        client, "_get", lambda params: {"result": {"trades": trades, "has_more": False}}
    )
    from datetime import datetime, timedelta, timezone
    start = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).replace(minute=0, second=0, microsecond=0)
    fields = client.fetch(currency="BTC", start=start, end=start + timedelta(hours=1))[0]["fields"]

    assert fields["moneyness_atm_band"] == 0.025
    assert fields["atm_trades"] == 1
    assert fields["itm_trades"] == 1
    assert fields["otm_trades"] == 2
    assert fields["unbucketed_trade_count"] == 0
    # bucket premiums partition total premium volume
    total = fields["atm_premium"] + fields["itm_premium"] + fields["otm_premium"]
    assert abs(total - fields["premium_volume"]) < 1e-9
    # only taker-BUY OTM amounts are tracked per side
    assert fields["otm_put_buy_amt"] > 0
    assert fields["otm_call_buy_amt"] == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_deribit_option_flow.py::test_option_flow_moneyness_bucket_fields -v`
Expected: FAIL with `KeyError` on a new field (fix fixture keys first if the client rejects the fake trades).

- [ ] **Step 3: Implement**

In `deribit_option_flow.py`: `from okx_quant.data.external_clients.deribit_option_surface import ATM_BAND, moneyness_bucket`. In the per-hour accumulator (where `call_buy_amt` etc. accumulate), for each inverse trade compute `bucket = moneyness_bucket(option_type, strike, trade.get("index_price"))` using the already-parsed `option_type`/`strike`, then:

```python
# per-hour accumulator additions (init alongside the existing counters)
bucket_premium = {"atm": 0.0, "itm": 0.0, "otm": 0.0}
bucket_trades = {"atm": 0, "itm": 0, "otm": 0}
otm_buy_amt = {"C": 0.0, "P": 0.0}
unbucketed = 0

# per-trade (premium = the same per-trade premium the existing amounts use)
if bucket is None:
    unbucketed += 1
else:
    bucket_premium[bucket] += premium
    bucket_trades[bucket] += 1
    if bucket == "otm" and direction == "buy":
        otm_buy_amt[option_type] += premium

# merged into fields when the hour row is emitted
"moneyness_atm_band": ATM_BAND,
"atm_premium": bucket_premium["atm"], "itm_premium": bucket_premium["itm"], "otm_premium": bucket_premium["otm"],
"atm_trades": bucket_trades["atm"], "itm_trades": bucket_trades["itm"], "otm_trades": bucket_trades["otm"],
"otm_put_buy_amt": otm_buy_amt["P"], "otm_call_buy_amt": otm_buy_amt["C"],
"unbucketed_trade_count": unbucketed,
```

Only inverse trades are bucketed (USDC-linear stay excluded, same as today).

- [ ] **Step 4: Run the full flow test file**

Run: `python -m pytest tests/unit/test_deribit_option_flow.py -v`
Expected: all PASS (existing 8 tests untouched).

- [ ] **Step 5: Run the full external-client test set**

Run: `python -m pytest tests/unit/test_deribit_option_surface.py tests/unit/test_deribit_option_flow.py tests/unit/test_deribit_dvol_client.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/okx_quant/data/external_clients/deribit_option_flow.py tests/unit/test_deribit_option_flow.py
git commit -m "feat(data): classify Deribit option flow by moneyness at trade time"
```

---

### Task 5: Re-ingest option-flow history with bucketed fields (2024-01-01 → now)

**Files:** none — long-running ingestion (idempotent upsert replaces old rows with the new field schema).

**Interfaces:**
- Consumes: Task 4's adapter.
- Produces: `optflow_deribit_btc` / `optflow_deribit_eth` hourly rows with moneyness fields from 2024-01-01. (Trades exist back to 2019; 2024+ matches the canonical backtest window — extend later only if the user asks. `optsurf_*` is snapshot-only and **cannot** be backfilled; its buckets start accruing at next scheduled ingest.)

- [ ] **Step 1: Smoke one small chunk in the foreground**

Run: `python scripts/market_data/ingest_external.py --dataset optflow_deribit_btc --start 2024-01-01T00:00:00Z --end 2024-01-02T00:00:00Z`
Expected: ~24 rows inserted/updated. Then spot-check fields: query one row's `fields` via asyncpg (same DSN pattern as `verify_backfill.py`) and confirm `atm_premium` is present.

- [ ] **Step 2: Run the full backfill chunked by month, in the background**

```powershell
$months = @(); $d = Get-Date "2024-01-01"
while ($d -lt (Get-Date)) { $months += $d; $d = $d.AddMonths(1) }
foreach ($ds in "optflow_deribit_btc","optflow_deribit_eth") {
  foreach ($m in $months) {
    $s = $m.ToString("yyyy-MM-01T00:00:00Z"); $e = $m.AddMonths(1).ToString("yyyy-MM-01T00:00:00Z")
    python scripts/market_data/ingest_external.py --dataset $ds --start $s --end $e
    if ($LASTEXITCODE -ne 0) { Write-Host "FAILED $ds $s - rerun this chunk"; }
  }
}
```

Runtime estimate: multiple hours total (≈1–3 paged requests per hour bucket, 0.2 s page delay). Run via the background shell facility; chunks are independently re-runnable (upsert). A failed month is rerun, not debugged inline, unless it fails twice.

- [ ] **Step 3: Verify**

Run: `python <scratchpad>\verify_backfill.py optflow_deribit_btc optflow_deribit_eth`
Expected: `lo` = 2024-01-01 00:00, `hi` = current hour, `n` ≈ 22,000+ per dataset. Also assert no NULL-fields rows:
`select count(*) from external_observations where dataset_id='optflow_deribit_btc' and observed_at >= '2024-01-01' and not (fields ? 'atm_premium');` → expected 0.

---

### Task 6: Docs + config notes

**Files:**
- Modify: `config/external_data.yaml` (notes lines only)
- Modify: `docs/DATA_FLOW.md` ("External Observations Ingestion Flow" section, ~line 148)

- [ ] **Step 1: Update yaml notes**

In `config/external_data.yaml`, extend `notes:` for these datasets (facts only, one sentence each):
- `dvol_deribit_btc_1h` / `eth_1h`: history backfilled from 2021-03-24 (DVOL inception).
- `rv30_deribit_btc_1h`: backfilled from 2018-09-14; add measured calibration vs `hv_deribit_btc_1h` from Task 2 (e.g. "overlap corr X.XX, mean diff Y.Y vol pts, n=NNN").
- `rv30_deribit_eth_1h`: same with ETH numbers, backfilled from 2019-04-14.
- `optsurf_deribit_*`: fields now include ATM/ITM/OTM OI and mark-IV buckets (`moneyness_atm_band` 0.025); snapshot-only, buckets accrue forward.
- `optflow_deribit_*`: fields now include per-hour moneyness premium/trade buckets and OTM taker-buy amounts; history re-ingested with buckets from 2024-01-01.

- [ ] **Step 2: Update DATA_FLOW.md**

In the "External Observations Ingestion Flow" section, amend the Deribit option-surface/option-flow sentence to mention moneyness bucket fields and the backfilled ranges (DVOL 1h 2021-03-24+, RV30 2018/2019+, optflow buckets 2024+). Keep to ≤3 lines, matching the section's existing style.

- [ ] **Step 3: Advisory doc-impact check**

Run: `python scripts/docs/check_doc_impact.py`
Expected: no blocking findings for the touched paths (advisory mode).

- [ ] **Step 4: Commit**

```powershell
git add config/external_data.yaml docs/DATA_FLOW.md
git commit -m "docs(data): record Deribit vol backfill ranges and moneyness bucket fields"
```

---

## Out of scope (explicitly)

- No frontend changes: `frontend/view-config.js` already lists these series; new data rides in the `fields` JSONB.
- No new HV endpoint or paid data source; `hv_deribit_*_1h` stays forward-accumulating (API hard limit).
- No optflow backfill before 2024 (possible later, same command with earlier `--start`).
- No strategy/signal consumption of the new fields — that is a separate research task with its own hypothesis-ledger entry.

## Session-end reminder for the implementing session

Follow CLAUDE.md session-end: refresh `docs/CURRENT_STATE.md`, update `docs/AI_HANDOFF.md` (+ mirror to `config/workstreams.yaml`), and write one merged handoff file in `tasks/`.
