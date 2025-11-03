"""Structured logging configuration using structlog.

This module provides structured logging functionality for the backend service.
It supports both development (pretty console output) and production (JSON) formats.
"""

import logging
import structlog
from datetime import datetime


def setup_logging(environment: str = "development"):
    """Configure structured logging.

    Args:
        environment: Environment name ("development" or "production")
                    - development: Pretty console output with colors
                    - production: JSON format for log aggregation
    """

    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        level=logging.INFO if environment == "production" else logging.DEBUG,
    )

    # Configure structlog processors
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    # Add appropriate renderer based on environment
    if environment == "production":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    # Configure structlog
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str):
    """Get a structured logger.

    Args:
        name: Logger name (typically __name__ of the calling module)

    Returns:
        Structured logger instance
    """
    return structlog.get_logger(name)
