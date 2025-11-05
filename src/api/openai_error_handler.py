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

import logging
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

console = Console()
logger = logging.getLogger(__name__)


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

    # APIStatusError with specific status codes
    if isinstance(error, APIStatusError):
        if error.status_code == 429:
            return ErrorType.RATE_LIMITED, "Rate limited (429)"
        if error.status_code == 401:
            return ErrorType.AUTHENTICATION_FAILED, "Unauthorized (401)"
        if error.status_code == 403:
            if "billing" in error_str or "quota" in error_str:
                return ErrorType.QUOTA_EXCEEDED, "Forbidden - quota/billing (403)"
            return ErrorType.AUTHENTICATION_FAILED, "Forbidden (403)"
        if error.status_code in (500, 502, 503, 504):
            return ErrorType.API_ERROR, f"Server error ({error.status_code})"

    # Specific exception types
    if isinstance(error, RateLimitError):
        return ErrorType.RATE_LIMITED, "Rate limit error"
    if isinstance(error, APITimeoutError):
        return ErrorType.TIMEOUT, "Timeout error"
    if isinstance(error, APIConnectionError):
        return ErrorType.CONNECTION_ERROR, "Connection error"
    if isinstance(error, AuthenticationError):
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
        return ErrorType.QUOTA_EXCEEDED, "Quota exceeded"
    if any(kw in error_str for kw in keywords_rate):
        return ErrorType.RATE_LIMITED, "Rate limited"
    if any(kw in error_str for kw in keywords_timeout):
        return ErrorType.TIMEOUT, "Timeout"
    if any(kw in error_str for kw in keywords_auth):
        return ErrorType.AUTHENTICATION_FAILED, "Authentication failed"

    if isinstance(error, APIError):
        return ErrorType.API_ERROR, str(error)

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
            f"Fatal OpenAI error: {error_type.value}{log_context} - {message}"
        )
        console.print(f"[bold red]❌ FATAL: {error_type.value}{log_context}[/bold red]")
    elif is_retryable(error_type):
        logger.warning(
            f"Transient OpenAI error: {error_type.value}{log_context} - {message}"
        )
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
    error_type, message = classify_error(error)
    log_and_raise(error, error_type, message, context)

    if should_raise:
        raise error

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
    return actions.get(error_type, "Unknown error")
