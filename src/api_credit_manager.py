"""API Credit Management and Graceful Degradation.

This module handles OpenAI API quota exhaustion and provides fallback mechanisms
when credits run out. It tracks API errors, maintains fallback content strategies,
and enables the system to continue operating in degraded modes.

Key Features:
- Detects when API quotas are exhausted
- Falls back to cached/template-based content
- Tracks API error patterns for monitoring
- Gracefully degrades quality when necessary
- Provides detailed error reporting

Supported Error Modes:
1. QUOTA_EXCEEDED: No more API calls available
2. INVALID_KEY: API key is invalid or revoked
3. RATE_LIMITED: Too many requests, temporary backoff
4. SERVICE_ERROR: OpenAI service unavailable
5. NETWORK_ERROR: Network connectivity issues
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

from openai import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    RateLimitError,
)
from rich.console import Console

from .utils.file_io import atomic_write_json
from .utils.logging import get_logger

logger = get_logger(__name__)
console = Console()


class APIErrorMode(Enum):
    """Categorize API errors."""

    QUOTA_EXCEEDED = "quota_exceeded"  # 429 - Rate limit / quota
    INVALID_KEY = "invalid_key"  # 401 - Authentication failed
    SERVICE_UNAVAILABLE = "service_unavailable"  # 503 - OpenAI service down
    RATE_LIMITED = "rate_limited"  # 429 - Too many requests
    CONNECTION_ERROR = "connection_error"  # Network issues
    UNKNOWN = "unknown"  # Unexpected error


class ContentDegradationMode(Enum):
    """Define quality levels when API is unavailable."""

    FULL = "full"  # Normal operation with API
    DEGRADED = "degraded"  # Use cached prompts and templates
    TEMPLATE = "template"  # Use generic templates only
    CACHED = "cached"  # Use only cached content
    OFFLINE = "offline"  # No API calls, cached content only


@dataclass
class APIErrorEvent:
    """Record of an API error occurrence."""

    timestamp: datetime
    error_type: APIErrorMode
    error_message: str
    status_code: int | None = None
    retry_after: int | None = None  # Seconds to wait before retry


@dataclass
class CreditManager:
    """Manages API credits and graceful degradation."""

    config_path: Path = Path("data/api_credit_config.json")
    history_path: Path = Path("data/api_error_history.json")

    # State tracking
    error_events: list[APIErrorEvent] = field(default_factory=list)
    current_mode: ContentDegradationMode = ContentDegradationMode.FULL
    quota_exhausted_at: datetime | None = None
    fallback_cache_path: Path = Path("data/fallback_content_cache.json")

    # Configuration
    max_retries: int = 3
    base_retry_delay: float = 1.0  # seconds
    max_retry_delay: float = 300.0  # 5 minutes
    error_threshold: int = 5  # Switch to degraded after N errors in window
    error_window: timedelta = timedelta(minutes=10)

    def __post_init__(self) -> None:
        """Initialize credit manager."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self._load_error_history()

    def _load_error_history(self) -> None:
        """Load API error history from disk."""
        if self.history_path.exists():
            try:
                with open(self.history_path) as f:
                    data = json.load(f)
                    self.error_events = [
                        APIErrorEvent(
                            timestamp=datetime.fromisoformat(event["timestamp"]),
                            error_type=APIErrorMode(event["error_type"]),
                            error_message=event["error_message"],
                            status_code=event.get("status_code"),
                            retry_after=event.get("retry_after"),
                        )
                        for event in data.get("events", [])
                    ]
                    if data.get("quota_exhausted_at"):
                        self.quota_exhausted_at = datetime.fromisoformat(
                            data["quota_exhausted_at"]
                        )
            except Exception as e:
                logger.warning(f"Failed to load error history: {e}")

    def _save_error_history(self) -> None:
        """Save API error history to disk."""
        try:
            data = {
                "events": [
                    {
                        "timestamp": event.timestamp.isoformat(),
                        "error_type": event.error_type.value,
                        "error_message": event.error_message,
                        "status_code": event.status_code,
                        "retry_after": event.retry_after,
                    }
                    for event in self.error_events[-1000:]  # Keep last 1000 events
                ],
                "quota_exhausted_at": (
                    self.quota_exhausted_at.isoformat()
                    if self.quota_exhausted_at
                    else None
                ),
                "current_mode": self.current_mode.value,
                "last_updated": datetime.now(UTC).isoformat(),
            }
            # Use atomic write to prevent corruption
            atomic_write_json(self.history_path, data)
        except Exception as e:
            logger.error(f"Failed to save error history: {e}")

    def record_api_error(
        self,
        error: Exception,
        context: str = "",
    ) -> APIErrorMode:
        """Record and categorize an API error.

        Args:
            error: The exception that occurred
            context: Additional context about where the error occurred

        Returns:
            The categorized error mode
        """
        error_type, status_code, retry_after = self._categorize_error(error)

        event = APIErrorEvent(
            timestamp=datetime.now(UTC),
            error_type=error_type,
            error_message=str(error),
            status_code=status_code,
            retry_after=retry_after,
        )

        self.error_events.append(event)
        self._save_error_history()

        # Log with context
        context_str = f" [{context}]" if context else ""
        logger.error(f"API Error ({error_type.value}){context_str}: {str(error)[:100]}")

        console.print(
            f"[red]✗ API Error[/red]: {error_type.value}{context_str}\n"
            f"  {str(error)[:80]}"
        )

        # Check if we should degrade
        self._check_and_update_degradation_mode()

        return error_type

    def _categorize_error(
        self, error: Exception
    ) -> tuple[APIErrorMode, int | None, int | None]:
        """Categorize an API error by type.

        Returns:
            Tuple of (error_type, status_code, retry_after_seconds)
        """
        if isinstance(error, AuthenticationError):
            return APIErrorMode.INVALID_KEY, 401, None

        if isinstance(error, RateLimitError):
            # Check if it's quota exhausted (429 with specific message)
            status_code = 429
            retry_after = None

            if isinstance(error, APIStatusError):
                if error.response.status_code == 429:
                    # Try to extract retry-after header
                    retry_after = error.response.headers.get("retry-after")
                    if retry_after:
                        retry_after = int(retry_after)

            if "quota" in str(error).lower() or "billing" in str(error).lower():
                return APIErrorMode.QUOTA_EXCEEDED, status_code, retry_after or 3600
            else:
                return APIErrorMode.RATE_LIMITED, status_code, retry_after or 60

        if isinstance(error, APIStatusError):
            if error.response.status_code == 503:
                return APIErrorMode.SERVICE_UNAVAILABLE, 503, 60
            # Generic API status error
            return APIErrorMode.UNKNOWN, error.response.status_code, None

        if isinstance(error, APIConnectionError):
            return APIErrorMode.CONNECTION_ERROR, None, 30

        # Default to unknown
        return APIErrorMode.UNKNOWN, None, None

    def _check_and_update_degradation_mode(self) -> None:
        """Check error frequency and update degradation mode."""
        if not self.error_events:
            self.current_mode = ContentDegradationMode.FULL
            return

        # Check for quota exhaustion errors
        recent_quota_errors = [
            e
            for e in self.error_events[-10:]
            if e.error_type == APIErrorMode.QUOTA_EXCEEDED
        ]

        if recent_quota_errors:
            self.current_mode = ContentDegradationMode.OFFLINE
            self.quota_exhausted_at = datetime.now(UTC)
            console.print(
                "[red bold]⚠ API Quota Exhausted[/red bold] - "
                "Switching to offline mode (cached content only)"
            )
            return

        # Check for invalid key
        recent_auth_errors = [
            e
            for e in self.error_events[-10:]
            if e.error_type == APIErrorMode.INVALID_KEY
        ]

        if recent_auth_errors:
            self.current_mode = ContentDegradationMode.OFFLINE
            console.print(
                "[red bold]⚠ Invalid API Key[/red bold] - Switching to offline mode"
            )
            return

        # Check error frequency in window
        now = datetime.now(UTC)
        recent_errors = [
            e for e in self.error_events if (now - e.timestamp) < self.error_window
        ]

        if len(recent_errors) >= self.error_threshold:
            # Too many errors in short time
            if self.current_mode == ContentDegradationMode.FULL:
                self.current_mode = ContentDegradationMode.DEGRADED
                console.print(
                    "[yellow bold]⚠ High Error Rate[/yellow bold] - "
                    f"{len(recent_errors)} errors in {self.error_window}. "
                    "Switching to degraded mode (templates + cached content)"
                )
        elif len(recent_errors) < 2:
            # Few errors, try to recover to full mode
            if self.current_mode in [
                ContentDegradationMode.DEGRADED,
                ContentDegradationMode.TEMPLATE,
            ]:
                self.current_mode = ContentDegradationMode.FULL
                console.print("[green]✓ API recovered[/green] - Returning to full mode")

    def get_degradation_mode(self) -> ContentDegradationMode:
        """Get the current content degradation mode."""
        return self.current_mode

    def should_attempt_api_call(self) -> bool:
        """Determine if we should attempt an API call.

        Returns:
            True if we should try the API, False if we should skip to cache/fallback
        """
        should_attempt = self.current_mode in [
            ContentDegradationMode.FULL,
            ContentDegradationMode.DEGRADED,
        ]
        logger.debug(
            f"Should attempt API call: {should_attempt} (mode={self.current_mode.value})"
        )
        return should_attempt

    def get_retry_delay(self, attempt: int) -> float:
        """Calculate retry delay with exponential backoff.

        Args:
            attempt: The attempt number (0-indexed)

        Returns:
            Delay in seconds before next retry
        """
        delay = self.base_retry_delay * (2**attempt)
        return min(delay, self.max_retry_delay)

    def can_retry(self, error_type: APIErrorMode, attempt: int) -> bool:
        """Determine if we should retry based on error type and attempt count.

        Args:
            error_type: The type of error that occurred
            attempt: The current attempt number (0-indexed)

        Returns:
            True if we should retry
        """
        # Don't retry authentication errors or quota exhaustion
        if error_type in [
            APIErrorMode.INVALID_KEY,
            APIErrorMode.QUOTA_EXCEEDED,
        ]:
            return False

        # Retry other errors up to max_retries
        return attempt < self.max_retries

    def get_error_summary(self) -> dict[str, Any]:
        """Get a summary of recent API errors.

        Returns:
            Dictionary with error statistics
        """
        if not self.error_events:
            return {
                "total_errors": 0,
                "recent_errors": [],
                "error_types": {},
                "current_mode": self.current_mode.value,
            }

        now = datetime.now(UTC)
        recent_errors = [
            e
            for e in self.error_events[-100:]
            if (now - e.timestamp) < timedelta(hours=24)
        ]

        error_types: dict[str, int] = {}
        for event in recent_errors:
            error_types[event.error_type.value] = (
                error_types.get(event.error_type.value, 0) + 1
            )

        return {
            "total_errors": len(self.error_events),
            "recent_errors_24h": len(recent_errors),
            "error_types": error_types,
            "current_mode": self.current_mode.value,
            "quota_exhausted_at": (
                self.quota_exhausted_at.isoformat() if self.quota_exhausted_at else None
            ),
            "last_error": {
                "timestamp": self.error_events[-1].timestamp.isoformat(),
                "type": self.error_events[-1].error_type.value,
                "message": self.error_events[-1].error_message[:100],
            }
            if self.error_events
            else None,
        }

    def print_status(self) -> None:
        """Print API status to console."""
        summary = self.get_error_summary()
        mode = self.current_mode

        mode_color = {
            ContentDegradationMode.FULL: "green",
            ContentDegradationMode.DEGRADED: "yellow",
            ContentDegradationMode.TEMPLATE: "yellow",
            ContentDegradationMode.CACHED: "yellow",
            ContentDegradationMode.OFFLINE: "red",
        }[mode]

        console.print(f"\n[bold]{mode_color}API Status:[/bold {mode_color}]")
        console.print(f"  Mode: {mode.value}")
        console.print(f"  Total Errors: {summary['total_errors']}")
        console.print(f"  24h Errors: {summary['recent_errors_24h']}")

        if summary["error_types"]:
            console.print("  Error Types:")
            for error_type, count in summary["error_types"].items():
                console.print(f"    - {error_type}: {count}")

        if summary["quota_exhausted_at"]:
            console.print(
                f"  [red]Quota Exhausted:[/red] {summary['quota_exhausted_at']}"
            )

        if summary["last_error"]:
            console.print(f"  Last Error: {summary['last_error']['type']}")


# Global instance
_credit_manager: CreditManager | None = None


def get_credit_manager() -> CreditManager:
    """Get the global credit manager instance."""
    global _credit_manager
    if _credit_manager is None:
        _credit_manager = CreditManager()
    return _credit_manager


def handle_api_error(error: Exception, context: str = "") -> tuple[APIErrorMode, bool]:
    """Handle an API error and determine if we should retry.

    Args:
        error: The exception that occurred
        context: Additional context about where the error occurred

    Returns:
        Tuple of (error_type, should_retry)
    """
    manager = get_credit_manager()
    error_type = manager.record_api_error(error, context)

    # Determine if we should retry
    # In a real scenario, this would also track attempt count
    should_retry = manager.can_retry(error_type, 0)

    return error_type, should_retry
