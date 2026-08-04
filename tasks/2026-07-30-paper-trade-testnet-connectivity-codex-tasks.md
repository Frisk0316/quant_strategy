---
status: current
type: task
owner: claude
created: 2026-07-30
last_reviewed: 2026-07-30
expires: none
superseded_by: null
---

# Paper-trade testnet connectivity (Deribit / Binance / OKX) — Codex tasks

User request 2026-07-30: connect Deribit, Binance, and OKX testnet/paper-
trading. Scope decided in-session (AskUserQuestion): (1) activate H-014's
existing-but-disabled live-execution adapter to run its **real signal-driven
order loop on Deribit testnet**; (2) build **new** testnet connectivity for
Binance, covering **both spot and USDT-margined futures**; OKX demo
connectivity already exists in code and only needs verification once the
human supplies a key.

**Three independent sub-tasks below (T1/T2/T3). They do not share files and
can run in parallel or in any order, except T1's Phase 2 has a hard STOP.**

Read first: `docs/ADR/0017-h014-live-execution-layer.md`,
`docs/ADR/0018-h014-testnet-signal-driven-execution-exception.md`,
`docs/DOMAIN_RULES.md` R8.8/R8.9, `docs/RUNBOOK.md` lines ~970-1020 (existing
H-014 live plumbing-check + panic procedure), `docs/KNOWN_ISSUES.md` (OKX
demo-key entry).

**Hard precondition for T1 only:** ADR-0018's frontmatter `status:` must read
`accepted` (Claude/user update it in-session, mirroring the ADR-0017
acceptance record) before any T1 code lands. If it still says `proposed`,
stop T1 and tell Claude — do not implement ahead of acceptance. T2 and T3
have no such precondition; they touch no gate.

---

## T1 — Deribit: activate H-014 signal-driven execution on testnet

Contract: ADR-0017 (design) + ADR-0018 (testnet-only activation exception).
Frozen strategy/intent logic in `execution/deribit_shadow/` is consumed, not
modified. `env` must remain `"test"` throughout this task — never set
`h014_live.env: live` here.

### Phase 1 (build + verify; `enabled` stays `false`)

1. In `execution/deribit_live/private_client.py` and `adapter.py`, add a hard
   assertion that construction fails closed unless `env == "test"` while
   ADR-0018's exception is in effect (i.e. while `enabled: true` is being
   requested through this exception path) — a config typo must not be able
   to reach `www.deribit.com` under this exception.
2. Run the existing RUNBOOK read-only plumbing check
   (`docs/RUNBOOK.md:993-997`) once the user has placed a trade-scoped
   **testnet** `DERIBIT_API_KEY`/`DERIBIT_API_SECRET` in `.env`: auth,
   account-summary, option-position calls, `enabled` unchanged. Paste the
   real output.
3. Add ONE new integration-style test (mocked transport, no real network in
   CI) that exercises a full place→ack→cancel round trip through
   `DeribitPrivateClient` against the test host, to close the gap that only
   read-only calls have been exercised so far.
4. Add `DERIBIT_API_KEY=` / `DERIBIT_API_SECRET=` to `.env.example` (missing
   today — testnet key, comment that it must be trade-scoped, no withdrawal,
   and is separate from any future live-key rotation).
5. Report Phase 1 evidence and STOP. Do not touch `config/risk.yaml` yet.

### Phase 2 (activate — only after Claude reviews Phase 1 evidence and says go)

6. Set `config/risk.yaml` `h014_live.enabled: true`, `env` stays `test`.
7. Add `scripts/run_h014_live.py`: a manual, on-demand entry point (same
   manual-first pattern as `scripts/run_h014_shadow.py` — no scheduled task
   registration in this task) that runs one signal-driven live-adapter cycle
   against Deribit testnet using real current signals, journals to
   `results/live_h014/orders.jsonl`, and exits.
8. Run one real manual testnet cycle end-to-end. Paste the journal entries
   produced (order placed/repriced/filled/cancelled per real signal) and
   confirm byte-parity of the intent against what `deribit_shadow` would have
   produced for the same inputs (R8.8).
