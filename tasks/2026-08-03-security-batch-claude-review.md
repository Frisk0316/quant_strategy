---
status: current
type: review
owner: claude
created: 2026-08-03
last_reviewed: 2026-08-03
expires: none
superseded_by: null
---

# Claude review: F1 + WS-A + B1 security batch — 2026-08-03

Reviewed: the ungated batch from
`tasks/2026-08-03-project-optimization-codex-plan.md`.
Commit: `181f82b` (pushed to `origin/feature/deribit-moneyness-hypotheses`).

## Verdict: APPROVE

Initially APPROVE-WITH-FINDINGS on one confirmed functional regression; Codex
fixed it and the fix was re-verified empirically. All seven security objectives
are met, scope is compliant, and no protected path was touched by the batch.

## Objectives verified

| ID | Change | Verification performed |
| --- | --- | --- |
| F1 | Telegram sender auth + `/reset confirm` | Confirmed `telegram_chat_id` is `Optional[str]` and the monitor is built only when token+chat_id are both present, so the string compare is type-correct (an int would have silently disabled the bot). Non-`message` updates fall to `str(None)` and are skipped — fail-closed. |
| A1 | Loopback default + non-loopback bind requires `API_KEY` | `0.0.0.0`, `::` and unresolvable hostnames all classify as non-loopback. Both uvicorn entry points (`run_api_server`, `run_server.main`) call `require_remote_api_key`; grep confirms no third serving path. |
| A2 | `inst_id` validation before `rmtree` | `validate_artifact_id` regex allows hyphens, so `BTC-USDT-SWAP` is unaffected (no functional regression). `%2e%2e`, `%2e`, `%2e%2e%2f` are covered by parametrized tests and return 400. `{inst_id:path}` is the only `/pairs` route, so no shadowing. |
| A3 | DSN out of argv and job status | DSN absent from `cmd` and from the stored `command`. See regression below. |
| A4 | Standalone auth + `--allow-remote` | Three destructive routers carry `Depends(verify_api_key)`. Removed `WebSocketDisconnect` import confirmed unused; `make_config_router(dependencies=...)` signature confirmed to exist. |
| A5 | Compose required secrets + loopback port | `${VAR:?}` on the three secrets; app port `127.0.0.1:8080:8080`. `API_HOST: 0.0.0.0` is consistent with A1 because `API_KEY` is simultaneously made mandatory. |
| B1 | `OKX_DEMO_*` only, fail-closed | `load_config(require_secrets=False)` parameter confirmed present; `python-dotenv` declared; `demo=True` hardcoded; `.env` anchored to repo root (incidentally closes B5 for this script). |

## Regression found and closed

`routes_backtest.py` moved the DSN from argv into `env["DATABASE_URL"]`, but
`scripts/backtest_ohlcv_rotation.py` hard-required `--dsn` and never read
`DATABASE_URL`, so every postgres-backend rotation job launched from the API
exited immediately. Reproduced empirically before the fix
(`Error: --dsn is required when --backend=postgres`, exit 1).

Root cause of the miss: `test_rotation_job_keeps_dsn_out_of_command` mocks
`subprocess.Popen`, so the child's validation never ran — the test proved the
secret was out of argv, not that the job still worked.

Fix verified after the change: with `DATABASE_URL` set and no `--dsn`, the run
proceeds to a real connection attempt and fails only on
`InvalidPasswordError` for the deliberately fake test password — proving the env
DSN reaches the connection, not merely the validator. With neither set it fails
closed. Codex also added `test_rotation_runner_reads_database_url`, which calls
the real `main()`, mocks only `load_candles`, asserts the DSN reaches the
loader, and parametrizes both the `postgres` and `--exchange`-forced `market`
branches.

## Residual items (not blocking)

- `verify_api_key` / `_is_valid_ws_api_key` still fail open when `API_KEY` is
  unset. Acceptable because non-loopback startup now requires a key, so the
  fail-open path is loopback-only — but the guarantee lives in the two bind
  entry points, not in the auth function. Recorded as the I65 caveat.
- WS-A A6 (manual/progress routers unauthenticated on the engine app, non-ASCII
  header 500, WS key in query string, CORS `*`) and WS-B B2-B5 remain open
  follow-ups; Codex correctly scoped them out.
- `.env.example` now ships empty `API_KEY=`/`GRAFANA_PASSWORD=`; with `:?`
  semantics an empty value also fails, so a fresh copy makes Compose refuse to
  start until filled. Intended fail-closed behavior, documented in RUNBOOK.

## Checks run

- `pytest tests/unit/test_api_security.py test_monitoring.py
  test_okx_demo_smoke.py test_routes_data_delete.py -q` — 30 passed.
- `pytest tests/unit -q` — 1105 passed, 1 skipped, 1 failed. The single failure
  (`test_data_coverage_uses_short_inflight_cache`) was pre-existing drift
  against `frontend/data.js` (`_memoGet` vs `_memoGetLarge`, from commit
  `97e71f2`); `frontend/` is unmodified in the working tree so it fails at HEAD
  independently of this batch. Fixed separately in this session.
- Manual reproduction of the A3 regression and of its fix (above).

## Commit scope note

`181f82b` deliberately excludes the governance rows (FAILURE_MODES F68-F70,
INVARIANTS I65-I66) and RUNBOOK updates: those files also carry another
session's in-flight entries describing that session's still-uncommitted code,
so committing them wholesale would have published unreviewed work. They land
with that session's commit. No Change Manifest is required — every item in this
batch is a security fix, marked `Manifest:N` in the plan.

`scripts/run_okx_demo_smoke.py` carries six lines that belong to the 2026-08-02
paper-demo work (`_resting_buy_price`), inseparable at hunk level from B1.
Reviewed before inclusion: the derived buy price rests below bid, is guarded
positive and strictly below bid, and is demo-only — sound.
