# OKX Quant Strategy

A quantitative trading research codebase for crypto perpetuals/spot, targeting
$1k–$10k capital on OKX. Built around maker-only (`post_only`) execution
because taker fees make pure taker strategies mathematically unviable at this
capital level. Includes a multi-exchange data layer (OKX/Binance/Bybit), an
event-driven replay backtesting stack with CPCV/walk-forward validation, a
FastAPI dashboard, and an asyncio trading engine.

## Project Status

**This is a research project. NO strategy is promotion, demo, shadow, or live
ready.** The deployment gates in [docs/ai_collaboration.md](docs/ai_collaboration.md)
govern any promotion; passing gates plus explicit human approval are both
required, and neither the engine nor any AI assistant may self-promote.

## Strategies

| Strategy | Module | Description |
| -------- | ------ | ----------- |
| Funding Carry | `strategies/funding_carry.py` | Delta-neutral long spot / short perp, earns 8h funding |
| Pairs Trading | `strategies/pairs_trading.py` | Kalman filter hedge ratio + Ornstein-Uhlenbeck spread z-score |
| MA/EMA/MACD Crossover | `strategies/technical_indicators.py` | Long/flat technical-indicator baselines |
| Fear & Greed / CME Gap | `strategies/external_features.py` | Research-only external-feature baselines |

Key design rules: all orders use `post_only` (error 51026 is logged and
dropped, never retried as taker); order-book market-making strategies were
removed; delta-neutral carry earns funding without directional exposure.
Strategy assumptions live in
[research/strategy_synthesis.md](research/strategy_synthesis.md) — the source
of truth.

## Architecture

```text
EventBus (asyncio.Queue)
  MARKET → SignalGenerator → SIGNAL → PortfolioManager → ORDER → ExecutionHandler → FILL
                                                                         ↓
                                                             DrawdownTracker + RiskGuard
```

| Area | Where |
| --- | --- |
| Engine core | `src/okx_quant/` — core, data (TimescaleDB candle store, exchange clients, validators), signals, strategies, portfolio, risk, execution, monitoring, analytics, api, `engine.py` |
| Backtesting | `backtesting/` — replay engine, differential validation, CPCV, walk-forward, data loaders, vectorbt scanner |
| Data tooling | `scripts/market_data/` — ingestion, canonicalization, backfill, gap repair, validation |
| Frontend | `frontend/` — dashboard served by the FastAPI server |

Two database systems (legacy OKX-only and multi-exchange `market_*`) are
bridged by `canonical_inst_id`; backtests read `canonical_candles`. See
[docs/DATA_FLOW.md](docs/DATA_FLOW.md) and the promotion workflow in
[docs/RUNBOOK.md](docs/RUNBOOK.md).

## Quick Setup

```bash
pip install -e ".[dev]"        # add ,backtest / ,validation extras as needed
make dev                       # local dashboard server (http://localhost:8080)
make verify                    # lint + docs + frontend + config + unit tests + smokes
```

Credentials (`.env`) and `config/*.yaml` reference: see "Configuration
Reference" in [docs/RUNBOOK.md](docs/RUNBOOK.md). Tests: `make test-unit` /
`make test-integration`.

## Where To Find Things

| Need | Read |
| --- | --- |
| Operations: setup, DB/no-DB modes, data ingestion, backtest CLI, validation gates, calibration, deployment gates, engine modes, config reference | [docs/RUNBOOK.md](docs/RUNBOOK.md) |
| Deployment gates and AI collaboration contract | [docs/ai_collaboration.md](docs/ai_collaboration.md) |
| Feature ownership — which files own which behavior | [docs/FEATURE_MAP.md](docs/FEATURE_MAP.md) |
| Data paths: ingestion, artifacts, API, validation | [docs/DATA_FLOW.md](docs/DATA_FLOW.md) |
| Frontend navigation, charts, API calls | [docs/UI_MAP.md](docs/UI_MAP.md) |
| Project onboarding (AI and human) | [AI_CONTEXT.md](AI_CONTEXT.md) |
| Strategy assumptions (source of truth) | [research/strategy_synthesis.md](research/strategy_synthesis.md) |
| Business rules and invariants | [docs/DOMAIN_RULES.md](docs/DOMAIN_RULES.md), [docs/INVARIANTS.md](docs/INVARIANTS.md) |
| Human review of AI-generated plans | [docs/review_index.md](docs/review_index.md) |

## Backtest Validation (summary)

Three-layer gate before any live capital deployment: (1) replay walk-forward /
CPCV, (2) differential validation against reference engines, (3) shadow/demo
calibration. Promotion requires DSR ≥ 0.95 plus the full gate table — commands
and gate details in [docs/RUNBOOK.md](docs/RUNBOOK.md), authoritative gate
policy in [docs/ai_collaboration.md](docs/ai_collaboration.md).

## Research Layer

`research/` tracks quant finance literature and maps it to strategy
hypotheses. No imports — pure decision support:
[papers_database.md](research/papers_database.md),
[strategy_synthesis.md](research/strategy_synthesis.md),
[search_log.md](research/search_log.md).

## AI Collaboration

Claude handles research, strategy critique, and risk review; Codex handles
implementation and tests. The full contract, role split, and mandatory
deployment gates are in [docs/ai_collaboration.md](docs/ai_collaboration.md).
No AI can self-promote a strategy to demo, shadow, or live — explicit user
approval is always required.