9. Re-run `python scripts/h014_live_panic.py --dry-run` and confirm it still
   makes no network call; then run the real panic command once against the
   testnet position opened in step 8 to prove rollback, and confirm
   `results/live_h014/reduce_only.flag` is written.
10. Write a Change Manifest at
    `docs/change_manifests/2026-07-30-h014-testnet-activation.md` (business
    rules affected: R8.9 exception per ADR-0018; trigger area A2). Update
    `docs/FEATURE_MAP.md`'s "H-014 Deribit Options Live Execution" row from
    "(disabled)" to reflect testnet-active/signal-driven, still
    non-evidentiary and still `env: test`-only.

### T1 PERMITTED FILES
- `src/okx_quant/execution/deribit_live/private_client.py`, `adapter.py`
- `tests/unit/test_deribit_private_client.py`, `tests/unit/test_h014_live_adapter.py` (extend)
- `scripts/run_h014_live.py` (new, Phase 2 only)
- `config/risk.yaml` `h014_live` block only (Phase 2 only — explicitly
  authorized this session per ADR-0018; do not touch any other block)
- `.env.example`, `docs/FEATURE_MAP.md`, `docs/change_manifests/2026-07-30-h014-testnet-activation.md`,
  `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `config/workstreams.yaml`

### T1 FORBIDDEN
- `execution/deribit_shadow/` (frozen intent logic — read-only import)
- Any change that lets `env` become `"live"`, any real-money credential, any
  scheduler/Task Scheduler registration, `results/shadow_h014/**`,
  `docs/HYPOTHESIS_LEDGER.md` / `docs/EXPERIMENT_REGISTRY.md` (testnet output
  is non-evidentiary — do not record it there)

### T1 ACCEPTANCE CRITERIA (binary)
- [ ] Phase 1: plumbing check output pasted; new place/cancel round-trip test
      passes; `.env.example` has both Deribit keys.
- [ ] Phase 2 gated: only proceeds after ADR-0018 `status: accepted` AND
      Claude's explicit go on Phase 1 evidence — both quoted in the report.
- [ ] One real testnet cycle journaled with byte-identical intent vs shadow
      on the same inputs.
- [ ] Panic dry-run still no-network; real panic proven against the opened
      testnet position; `reduce_only.flag` present.
- [ ] `config/risk.yaml` diff touches only the `h014_live` block; `env`
      remains `"test"` in the committed file.
- [ ] Change Manifest exists and is referenced in the commit/PR.

---

## T2 — Binance: new testnet connectivity (spot + USDT-margined futures)

No Binance strategy exists yet — this is connectivity-only. **Never** wire
these clients to any strategy signal or scheduler in this task.

1. New `src/okx_quant/execution/binance_testnet/` package, following the
   existing `DeribitPrivateClient` shape (plain `httpx` client, HMAC-SHA256
   query-param signing per Binance's documented scheme — no new dependency,
   `hmac`/`hashlib` are stdlib):
   - `spot_client.py` — `https://testnet.binance.vision`: account info,
     place/cancel a single test order (use Binance's `/api/v3/order/test`
     endpoint plus one real testnet limit order far from market, then cancel
     it), open orders query.
   - `futures_client.py` — `https://testnet.binancefuture.com`: account
     balance/position info, place/cancel one reduce-only-safe test order,
     open orders query.
   - Both fail closed exactly like `DeribitPrivateClient.__init__`: missing
     `BINANCE_API_KEY`/`BINANCE_SECRET` (or futures-specific env vars if
     Binance testnet requires separate keys per market — confirm and report)
     raises before any network call.
2. `scripts/run_binance_testnet_smoke.py`: manual CLI that authenticates,
   prints account/position snapshot, places one far-from-market limit order
   on each of spot and futures, cancels both, prints the round trip. No
   scheduler, no strategy wiring.
3. Unit tests with a mocked `httpx` transport (no real network) covering:
   signature construction, the fail-closed missing-credential path, and
   place/cancel response parsing for both clients.
4. Add `BINANCE_API_KEY=` / `BINANCE_SECRET=` (and futures-specific vars if
   distinct) to `.env.example`, commented as **testnet-only**, no
   withdrawal permission.
5. Once the user supplies real testnet keys, run the smoke script once and
   paste the real output.

### T2 PERMITTED FILES
- `src/okx_quant/execution/binance_testnet/**` (new)
- `scripts/run_binance_testnet_smoke.py` (new)
- `tests/unit/test_binance_testnet_client.py` (new)
- `.env.example`, `docs/FEATURE_MAP.md` (new row: "Binance testnet
  connectivity (no strategy)")

### T2 FORBIDDEN
- Any file under `src/okx_quant/strategies/`, `signals/`, `risk/`,
  `portfolio/`, existing `execution/` packages, `config/risk.yaml`
- Any scheduled task, any signal/strategy wiring, any mainnet Binance host

### T2 ACCEPTANCE CRITERIA (binary)
- [ ] Both clients fail closed with no network call when credentials are
      absent (unit-tested).
- [ ] Mocked-transport unit tests green for signing + place/cancel parsing.
- [ ] Real smoke-script output pasted for both spot and futures once keys
      are supplied (or reported as blocked-pending-user-key if not yet
      available — do not claim success without real output).
- [ ] `.env.example` updated; diff contains only permitted files.

---

## T3 — OKX: verify existing demo connectivity (blocked on user key)

`OKXBroker(demo=True)` already exists (`src/okx_quant/execution/broker.py`).
The blocker is `docs/KNOWN_ISSUES.md`'s recorded `60005 Invalid apiKey` —
the user has not yet created a valid OKX **Demo Trading** API key (this is a
human action Codex cannot substitute; OKX demo keys are generated separately
from live keys on OKX's demo-trading site).

1. Confirm which env vars `OKXBroker(demo=True)` reads today and whether
   `.env.example`'s single `OKX_API_KEY`/`OKX_SECRET`/`OKX_PASSPHRASE` set is
   reused for both demo and live, or whether demo needs distinct vars.
   Report the finding — do not silently add vars that duplicate existing
   ones.
2. Write or extend a small manual CLI smoke script
   (check `scripts/run_demo.py` first — it may already cover this; extend
   rather than duplicate if so) that authenticates via `OKXBroker(demo=True)`,
   fetches account balance, places one small far-from-market demo order, and
   cancels it.
3. If the user has supplied a working Demo key by the time this task runs,
   execute the smoke script and paste real output; update
   `docs/KNOWN_ISSUES.md` to close the `60005` entry. If not, report exactly
   that it remains blocked-pending-user-key — do not claim resolution.

### T3 PERMITTED FILES
- `scripts/run_demo.py` (extend, if that's the right entry point) or one new
  small script
- `.env.example` (only if step 1 finds a genuine gap)
- `docs/KNOWN_ISSUES.md` (only if actually resolved)

### T3 FORBIDDEN
- `src/okx_quant/execution/broker.py` internals beyond what's needed to call
  the existing `OKXBroker(demo=True)` path — do not rewrite the broker
- Any strategy/signal wiring, any live (`demo=False`) call

### T3 ACCEPTANCE CRITERIA (binary)
- [ ] Credential-source finding reported (shared vs separate demo vars).
- [ ] Smoke script exists and either (a) ran with real output and
      `KNOWN_ISSUES.md` updated, or (b) is reported as still
      blocked-pending-user-key with no readiness claim.

---

## REPORT (all three, standard AGENTS.md block)

Changed files, exact test commands + pasted output tails, docs updated per
matrix, assumptions, and — critically — for T1 quote the ADR-0018 acceptance
line and Claude's Phase-1→Phase-2 go/no-go verbatim. State explicitly for
each venue whether any strategy signal now drives real (even testnet) orders
— T1 yes (by design, testnet only), T2/T3 no (connectivity only). Questions
to Claude instead of silent deviation.
