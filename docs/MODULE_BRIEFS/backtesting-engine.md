---
status: current
type: reference
owner: human
created: 2026-06-12
last_reviewed: 2026-06-12
expires: none
superseded_by: null
---

# Module Brief: Backtesting Engine

- **Path(s):** `backtesting/`, `scripts/run_backtest.py`,
  `scripts/run_replay_backtest.py`
- **Responsibility:** Historical replay backtesting — drives strategies bar by
  bar, models fills/latency, accounts PnL/fees/funding, writes file/DB artifacts,
  and enforces the replay validation gates.
- **Owns business rules:** R5 (fill/execution semantics), R6 (data provenance),
  R7 (promotion gates), and contributes to R1–R3 accounting in replay.
- **Key invariants:** I8 (no lookahead), I9 (no orphan positions), I10 (terminal
  liquidation), I11 (data coverage ≥ 80%).
- **Common failure modes:** F4 lookahead, F6 orphan position, F7 terminal leak,
  F8 coverage, F11 no-fill replay.
- **Do not touch without approval:** Result schema and validation gates are
  governed by ADR-0002 and ADR-0005 — changes need an ADR + human approval.
- **Source of truth for intent:** `config/`, `research/strategy_synthesis.md`,
  ADR-0002 (result schema), ADR-0005 (gates).
- **Tests:** `tests/unit/test_backtesting.py`,
  `tests/integration/test_replay_engine.py`, oracle correctness tests.
- **Gotchas:** Idealized-fill and in-sample output are upper bounds, never
  promotion evidence (R7.1). A run can complete "clean" with zero fills — check
  the Gate 2 fill-rate warning. Funding needs a full settlement window to show up.

Related: [[../DATA_FLOW]] · [[../GOLDEN_CASES]] · `docs/ADR/0005-replay-validation-gates.md`.
