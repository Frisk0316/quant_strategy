"""
Loguru structured logging setup.
Production: JSON lines (serialize=True) for Loki/ELK ingestion.
Development: pretty format with colors.
"""
from __future__ import annotations

import sys
from loguru import logger


def setup_logging(log_level: str = "INFO", json_output: bool = False) -> None:
    logger.remove()

    if json_output:
        logger.add(
            sys.stdout,
            level=log_level,
            serialize=True,
            enqueue=True,
        )
    else:
        fmt = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{line}</cyan> | "
            "{message}"
        )
        logger.add(sys.stdout, level=log_level, format=fmt, colorize=True)

    # Rotating file log regardless of format
    logger.add(
        "logs/okx_quant_{time:YYYY-MM-DD}.log",
        level="DEBUG",
        rotation="00:00",
        retention="14 days",
        compression="gz",
        serialize=True,
        enqueue=True,
    )


def get_logger():
    return logger
