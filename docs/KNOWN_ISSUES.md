---
status: current
type: handoff
owner: human
created: 2026-06-12
last_reviewed: 2026-07-17
expires: none
superseded_by: null
---

# Known Issues

Durable backlog for bugs, gaps, and open operational risks. `docs/AI_HANDOFF.md`
may still reference active issues, but long-lived backlog items should move here
over time.

## Audit blockers and closures from 2026-07-12

- **Closed — artifact path containment (F30/I32):** API, artifact writer,
  differential validation and caller-facing CLIs now share reject-not-truncate
  ID validation plus resolved-root containment.
- **Closed — venue fail-closed validation (F31/I33):** omitted venue uses the
  configured primary exchange; explicit unknown venues return HTTP 400 before
  a run/sweep is queued.
- **Closed — numeric `ct_val` validation (F32/I34):** the shared validator now
  accepts finite positive multipliers through `1e7` and rejects zero, negative,
  NaN, infinity and over-cap values. R1.4/I16 still enforce provenance
  separately; PnL formulas are unchanged.
- **Branch integration:** `codex/pipeline-batch1-stage3` was 96 commits ahead and
  5 behind `origin/main` at audit time. Option B is approved but not executed:
  merge the five main-only commits first, then one documented integration-
  exception PR with `verify-full`; no force-push is authorized.

## Research and operations state

- ADR-0011's first H-014 DB smoke found stale canonical/DVOL inputs. A bounded
  refresh through the existing public Binance and Deribit ingestion paths
  restored the exact prior-day signal on 2026-07-14, but freshness remains an
  operational prerequisite because no scheduler was authorized. The runner
  now raises before journaling rather than reusing a stale date (F39/I40), and
  its signal-day-qualified intent ID lets a corrected rerun coexist with audit
  history. Two pre-guard stale records remain in append-only JSONL; the report
  counts and excludes them from the 8-week gate. Do not substitute a new data
  source or schedule refreshes silently.
- H-009 remains a non-passing `testing` candidate with no chase-the-gate retry.
  H-012 is user-ratified `shelved`, no retry; its E-037 spot-check also found
  F36: turnover cost is posted on signal day while position/funding begin at
  t+1. The immutable artifact remains non-promotion evidence; fix and a new
  registered experiment are required before this runner is ever reused.
- H-013/F-VRP-TIMING Stage-1 is user-signed-off and remains `proposed`; E-038 is
  deliberately reserved-only and absent from the experiment registry until the
  approved Stage-2 probe actually runs.
- **Closed data boundary — H-010/F44/I47 (2026-07-17):** ADR-0014 added an
  additive source-aware canonical identity without changing the priority-
  resolved table or its CAGGs. The authorized OKX BTC/ETH frozen-window
  promotion has 1,293,120 rows per symbol, raw parity mismatches 0, and
  coverage/alignment 1.0; rerun changes 0 rows. H-010 itself was not retried and
  its ledger status/verdict remains unchanged. Binance substitution remains
  forbidden by I19.
- **Closed caller/observability bugs — F45/F46:** active Stage-2 callers now
  reject missing candidate-specific power inputs before probe/artifact/status
  mutation, and malformed artifacts are reported per file without aborting the
  schema-v3 funnel.
- By user decision, Deribit snapshot/forward-ingest Windows tasks remain
  unregistered and stale series are accepted while the RUNBOOK manual path
  remains usable. Daily `dvol_deribit_*` is retained and was backfilled on
  2026-07-12 (1,936 gap-free rows per symbol through 2026-07-11); its manual
  update command is recorded in the RUNBOOK.
- OKX Demo private login returns `60005 Invalid apiKey`; a valid Demo key is
  required. Do not switch to live as a workaround.
- The existing `127.0.0.1:8080` listener (PID 23696 during the audit) timed out
  and was not stopped because it was not owned by this session. The user has
  abandoned that port; use another port and do not kill the user process.
- P1.4 repo support is implemented: the liquidation wrapper pins the verified
  Python executable, and the RUNBOOK records least-privilege S4U registration,
  verification, run, rollback, and removal commands. Host activation remains
  blocked: `quant_liq_okx_ingest` still reported `Interactive` on 2026-07-15
  because this session could not obtain Administrator Task Scheduler rights.
  Run the documented `/NP` command from Administrator PowerShell, then require
  `LogonType=S4U`, `RunLevel=Limited`, and a successful manual task result.

## Governance follow-ups

- `make verify` still lacks the separate crypto-alpha-lab test target required
  by the original M1 acceptance criteria; parent and lab suites must remain
  separate packages.
- DOC_IMPACT A11 cannot be enforced honestly from Git diff alone. Add a ledger
  consistency validator for hypothesis/experiment/family/K-budget relations.
- Lifecycle metadata coverage currently excludes `tasks/`; four templates and
  many historical handoffs therefore remain implicit drafts.
- ADR-0006 is user-confirmed accepted, and ADR-0001 now records the approved
  local-`tasks/` exception. Remaining P1.2 work is narrative/archive cleanup,
  not a pending policy decision.

## Harness

- `make api-smoke` is a real smoke only when `API_BASE_URL` points at a running
  server; otherwise it exits with an explicit SKIP.
- `make backtest-smoke` uses a tiny frozen no-DB replay fixture. It is smoke
  coverage only; full replay/data-provenance coverage and promotion evidence
  still require the normal validation gates.
