---
status: current
type: task
owner: claude
created: 2026-07-31
last_reviewed: 2026-07-31
expires: none
superseded_by: null
---

# OKX demo-smoke credential isolation — Codex task

User reported 2026-07-31: the newly obtained OKX API key has real trade
permission (not read-only). `scripts/run_okx_demo_smoke.py` currently sources
credentials via `load_config()` → `OKXSecrets` → the required
`OKX_API_KEY`/`OKX_SECRET`/`OKX_PASSPHRASE` fields (`src/okx_quant/core/config.py:40-42`).
Those are the SAME env vars already read by two live-capable paths:
`scripts/download_okx_data.py:155-160` (`demo=False`, historical data) and
`src/okx_quant/engine.py:75-80` (`OKXBroker(..., demo=cfg.is_demo())`, which
`scripts/run_live.py` can flip to `demo=False` by changing
`config/settings.yaml` `system.mode` to `live` plus a typed confirmation).

OKX's demo/live isolation is a request-header flag (`x-simulated-trading`) on
the SAME host, not a separate host like Deribit/Binance testnet — so unlike
those two venues, an OKX key with live trade permission is only as safe as
the code path that carries it. The `system.mode` + typed-confirmation gate in
`run_live.py` is real but is a single config value, not credential-level
isolation. This task adds that missing layer: a demo-only credential path
that a `system.mode`/code mistake elsewhere cannot reach, matching the
`DeribitPrivateClient.from_env` pattern already used for Deribit.

Do NOT touch `src/okx_quant/execution/broker.py` or
`src/okx_quant/data/rest_client.py` — both already accept explicit
`api_key`/`secret`/`passphrase` constructor args; only the credential
*source* for the demo smoke needs to change.

## Required behavior

1. Add `OKX_DEMO_API_KEY` / `OKX_DEMO_SECRET` / `OKX_DEMO_PASSPHRASE` to
   `.env.example` (blank, commented as OKX Demo-Trading-specific — created
   via OKX's Demo Trading key flow, distinct from the live
   `OKX_API_KEY`/`OKX_SECRET`/`OKX_PASSPHRASE` used by `download_okx_data.py`
   and the live engine path).
2. `scripts/run_okx_demo_smoke.py`: stop calling `load_config()` for
   credentials. Read `OKX_DEMO_API_KEY`/`OKX_DEMO_SECRET`/
   `OKX_DEMO_PASSPHRASE` directly from the environment/`.env` (mirror
   `DeribitPrivateClient.from_env`'s `dotenv_values` pattern — no new
   dependency). Keep the existing placeholder/blank check, and keep the
   `cfg.is_demo()` / `system.mode` check for the unrelated settings-consistency
   reason it exists today, but credentials themselves must come only from the
   new demo-specific vars. Still hardcode `demo=True` in the `OKXBroker`/
   `OKXRestClient` construction (unchanged).
3. Missing `OKX_DEMO_*` vars must fail closed with the same
   `blocked-pending-user-key` message shape used today, updated to name the
   new vars.
4. Update `docs/RUNBOOK.md`'s Binance/OKX paper-connectivity section (added
   2026-07-30) and `docs/FEATURE_MAP.md`'s OKX/Binance connectivity entries to
   name `OKX_DEMO_API_KEY`/`OKX_DEMO_SECRET`/`OKX_DEMO_PASSPHRASE` instead of
   the shared live vars.
5. Extend/add a unit test proving the smoke script's credential loader never
   reads `OKX_API_KEY`/`OKX_SECRET`/`OKX_PASSPHRASE` (only the `OKX_DEMO_*`
   names) — a fixture `.env` with only the live vars set must still report
   `blocked-pending-user-key`, not succeed.

## PERMITTED FILES
- `scripts/run_okx_demo_smoke.py`
- `.env.example`
- `docs/RUNBOOK.md` (only the 2026-07-30-added Binance/OKX section)
- `docs/FEATURE_MAP.md` (only the Binance testnet connectivity entry)
- `tests/unit/test_okx_demo_smoke.py` (new, if a test file doesn't already
  cover this script)

## FORBIDDEN
- `src/okx_quant/execution/broker.py`, `src/okx_quant/data/rest_client.py`,
  `src/okx_quant/core/config.py`, `src/okx_quant/engine.py`,
  `scripts/run_live.py`, `scripts/download_okx_data.py`, `config/risk.yaml`,
  `config/settings.yaml`
- Any change to the shared `OKX_API_KEY`/`OKX_SECRET`/`OKX_PASSPHRASE`
  contract used by the live-labeled paths

## ACCEPTANCE CRITERIA (binary)
- [ ] `.env.example` has the three new `OKX_DEMO_*` vars, blank, commented.
- [ ] `run_okx_demo_smoke.py` no longer calls `load_config()` for credentials
      and never reads `OKX_API_KEY`/`OKX_SECRET`/`OKX_PASSPHRASE`.
- [ ] New/updated test proves a `.env` with only the old live vars set still
      reports `blocked-pending-user-key`.
- [ ] `python -m pytest` on the touched/new test file green.
- [ ] `git diff` touches only permitted files.

REPORT: standard AGENTS.md block. State explicitly that no live-labeled file
was touched and that the old shared vars are unreachable from this script
after the change.
