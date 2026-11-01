"""
Structured logging configuration.
"""
from __future__ import annotations
import logging
import sys


def setup_logging(level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("ledger")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s (%(module)s): %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    return logger


logger = setup_logging()
