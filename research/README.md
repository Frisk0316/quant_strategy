# Research Knowledge Layer

This directory is a standalone research layer for the OKX quantitative trading
system. It does not import from `src/` or `backtesting/`; it is meant to guide
strategy selection, implementation priorities, and validation design.

## Files

| File | Purpose |
|---|---|
| [papers_database.md](papers_database.md) | Curated quantitative strategy paper database organized by year and strategy category. |
| [strategy_synthesis.md](strategy_synthesis.md) | Crypto strategy ideas synthesized from the literature, with implementation hooks into the current codebase. |
| [search_log.md](search_log.md) | Reproducible search notes, source families, and future expansion queries. |

## How To Use

1. Start with [papers_database.md](papers_database.md) to identify the paper,
   signal, data requirement, evidence quality, and crypto applicability.
2. Move to [strategy_synthesis.md](strategy_synthesis.md) to see which ideas map
   cleanly into the existing OKX system.
3. Before implementation, convert each strategy into a testable hypothesis:
   signal definition, sizing rule, execution rule, risk stop, and validation
   path.
4. Promote only after realistic costs, maker-only constraints, walk-forward or
   CPCV validation, and Deflated Sharpe Ratio checks.

## Research Standards

- Prefer papers with out-of-sample tests, transaction-cost discussion, or clear
  microstructure logic.
- Mark theoretical or in-sample-only results explicitly.
- Track failure modes, not only reported performance.
- Separate alpha source from execution style. A paper can be useful as a signal,
  a sizing rule, a risk filter, or an execution constraint.
- Treat all live-deployment claims as hypotheses until tested on OKX data.

