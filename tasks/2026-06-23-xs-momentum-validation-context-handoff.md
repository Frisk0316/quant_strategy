# Context Handoff: XS momentum validation - 2026-06-23

## Goal (one sentence)
Validate the XS momentum universe on canonical DB coverage >=25 symbols / >=12 months with WF/CPCV and DSR/PSR.

## Current state
- Branch: `codex/xs-momentum-universe-scaffold`
- Last known good commit / state: `be2d9b0 feat(backtest): add xs momentum phase c runner`
- In-progress edits (files): `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md`, this handoff, session handoff; pre-existing unrelated dirty files remain in the worktree.
- What works right now: coverage artifact has 28 passed symbols; validation artifact ran on 27 symbols, because `ETH-USDT-SWAP` returned zero rows/funding under the source-scoped query.
- What does not work / unfinished: human/Claude review still required; this is not live approval.

## Decisions made (and why)
- Used canonical `1m` Binance rows aggregated to `1H` in SQL because pulling all 1m rows into Python would be slow and memory-heavy.
- Used `funding_rates source='binance'` and R3.1 funding sign via existing XS backtest because the Phase C runner already implements short-leg funding receipt.
- Used 8 searched parameter combinations because it is enough to exercise the current grid while keeping `n_trials` honest and runtime practical.

## Open questions / unverified assumptions
- Why `ETH-USDT-SWAP` has zero rows/funding under the strict source-scoped validation query despite appearing in coverage.
- Whether the repeated pandas `pct_change(fill_method='pad')` FutureWarning should be fixed before the next promotion run.

## Rules in play (preserve verbatim)
- Invariants touched: I4 funding sign; I13 `n_trials` honesty; I15 no live-readiness claim; I19 venue-scoped data source; I20 point-in-time universe.
- Domain rules touched: R3.1 funding carry; R6 data provenance; R7 promotion gates.
- Do-not-touch: `research/`; unrelated dirty files; live/shadow/deployment gates.

## Context to load next (the reading list)
- Source of truth: `docs/superpowers/specs/2026-06-23-xs-momentum-universe-design.md`, `docs/superpowers/plans/2026-06-23-xs-momentum-universe.md`, `docs/DOMAIN_RULES.md`, `docs/INVARIANTS.md`
- Owning files / MODULE_BRIEFS: `backtesting/xs_momentum_backtest.py`, `backtesting/walk_forward.py`, `backtesting/cpcv.py`, `scripts/market_data/backfill_cmc_top_binance.py`, `scripts/build_universe_membership.py`
- Context Pack: none loaded; use `docs/CONTEXT_INDEX.md` for next-session routing.

## Checks run
- `scripts/market_data/backfill_cmc_top_binance.py --symbols ... --start 2024-01-01 --end 2026-06-24T00:00:00+00:00` - backfilled Binance canonical 1m rows until coverage threshold was reached.
- Funding backfill inline script - upserted Binance funding for BTC/ETC/AAVE/ALGO/ICP.
- Coverage report inline script - wrote `results/universe_coverage_20260623.json` with 28 passed symbols.
- XS validation inline script - wrote `results/xs_momentum_validation_20260623/summary.json`; CPCV DSR 1.000 and PSR 0.992.
- Readback verification inline script - confirmed 27 symbols, WF/CPCV metrics, and artifact files.

## Approvals
- Human approval needed / obtained: human requested the data refill plus WF/CPCV + DSR/PSR run; no live-trading approval requested or obtained.

## Next action (single, concrete)
- Ask Claude/WF reviewer to inspect `results/xs_momentum_validation_20260623/summary.json`, especially ETH skip, the high WF Sharpe, and the pandas `pct_change` warning.

## Human Learning Notes
The shortest safe route was not a new runner; direct SQL aggregation from canonical 1m to 1H was enough. Source-scoped validation exposed an ETH data-source gap that the broader coverage report did not surface.
