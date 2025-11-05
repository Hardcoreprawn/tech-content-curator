"""API Credit Status and Graceful Shutdown.

This module handles detection of exhausted API credits and gracefully stops
the pipeline with clear reporting. When credits run out, the system:

1. Detects the quota exhaustion error
2. Records it in the error history
3. Stops further API calls
4. Reports the status clearly
5. Exits with an informative message

No fallback content generation - when credits are gone, we stop.
"""

from __future__ import annotations

import logging

from rich.console import Console

logger = logging.getLogger(__name__)
console = Console()


class CreditsExhaustedError(Exception):
    """Raised when OpenAI API credits are exhausted."""

    pass


def handle_credits_exhausted(error_message: str) -> None:
    """Handle exhausted credits by stopping gracefully.

    Args:
        error_message: The error message from the API

    Raises:
        CreditsExhaustedError: Always raised to stop the pipeline
    """
    console.print("\n[bold red]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold red]")
    console.print("[bold red]⚠ API CREDITS EXHAUSTED[/bold red]")
    console.print("[bold red]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold red]\n")

    console.print("[yellow]What happened:[/yellow]")
    console.print("  • OpenAI API returned a quota exceeded error")
    console.print("  • Your account has run out of available credits")
    console.print("  • Article generation pipeline has stopped\n")

    console.print("[yellow]Next steps:[/yellow]")
    console.print(
        "  1. Log into your OpenAI account: https://platform.openai.com/account/billing"
    )
    console.print("  2. Add more credits or set a higher usage limit")
    console.print("  3. Verify your API key is still valid")
    console.print("  4. Restart the pipeline once credits are available\n")

    console.print(f"[dim]API Error: {error_message[:100]}[/dim]\n")

    logger.error(f"API credits exhausted: {error_message}")

    raise CreditsExhaustedError(
        "OpenAI API credits exhausted. Please add credits and restart the pipeline."
    )


def check_for_quota_error(error: Exception) -> bool:
    """Check if an error indicates quota exhaustion.

    Args:
        error: The exception to check

    Returns:
        True if this is a quota exhaustion error
    """
    error_str = str(error).lower()
    return any(
        keyword in error_str
        for keyword in [
            "quota",
            "insufficient_quota",
            "billing_not_active",
            "usage_limits",
            "error_429",
        ]
    )
