"""Centralized OpenAI API error handling and classification.

Provides consistent error classification and logging across all OpenAI API calls.
Uses functional composition - classify, log, raise - keeping it simple and testable.

Usage:
    try:
        response = client.chat.completions.create(...)
    except Exception as e:
        handle_openai_error(e, context="analyzing content", should_raise=True)
"""

from __future__ import annotations

from enum import Enum

from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    RateLimitError,
)
from rich.console import Console

from ..utils.logging import get_logger

console = Console()
logger = get_logger(__name__)


class ErrorType(Enum):
    """OpenAI error classifications."""

    QUOTA_EXCEEDED = "quota_exceeded"
    BILLING_INACTIVE = "billing_inactive"
    AUTHENTICATION_FAILED = "authentication_failed"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    INVALID_REQUEST = "invalid_request"
    API_ERROR = "api_error"
    UNKNOWN = "unknown"


def classify_error(error: Exception) -> tuple[ErrorType, str]:
    """Classify an OpenAI error and extract details.

    Args:
        error: The exception from OpenAI

    Returns:
        Tuple of (error_type, message)
    """
    error_str = str(error).lower()
    logger.debug(f"Classifying OpenAI error: {type(error).__name__}")

    # APIStatusError with specific status codes
    if isinstance(error, APIStatusError):
        if error.status_code == 429:
            logger.debug("Classified as RATE_LIMITED (429)")
            return ErrorType.RATE_LIMITED, "Rate limited (429)"
        if error.status_code == 401:
            logger.debug("Classified as AUTHENTICATION_FAILED (401)")
            return ErrorType.AUTHENTICATION_FAILED, "Unauthorized (401)"
        if error.status_code == 403:
            if "billing" in error_str or "quota" in error_str:
                logger.debug("Classified as QUOTA_EXCEEDED (403)")
                return ErrorType.QUOTA_EXCEEDED, "Forbidden - quota/billing (403)"
            logger.debug("Classified as AUTHENTICATION_FAILED (403)")
            return ErrorType.AUTHENTICATION_FAILED, "Forbidden (403)"
        if error.status_code in (500, 502, 503, 504):
            logger.debug(f"Classified as API_ERROR ({error.status_code})")
            return ErrorType.API_ERROR, f"Server error ({error.status_code})"

    # Specific exception types
    if isinstance(error, RateLimitError):
        logger.debug("Classified as RATE_LIMITED (RateLimitError)")
        return ErrorType.RATE_LIMITED, "Rate limit error"
    if isinstance(error, APITimeoutError):
        logger.debug("Classified as TIMEOUT (APITimeoutError)")
        return ErrorType.TIMEOUT, "Timeout error"
    if isinstance(error, APIConnectionError):
        logger.debug("Classified as CONNECTION_ERROR (APIConnectionError)")
        return ErrorType.CONNECTION_ERROR, "Connection error"
    if isinstance(error, AuthenticationError):
        logger.debug("Classified as AUTHENTICATION_FAILED (AuthenticationError)")
        return ErrorType.AUTHENTICATION_FAILED, "Authentication error"

    # String-based indicators
    keywords_quota = [
        "quota",
        "insufficient_quota",
        "billing_not_active",
        "no_available_quota",
    ]
    keywords_rate = ["rate limit", "too many requests"]
    keywords_timeout = ["timeout", "timed out"]
    keywords_auth = ["authentication", "invalid api key", "unauthorized"]

    if any(kw in error_str for kw in keywords_quota):
        logger.debug("Classified as QUOTA_EXCEEDED (keyword match)")
        return ErrorType.QUOTA_EXCEEDED, "Quota exceeded"
    if any(kw in error_str for kw in keywords_rate):
        logger.debug("Classified as RATE_LIMITED (keyword match)")
        return ErrorType.RATE_LIMITED, "Rate limited"
    if any(kw in error_str for kw in keywords_timeout):
        logger.debug("Classified as TIMEOUT (keyword match)")
        return ErrorType.TIMEOUT, "Timeout"
    if any(kw in error_str for kw in keywords_auth):
        logger.debug("Classified as AUTHENTICATION_FAILED (keyword match)")
        return ErrorType.AUTHENTICATION_FAILED, "Authentication failed"

    if isinstance(error, APIError):
        logger.debug("Classified as API_ERROR (APIError)")
        return ErrorType.API_ERROR, str(error)

    logger.debug("Classified as UNKNOWN")
    return ErrorType.UNKNOWN, str(error)


