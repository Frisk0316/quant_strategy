FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

# Copy source
COPY src/ src/
COPY config/ config/
COPY scripts/ scripts/
COPY backtesting/ backtesting/

# Create data directory
RUN mkdir -p data/ticks logs

# Non-root user for security
RUN useradd -m trader && chown -R trader:trader /app
USER trader

# Default: demo mode
CMD ["python", "scripts/run_demo.py"]