- `make verify-full` may require TimescaleDB and seeded data.
- Frontend backtest-chart behavior is still mostly covered by syntax/static
  checks plus API artifact tests. Known gap: add a browser-level interaction test
  before treating progressive multi-symbol chart loading as fully guarded.
- The crypto-alpha-lab (`research/crypto-alpha-lab/`) is a **separate Python
  package**; its tests must run as their own step (`pip install -e
  research/crypto-alpha-lab` then `python -m pytest
  research/crypto-alpha-lab/tests -p no:cacheprovider`). Collecting them in the
  same `pytest` invocation as `tests/unit/` fails with
  `ImportError: crypto_alpha_lab`. CI now runs the parent and lab suites as
  separate steps.

## Validation

- Differential-validation unit coverage and the
  `codex_20260616_signal_validation` fixture batch verify source-data validation,
  portable validation gates, signal-point correctness, and active-strategy
  `reference_signals_only` contracts. These fixtures are signal-point evidence,
  not live execution or profitability evidence. CI now runs this fixture batch as
  a regression gate.
- Nautilus remains advisory in v1. Full Nautilus matching-engine parity for
  order/fill/PnL/funding semantics is not implemented.
- The signal-validation runner disables Numba JIT by default for vectorbt fixture
  validation because vectorbt import/JIT initialization can stall on Windows for
  tiny fixture workloads.
- Advisory validation evidence, in-sample backtests, idealized-fill artifacts, and
  DB parity SKIP states are not promotion evidence.
- `scripts/recheck_dsr.py` is the current audit for DSR-bearing JSON artifacts.
  The 2026-06-24 run found 7 CPCV rows and 38 replay-level single-run diagnostic
  rows. `xs_momentum_validation_20260623` and
  `xs_momentum_validation_20260624_leakfix` have stored CPCV DSR values that
  violate `DSR <= PSR(0)` and must not be cited. Daily Winner CPCV was
  recomputed from saved returns and remains non-passing. The portfolio-vol XS
  artifact has a fixed, non-passing DSR/PSR pair, but only summary/path Sharpe
  fields were saved. As of 2026-06-29, future CPCV outputs retain raw path
  returns, or combined returns when path assembly is unavailable, so
  `scripts/recheck_dsr.py` can recompute DSR from saved artifacts; historical
  artifacts were not backfilled and remain summary-only.
- A fresh DB-backed artifact PASS still needs a reachable seeded DSN. On
  2026-06-18, `DATABASE_URL` was unset, the configured `.env` DSN on port 5432
  refused connections, local PostgreSQL on port 5433 rejected the repo `quant`
  credentials, and Docker Desktop could not be started from that session.
- Source-scoped canonical reads are now a validation boundary: DB parity for
  exchange `<x>` must query `canonical_candles.source_primary = <x>` and emit
  `checks.db_parity.canonical_source_primary == <x>`. If a Binance validation
  run compares OKX-tagged candles or omits this field, fix the candle source
  tagging / DB read path instead of loosening the gate.
- For `price_series.csv`, DB parity is close-only provenance: it compares
  timestamped artifact closes to canonical candle closes after source scoping.
  O/H/L flattening and volume-unit differences are not like-for-like DB parity
  fields; they remain covered by artifact-level structure/data-quality checks. A
  2026-06-23 Codex reseed created 20,400 Binance-sourced 1H canonical rows for
  `BTC-USDT-SWAP` from Binance 1m canonical data, then a targeted
  `download_binance_data.py --bar 1H --start 2024-04-29 --end 2024-04-30`
  repaired the remaining one-day gap. Local parquet and DB canonical Binance 1H
  closes now match for 2024-04-29 (24 rows, 0 mismatches). Existing
  validation-lab artifacts from before the repair still fail DB parity with 24
  close mismatches; rerun/regenerate those artifacts before citing a current
  DB-backed Binance 1H PASS. The older
  `adr0007_binance_btc_1h_db_pass_20260618_source_provenance` artifact still
  records the pre-fix FAIL, carries `SUPERSEDED.md`, and should not be cited as
  PASS.
- Pipeline batch 1's remaining gap is validation quality, not ETH data
  availability: S6 did not re-earn the statistical gate on the fold-refit
  harness, so portable validation adapters and authoritative ct_val evidence
  must not start for S6. S7 is shelved after a non-degenerate half-life rerun.
  S5 has a separate point-in-time universe/canonical coverage mismatch: the
  current membership artifact plus strict venue-scoped complete-window candle
  coverage produces `nonzero_grid_activity:false`, so the S5 refit summary is a
  data-universe artifact rather than a strategy verdict.
- The `docs/EXPERIMENT_REGISTRY.md` Family K-budget table is hand-maintained
  checkpoint state. Even though the family-minting checker now reads `k_used`,
  `k_limit`, and `at_k_limit`, stale table values still need human review before
  they are relied on for K-budget decisions.
- Future experiment-registry rows should continue to state
  `family-cumulative n_trials=...` clearly. If they do not, the shared
  `family_registry_from_text()` parser falls back to the historical max-row
  interpretation.

## Operations

- Monitoring modules exist, but this map does not prove production alert coverage.
  Treat Telegram/metrics deployment readiness as a separate operational check.
