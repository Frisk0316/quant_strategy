---
status: current
type: reference
owner: human
created: 2026-05-11
last_reviewed: 2026-06-30
expires: none
superseded_by: null
---

# Debugging Runbook

Standard diagnostic flows for common failure modes. Before asking an AI to fix anything, work through the relevant section below and collect evidence. Then file a bug report using `.github/ISSUE_TEMPLATE/bug_report.md`.

---

## Rule: Diagnose Before Fixing

Do not ask Codex or Claude to "just fix it" without first:
1. Identifying which layer the failure is in
2. Collecting a concrete error message or reproduction step
3. Filing a bug report with scope and constraints

---

## Frontend Blank Page

**Symptoms:** Dashboard loads but shows nothing; console errors; white screen.

1. Open browser DevTools → Console tab
2. Look for `TypeError`, `SyntaxError`, or `Failed to fetch` errors
3. Check for MIME type error: `Expected a JavaScript module script but the server responded with a MIME type of "text/html"`
   - Root cause: FastAPI not registering `.js` or `.jsx` with `application/javascript`
   - Fix path: `src/okx_quant/api/server.py` — check `StaticFiles` mount and any custom MIME registration
4. Check Network tab → filter by JS — look for 404s on module imports
5. Check `frontend/index.html` — verify `<script type="module">` src paths are correct
6. Check `/api/backtest/runs` returns valid JSON (not 500 or empty)
7. Check `frontend/app.js` import graph — a single broken import silently breaks the whole module tree

If legacy `.jsx` modules still exist, also check:

```bash
curl -I http://localhost:8080/app.jsx
```

Expected `Content-Type`: `application/javascript` or `text/javascript`. Any of the following is invalid for ES modules: `application/octet-stream`, `text/plain`, `text/html`.

**Evidence to collect before filing bug:**

- Full console error text
- Network tab screenshot showing failed requests and their status + MIME type
- Output of `curl -I http://localhost:8080/app.js`

---

## Before Filing a Bug

- [ ] Console error copied verbatim (not paraphrased)
- [ ] Network response status and `Content-Type` checked
- [ ] Exact command used to reproduce recorded
- [ ] Suspected layer selected from the layer checklist
- [ ] Relevant files listed
- [ ] Out-of-scope constraints written (what must not be changed)

---

## Replay / Backtest Result Looks Wrong

**Symptoms:** Equity curve doesn't match expectation; final PnL is implausible; Sharpe is suspiciously high or negative.

Work through layers bottom-up:

### Layer 1: Fill data
```
results/<run_id>/fills.csv
```
- Are fills present? Are timestamps in order?
- Do fill prices look like realistic market prices for the period?
- Are fees present and non-zero?

### Layer 2: Trade data
```
results/<run_id>/trades.csv
```
- Do open/close pairs match?
- Are there orphan open trades with no corresponding close?
- Check `hedge_inst_id` for pairs trades — does the hedge leg have a matching close?

### Layer 3: Position ledger
- After each trade, does the position size change correctly?
- After the final bar, is position zero (if `liquidate_on_end=true`)?

### Layer 4: PnL accounting
- For SWAP instruments: `unrealized_pnl = qty * ct_val * (current_price - avg_price)`
  - `ct_val` for BTC-USDT-SWAP is 0.01. Missing this factor = 100x error.
- For SPOT instruments: `unrealized_pnl = qty * (current_price - avg_price)`
- Funding cashflow: check sign. Long perp pays funding when rate > 0.
- Fees: check taker vs. maker rate applied.

### Layer 5: Equity curve
- `equity = initial_capital + realized_pnl + unrealized_pnl + funding_cashflow - fees`
- If equity curve is flat then suddenly jumps: check if terminal liquidation fill was posted

### Layer 6: Config
- Check `config/strategies.yaml` — are the parameters for this run what you intended?
- Check `config/settings.yaml` — is `mode` correct?

**Evidence to collect before filing bug:**
- `fills.csv` (first 20 rows and last 5 rows)
- `equity_curve` from result JSON (first and last 10 points)
- Strategy config snapshot from result JSON
- Exact command used to run the replay

---

## Funding Carry PnL Looks Wrong

**Symptoms:** Funding income is zero or negative when it should be positive; total PnL doesn't match funding APR estimate.

