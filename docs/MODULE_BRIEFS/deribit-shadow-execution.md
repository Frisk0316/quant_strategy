---
status: current
type: reference
owner: codex
created: 2026-07-14
last_reviewed: 2026-07-14
expires: none
superseded_by: null
---

# Module Brief: H-014 Deribit Shadow Execution

- **Path(s):** `src/okx_quant/execution/deribit_shadow/`,
  `scripts/run_h014_shadow.py`, `config/h014_shadow.yaml`.
- **Responsibility:** One manual credential-free daily cycle: reproduce the
  accepted signal, create bounded three-leg intents, read public books, append
  hypothetical fills/marks/settlements, and report shadow-vs-research bias.
- **Owns business rules:** R8.3–R8.7 under accepted ADR-0011.
- **Key invariants:** I39 (bounded structure/accounting), I40 (F26/parity/public-only).
- **Common failure modes:** F26 (early publication), F39 (stale/wrong day boundary).
- **Do not touch without approval:** Frozen `ivp_min=85`, `z_min=0.5`, 1.0-unit
  cap, scheduler state, and every private/order/live surface require explicit
  user approval; a live path also needs a future ADR.
- **Source of truth for intent:** ADR-0011, ADR-0010/R8, and the accepted
  research helpers imported by the runner.
- **Tests:** `tests/unit/test_h014_shadow.py`,
  `tests/unit/test_h014_options_accounting.py`.
- **Gotchas:** The shadow price day ends at 08:00 UTC, while the last hourly
  DVOL bucket is observed at 23:00 and becomes F26-safe at 00:00. Any missing
  exact prior common day must reject the cycle, never silently use the last row.

The close series intentionally uses the Deribit-aligned 08:00 UTC session
(`ts - INTERVAL '8 hours'`) rather than E-039's midnight-UTC close. Claude's
review measured 1,570 common days: IVP was identical, mean/max absolute z drift
was 0.03/0.30, and RICH(85/0.5) flipped on 0/1,570 BTC days and 3/1,570 ETH
days. This measured-immaterial convention is explicit and guarded by the
recorded DB-shape fixture test.

Related: `docs/ADR/0011-deribit-options-shadow-execution.md` ·
[[../DOMAIN_RULES]] · [[../DATA_FLOW]].
