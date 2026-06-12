---
status: current
type: reference
owner: human
created: 2026-06-12
last_reviewed: 2026-06-12
expires: none
superseded_by: null
---

# Module Brief: Portfolio

- **Path(s):** `src/okx_quant/portfolio/`
- **Responsibility:** Position accounting and sizing — tracks positions, realized
  and unrealized PnL, applies fees and funding cashflows, and coordinates linked
  (e.g. hedge) closes.
- **Owns business rules:** R1 (PnL accounting), R2 (fees), R3 (funding), R4
  (sizing — shared with `risk/`).
- **Key invariants:** I1 (`ct_val` scaling), I2 (realized/unrealized
  reconciliation), I4 (funding sign), I9 (no orphan positions).
- **Common failure modes:** F1 missing `ct_val`, F2 funding sign, F6 orphan
  hedge, F12 maker charged taker fees.
- **Do not touch without approval:** Yes — trading-core. Changes require a
  Change Manifest, the relevant invariant tests, and (for accounting policy
  changes) an ADR; see ADR-0003 and ADR-0006.
- **Source of truth for intent:** `config/risk.yaml`,
  `research/strategy_synthesis.md`, ADR-0003 (PnL accounting), ADR-0006
  (reduce-only semantics).
- **Tests:** portfolio/PnL accounting tests under `tests/unit/`, plus replay
  integration tests.
- **Gotchas:** `ct_val` errors are invisible when tests use ct_val=1 — golden
  cases must use a realistic multiplier. Funding sign is a one-character,
  PnL-inverting bug.

Related: [[../DOMAIN_RULES]] · [[../INVARIANTS]] · `docs/ADR/0003-position-pnl-accounting.md`.
