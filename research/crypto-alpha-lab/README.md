# crypto-alpha-lab

Research-only skeleton for a paper-driven crypto alpha lab.

This project is intentionally separate from the parent OKX backtesting and
trading code. Its job is to systematize alpha discovery, score papers, define
research strategies, and emit backtest-ready configuration contracts that can
later be adapted to the existing backtest framework.

## Phase 1 Scope

Included:

- Folder structure for papers, alpha specs, backtest configs, experiments, and
  reports.
- `pyproject.toml` for a standalone Python package.
- `BaseStrategy` research interface.
- `PaperScoring` schema for ranking literature-derived alpha ideas.
- `BacktestConfig` schema for research backtest requests.
- Pytest skeleton covering the interface and schemas.

Excluded:

- Live trading.
- Real exchange API clients.
- API keys, secrets, or account state.
- Direct modifications to the parent backtesting engine.

## Difference From Existing Research Files

The parent `research/` directory already contains curated paper notes and
strategy synthesis for the current OKX system. This lab has a different role:

- Existing research files are the current strategy truth sources.
- This lab is a systematic alpha factory for future candidates.
- This lab does not rewrite `strategy_synthesis.md`.
- This lab produces scored alpha candidates and backtest configs that can be
  reviewed before any parent-framework integration.

When conflicts appear, prefer the parent repo truth sources:

- `research/strategy_synthesis.md`
- `docs/backtest_live_parity_plan.md`
- `config/`

## File Tree

```text
crypto-alpha-lab/
|-- AGENTS.md
|-- README.md
|-- pyproject.toml
|-- alpha_specs/
|   `-- README.md
|-- backtest_configs/
|   `-- README.md
|-- data/
|   `-- README.md
|-- experiments/
|   `-- README.md
|-- papers/
|   `-- README.md
|-- reports/
|   `-- README.md
|-- src/
|   `-- crypto_alpha_lab/
|       |-- __init__.py
|       |-- adapters/
|       |   `-- __init__.py
|       |-- pipeline/
|       |   `-- __init__.py
|       |-- schemas/
|       |   |-- __init__.py
|       |   |-- backtest_config.py
|       |   `-- paper_scoring.py
|       `-- strategies/
|           |-- __init__.py
|           `-- base.py
`-- tests/
    |-- conftest.py
    |-- test_base_strategy.py
    `-- test_schemas.py
```

## Module Purposes

| Module | Purpose |
| --- | --- |
| `papers/` | Store literature intake notes and paper metadata drafts. |
| `alpha_specs/` | Store reviewed alpha hypotheses before implementation. |
| `backtest_configs/` | Store research backtest request examples and config fixtures. |
| `experiments/` | Store local experiment notes and non-production research outputs. |
| `reports/` | Store local research summaries and candidate promotion notes. |
| `data/` | Local-only research data notes or tiny fixtures; no secrets or raw exchange dumps. |
| `crypto_alpha_lab.strategies` | Research strategy interface and reusable strategy contracts. |
| `crypto_alpha_lab.schemas` | Pydantic schemas for paper scoring and backtest configuration. |
| `crypto_alpha_lab.pipeline` | Reserved for future paper-to-alpha workflow orchestration. |
| `crypto_alpha_lab.adapters` | Reserved for future adapters into the parent backtest framework. |
| `tests/` | Pytest skeleton for contract and schema validation. |

## Run Tests

From this directory:

```bash
python -m pytest
```

If dependencies are missing:

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

## Next Stage

1. Add paper intake templates and a scoring rubric review checklist.
2. Create alpha candidate records from the current paper database.
3. Add a config exporter that produces parent-framework backtest requests
   without importing live trading modules.
4. Add validation gates for lookahead risk, cost assumptions, and data
   availability before an alpha can be promoted.

## Current Research Artifacts

| Artifact | Purpose |
| --- | --- |
| `papers/scoring_rubric.md` | Defines scoring criteria and promotion guidance. |
| `papers/paper_intake_template.md` | Template for adding a new source paper. |
| `papers/search_log_2026-05-26.md` | Reproducible search notes for the first paper screen. |
| `papers/initial_screen_2026-05-26.json` | Machine-validated first batch of scored paper candidates. |
| `alpha_specs/alpha_candidate_template.md` | Template for converting papers into alpha specs. |
| `alpha_specs/initial_candidates_2026-05-26.json` | Machine-validated first alpha candidate registry. |
