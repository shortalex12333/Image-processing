"""
Structured logging configuration using structlog.
"""

import logging
import sys
from typing import Any

import structlog
from src.config import settings


def configure_logging() -> None:
    """
    Configure structured logging for the application.

    Sets up:
    - JSON formatting for production
    - Pretty console output for development
    - Standard library logging integration
    """

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper())
    )

    # Processors for all environments
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    # Development: Pretty console output
    if settings.is_development:
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer()
        ]
    # Production: JSON output
    else:
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer()
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> Any:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Structured logger instance

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Image uploaded", image_id=uuid, yacht_id=yacht_id)
    """
    return structlog.get_logger(name)


# Initialize logging on module import
configure_logging()