def is_retryable(error_type: ErrorType) -> bool:
    """Check if error is transient and worth retrying.

    Args:
        error_type: The classified error type

    Returns:
        True if transient (rate-limit, timeout, connection)
    """
    return error_type in (
        ErrorType.RATE_LIMITED,
        ErrorType.TIMEOUT,
        ErrorType.CONNECTION_ERROR,
    )


def is_fatal(error_type: ErrorType) -> bool:
    """Check if error is fatal and should stop the pipeline.

    Args:
        error_type: The classified error type

    Returns:
        True if fatal (quota, billing, auth)
    """
    return error_type in (
        ErrorType.QUOTA_EXCEEDED,
        ErrorType.BILLING_INACTIVE,
        ErrorType.AUTHENTICATION_FAILED,
    )


def log_and_raise(
    error: Exception,
    error_type: ErrorType,
    message: str,
    context: str = "",
) -> None:
    """Log error and prepare for raising.

    Args:
        error: Original exception
        error_type: Classified error type
        message: Descriptive message
        context: What operation was being attempted
    """
    log_context = f" ({context})" if context else ""

    # Log appropriately
    if is_fatal(error_type):
        logger.critical(
            f"Fatal OpenAI error: {error_type.value}{log_context} - {message}",
            exc_info=True,
        )
        console.print(f"[bold red]❌ FATAL: {error_type.value}{log_context}[/bold red]")
    elif is_retryable(error_type):
        logger.warning(
            f"Transient OpenAI error: {error_type.value}{log_context} - {message}"
        )
        logger.debug(f"Will retry operation: {context or 'unknown'}")
        console.print(f"[yellow]⚠ {error_type.value}{log_context}: will retry[/yellow]")
    else:
        logger.error(f"OpenAI error: {error_type.value}{log_context} - {message}")
        console.print(f"[yellow]⚠ {error_type.value}{log_context}[/yellow]")


def handle_openai_error(
    error: Exception,
    context: str = "",
    should_raise: bool = True,
) -> ErrorType:
    """Handle OpenAI error: classify, log, optionally raise.

    Args:
        error: The exception from OpenAI API
        context: Description of what was being attempted (for logging)
        should_raise: If True, re-raise after logging

    Returns:
        Classified error type

    Raises:
        Exception: Re-raises original error if should_raise=True
    """
    logger.debug(f"Handling OpenAI error during: {context or 'unknown operation'}")
    error_type, message = classify_error(error)
    log_and_raise(error, error_type, message, context)

    if should_raise:
        logger.debug(f"Re-raising OpenAI error: {error_type.value}")
        raise error

    logger.debug(f"Suppressed OpenAI error: {error_type.value}, returning error type")
    return error_type


def get_recovery_action(error_type: ErrorType) -> str:
    """Get actionable recovery suggestion.

    Args:
        error_type: The classified error type

    Returns:
        Recovery suggestion
    """
    actions = {
        ErrorType.QUOTA_EXCEEDED: "Add credits to OpenAI account: https://platform.openai.com/account/billing",
        ErrorType.BILLING_INACTIVE: "Enable billing on OpenAI account",
        ErrorType.AUTHENTICATION_FAILED: "Check OPENAI_API_KEY environment variable",
        ErrorType.RATE_LIMITED: "Wait and retry - rate limit will reset",
        ErrorType.TIMEOUT: "Check network connection and retry",
        ErrorType.CONNECTION_ERROR: "Check internet connection and retry",
        ErrorType.INVALID_REQUEST: "Check request parameters",
        ErrorType.API_ERROR: "OpenAI service issue - retry later",
        ErrorType.UNKNOWN: "Check logs for error details",
    }
    action = actions.get(error_type, "Unknown error")
    logger.debug(f"Recovery action for {error_type.value}: {action}")
    return action
