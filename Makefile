PYTHON ?= python
PYTEST ?= pytest
RUFF ?= ruff
NODE ?= node
VALIDATION_STRATEGIES ?= all
VALIDATION_ENGINES ?= vectorbt,backtrader,nautilus
VALIDATION_RESULTS_DIR ?= results
SOURCE_PROVENANCE_ARGS ?= --help

FRONTEND_JS = frontend/data.js frontend/tweaks-panel.js frontend/charts.js frontend/view-config.js frontend/view-results.js frontend/view-trades.js frontend/view-backtest.js frontend/view-validation.js frontend/view-glossary.js frontend/view-manual.js frontend/view-progress.js frontend/app.js

.PHONY: setup dev test-unit test-integration test-all lint check-config validate-data frontend-check strategy-signal-validation source-provenance-validation engine-consistency-smoke api-smoke backtest-smoke smoke docs-check docs-impact verify verify-full all

setup:
	$(PYTHON) -m pip install -e ".[dev,backtest]"

dev:
	$(PYTHON) scripts/run_server.py

test-unit:
	$(PYTEST) tests/unit/ -v --tb=short

test-integration:
	$(PYTEST) tests/integration/ -v --tb=short

test-all:
	$(PYTEST) tests/ -v --tb=short

validate-data:
	$(PYTHON) scripts/validate_pipeline.py --data-dir data/ticks --inst BTC-USDT-SWAP

strategy-signal-validation:
	$(PYTHON) scripts/run_all_strategy_signal_validation.py --results-dir "$(VALIDATION_RESULTS_DIR)" --strategies "$(VALIDATION_STRATEGIES)" --engines "$(VALIDATION_ENGINES)"

source-provenance-validation:
	$(PYTHON) scripts/run_source_provenance_validation.py $(SOURCE_PROVENANCE_ARGS)

engine-consistency-smoke:
	$(PYTHON) scripts/run_engine_consistency_smoke.py

check-config:
	$(PYTHON) scripts/validate_pipeline.py --check-config-only

lint:
	$(RUFF) check src/ tests/ backtesting/ scripts/

frontend-check:
	$(NODE) --check frontend/data.js
	$(NODE) --check frontend/tweaks-panel.js
	$(NODE) --check frontend/charts.js
	$(NODE) --check frontend/view-config.js
	$(NODE) --check frontend/view-backtest.js
	$(NODE) --check frontend/view-results.js
	$(NODE) --check frontend/view-validation.js
	$(NODE) --check frontend/view-trades.js
	$(NODE) --check frontend/view-glossary.js
	$(NODE) --check frontend/view-manual.js
	$(NODE) --check frontend/view-progress.js
	$(NODE) --check frontend/app.js

api-smoke:
	$(PYTHON) scripts/smoke/api_smoke.py

backtest-smoke:
	$(PYTHON) scripts/smoke/backtest_smoke.py

smoke: frontend-check api-smoke backtest-smoke

docs-check:
	$(PYTHON) scripts/docs/check_doc_metadata.py
	$(PYTHON) scripts/docs/check_feature_map_links.py

docs-impact:
	$(PYTHON) scripts/docs/check_doc_impact.py

verify: lint docs-check frontend-check check-config test-unit api-smoke backtest-smoke

verify-full: verify test-integration validate-data

all: verify-full
