---
status: current
type: task
owner: claude
created: 2026-07-28
last_reviewed: 2026-07-28
expires: none
superseded_by: null
---

# H-014 live-execution layer implementation (ADR-0017) — Codex tasks

Strategy/spec source: `docs/ADR/0017-h014-live-execution-layer.md` (ACCEPTED
2026-07-28, explicit user acceptance in-session). Read it first; every design
decision below is anchored there. ADR-0011 (`docs/ADR/0011-*.md`) defines the
shadow layer whose intents this layer consumes.

**Authorization note (template FORBIDDEN override):** the default forbidden
paths `src/okx_quant/execution/` and `config/risk.yaml` are partially opened
for THIS task only, per the user's explicit acceptance of ADR-0017 ("接受",
2026-07-28), which assigns Codex the implementation including "risk
enforcement (config-gated, wired to config/risk.yaml by Codex at
implementation time)". The opening is narrow: ONLY the new subpackage
`src/okx_quant/execution/deribit_live/` may be created, existing execution
files may not change, and `config/risk.yaml` may only gain NEW `h014_live.*`
keys — no existing key may change.

**Hard rules (all tasks):**
- `h014_live.enabled` defaults to `false` and the process fails closed
  (no private client construction, no order path import side effects) when
  false or when credentials are absent.
- NO activation: no scheduled task registration, no mode flip in
  `config/settings.yaml`, no live/demo/shadow readiness claim (R7.2).
- Strategy logic is FROZEN: `src/okx_quant/execution/deribit_shadow/` is
  import-only/read-only. Any intent-generation change is out of scope.
- No withdrawal-related endpoint is implemented at all.
- Tests use mocked HTTP only — no network calls in unit tests.

## T1 — `DeribitPrivateClient` (auth + order lifecycle)

New: `src/okx_quant/execution/deribit_live/private_client.py` (+ package
`__init__.py`). OAuth client_credentials auth from env
(`DERIBIT_API_KEY`/`DERIBIT_API_SECRET`, loaded via existing .env pattern);
base URL switchable between `www.deribit.com` and `test.deribit.com`
(config, default test). Methods: `buy`/`sell` (limit, `post_only=true`
mandatory parameter), `cancel`, `cancel_all_by_currency`, `get_positions`,
`get_account_summary`. Token refresh on 401 once, then fail closed.

Acceptance (binary):
- [ ] Missing env credentials + enabled=false → client never constructed;
      enabled=true + missing credentials → startup raises with clear message.
- [ ] Every order-placing method sends `post_only=true` unless the call is
      explicitly flagged `reduce_only` (risk exit); a plain taker order is
      unrepresentable in the public API of the client.
- [ ] No withdrawal/transfer endpoint exists in the module (grep-clean).
- [ ] Unit tests cover auth, refresh-on-401, each method's request shape.

## T2 — Execution adapter + shadow parity

New: `src/okx_quant/execution/deribit_live/adapter.py`. Consumes the SAME
intent records the shadow layer emits (import the shadow intent builder;
do not reimplement). When `h014_live.enabled`: place post-only maker orders
at our side of the book, reprice at a bounded cadence (config, default
30s, max N reprices then give up and journal `missed`), instrument allowlist
= BTC/ETH options only, aggregate cap 1.0 unit/symbol and R8.3 naked-put
rejection enforced by REUSING the shadow layer's checks.

Acceptance (binary):
- [ ] Golden parity test: for fixed fixture inputs, live-adapter intents
      byte-match shadow intents (serialize both, assert equal).
- [ ] With `enabled=false`, adapter is a no-op that still appends shadow
      journal records (shadow never stops in live mode, per ADR §8).
- [ ] Order attempts/fills/rejects append to `results/shadow_h014/`-style
      JSONL (`results/live_h014/orders.jsonl`, append-only, lock sidecar
      pattern copied from shadow journal).
- [ ] A non-allowlisted instrument or naked-put intent set is rejected in
      tests before any client call.

