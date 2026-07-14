---
status: current
type: task
owner: claude
created: 2026-07-14
last_reviewed: 2026-07-14
expires: 2026-10-14
superseded_by: null
---

# Codex Task List: H-014 Deribit shadow-execution layer (ADR-0011 v1)

Authority: ADR-0011 (accepted 2026-07-14, shadow-only) + explicit user
authorization in-session. Claude reviews every diff. NOTHING in this task may
place a real order or touch credentials; live execution needs a future ADR.

## Global scope rules

PERMITTED FILES:
- `src/okx_quant/execution/deribit_shadow/` (new package: signal engine,
  intent generator, book-snapshot client, shadow fill model, JSONL journal)
- `scripts/run_h014_shadow.py` (single entrypoint, one daily cycle per run)
- `config/h014_shadow.yaml` (new; frozen combo ivp_min=85/z_min=0.5, cap,
  fee constants — NOT `config/risk.yaml`, NOT `config/strategies.yaml`)
- `tests/unit/test_h014_shadow_*.py`; docs per the AGENTS.md matrix
  (`docs/RUNBOOK.md` run/remove instructions; `docs/FEATURE_MAP.md` row)

FORBIDDEN:
- Any private/authenticated Deribit endpoint; any order-placement code path
- `src/okx_quant/{strategies,signals,risk,portfolio}/`, `config/risk.yaml`,
  deployment gates, DB schema (`sql/`), scheduler registration (manual run
  only until the user approves a scheduled task)
- `research/probes/*` (read-only reference), existing `results/**`

## T1 — Signal engine + intent generator

Daily cycle: load hourly DVOL (`published_at` as-of ≤ yesterday's close, F26)
and canonical daily closes from the DB; compute IVP(365d)/VRP-z(90d) exactly
per the research definitions (`research/probes/f_vol_regime_opt_probe.py`
`build_series` is the reference; do not re-derive); if yesterday was RICH at
the frozen combo, emit today's tranche intents (1/30 unit per symbol,
short ~25Δ call + 25Δ/10Δ put spread, nearest-30d expiry among instruments
listed NOW, aggregate cap 1.0/symbol from the journal's open tranches).
**R8.3 in code:** reject any intent set leaving a naked short put; unit test
proves the rejection.

ACCEPTANCE (binary):
- [ ] Signal values reproduce the research series on 5 sampled historical
      days (|Δivp| < 0.5, |Δz| < 0.05)
- [ ] Naked-put rejection unit test green; cap unit test green
- [ ] No network call in the signal path except the DB

## T2 — Book snapshot + shadow fill + journal

At intent time fetch public order books for the selected instruments; record
top-of-book, mid, depth; hypothetical fill = bid for sells / ask for buys;
fees per R8.4; append JSONL to `results/shadow_h014/journal.jsonl`
(append-only; each record: ts, signal inputs, intent, book, fill, fees).
Daily M2M + settlement records per R8.2/R8.5 mirroring the research runner's
fields; reuse `research/probes/h014_stage3_backtest.py` accounting helpers by
import, NOT by copy (single accounting implementation, I39).

ACCEPTANCE (binary):
- [ ] One full manual cycle runs end-to-end on live public data and appends
      valid records (schema-checked by unit test)
- [ ] Golden accounting test still 6/6 (imports unchanged)
- [ ] Journal is append-only (re-run does not rewrite history; dedupe by
      intent id)

## T3 — Shadow-vs-research bias report tool

`scripts/run_h014_shadow.py --report`: from the journal, per-leg fill bias vs
day VWAP, missed-entry rate (RICH days with no fillable book), mark tracking
error vs research fallback marks, shadow equity curve in coin (R8.1).

ACCEPTANCE (binary):
- [ ] Report runs on a synthetic 3-day fixture journal in tests
- [ ] Outputs the ADR-0011 §7 exit-criteria metrics explicitly

## T4 — Docs + handoff

RUNBOOK: manual run + removal commands (no scheduler registration);
FEATURE_MAP row; session handoffs per AGENTS.md. Report with the standard
end-of-task block; Claude reviews before any scheduled operation is proposed
to the user.

## Verification

`make test-unit` equivalent (targeted pytest), Ruff on new files, docs
checkers; one live manual cycle with its journal excerpt pasted in the report.
