test-unit:
	pytest tests/unit/ -v --tb=short

test-integration:
	pytest tests/integration/ -v --tb=short

test-all:
	pytest tests/ -v --tb=short

validate-data:
	python scripts/validate_pipeline.py --data-dir data/ticks --inst BTC-USDT-SWAP

check-config:
	python scripts/validate_pipeline.py --check-config-only

lint:
	ruff check src/ tests/ backtesting/ scripts/

all: lint check-config test-unit test-integration validate-data