## T3 — Risk config, kill switches, alerts

- `config/risk.yaml`: NEW `h014_live:` block only — `enabled: false`,
  `max_notional_per_symbol`, `max_notional_aggregate`, `daily_loss_stop`,
  `drawdown_reduce_only_threshold`, `env: test` (testnet default).
- Panic script `scripts/h014_live_panic.py`: cancel-all both currencies +
  set reduce-only intent state; runnable standalone; documented in RUNBOOK.
- Alerts: on order placement, rejection, risk-stop trigger, and adapter
  failure — reuse the existing notification pattern
  (`scripts/h014_shadow_notify.ps1` toast; Telegram if already configured,
  else log-only with a TODO note, do not add a new dependency).

Acceptance (binary):
- [ ] `make check-config` equivalent (`python scripts/check_config.py` or the
      repo's config validator) passes with the new keys.
- [ ] Risk stops are enforced in the adapter with unit tests (breach →
      reduce-only mode, new entries rejected).
- [ ] Panic script has a dry-run mode test with mocked client asserting
      cancel_all is called for both currencies.
- [ ] No existing `config/risk.yaml` key changed (diff shows additions only).

## T4 — Change Manifest + docs + verification

- Change Manifest from `docs/CHANGE_MANIFEST_TEMPLATE.md` (execution/risk
  paths are Manifest-relevant per `docs/DOC_IMPACT_MATRIX.md`).
- Docs: `docs/FEATURE_MAP.md` (new feature row: owning files above),
  `docs/RUNBOOK.md` (panic command, testnet plumbing check, activation
  checklist pointer to ADR-0017 gate order), `docs/AI_HANDOFF.md` mirror +
  `config/workstreams.yaml`.
- Run: targeted pytest for new tests, `python scripts/docs/check_doc_impact.py`,
  docs-check scripts. Windows: no `make` — run pytest directly.

Acceptance (binary):
- [ ] `python -m pytest tests/unit/test_deribit_private_client.py
      tests/unit/test_h014_live_adapter.py -v` all pass (names may differ,
      list actual).
- [ ] `python scripts/docs/check_doc_impact.py` no blocking findings.
- [ ] Change Manifest exists and lists every touched business-rule surface.
- [ ] Diff contains only permitted files (below).

## PERMITTED FILES (only these)

- `src/okx_quant/execution/deribit_live/` (new package, any file inside)
- `tests/unit/test_deribit_private_client.py`, `tests/unit/test_h014_live_adapter.py`
  (or equivalently named new test files)
- `config/risk.yaml` (additive `h014_live:` block ONLY)
- `scripts/h014_live_panic.py` (new)
- `docs/FEATURE_MAP.md`, `docs/RUNBOOK.md`, `docs/AI_HANDOFF.md`,
  `config/workstreams.yaml`, `docs/change_manifests/` (new manifest),
  `docs/CHANGELOG_AI.md`

## FORBIDDEN (do not touch)

- `src/okx_quant/execution/deribit_shadow/` and every other existing file in
  `src/okx_quant/execution/`
- `src/okx_quant/{strategies,signals,risk,portfolio}/`
- `config/settings.yaml` (no mode flip), `config/h014_shadow.yaml`
- `scripts/run_h014_shadow.py`, `scripts/run_h014_shadow_task.cmd`,
  `results/**` (no artifact writes from tests)
- Any scheduler registration (schtasks) — activation is a later, separately
  approved step

SCOPE LIMIT: implement exactly the ADR-0017 v1 scope; no adjacent
refactoring; deviations from the ADR go back to Claude/user as questions,
not silent design changes.

REQUIRED ON COMPLETION: standard AGENTS.md completion report (diff scope,
tests + output tail, assumptions, docs updated, limitations, risks, rollback,
questions for Claude review, next recommended task, deployment readiness —
which is "not deployable; activation gated per ADR-0017/R7.2").