1. **Check perp leg direction**: When funding rate > 0, the short perp earns funding. Confirm strategy entered short perp.
2. **Check spot leg direction**: Short perp + long spot is the standard carry. Confirm spot leg is long.
3. **Check notional alignment**: Perp notional (qty × ct_val × price) should approximately equal spot notional (qty × price). Mismatch means one leg is over/under-hedged.
4. **Check funding rate sign in data**: Confirm TimescaleDB funding rate is positive for the test period.
5. **Check funding cashflow calculation**: `funding_pnl = perp_qty * ct_val * funding_rate * perp_price` (approximate). Sign must be correct for the position direction.
6. **Check settlement timing**: OKX funding settles every 8h. Confirm the replay timestamps cover at least one settlement event.
7. **Check open position at end**: If perp position is still open at replay end with `liquidate_on_end=false`, unrealized PnL is excluded from realized summary.

**Evidence to collect:**
- Funding rate time series for the test period (from DB or results)
- Perp position size and direction at entry
- Spot position size and direction at entry
- Funding cashflow column from results

---

## Pairs Trading Hedge Not Closing

**Symptoms:** After exit signal, main leg is closed but hedge leg remains open; position ledger shows orphan position.

1. Check entry fill: does the fill metadata include `hedge_inst_id` and `hedge_side`?
2. Check exit signal handler: does `on_exit` close both legs, or only the main leg?
3. Check stop-loss handler: same question — does it close both legs?
4. Check position ledger after exit: query `results/<run_id>/trades.csv` — is there a close fill for `hedge_inst_id`?
5. Check for legging risk: if main leg fill arrived but hedge leg order was rejected, does the strategy handle this state?

**Evidence to collect:**
- `fills.csv` — show all fills for the affected instrument pair
- `trades.csv` — show open/close pairs for both legs
- Position ledger state at exit time

---

## Test Suite Fails Unexpectedly

**Symptoms:** `pytest` fails on tests that previously passed.

1. Run `pytest tests/unit/ -v` first — isolate unit vs. integration failures
2. For import errors: check if a new file was added without `__init__.py`
3. For fixture errors: check `tests/conftest.py` — was a fixture removed or renamed?
4. For numeric assertion failures in PnL tests: check if `ct_val` constant changed
5. For integration test failures: confirm TimescaleDB is running and seeded
   ```powershell
   docker ps | Select-String "timescale"
   ```

**Evidence to collect:**
- Full pytest output (`pytest tests/unit/ -v 2>&1`)
- Python version (`python --version`)
- Whether the failure is in CI or local only

---

## API Returns 500 or Unexpected Schema

**Symptoms:** Frontend shows error; API call returns 500 or missing fields.

1. Check FastAPI logs in terminal where server is running
2. `GET /api/backtest/runs` — does it return a list?
3. `GET /api/backtest/runs/<id>` — does result include `metrics`, `equity_curve`, `fills`, `trades`, `config_snapshot`?
4. If a field is missing: check `backtesting/artifacts.py` — was a field removed from the result writer?
5. Check `src/okx_quant/api/routes_backtest.py` — does the route transform match what frontend expects?

**Evidence to collect:**
- Full API response body (not just status code)
- Server-side traceback from logs
- Frontend network tab showing request/response

---

## Private WebSocket Reconnect Loop

**Symptoms:** `WS private connected`, `WS private error, reconnecting`, then
`Circuit breaker: too many WS reconnects` during demo startup.

1. Check `config/settings.yaml` mode. Demo mode connects to
   `wss://wspap.okx.com:8443/ws/v5/private` and requires a Demo Trading API key;
   a production key is not interchangeable.
2. Read the first terminal authentication error. `60005 Invalid apiKey` means
   the configured key is not valid for that environment; create a Demo Trading
   API key in OKX rather than increasing reconnect thresholds or switching live.
3. For frontend/backtest/data work only, run `python scripts/run_server.py`;
   it serves the dashboard without starting public/private trading sockets.
4. Check for duplicate local servers with `netstat -ano | Select-String ':8080'`.
   Stop the stale listener before restarting, otherwise the browser may keep
   reaching old code bound specifically to `127.0.0.1`.

The private handler treats authentication failure as terminal and does not retry;
transient socket failures still use the existing reconnect path and threshold.
