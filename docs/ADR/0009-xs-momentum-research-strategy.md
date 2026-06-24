---
status: current
type: adr
owner: codex
created: 2026-06-23
last_reviewed: 2026-06-24
expires: none
superseded_by: null
---

# ADR-0009: XS Momentum Research Strategy

## Status

Accepted - 2026-06-23, research-only scaffold.

**Validation outcome (2026-06-24): BLOCKED / shelved.** Full Phase C ran
leak-free with a corrected DSR. Both anti-overfit gates fail — E-005
(portfolio-vol sizing, DSR-fixed) reports DSR 0.7823, PSR 0.8234, CPCV OOS
Sharpe 0.60 with dispersed, partly-negative groups (HYPOTHESIS_LEDGER H-002
refuted; EXPERIMENT_REGISTRY E-003 invalid, E-004/E-005 refuted). `xs_momentum`
stays `enabled:false`; not promotion/live evidence. Decision: shelve as a
spec-correct research baseline; do **not** tune research assumptions to chase the
gate (that raises honest `n_trials` and deflates DSR further). Revisit only with
materially more OOS history or a genuinely new signal thesis with honest
`n_trials` declared up front. Open item: the CPCV `n_trials` is still hard-set to
8 — making it honest lowers DSR further and reinforces the block. The
architectural decision below (add `xs_momentum` as a disabled research family)
still stands.

## Context

The cross-sectional momentum design introduces a wide Binance USDT-perp
research universe and a dollar-neutral long-short strategy family. This touches
strategy configuration, portfolio construction, data provenance, and validation
rules, so it needs a durable architecture record even though it is not a
deployment change.

The current implementation only covers the local universe builder, target-weight
assembly, crash-regime gross scaler, and disabled strategy stub. Bulk 1m plus
funding coverage, venue-scoped DB evidence, vectorized funding-aware backtest,
walk-forward, CPCV, DSR, and PSR remain prerequisites for any promotion
discussion.

## Decision

Add `xs_momentum` as a disabled-by-default, research-only strategy family.

- Universe membership must be point-in-time and generated from raw candle
  history; a final observed symbol list must not be used as historical
  membership.
- The strategy constructs long top-quantile and short bottom-quantile target
  weights through `dollar_neutral_long_short_weights`, with equal gross legs,
  optional inverse-vol leg weights, per-name caps, portfolio book-vol targeting,
  a max gross-leverage cap, and a market-drawdown/high-vol gross scaler.
- `XSMomentumStrategy.on_market()` remains a no-op until a separate task wires
  live/replay execution semantics. Current use is vectorized research only.
- Promotion-grade validation must use venue-scoped canonical DB data and must
  cite the universe membership artifact, honest `n_trials`, WF/CPCV, DSR/PSR,
  and funding-accounting evidence.
- Funding cashflow sign continues to follow `docs/DOMAIN_RULES.md` R3.1 unless
  a separate human-approved rule change supersedes it. The current plan text for
  C1 conflicts with R3.1 on short-leg positive funding and is treated as an
  unresolved review item, not as authority to change PnL semantics.

## Consequences

- Existing OHLCV rotation behavior and artifacts remain untouched.
- `config/universe.yaml` and `data/universe/universe_membership.parquet` become
  the local research-tier inputs for the strategy family.
- Research docs under `research/` remain Claude-owned and are not updated by
  this Codex implementation pass.
- The strategy cannot be described as live-ready, demo-ready, shadow-ready, or
  promotion-ready until the incomplete A2/C validation tasks are implemented and
  all gates in `docs/ai_collaboration.md` pass with explicit human approval.
- Tests must keep guarding dollar-neutral gross normalization, point-in-time
  membership, target-weight caps, portfolio-vol gross sizing, disabled config
  loading, and crash-regime exposure reduction.
