"""
Jan-Seva AI — Logging Configuration
Structured logging for all services.
"""

import logging
import sys


def setup_logger(name: str = "jan-seva-ai") -> logging.Logger:
    """Create a configured logger with console output."""
    logger = logging.getLogger(name)

    if not logger.handlers:
        logger.setLevel(logging.INFO)

        # Console handler with format
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)

        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


# Global logger instance
logger = setup_logger()
