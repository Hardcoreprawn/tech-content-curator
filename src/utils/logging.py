"""Standardized logging configuration for the entire application.

This module provides:
- Consistent log formatting across all modules
- Centralized logger initialization
- Standard log levels and usage patterns

Usage in any module:
    from ..utils.logging import get_logger
    logger = get_logger(__name__)

    logger.debug("Internal state info")        # Detailed debugging
    logger.info("Operation completed")         # Key operations
    logger.warning("Recoverable issue")        # Non-fatal problems
    logger.error("Operation failed")           # Operation failures
    logger.critical("System failure")          # Fatal errors

Log Format: [LEVEL] module_name - message
Example: [INFO] src.enrichment.orchestrator - Starting enrichment of 5 items
"""

import logging

# Standard format for all logs
LOG_FORMAT = "[%(levelname)s] %(name)s - %(message)s"


def get_logger(name: str, level: int | None = None) -> logging.Logger:
    """Get a configured logger for a module.

    Args:
        name: Module name (typically __name__)
        level: Optional log level override (defaults to INFO)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Only configure if not already configured
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(LOG_FORMAT)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(level or logging.INFO)

    return logger


def configure_root_logger(level: int = logging.INFO) -> None:
    """Configure the root logger for the entire application.

    Call this once in your main entry point to set application-wide log level.

    Args:
        level: Log level (logging.DEBUG, logging.INFO, etc.)
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove any existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler()
    formatter = logging.Formatter(LOG_FORMAT)
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
