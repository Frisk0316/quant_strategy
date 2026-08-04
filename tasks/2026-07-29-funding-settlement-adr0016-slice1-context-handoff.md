---
status: current
type: handoff
owner: codex
created: 2026-07-29
last_reviewed: 2026-07-29
expires: none
superseded_by: null
---

# Context Handoff: H-029 + ADR-0016 slice 1 — 2026-07-29

## Goal (one sentence)
Execute the frozen H-029 Stage-2 probe and build ADR-0016 manifest infrastructure without running a real complete round.

## Current state
- Branch: current working tree.
- Last known good state: targeted tests and ledger/config/doc checks pass.
- In-progress edits: files listed in the paired session handoff.
- What works: H-029/E-068 artifact is SHA-bound; round validation, resume, and reconciliation have synthetic tests.
- Unfinished: candidate-specific runner breadth and one-command real-round wiring.

## Decisions made (and why)
- Canonicalize millisecond-offset funding timestamps to the settlement minute before +1m entry — Binance rows otherwise miss valid minute bars.
- Stop H-029 before Stage 3 — cost and power failed the frozen four-check gate.
- Keep round execution sequential — ADR-0016 explicitly defers concurrency.

## Open questions / unverified assumptions
- E-026 has no dated return series; Claude should review the recorded I49 best-effort gap.

## Rules in play (preserve verbatim)
- Invariants touched: I49, I53, I54.
- Domain rules touched: R6.3, R6.8, R6.9; no semantic change.
- Do-not-touch: strategy/signal/risk/portfolio/execution code, existing result artifacts, live gates.

## Context to load next (the reading list)
- Source of truth: ADR-0016 and `docs/superpowers/specs/2026-07-29-event-probe-hypotheses.md`.
- Owning files: `backtesting/funding_settlement_probe.py`, `backtesting/pipeline_round.py`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run
- Targeted pytest — 35 passed.
- Ledger consistency — passed (30 hypotheses, 69 experiments, 27 K families).
- Config validation and artifact SHA reconciliation — passed.
- Doc impact — advisory exit 0 with A5 warning because task scope did not permit FEATURE_MAP/DATA_FLOW/GOLDEN_CASES edits.
- H-028 data preflight — `liq_okx_btc` and `liq_okx_eth` each cover only 26 distinct days through 2026-07-29, so the frozen ~12-month gate remains blocked.
- `quant_liq_okx_ingest` scheduler check — S4U/Ready, last result 0, next run scheduled, zero missed runs.

## Approvals
- H-029 Stage 2 and conditional Stage 3 were authorized; Stage 3 did not unlock.
- No real ADR-0016 round was authorized or run.

## Next action (single, concrete)
- Claude reviews E-068 event accounting and the slice-1 manifest boundary.

## Human Learning Notes
Binance funding timestamps can carry millisecond jitter even when they represent regular 8-hour settlement minutes; exact raw-timestamp candle joins silently undercount coverage.
